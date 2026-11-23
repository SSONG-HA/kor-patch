"""수집한 JSON 을 런타임 Lua 사전(src/KR2/Data)으로 굽는다.

PoE1(kor-patch) emit_lua.py 와 같은 구조입니다.
  exact.lua     영문 → 한글 (정확 일치)
  templates.lua 숫자 자리표시(%1 %2) 문구
"""
from __future__ import annotations

import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import DATA, SRC, load_json, shape  # noqa: E402

OUT = os.path.join(SRC, "Data")
os.makedirs(OUT, exist_ok=True)

EXACT_SOURCES = (
    ("tree_names.json", "패시브 노드 이름"),
    ("tree_stats.json", "패시브 효과 문구"),
    ("tree_classes.json", "클래스·전직 이름"),
    ("gems.json", "젬 이름"),
    ("bases.json", "베이스 아이템 이름"),
    ("uniques.json", "유니크 아이템 이름"),
    ("mods_static.json", "숫자 없는 속성 문구"),
    ("keywords.json", "태그·키워드 이름"),
    ("properties_exact.json", "아이템·젬 창 고정 문구"),
)


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
    lines = ["-- PoB-KR2 : %s" % comment, "-- 자동 생성 파일입니다. 수정하지 마세요.", "return {"]
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
    """자리표시가 키의 # 개수보다 하나 많고 두 칸이 '~' 로 붙어 있으면 한 칸으로 합친다."""
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


def have(name: str) -> bool:
    return os.path.exists(os.path.join(DATA, name))


def main() -> None:
    exact: dict[str, str] = {}
    counts: dict[str, int] = {}
    for fname, label in EXACT_SOURCES:
        if not have(fname):
            print("  %-22s (없음, 건너뜀)" % fname)
            continue
        data = load_json(fname)
        before = len(exact)
        for k, v in data.items():
            exact.setdefault(k, v)
        counts[label] = len(exact) - before

    for name, label in (("ui_ko.json", "PoB UI 문구"), ("overrides_ko.json", "수동 보정")):
        if not have(name):
            continue
        data = load_json(name)
        before = len(exact)
        for k, v in data.items():
            exact[k] = v
        counts[label] = len(exact) - before

    size = write_table("exact.lua", exact, "영문 -> 한글 (정확 일치)")

    templates: dict[str, str] = {}
    if have("mods_exact.json"):
        for key, value in load_json("mods_exact.json").items():
            templates[key] = value["kr"] if isinstance(value, dict) else value
    for name in ("mods_extra.json", "properties_templates.json"):
        if have(name):
            extra = load_json(name)
            before = len(templates)
            for k, v in extra.items():
                templates.setdefault(k, v)
            counts["추가 템플릿 " + name] = len(templates) - before

    if have("calcs_ko.json"):
        calcs = load_json("calcs_ko.json")
        added = 0
        for label, ko in calcs.items():
            exact.setdefault(label, ko)
            for en, kr in (("+0 %s (+0%%)" % label, "%%1 %s (%%2%%)" % ko),
                           ("+0%% %s (+0%%)" % label, "%%1%% %s (%%2%%)" % ko),
                           ("+0 %s" % label, "%%1 %s" % ko),
                           ("+0%% %s" % label, "%%1%% %s" % ko)):
                key = shape(en)
                before = len(templates)
                templates.setdefault(key, kr)
                added += len(templates) - before
        print("%-16s %5d entries (비교 문형 %d)" % ("계산 스탯 이름", len(calcs), added))

    fixed = 0
    for key, kr in list(templates.items()):
        new = merge_placeholder_pair(key, kr)
        if new != kr:
            templates[key] = new
            fixed += 1
    if fixed:
        print("%-16s %5d entries" % ("자리표시 합침", fixed))

    size2 = write_table("templates.lua", templates, "모드 문구 템플릿 (숫자 자리표시 %1 %2)")
    # 계산 이름을 exact 에 넣었으므로 다시 굽는다.
    size = write_table("exact.lua", exact, "영문 -> 한글 (정확 일치)")

    print("exact %d개 (%.0f KB) / templates %d개 (%.0f KB)" % (
        len(exact), size / 1024, len(templates), size2 / 1024))
    for k, v in counts.items():
        print("   %-18s %5d" % (k, v))


if __name__ == "__main__":
    main()
