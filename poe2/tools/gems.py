"""PoE2 젬 이름 사전 (PoB2 Data/Gems.lua 이름 ↔ poe2db 젬 목록 슬러그).

poe2db 의 젬 페이지는 언어별로 같은 슬러그를 쓰므로, 슬러그(공백 대신 _)로
영문 이름과 한글 이름을 짝지을 수 있습니다.

결과: data/gems.json {영문 젬 이름: 한글 이름}, data/gems_report.json
"""
from __future__ import annotations

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import POB2, fetch, load_lua_table, lua_to_py, page_links, save_json  # noqa: E402

PAGES = ("Skill_Gems", "Support_Gems", "Spirit_Gems", "Lineage_Supports", "Meta_Skill_Gem")
HANGUL_RE = re.compile(r"[\uac00-\ud7a3]")


def norm(slug: str) -> str:
    return re.sub(r"[^a-z0-9]", "", slug.lower())


def main() -> None:
    labels: dict[str, str] = {}
    for page in PAGES:
        for lang in ("us", "kr"):
            text = fetch("https://poe2db.tw/%s/%s" % (lang, page), "%s_%s.html" % (page, lang))
            links = page_links(text, lang)
            print("  %-18s %-3s %4d links" % (page, lang, len(links)))
            if lang == "kr":
                for slug, label in links.items():
                    labels.setdefault(norm(slug), label)

    gems = lua_to_py(load_lua_table(os.path.join(POB2, "Data", "Gems.lua")))
    names: dict[str, str] = {}
    missing: list[str] = []
    for value in gems.values():
        if not isinstance(value, dict):
            continue
        name = (value.get("name") or "").strip()
        if not name or name in names:
            continue
        ko = labels.get(norm(name)) or ""
        if ko and HANGUL_RE.search(ko):
            names[name] = ko
        else:
            missing.append(name)

    save_json("gems.json", names)
    save_json("gems_missing.json", sorted(missing))
    print("젬 이름 %d/%d 짝지음" % (len(names), len(names) + len(missing)))


if __name__ == "__main__":
    main()
