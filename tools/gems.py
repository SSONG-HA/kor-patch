"""Build the gem name dictionary (English -> Korean) from poedb.tw."""
from __future__ import annotations

import re
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import (  # noqa: E402
    POB, clean_pairs, fetch, load_lua_table, lua_to_py, page_links, save_json, strip_tags,
)

PAGES = ["Skill_Gems", "Support_Gems", "Transfigured_Gems", "Exceptional"]


def poedb_gem_pairs() -> dict[str, tuple[str, str]]:
    pairs: dict[str, tuple[str, str]] = {}
    for page in PAGES:
        us = page_links(fetch("https://poedb.tw/us/" + page, page + "_us.html"), "us")
        kr = page_links(fetch("https://poedb.tw/kr/" + page, page + "_kr.html"), "kr")
        for slug in sorted(set(us) & set(kr)):
            if slug in pairs:
                continue
            pairs[slug] = (us[slug], kr[slug])
    return clean_pairs(pairs)


def pob_gem_names() -> set[str]:
    """PoB 원본(POB_SRC)의 Data/Gems.lua 기준 젬 이름 목록. 없으면 빈 집합."""
    if not POB:
        return set()
    path = os.path.join(POB, "Data", "Gems.lua")
    if not os.path.exists(path):
        print("  (PoB Data/Gems.lua 없음 — poedb 전체 목록으로 사전 생성)")
        return set()
    gems = lua_to_py(load_lua_table(path))
    names = set()
    for k, v in gems.items():
        if isinstance(v, dict) and v.get("name"):
            names.add(v["name"])
    return names


def main() -> None:
    pairs = poedb_gem_pairs()
    by_en = {en: kr for (en, kr) in pairs.values()}
    names = pob_gem_names()
    target = sorted(names) if names else sorted(by_en)
    table = {}
    missing = []
    for name in target:
        kr = by_en.get(name)
        if kr:
            table[name] = kr
        else:
            missing.append(name)
    # poedb renders support gems with a "Support" suffix that PoB drops from `name`
    loose = {re.sub(r"\s+", " ", en).strip(): kr for (en, kr) in pairs.values()}
    for (en, kr) in pairs.values():
        loose.setdefault(re.sub(r" Support$", "", en), kr)
    for name in list(missing):
        kr = loose.get(re.sub(r"\s+", " ", name).strip())
        if kr:
            table[name] = kr
            missing.remove(name)
    save_json("gems.json", table)
    save_json("gems_missing.json", missing)
    print("poedb pairs: %d (unique en: %d)" % (len(pairs), len(by_en)))
    print("PoB gem names: %d, translated: %d (%.1f%%), missing: %d" % (
        len(names), len(table), 100.0 * len(table) / max(1, len(names)), len(missing)))
    for m in missing[:40]:
        print("   missing:", m)


if __name__ == "__main__":
    main()
