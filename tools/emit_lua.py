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


def main() -> None:
    check_inputs()
    exact: dict[str, str] = {}
    sources = [
        ("gems.json", "젬 이름"),
        ("passives_names.json", "패시브 노드 이름"),
        ("passives_stats.json", "패시브 효과 문구"),
        ("uniques.json", "유니크 아이템 이름"),
        ("bases.json", "베이스 아이템 이름"),
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
    size2 = write_table("templates.lua", templates, "모드 문구 템플릿 (숫자 자리표시 %1 %2)")

    print("exact entries: %d (%.0f KB)" % (len(exact), size / 1024))
    print("template entries: %d (%.0f KB)" % (len(templates), size2 / 1024))
    for k, v in counts.items():
        print("   %-16s %5d" % (k, v))


if __name__ == "__main__":
    main()
