"""클러스터 주얼(스킬 군 주얼) 사전 — poedb.tw 의 Cluster_Jewel 페이지 + PoB 원본 데이터.

클러스터 주얼은 세 가지 문구가 화면에 그려집니다.

  1. 인챈트  : "Adds 8 Passive Skills", "Added Small Passive Skills grant: 12% increased Chaos Damage"
              (PoB 는 Data/ClusterJewels.lua 의 enchant 목록을 그대로 그립니다)
  2. 주요 패시브: "1 Added Passive Skill is Unholy Grace" (주얼 아이템 설명) 와 트리 안의 노드 이름·효과
  3. 주얼 슬롯: "1 Added Passive Skill is a Jewel Socket" / "2 Added Passive Skills are Jewel Sockets"

poedb 의 같은 페이지는 영어/한국어가 **같은 카드 slug** 로 되어 있어 이름과 효과를 그대로 짝지을 수
있습니다. 인챈트의 효과 문구는 아이템 속성 사전(data/mods_exact.json)에 있는
"Added Small Passive Skills also grant: …" 문장에서 효과 부분만 떼어 씁니다.
"""
from __future__ import annotations

import html
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import DATA, POB, fetch, load_json, load_lua_table, lua_to_py, norm_space, save_json  # noqa: E402
from items import NUM_TOKEN_RE, shape  # noqa: E402
from passives import _assign  # noqa: E402  (영문 줄 ↔ 한글 줄 배정 규칙을 그대로 씁니다)

PAGE = "https://poedb.tw/%s/Cluster_Jewel"
# 탭 id (한국어 페이지는 탭 id 까지 번역되어 있다)
TABS = ("ClusterJewelSpecial", "스킬군주얼Special")
TAG_RE = re.compile(r"<[^>]+>")
BR_RE = re.compile(r"<br\s*/?>")
CARD_SPLIT = '<div class="col"><div class="d-flex border-top rounded">'

SIZES = {
    "Small Cluster Jewel": "소형 스킬 군 주얼",
    "Medium Cluster Jewel": "중형 스킬 군 주얼",
    "Large Cluster Jewel": "대형 스킬 군 주얼",
}
JEWEL_SOCKET_1 = ("1 Added Passive Skill is a Jewel Socket", "주얼 슬롯 패시브 스킬 1개 추가")
JEWEL_SOCKET_2 = ("2 Added Passive Skills are Jewel Sockets", "주얼 슬롯 패시브 스킬 2개 추가")
ENCHANT_PREFIX = "추가된 소형 패시브 스킬 효과: "
# "Added Small Passive Skills grant: …" 줄이 만드는 키의 앞부분 (shape() 은 공백을 지운다)
ENCHANT_KEY = "AddedSmallPassiveSkillsgrant:"
ALSO_PREFIX = "추가되는 소형 패시브 스킬이 "
ALSO_SUFFIX = " 부여"


def page(lang: str) -> str:
    return fetch(PAGE % lang, "poedb_%s_Cluster_Jewel.html" % lang)


def section(text: str, names) -> str:
    for name in names:
        m = re.search(r'<div id="%s" class="tab-pane fade">' % re.escape(name), text)
        if not m:
            continue
        start = m.end()
        nxt = re.search(r'<div id="[^"]+" class="tab-pane fade">', text[start:])
        return text[start:start + nxt.start()] if nxt else text[start:]
    return ""


def strip(s: str) -> str:
    return html.unescape(TAG_RE.sub("", s)).strip()


def cards(sec: str) -> dict[str, dict]:
    """slug -> {name, lines, hover} (효과 줄은 <br> 로 나눠 담습니다)"""
    out: dict[str, dict] = {}
    for block in sec.split(CARD_SPLIT)[1:]:
        m = re.search(r'<a class="PassiveSkills"[^>]*href="([^"]*)"[^>]*>([^<]*)</a>', block)
        if not m:
            continue
        slug, name = m.group(1), html.unescape(m.group(2))
        hover = re.search(r'<a class="PassiveSkills"[^>]*data-hover="([^"]+)"', block)
        lines: list[str] = []
        for mod in re.findall(r'<div class="implicitMod">(.*?)</div>', block, re.S):
            for piece in BR_RE.split(mod):
                text = strip(piece)
                if text:
                    lines.append(norm_space(text))
        out.setdefault(slug, {"name": name, "lines": lines,
                              "hover": hover.group(1) if hover else ""})
    return out


def hover_lines(url: str) -> list[str]:
    """poedb 카드의 hover 자료(같은 문구를 <br/> 로 정확히 나눠 둔 HTML)에서 효과 줄만 읽습니다."""
    if not url:
        return []
    try:
        text = subprocess.run(["curl", "-sSL", "--max-time", "30", url],
                              capture_output=True).stdout.decode("utf-8", "ignore")
    except Exception:  # noqa: BLE001
        return []
    if not text:
        return []
    out: list[str] = []
    for mod in re.findall(r'<div class="implicitMod">(.*?)</div>', text, re.S):
        if "item_description" in mod:
            continue
        for piece in BR_RE.split(mod):
            line = strip(piece)
            if line:
                out.append(norm_space(line))
    return out


# ── 숫자 자리표시 ────────────────────────────────────────────────────────────
def numbers(text: str) -> list[str]:
    return NUM_TOKEN_RE.findall(text.replace("\u2014", "-").replace("\u2013", "-"))


def templated(en: str, kr: str) -> str | None:
    """영문/한글 한 줄을 짝지어 자리표시(%1, %2 …) 한글 템플릿을 만듭니다."""
    en_nums = numbers(en)
    if not en_nums:
        return kr
    kr_nums = numbers(kr)
    # 한글에는 영문에 없는 숫자가 섞이기도 합니다 ("시체 1구를 … 5% 회복").
    # 영문 쪽 숫자를 모두 설명할 수 있으면, 나머지 한글 숫자는 그대로 둡니다.
    mapping: dict[int, int] = {}
    used: set[int] = set()
    for ki, kn in enumerate(kr_nums):
        value = kn.lstrip("+").strip("()")
        for ej, e in enumerate(en_nums):
            if ej not in used and e.lstrip("+").strip("()") == value:
                mapping[ki] = ej
                used.add(ej)
                break
    if len(used) != len(en_nums):
        return None  # 영문 숫자를 다 설명하지 못하면 건너뜀
    counter = {"n": 0}

    def repl(m):
        idx = counter["n"]
        counter["n"] += 1
        return "%%%d" % (mapping[idx] + 1) if idx in mapping else m.group(0)

    text = NUM_TOKEN_RE.sub(repl, kr.replace("\u2014", "-").replace("\u2013", "-"))
    return norm_space(text)


def main() -> None:
    exact: dict[str, str] = {}
    templates: dict[str, str] = {}
    report: list[str] = []

    # 지난번에 만든 인챈트 줄(대·중·소형 군주얼). PoB 원문이 없을 때는 이것을 그대로 쓴다.
    prev: dict[str, str] = {}
    prev_path = os.path.join(DATA, "cluster_templates.json")
    if os.path.exists(prev_path):
        try:
            prev = load_json("cluster_templates.json")
        except Exception:  # noqa: BLE001
            prev = {}

    for en, kr in SIZES.items():
        exact[en] = kr
    exact[JEWEL_SOCKET_1[0]] = JEWEL_SOCKET_1[1]
    exact[JEWEL_SOCKET_2[0]] = JEWEL_SOCKET_2[1]
    templates[shape("Adds # Passive Skills")] = "패시브 스킬 %1개 추가"

    us, kr = page("us"), page("kr")
    cu = cards(section(us, TABS))
    ck = cards(section(kr, TABS))
    print("클러스터 주요 패시브: 영문 %d / 한국어 %d 카드" % (len(cu), len(ck)))

    names = stat_lines = 0
    for slug, card in cu.items():
        mate = ck.get(slug)
        if not mate:
            report.append("한국어 카드 없음: %s" % card["name"])
            continue
        en_name, kr_name = card["name"], mate["name"]
        if en_name and kr_name and en_name != kr_name:
            exact.setdefault(en_name, kr_name)
            exact.setdefault("1 Added Passive Skill is " + en_name, "패시브 스킬 1개 추가: " + kr_name)
            names += 1
        en_lines = [x for x in card["lines"] if not x.startswith("(")]
        kr_lines = [x for x in mate["lines"] if not x.startswith("(")]
        if len(en_lines) != len(kr_lines):
            # 한국어 카드는 두 속성이 한 줄로 붙어 있는 경우가 있다 → hover 자료의 <br/> 를 씀
            alt_en = [x for x in hover_lines(card["hover"]) if not x.startswith("(")]
            alt_kr = [x for x in hover_lines(mate["hover"]) if not x.startswith("(")]
            if alt_en:
                en_lines = alt_en
            if alt_kr:
                kr_lines = alt_kr
        pairs = _assign(en_lines, kr_lines)
        for i, a in enumerate(en_lines):
            b = pairs.get(i)
            if b is None:
                report.append("짝 없음: %s / %s" % (en_name, a[:60]))
                continue
            tpl = templated(a, b)
            if tpl is None:
                report.append("숫자 짝짓기 실패: %s / %s" % (en_name, a))
                continue
            key = shape(a)
            if "#" in key:
                templates.setdefault(key, tpl)
            else:
                exact.setdefault(a, tpl)
            stat_lines += 1

    # ── 인챈트: PoB 가 그리는 문구를 기준으로 만듭니다 ────────────────────────
    enchants = 0
    mods = {}
    path = os.path.join(DATA, "mods_exact.json")
    if os.path.exists(path):
        mods = load_json("mods_exact.json")
    # 패시브 트리 효과 문구(값이 박힌 영문 -> 한글). 아이템 속성 사전에 없는
    # 클러스터 소형 패시브 효과(예: 12% increased Cold Damage over Time)를 마지막에 여기서 찾습니다.
    passive_stats = {}
    stats_path = os.path.join(DATA, "passives_stats.json")
    if os.path.exists(stats_path):
        passive_stats = load_json("passives_stats.json")
    if POB:
        cluster_path = os.path.join(POB, "Data", "ClusterJewels.lua")
        if not os.path.exists(cluster_path):
            # v2.0.1: 시즌 갱신이 이 파일을 받지 않아 인챈트 52줄이 조용히 사라졌습니다.
            # 조용한 누락을 다시 만들지 않도록 여기서 멈춥니다.
            raise SystemExit(
                "PoB 원본 Data/ClusterJewels.lua 가 없습니다: %s\n"
                "  먼저 tools/fetch_pob.py 를 실행해 PoB 원문 데이터를 받으세요.\n"
                "  (이 파일이 없으면 대·중·소형 군주얼 인챈트가 통째로 빠집니다)" % cluster_path)
        jewels = lua_to_py(load_lua_table(cluster_path)).get("jewels") or {}
        for size, data in jewels.items():
            for skill in ((data or {}).get("skills") or {}).values():
                if not isinstance(skill, dict):
                    continue
                stats = skill.get("stats") or []
                for line in skill.get("enchant") or []:
                    m = re.match(r"^Added Small Passive Skills grant: (.+)$", line)
                    if not m:
                        continue
                    # 인챈트 줄의 효과 문구가 곧 그 소형 패시브의 효과다.
                    # 한 스킬에 효과가 둘(예: affliction_dagger_and_claw_damage)일 때
                    # 첫 효과를 그대로 쓰면 다른 쪽이 통째로 잘못 번역된다 (클로 ← 단검).
                    stat = m.group(1) if m.group(1) in stats else next(iter(stats), "")
                    if not stat:
                        continue
                    kr_stat = ko_stat(stat, mods, templates, passive_stats)
                    if not kr_stat:
                        report.append("인챈트 효과 번역 없음: %s" % stat)
                        continue
                    key = shape(line)
                    if "#" in key:
                        templates.setdefault(key, ENCHANT_PREFIX + kr_stat)
                    else:
                        exact.setdefault(line, ENCHANT_PREFIX + kr_stat)
                    enchants += 1
    else:
        # POB_SRC 없이 돌리면 인챈트를 만들 수 없다. 그대로 비우면 v2.0.1 처럼
        # 60줄이 조용히 사라지므로, 지난번 결과를 유지하고 크게 알린다.
        kept = {k: v for k, v in prev.items() if k.startswith(ENCHANT_KEY)}
        templates.update(kept)
        print("  !! POB_SRC 가 없어 군주얼 인챈트를 새로 만들지 못했습니다 — 기존 %d줄을 그대로 둡니다." % len(kept))
        print("     (tools/fetch_pob.py 를 실행하고 POB_SRC 를 지정하면 다시 만들어집니다)")
        if not kept:
            report.append("POB_SRC 없음 — 군주얼 인챈트 없음")

    save_json("cluster_exact.json", exact)
    save_json("cluster_templates.json", templates)
    print("클러스터 주얼 사전: 이름/문구 %d개, 주얼 효과 %d줄, 인챈트 %d개" % (names, stat_lines, enchants))
    if report:
        print("  보류 %d건 (예: %s)" % (len(report), report[:3]))


def ko_stat(stat: str, mods: dict, templates: dict | None = None,
            passive_stats: dict | None = None) -> str | None:
    """클러스터 인챈트 효과 문구의 한글.

    ① 아이템 속성 사전의 "Added Small Passive Skills also grant: …" 에서 효과 부분만 뗌
    ② 같은 효과가 아이템 속성으로 따로 있을 때 그 문구
    ③ 클러스터 주요 패시브 카드에서 짝지은 효과 줄
    ④ 패시브 트리 효과 문구 사전(passives_stats)의 같은 값 문장 → 숫자만 자리표시로
       (3.30 에 새로 생긴 "12% increased Cold Damage over Time" 처럼
        아이템 속성으로는 존재하지 않고 트리 효과로만 있는 문구)
    """
    key = shape("Added Small Passive Skills also grant: " + stat)
    entry = mods.get(key)
    if entry:
        kr = entry["kr"] if isinstance(entry, dict) else entry
        if kr.startswith(ALSO_PREFIX) and kr.endswith(ALSO_SUFFIX):
            return kr[len(ALSO_PREFIX):-len(ALSO_SUFFIX)].strip()
    for source in (mods, templates or {}):
        entry = source.get(shape(stat))
        if not entry:
            continue
        if isinstance(entry, dict):
            return entry.get("kr")
        return entry
    if passive_stats:
        kr = passive_stats.get(norm_space(stat))
        if isinstance(kr, dict):
            kr = kr.get("kr")
        if kr:
            return templated(stat, norm_space(kr))
    return None


if __name__ == "__main__":
    main()
