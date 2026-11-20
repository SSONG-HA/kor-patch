"""Emit runtime Lua dictionaries from the harvested JSON data."""
from __future__ import annotations

import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import DATA, SRC, load_json  # noqa: E402

REQUIRED_INPUTS = ("gems.json", "passives_names.json", "passives_stats.json",
                   "uniques.json", "bases.json", "mods_exact.json")


def check_inputs():
    missing = [f for f in REQUIRED_INPUTS if not os.path.exists(os.path.join(DATA, f))]
    if missing:
        print("먼저 데이터 수집 스크립트를 실행하세요 (gems.py, passives.py, items.py).")
        print("없는 파일:", ", ".join(missing))
        raise SystemExit(1)


OUT = os.path.join(SRC, "Data")
os.makedirs(OUT, exist_ok=True)


def esc(s: str) -> str:
    out = []
    for ch in s:
        o = ord(ch)
        if ch == '"':
            out.append('\\"')
        elif ch == "\\":
            out.append("\\\\")
        elif ch == "\n":
            out.append("\\n")
        elif ch == "\t":
            out.append("\\t")
        elif o < 32:
            out.append("\\%d" % o)
        else:
            out.append(ch)
    return "".join(out)


def write_table(name: str, table: dict[str, str], comment: str) -> int:
    items = sorted(table.items())
    lines = ["-- PoB-KR : %s" % comment, "-- 자동 생성 파일입니다. 수정하지 마세요.", "return {"]
    for k, v in items:
        if not k or not v:
            continue
        lines.append('["%s"]="%s",' % (esc(k), esc(v)))
    lines.append("}")
    path = os.path.join(OUT, name)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + "\n")
    return os.path.getsize(path)


PAIR_RE = re.compile(r"%(\d)\s*[~\-]\s*%(\d)")


def merge_placeholder_pair(key: str, kr: str) -> str:
    """자리표시가 키의 # 개수보다 하나 많고 두 칸이 "~" 로 붙어 있으면 한 칸으로 합칩니다.

    poedb 는 "Adds 10 to 20 Fire Damage" 처럼 한 덩어리로 그려지는 값을 두 칸으로
    나눠 적어 두기도 합니다. 그대로 두면 화면에 "%2" 가 남습니다.
    """
    if kr.count("%") != key.count("#") + 1:
        return kr
    m = PAIR_RE.search(kr)
    if not m:
        return kr
    merged = kr[:m.start()] + "%" + m.group(1) + kr[m.end():]
    order: dict[str, str] = {}

    def ren(mo):
        idx = mo.group(1)
        if idx not in order:
            order[idx] = str(len(order) + 1)
        return "%" + order[idx]

    return re.sub(r"%(\d+)", ren, merged)


def main() -> None:
    check_inputs()
    exact: dict[str, str] = {}
    sources = [
        ("gems.json", "젬 이름"),
        ("passives_names.json", "패시브 노드 이름"),
        ("passives_stats.json", "패시브 효과 문구"),
        ("uniques.json", "유니크 아이템 이름"),
        ("bases.json", "베이스 아이템 이름"),
        # 군단 주얼(무궁한 주얼): 정복된 패시브 이름·스탯과 정복자 이름
        ("legion_exact.json", "군단 주얼 이름·문구"),
        # 클러스터 주얼(스킬 군 주얼): 주요 패시브 이름·인챈트·주얼 슬롯 문구
        ("cluster_exact.json", "클러스터 주얼 이름·문구"),
    ]
    counts = {}
    for fname, label in sources:
        data = load_json(fname)
        before = len(exact)
        for k, v in data.items():
            exact.setdefault(k, v)
        counts[label] = len(exact) - before

    # manual / curated tables win over harvested data
    for name, label in (("ui_ko.json", "PoB UI 문구"), ("overrides_ko.json", "수동 보정")):
        path = os.path.join(DATA, name)
        if os.path.exists(path):
            data = json.load(open(path, encoding="utf-8"))
            before = len(exact)
            for k, v in data.items():
                exact[k] = v
            counts[label] = len(exact) - before
            print("%-14s %5d entries" % (label, len(data)))

    size = write_table("exact.lua", exact, "영문 -> 한글 (정확 일치)")

    mods = load_json("mods_exact.json")
    templates = {k: v["kr"] for k, v in mods.items()}
    extra_path = os.path.join(DATA, "mods_extra.json")
    if os.path.exists(extra_path):
        extra = json.load(open(extra_path, encoding="utf-8"))
        templates.update(extra)
        print("%-14s %5d entries" % ("추가 모드 템플릿", len(extra)))
    # 군단 주얼 스탯 줄은 아이템 모드보다 먼저 넣어, 같은 키가 있으면 모드 문구를 남긴다.
    legion_path = os.path.join(DATA, "legion_templates.json")
    if os.path.exists(legion_path):
        legion = json.load(open(legion_path, encoding="utf-8"))
        before = len(templates)
        for k, v in legion.items():
            templates.setdefault(k, v)
        print("%-14s %5d entries (신규 %d)" % ("군단 주얼 스탯", len(legion), len(templates) - before))
    # 계산(Calcs) 화면 스탯 이름 + 비교 툴팁("+254 Effective Hit Pool (+0.3%)") 문형
    calcs_path = os.path.join(DATA, "calcs_ko.json")
    if os.path.exists(calcs_path):
        calcs = json.load(open(calcs_path, encoding="utf-8"))
        from items import shape  # noqa: E402  (런타임과 같은 정규화 규칙)
        added = 0
        for label, ko in calcs.items():
            exact.setdefault(label, ko)
            # 비교 툴팁에 그려지는 네 가지 모양: "+254 Label (+0.3%)", "+23% Label", …
            forms = (
                ("+0 %s (+0%%)" % label, "%%1 %s (%%2%%)" % ko),
                ("+0%% %s (+0%%)" % label, "%%1%% %s (%%2%%)" % ko),
                ("+0 %s" % label, "%%1 %s" % ko),
                ("+0%% %s" % label, "%%1%% %s" % ko),
            )
            for en, kr in forms:
                key = shape(en)
                before = len(templates)
                templates.setdefault(key, kr)
                added += len(templates) - before
        print("%-14s %5d entries (비교 문형 %d)" % ("계산 스탯 이름", len(calcs), added))
    cluster_path = os.path.join(DATA, "cluster_templates.json")
    if os.path.exists(cluster_path):
        cluster = json.load(open(cluster_path, encoding="utf-8"))
        before = len(templates)
        for k, v in cluster.items():
            templates.setdefault(k, v)
        print("%-14s %5d entries (신규 %d)" % ("클러스터 주얼 효과", len(cluster), len(templates) - before))
    fixed = 0
    for key, kr in list(templates.items()):
        new = merge_placeholder_pair(key, kr)
        if new != kr:
            templates[key] = new
            fixed += 1
    if fixed:
        print("%-14s %5d entries" % ("자리표시 합침", fixed))
    size2 = write_table("templates.lua", templates, "모드 문구 템플릿 (숫자 자리표시 %1 %2)")

    print("exact entries: %d (%.0f KB)" % (len(exact), size / 1024))
    print("template entries: %d (%.0f KB)" % (len(templates), size2 / 1024))
    for k, v in counts.items():
        print("   %-16s %5d" % (k, v))


if __name__ == "__main__":
    main()
