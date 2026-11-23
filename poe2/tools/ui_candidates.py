"""PoB2 UI 후보 문자열 추출.

CalcSections / ConfigOptions / 각 탭의 label·format 리터럴을 모아
번역 후보 목록(poe2/data/ui_candidates.json)을 만든다.
"""
from __future__ import annotations

import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import POB2, save_json  # noqa: E402

PATTERNS = [
    re.compile(r'\blabel\s*=\s*"((?:[^"\\]|\\.){2,80})"'),
    re.compile(r'\bformat\s*=\s*"((?:[^"\\]|\\.){2,80})"'),
    re.compile(r'\btitle\s*=\s*"((?:[^"\\]|\\.){2,80})"'),
    re.compile(r'\bplaceholder\s*=\s*"((?:[^"\\]|\\.){2,80})"'),
    re.compile(r'\btooltip\s*=\s*"((?:[^"\\]|\\.){2,120})"'),
    re.compile(r'"([A-Z][A-Za-z0-9 ,\'()/%\.\-]{2,40}):"'),
]

SKIP = re.compile(r"^[\^%d\s]|^https?:|\.lua$|\.png$|\.xml$|^%|ID$")


def main() -> None:
    found: dict[str, int] = {}
    for base, _dirs, files in os.walk(os.path.join(POB2)):
        if os.sep + "Data" in base or os.sep + "TreeData" in base:
            continue
        for name in files:
            if not name.endswith(".lua"):
                continue
            path = os.path.join(base, name)
            try:
                text = open(path, encoding="utf-8", errors="ignore").read()
            except OSError:
                continue
            for pat in PATTERNS:
                for m in pat.finditer(text):
                    s = m.group(1)
                    s = s.replace("\\n", " ").replace('\\"', '"').strip()
                    if not s or len(s) < 2:
                        continue
                    if not re.search(r"[A-Za-z]{2,}", s):
                        continue
                    if SKIP.search(s):
                        continue
                    if "${" in s or ".." in s:
                        continue
                    found[s] = found.get(s, 0) + 1
    ordered = dict(sorted(found.items(), key=lambda kv: (-kv[1], kv[0])))
    save_json("ui_candidates.json", ordered)
    print("후보 %d개" % len(ordered))
    for s, n in list(ordered.items())[:25]:
        print("  %3d %s" % (n, s))


if __name__ == "__main__":
    main()
