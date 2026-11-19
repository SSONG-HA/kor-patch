"""Build item dictionaries from poedb item-class pages.

Produces:
  data/mods_exact.json   {en template: {"kr": kr template, "n": slot count}}
  data/uniques.json      {en unique name: kr name}
  data/bases.json        {en base type line: kr base type line}
"""
from __future__ import annotations

import json
import re
import sys
import urllib.parse

sys.path.insert(0, __file__.rsplit("/", 1)[0])
from common import fetch, norm_space, save_json, strip_tags  # noqa: E402

CLASSES = [
    "Claws", "Daggers", "Wands", "One_Hand_Swords", "One_Hand_Axes", "One_Hand_Maces",
    "Sceptres", "Rune_Daggers", "Thrusting_One_Hand_Swords", "Bows", "Staves",
    "Two_Hand_Swords", "Two_Hand_Axes", "Two_Hand_Maces", "Warstaves", "Fishing_Rods",
    "Amulets", "Rings", "Belts", "Trinkets",
    "Gloves_str", "Gloves_dex", "Gloves_int", "Gloves_str_dex", "Gloves_str_int", "Gloves_dex_int",
    "Boots_str", "Boots_dex", "Boots_int", "Boots_str_dex", "Boots_str_int", "Boots_dex_int",
    "Body_Armours_str", "Body_Armours_dex", "Body_Armours_int", "Body_Armours_str_dex",
    "Body_Armours_str_int", "Body_Armours_dex_int", "Body_Armours_str_dex_int",
    "Helmets_str", "Helmets_dex", "Helmets_int", "Helmets_str_dex", "Helmets_str_int", "Helmets_dex_int",
    "Quivers", "Shields_str", "Shields_dex", "Shields_int", "Shields_str_dex", "Shields_str_int", "Shields_dex_int",
    "Crimson_Jewel", "Viridian_Jewel", "Cobalt_Jewel", "Prismatic_Jewel",
    "Murderous_Eye_Jewel", "Searching_Eye_Jewel", "Hypnotic_Eye_Jewel", "Ghastly_Eye_Jewel",
    "Assembled_Eye_Jewel", "Timeless_Jewel",
    "Life_Flasks", "Mana_Flasks", "Utility_Flasks", "Tinctures",
]

def is_merged_noise(kr_tpl: str) -> bool:
    """poedb 표에서 두 줄이 붙어 버린 항목을 버린다.

    예: "명중 시 %1%의 확률로 적 실명 유발local display socketed gems ... 장착된 젬에 20레벨 실명 보조 보조 효과 적용"
    이런 문자열은 게임/PoB 에 존재하는 한 줄 문장이 아니고, poedb 가 렌더링할 때마다 예시 레벨이
    달라져 사전이 매번 바뀐다. (사용되지 않는 키이므로 버려도 표시에는 영향이 없다)
    """
    return "보조 보조" in kr_tpl


NUM_TOKEN_RE = re.compile(r"[+-]?\(?\d+(?:\.\d+)?(?:-\d+(?:\.\d+)?)?\)?")


def _dash(s: str) -> str:
    return s.replace("\u2014", "-").replace("\u2013", "-")


def split_segments(raw: str) -> list[tuple[str, str]]:
    """Split poedb mod HTML into [('t', text), ('v', value)] segments."""
    raw = raw.replace('<span class="ndash">\u2014</span>', "\u2014")
    parts = re.split(r"(<span class='mod-value'>.*?</span>)", raw, flags=re.S)
    segs: list[tuple[str, str]] = []
    for p in parts:
        if not p:
            continue
        m = re.fullmatch(r"<span class='mod-value'>(.*?)</span>", p, flags=re.S)
        if m:
            segs.append(("v", strip_tags(m.group(1))))
        else:
            segs.append(("t", strip_tags(p)))
    return segs


def shape(text: str) -> str:
    """Canonical lookup key: numbers (with sign/parens/ranges) become '#', 'X to Y' becomes 'X-Y'."""
    s = _dash(text)
    s = re.sub(r"(?<=\d)\s+to\s+(?=\d)", "-", s)
    out = []
    i, n = 0, len(s)
    while i < n:
        m = NUM_TOKEN_RE.match(s, i)
        if m and m.end() > i:
            out.append("#")
            i = m.end()
            continue
        out.append(s[i])
        i += 1
    return "".join(out).replace(" ", "").replace("\u00a0", "")


def extract_mods_view(path: str):
    raw = fetch(path if path.startswith("http") else "https://poedb.tw/" + path)
    m = re.search(r"new ModsView\(", raw)
    if not m:
        return None, raw
    i = raw.find("{", m.end())
    depth = 0
    instr = esc = False
    for j in range(i, len(raw)):
        c = raw[j]
        if instr:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                instr = False
            continue
        if c == '"':
            instr = True
        elif c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return json.loads(raw[i:j + 1]), raw
    return None, raw


def flatten_mods(data: dict) -> list[dict]:
    out = []
    for key, val in data.items():
        if key in ("baseitem", "config", "gen", "opt"):
            continue
        entries = []
        if isinstance(val, list):
            entries = val
        elif isinstance(val, dict):
            for sub in val.values():
                if isinstance(sub, list):
                    entries.extend(sub)
                elif isinstance(sub, dict) and "str" in sub:
                    entries.append(sub)
        for e in entries:
            if isinstance(e, dict) and e.get("str"):
                out.append(e)
    return out


def mod_key(e: dict) -> str | None:
    hover = e.get("hover")
    if not hover:
        return None
    q = urllib.parse.parse_qs(hover.lstrip("?"))
    val = q.get("s", [""])[0]
    return urllib.parse.unquote(val)


def build_class(cls: str, mods: dict, uniques: dict, bases: dict, stats: dict) -> None:
    us, raw_us = extract_mods_view(f"us/{cls}")
    kr, raw_kr = extract_mods_view(f"kr/{cls}")
    if not us or not kr:
        print("  %-24s no ModsView" % cls)
        return
    us_by_key = {mod_key(e): e for e in flatten_mods(us) if mod_key(e)}
    kr_by_key = {mod_key(e): e for e in flatten_mods(kr) if mod_key(e)}
    common = set(us_by_key) & set(kr_by_key)
    added = 0
    for k in common:
        e_us, e_kr = us_by_key[k], kr_by_key[k]
        su = split_segments(e_us["str"])
        sk = split_segments(e_kr["str"])
        us_slots = [v for t, v in su if t == "v"]
        kr_slots = [v for t, v in sk if t == "v"]
        if len(us_slots) != len(kr_slots) or not us_slots:
            continue
        # map each korean slot to the english slot with the same roll text
        mapping = {}
        used = set()
        for i, kv in enumerate(kr_slots):
            target = None
            for j, uv in enumerate(us_slots):
                if j in used:
                    continue
                if _dash(uv) == _dash(kv):
                    target = j
                    used.add(j)
                    break
            mapping[i] = target
        if any(t is None for t in mapping.values()):
            continue
        en_tpl = "".join(v for _, v in su)
        key = shape(en_tpl)
        if "#" not in key:
            continue
        kr_tpl_parts = []
        vi = 0
        for t, v in sk:
            if t == "v":
                kr_tpl_parts.append("%%%d" % (mapping[vi] + 1))
                vi += 1
            else:
                kr_tpl_parts.append(v)
        kr_tpl = norm_space("".join(kr_tpl_parts))
        if not kr_tpl or is_merged_noise(kr_tpl):
            continue
        prev = mods.get(key)
        if prev and prev["kr"] != kr_tpl:
            stats["mod_conflicts"].setdefault(key, set()).add(prev["kr"])
            stats["mod_conflicts"][key].add(kr_tpl)
            continue
        mods[key] = {"kr": kr_tpl, "n": len(kr_slots)}
        added += 1
    # uniques + base types on the class page
    u_add = b_add = 0
    for raw_us, raw_kr in ((raw_us, raw_kr),):
        rx = re.compile(
            r'<a class="UniqueItem"[^>]*href="/us/([^"]+)"[^>]*>\s*<span class="uniqueName">(.*?)</span>\s*'
            r'<span class="uniqueTypeLine">(.*?)</span>', re.S)
        us_items = {s: (strip_tags(n).strip(), strip_tags(t).strip()) for s, n, t in rx.findall(raw_us)}
        rx_kr = re.compile(
            r'<a class="UniqueItem"[^>]*href="/kr/([^"]+)"[^>]*>\s*<span class="uniqueName">(.*?)</span>\s*'
            r'<span class="uniqueTypeLine">(.*?)</span>', re.S)
        kr_items = {s: (strip_tags(n).strip(), strip_tags(t).strip()) for s, n, t in rx_kr.findall(raw_kr)}
        for slug in sorted(set(us_items) & set(kr_items)):
            en_name, en_base = us_items[slug]
            kr_name, kr_base = kr_items[slug]
            if en_name and kr_name and en_name not in uniques:
                uniques[en_name] = kr_name
                u_add += 1
            if en_base and kr_base and en_base not in bases:
                bases[en_base] = kr_base
                b_add += 1
    # base item types listed on the class page (.whiteitem anchors)
    rx_base = re.compile(r'<a class="whiteitem[^"]*"[^>]*href="([^"]+)">([^<]+)</a>')
    us_b = {h: strip_tags(n).strip() for h, n in rx_base.findall(raw_us)}
    kr_b = {h: strip_tags(n).strip() for h, n in rx_base.findall(raw_kr)}
    for slug in sorted(set(us_b) & set(kr_b)):
        en_name, kr_name = us_b[slug], kr_b[slug]
        if en_name and kr_name and en_name not in bases:
            bases[en_name] = kr_name
            b_add += 1
    stats["classes"].append({"class": cls, "mods": added, "uniques": u_add, "bases": b_add})
    print("  %-26s mods +%-5d uniques +%-4d bases +%d" % (cls, added, u_add, b_add))


UNIQUE_SPLIT_RE = re.compile(r'<a class="UniqueItem"[^>]*href="/(?:us|kr)/([^"]+)"')
MOD_DIV_RE = re.compile(r'<div class="(?:implicitMod|explicitMod)">(.*?)</div>', re.S)


def unique_mods(raw: str) -> dict[str, list[str]]:
    """slug -> ordered list of mod html strings, from an item-class page."""
    out: dict[str, list[str]] = {}
    parts = UNIQUE_SPLIT_RE.split(raw)
    # parts = [prefix, slug1, body1, slug2, body2, ...]
    for i in range(1, len(parts) - 1, 2):
        slug, body = parts[i], parts[i + 1]
        mods = MOD_DIV_RE.findall(body.split('<div class="col">')[0])
        if mods and slug not in out:
            out[slug] = mods
    return out


def add_unique_mods(cls: str, mods: dict, stats: dict) -> int:
    us = fetch("https://poedb.tw/us/" + cls)
    kr = fetch("https://poedb.tw/kr/" + cls)
    u_us, u_kr = unique_mods(us), unique_mods(kr)
    added = 0
    for slug in sorted(set(u_us) & set(u_kr)):
        a, b = u_us[slug], u_kr[slug]
        if len(a) != len(b) or slug in stats.setdefault("unique_mod_slugs", []):
            continue
        stats["unique_mod_slugs"].append(slug)
        for en_html, kr_html in zip(a, b):
            segs_en = split_segments(en_html)
            segs_kr = split_segments(kr_html)
            us_slots = [v for t, v in segs_en if t == "v"]
            kr_slots = [v for t, v in segs_kr if t == "v"]
            if len(us_slots) != len(kr_slots) or not us_slots:
                continue
            mapping, used = {}, set()
            for i, kv in enumerate(kr_slots):
                for j, uv in enumerate(us_slots):
                    if j in used:
                        continue
                    if _dash(uv) == _dash(kv):
                        mapping[i] = j
                        used.add(j)
                        break
            if len(mapping) != len(kr_slots):
                continue
            en_tpl = "".join(v for _, v in segs_en)
            key = shape(en_tpl)
            if "#" not in key:
                continue
            parts = []
            vi = 0
            for t, v in segs_kr:
                if t == "v":
                    parts.append("%%%d" % (mapping[vi] + 1))
                    vi += 1
                else:
                    parts.append(v)
            kr_tpl = norm_space("".join(parts))
            if kr_tpl and not is_merged_noise(kr_tpl) and key not in mods:
                mods[key] = {"kr": kr_tpl, "n": len(kr_slots)}
                added += 1
    return added


def main() -> None:
    mods, uniques, bases = {}, {}, {}
    stats = {"mod_conflicts": {}, "classes": []}
    for cls in CLASSES:
        before = len(mods)
        build_class(cls, mods, uniques, bases, stats)
        added = add_unique_mods(cls, mods, stats)
        if added:
            print("    + unique mods %-22s %d (total %d)" % (cls, added, len(mods) - before))
    stats["mod_conflicts"] = {k: sorted(v) for k, v in stats["mod_conflicts"].items()}
    stats["unique_mod_slugs"] = sorted(set(stats.get("unique_mod_slugs", [])))
    save_json("mods_exact.json", mods)
    save_json("uniques.json", uniques)
    save_json("bases.json", bases)
    save_json("items_stats.json", stats)
    print("TOTAL mods=%d uniques=%d bases=%d conflicts=%d" % (
        len(mods), len(uniques), len(bases), len(stats["mod_conflicts"])))


if __name__ == "__main__":
    main()
