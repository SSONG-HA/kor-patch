"""Build passive-tree dictionaries (node names + stat lines + mastery effects) from poedb tree JSON.

poedb 의 트리 JSON 은 영어/한국어 페이지가 같은 노드 id 를 쓰므로 그대로 짝지을 수 있습니다.
여기서 만드는 사전이 PoB 화면에 그려지는 문자열과 맞도록 세 가지를 지킵니다.

  1. `[키워드|표시문]` 태그를 지운 뒤 짝짓습니다. (PoB 는 그리기 전에 태그를 지웁니다)
  2. 여러 줄로 된 스탯(`\\n`)은 줄 단위로 나눠 짝짓습니다. (PoB 는 줄마다 따로 그립니다)
  3. 숙련(Mastery) 선택지는 노드의 `masteryEffects` 에 들어 있어 `stats` 만 읽으면 통째로 빠집니다.
     숙련 이름·선택지 문구·힌트 문구까지 모두 사전에 넣습니다.

만들어지는 파일:
  data/passives_names.json   {영문 노드 이름: 한글}
  data/passives_stats.json   {영문 효과/힌트/플레이버 문구: 한글}
  data/passive_conflicts.json {같은 영문 문구에 다른 한글이 붙은 경우}
  data/passives_report.json  전수 점검 결과(영역별 커버리지·남은 미번역과 사유)
"""
from __future__ import annotations

import json
import os
import re
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import (  # noqa: E402
    CACHE, POB, fetch, load_lua_table, lua_to_py, norm_space, save_json, strip_ggg,
)

# poedb 트리 데이터 경로에 쓰이는 시즌 표기 (3_30 → 3.30). 새 시즌에는 이 값을 갱신한다.
TREE_VERSION = os.environ.get("POE_TREE_VERSION", "3_30")
TREE_URL = "https://poedb.tw/data/passive-skill-tree/%s/data_%s.json"


def poedb_tree(lang: str) -> dict:
    path = os.path.join(CACHE, "tree_%s.json" % lang)
    if not os.path.exists(path) or os.path.getsize(path) < 4096:
        version = TREE_VERSION.replace("_", ".")
        fetch(TREE_URL % (version, lang), "tree_%s.json" % lang, force=True)
    if not os.path.exists(path):
        raise SystemExit("패시브 트리 데이터를 받지 못했습니다: %s" % (TREE_URL % (TREE_VERSION.replace("_", "."), lang)))
    return json.load(open(path, encoding="utf-8"))


def pob_tree_nodes() -> dict:
    """PoB 원본(POB_SRC)이 있으면 노드 목록을 읽어 커버리지 계산에 쓴다. 없으면 빈 dict."""
    if not POB:
        return {}
    path = os.path.join(POB, "TreeData", TREE_VERSION, "tree.lua")
    if not os.path.exists(path):
        print("  (PoB TreeData 없음 — 커버리지 계산 생략: %s)" % path)
        return {}
    return lua_to_py(load_lua_table(path))["nodes"]


# ── 문구 다듬기 ──────────────────────────────────────────────────────────────
def lines_of(value) -> list[str]:
    """poedb 의 stats/reminderText/flavourText 를 '화면에 그려지는 줄' 목록으로 바꿉니다."""
    if isinstance(value, dict):
        value = [v for _, v in sorted(value.items())]
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, (list, tuple)):
        return []
    out: list[str] = []
    for item in value:
        if not isinstance(item, str):
            continue
        for piece in strip_ggg(item).split("\n"):
            piece = norm_space(piece)
            if piece:
                out.append(piece)
    return out


NUM_RE = re.compile(r"[-+]?\d+(?:\.\d+)?")


def num_sig(text: str) -> Counter:
    """숫자 구성 비교용 (부호·괄호는 떼고 셉니다: "+4" 와 "4" 는 같은 값)."""
    return Counter(t.lstrip("+").strip("()") for t in NUM_RE.findall(text))


def _assign(en_lines: list[str], kr_lines: list[str]) -> dict[int, str]:
    """영문 줄 -> 한글 줄 배정.

    한글 쪽에는 같은 자리에 없는 힌트가 덧붙어 있는 경우가 흔하다(예: "맹공" 설명).
    그래서 같은 순서 + 숫자 구성이 맞는 줄을 먼저 잡고, 그 다음 숫자가 하나뿐인 짝,
    마지막으로 줄 수가 같을 때만 순서대로 잡습니다.
    """
    out: dict[int, str] = {}
    used: set[int] = set()
    for i, en in enumerate(en_lines):
        if i < len(kr_lines) and i not in used and num_sig(kr_lines[i]) == num_sig(en):
            out[i] = kr_lines[i]
            used.add(i)
    for i, en in enumerate(en_lines):
        if i in out:
            continue
        sig = num_sig(en)
        cands = [j for j, kr in enumerate(kr_lines) if j not in used and num_sig(kr) == sig]
        if len(cands) == 1:
            out[i] = kr_lines[cands[0]]
            used.add(cands[0])
    rest_en = [i for i in range(len(en_lines)) if i not in out]
    rest_kr = [j for j in range(len(kr_lines)) if j not in used]
    if len(rest_en) == len(rest_kr):
        for i, j in zip(rest_en, rest_kr):
            out[i] = kr_lines[j]
    return out


class Dicts:
    def __init__(self) -> None:
        self.names: dict[str, str] = {}
        self.stats: dict[str, str] = {}
        self.conflicts: dict[str, set] = {}
        self.reasons: Counter = Counter()
        self.samples: dict[str, list] = {}
        self.pending_hints: list = []

    def name(self, en: str, kr: str) -> None:
        en, kr = norm_space(strip_ggg(en or "")), norm_space(strip_ggg(kr or ""))
        if not en or not kr or en == kr:
            return
        prev = self.names.get(en)
        if prev is not None and prev != kr:
            self.conflicts.setdefault(en, set()).update({prev, kr})
            self.note("이름 충돌", en)
            return
        self.names[en] = kr

    def line(self, en: str, kr: str) -> None:
        en, kr = norm_space(strip_ggg(en or "")), norm_space(strip_ggg(kr or ""))
        if not en or not kr or en == kr:
            return
        prev = self.stats.get(en)
        if prev is not None and prev != kr:
            self.conflicts.setdefault(en, set()).update({prev, kr})
            if num_sig(prev) != num_sig(kr):
                # 줄을 나누는 자리에 걸린 조각 문구다. 같은 영문 조각에 숫자가 다른 한글이 붙으면
                # 어느 쪽이 맞는지 런타임에 알 수 없으므로, 틀린 숫자를 보이느니 영문을 남긴다.
                self.stats.pop(en, None)
                self.note("숫자가 갈리는 조각 문구(제외)", en)
            else:
                self.note("문구 충돌", en)
            return
        self.stats[en] = kr

    def pair_lines(self, en_lines: list[str], kr_lines: list[str], label: str) -> None:
        """영문/한글 줄 목록을 짝짓습니다.

        줄 수가 같으면 그대로, 다르면 한글이 더 짧은 경우가 대부분이므로(한글이 압축적)
        한글 전체를 영문 줄 길이 비율로 나눠 화면에 그려지는 줄 수에 맞춥니다.
        (PoB 는 영어 원문의 `\\n` 위치에서 줄을 나눠 그리므로, 그 자리에 맞춰야 합니다)
        """
        if not en_lines or not kr_lines:
            return
        if len(en_lines) == len(kr_lines):
            pairs = _assign(en_lines, kr_lines)
            for i, en in enumerate(en_lines):
                if i in pairs:
                    self.line(en, pairs[i])
                else:
                    self.note("%s 미번역" % label, en)
            return
        if len(en_lines) == 1:
            # 영문은 한 줄인데 한글이 여러 줄이면, 이어 붙여 한 줄로 그립니다.
            self.line(en_lines[0], " ".join(kr_lines))
            return
        # 영문이 여러 줄인데 한글 줄 수가 다르면, 어느 조각에 어떤 숫자가 들어가는지
        # 런타임에 알 수 없습니다. 틀린 숫자를 보이느니 영문을 남깁니다.
        self.note("%s 줄 나눔 불가(영문 유지)" % label,
                  "%s / %s" % (" | ".join(en_lines), " ".join(kr_lines)))

    def pair_hints(self, en_lines: list[str], kr_lines: list[str], label: str) -> None:
        """힌트 문구(괄호 안 설명)를 짝짓습니다.

        한글 쪽에는 PoB 에 없는 힌트가 섞여 있는 경우가 있어(예: 실명 설명 추가) 문장을
        이어 붙이면 서로 다른 힌트가 섞입니다. 줄 수가 같으면 그대로 짝짓고, 다르면
        숫자 토큰이 같은 줄끼리만 짝짓습니다.
        """
        if not en_lines or not kr_lines:
            return
        pairs = _assign(en_lines, kr_lines)
        for i, en in enumerate(en_lines):
            if i in pairs:
                self.line(en, pairs[i])
            else:
                self.note("%s 미번역" % label, en)

    def resolve_hints(self) -> None:
        """줄 수가 달랐던 힌트들을 숫자 토큰·이미 아는 문구로 맞춥니다."""
        for en_lines, kr_lines, label in self.pending_hints:
            # 아는 문구는 그대로 두고, 모르는 영문만 남은 한글 줄과 맞춘다.
            open_en = [e for e in en_lines if e not in self.stats]
            known = [e for e in en_lines if e in self.stats]
            free_kr = list(kr_lines)
            for en in known:
                kr = self.stats[en]
                if kr in free_kr:
                    free_kr.remove(kr)
            pairs = _assign(open_en, free_kr)
            for i, en in enumerate(open_en):
                if i in pairs:
                    self.line(en, pairs[i])
                else:
                    self.note("%s 미번역" % label, en)

    def note(self, why: str, sample: str) -> None:
        self.reasons[why] += 1
        bucket = self.samples.setdefault(why, [])
        if len(bucket) < 8:
            bucket.append(sample[:160])


def _effects(container) -> dict:
    out = {}
    for effect in (container or {}).get("masteryEffects") or []:
        if isinstance(effect, dict) and effect.get("effect") is not None:
            out.setdefault(effect["effect"], effect)
    return out


def build_classes(us: dict, kr: dict, d: Dicts) -> None:
    """직업·전직 이름을 먼저 넣습니다. (전직 드롭다운과 트리 안내에 그려집니다)"""
    for i, cls in enumerate(us.get("classes") or []):
        mate = (kr.get("classes") or [])[i] if i < len(kr.get("classes") or []) else {}
        d.name(cls.get("name"), mate.get("name"))
        for j, asc in enumerate(cls.get("ascendancies") or []):
            mate_asc = (mate.get("ascendancies") or [])[j] if j < len(mate.get("ascendancies") or []) else {}
            d.name(asc.get("name"), mate_asc.get("name"))


def build(us: dict, kr: dict, d: Dicts, pob: dict | None = None) -> None:
    """사전을 만듭니다. 영문은 PoB 가 실제로 그리는 문구를 우선 쓰고, 없으면 poedb 영문을 씁니다."""
    pob = pob or {}
    build_classes(us, kr, d)
    for node_id, other in kr.items():
        pob_node = pob.get(int(node_id)) if str(node_id).isdigit() else None
        us_node = us.get(node_id) or {}
        if not pob_node and not us_node:
            continue

        en_name = (us_node.get("name") or (pob_node or {}).get("name") or "")
        d.name(en_name, other.get("name") or "")

        # 일반 스탯 줄 — 화면에 그려지는 줄(PoB)을 기준으로 짝짓습니다.
        en_stats = lines_of((pob_node or {}).get("stats")) or lines_of(us_node.get("stats"))
        d.pair_lines(en_stats, lines_of(other.get("stats")), "스탯")

        # 숙련 효과: 노드 id 가 아니라 effect id 로 짝짓습니다.
        kr_effects = _effects(other)
        en_effects = _effects(pob_node) or _effects(us_node)
        for effect_id, effect in en_effects.items():
            mate = kr_effects.get(effect_id)
            if mate is None:
                d.note("한국어에 숙련 선택지 없음", "%s: %s" % (
                    other.get("name"), " | ".join(lines_of(effect.get("stats")))[:120]))
                continue
            en_effect_lines = lines_of(effect.get("stats"))
            if not en_effect_lines:
                poedb_effect = _effects(us_node).get(effect_id)
                en_effect_lines = lines_of((poedb_effect or {}).get("stats"))
            d.pair_lines(en_effect_lines, lines_of(mate.get("stats")), "숙련 선택지")
            kr_effect_hints = lines_of(mate.get("reminderText"))
            en_effect_hints = lines_of(effect.get("reminderText"))
            if len(en_effect_hints) != len(kr_effect_hints):
                alt = lines_of(_effects(us_node).get(effect_id, {}).get("reminderText"))
                if alt and len(alt) == len(kr_effect_hints):
                    en_effect_hints = alt
            d.pair_hints(en_effect_hints, kr_effect_hints, "숙련 힌트")

        # 힌트 문구 / 플레이버 문구
        kr_hints = lines_of(other.get("reminderText"))
        en_hints = lines_of((pob_node or {}).get("reminderText")) or lines_of(us_node.get("reminderText"))
        if len(en_hints) != len(kr_hints):
            alt = lines_of(us_node.get("reminderText"))
            if alt and len(alt) == len(kr_hints):
                en_hints = alt
        d.pair_hints(en_hints, kr_hints, "힌트")
        d.pair_lines(lines_of((pob_node or {}).get("flavourText")) or lines_of(us_node.get("flavourText")),
                     lines_of(other.get("flavourText")), "플레이버")


# ── 커버리지 (PoB 가 그리는 문자열 기준) ────────────────────────────────────
def node_kind(node: dict) -> str:
    if node.get("isMastery"):
        return "숙련"
    if node.get("ascendancyName") or node.get("isAscendancyStart"):
        return "전직"
    if node.get("isKeystone") or node.get("ks"):
        return "핵심노드"
    if node.get("isNotable") or node.get("notable"):
        return "주요노드"
    if node.get("isJewelSocket"):
        return "주얼슬롯"
    if node.get("classStartIndex") is not None:
        return "클래스시작"
    return "일반"


def coverage(pob: dict, names: dict, stats: dict) -> dict:
    per_kind: dict[str, dict[str, set]] = {}
    reminders: set[tuple[str, str]] = set()
    flavour: set[tuple[str, str]] = set()
    missing_names: list[str] = []
    missing_stats: list[str] = []
    missing_mastery: list[str] = []
    missing_reminder: list[str] = []
    missing_flavour: list[str] = []

    for node in pob.values():
        if not isinstance(node, dict):
            continue
        kind = node_kind(node)
        bucket = per_kind.setdefault(kind, {"names": set(), "stats": set()})
        name = norm_space(node.get("name") or "")
        if name:
            bucket["names"].add(name)
            if name not in names:
                missing_names.append("%s: %s" % (kind, name))
        for line in lines_of(node.get("stats")):
            bucket["stats"].add(line)
            if line not in stats:
                missing_stats.append("%s: %s" % (kind, line))
        for effect in node.get("masteryEffects") or []:
            if not isinstance(effect, dict):
                continue
            for line in lines_of(effect.get("stats")):
                bucket.setdefault("mastery_stats", set()).add(line)
                if line not in stats:
                    missing_mastery.append(line)
            for line in lines_of(effect.get("reminderText")):
                missing_reminder.append(line) if line not in stats else None
        for line in lines_of(node.get("reminderText")):
            reminders.add((kind, line))
            if line not in stats:
                missing_reminder.append(line)
        for line in lines_of(node.get("flavourText")):
            flavour.add((kind, line))
            if line not in stats:
                missing_flavour.append(line)

    counts = {}
    for kind, bucket in sorted(per_kind.items()):
        for what in ("names", "stats", "mastery_stats"):
            values = bucket.get(what)
            if not values:
                continue
            hit = sum(1 for v in values if (v in names if what == "names" else v in stats))
            counts["%s %s" % (kind, "이름" if what == "names" else "문구")] = {
                "total": len(values), "hit": hit}
    counts["힌트 문구"] = {"total": len(reminders), "hit": sum(1 for _, v in reminders if v in stats)}
    counts["플레이버 문구"] = {"total": len(flavour), "hit": sum(1 for _, v in flavour if v in stats)}

    def uniq(seq):
        return sorted(set(seq))

    return {
        "counts": counts,
        "missing": {
            "node_names": uniq(missing_names),
            "node_stats": uniq(missing_stats),
            "mastery_stats": uniq(missing_mastery),
            "reminders": uniq(missing_reminder),
            "flavour": uniq(missing_flavour),
        },
    }


def report(cov: dict) -> None:
    print("  [영역별 커버리지]")
    for key, value in cov["counts"].items():
        print("    %-16s %5d/%5d (%5.1f%%)" % (
            key, value["hit"], value["total"], 100.0 * value["hit"] / max(1, value["total"])))
    left = cov["missing"]
    total_miss = sum(len(v) for v in left.values())
    print("  남은 미번역 %d개" % total_miss)
    for key, values in left.items():
        if values:
            print("    %-14s %d  예: %s" % (key, len(values), values[0][:90]))


def main() -> None:
    us = poedb_tree("us")["nodes"]
    kr = poedb_tree("kr")["nodes"]
    pob = pob_tree_nodes()

    d = Dicts()
    build(us, kr, d, pob)
    save_json("passives_names.json", d.names)
    save_json("passives_stats.json", d.stats)
    save_json("passive_conflicts.json", {k: sorted(v) for k, v in d.conflicts.items()})

    mastery_nodes = sum(1 for n in us.values() if isinstance(n, dict) and n.get("masteryEffects"))
    mastery_effects = sum(len(n.get("masteryEffects") or [])
                          for n in us.values() if isinstance(n, dict))
    print("node names: dict=%d, stat lines: dict=%d, conflicts=%d" % (
        len(d.names), len(d.stats), len(d.conflicts)))
    print("숙련 노드 %d개 / 선택지 %d개 (힌트 문구 포함)" % (mastery_nodes, mastery_effects))
    if d.reasons:
        print("짝짓기 보류:", dict(d.reasons))
        for why, samples in d.samples.items():
            print("   %s 예: %s" % (why, samples[0][:100]))

    if not pob:
        return

    cov = coverage(pob, d.names, d.stats)
    report(cov)
    record = {
        "dict": {"names": len(d.names), "stats": len(d.stats), "conflicts": len(d.conflicts)},
        "mastery": {"nodes": mastery_nodes, "effects": mastery_effects},
        "pairing": {"reasons": dict(d.reasons), "samples": d.samples},
        "coverage": cov,
    }
    save_json("passives_report.json", record)


if __name__ == "__main__":
    main()
