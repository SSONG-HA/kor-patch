"""PoE2 아이템 사전 (poe2db 아이템 클래스 페이지: 베이스·유니크 이름 + 속성 문구).

각 아이템 클래스 페이지에는 `new ModsView({...})` JSON 이 들어 있어, 같은 클래스의
us/kr 페이지를 같은 순서로 짝지으면 속성 문구를 정확히 맞출 수 있습니다.
숫자(굴림값)가 양쪽에서 완전히 같을 때만 채택하므로 잘못 짝지을 위험이 낮습니다.

결과:
  data/mods_exact.json   {영문 템플릿(숫자→#): {"kr": 한글 템플릿(%1 %2), "n": 슬롯 수}}
  data/bases.json        {영문 베이스 이름: 한글}
  data/uniques.json      {영문 유니크 이름: 한글}
  data/items_report.json
"""
from __future__ import annotations

import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import (_dash, fetch, load_json, norm_space, save_json, shape,  # noqa: E402
                    strip_tags)

# PoE2 아이템 클래스 (poe2db 슬러그)
CLASSES = [
    "Claws", "Daggers", "Wands", "One_Hand_Swords", "One_Hand_Axes", "One_Hand_Maces",
    "Sceptres", "Spears", "Flails", "Bows", "Staves", "Two_Hand_Swords", "Two_Hand_Axes",
    "Two_Hand_Maces", "Quarterstaves", "Crossbows", "Traps", "Talismans",
    "Quivers", "Shields", "Bucklers", "Foci",
    "Gloves", "Boots", "Body_Armours", "Helmets",
    "Amulets", "Rings", "Belts",
    "Life_Flasks", "Mana_Flasks", "Charms",
    "Jewels", "Augment",
]

SKIP_GROUPS = ("baseitem", "config", "gen", "opt")


def extract_mods_view(raw: str):
    m = re.search(r"new ModsView\(", raw)
    if not m:
        return None
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
                return json.loads(raw[i:j + 1])
    return None


def flatten_mods(data: dict) -> list[tuple[str, dict]]:
    out = []
    for key, val in data.items():
        if key in SKIP_GROUPS:
            continue
        entries = []
        if isinstance(val, list):
            entries = [(key, e) for e in val]
        elif isinstance(val, dict):
            for sub_key, sub in val.items():
                if isinstance(sub, list):
                    entries += [(key + "/" + sub_key, e) for e in sub]
                elif isinstance(sub, dict) and "str" in sub:
                    entries.append((key, sub))
        for group, e in entries:
            if isinstance(e, dict) and e.get("str"):
                out.append((group, e))
    return out


VALUE_RE = re.compile(r"<span class='mod-value'>(.*?)</span>", re.S)


def split_segments(raw: str) -> list[tuple[str, str]]:
    raw = raw.replace('<span class="ndash">\u2014</span>', "\u2014")
    raw = raw.replace('<span class="ndash">-</span>', "-")
    parts = re.split(r"(<span class='mod-value'>.*?</span>)", raw, flags=re.S)
    segs: list[tuple[str, str]] = []
    for p in parts:
        if not p:
            continue
        m = re.fullmatch(r"<span class='mod-value'>(.*?)</span>", p, flags=re.S)
        if m:
            segs.append(("v", strip_tags(m.group(1)).strip()))
        else:
            segs.append(("t", strip_tags(p)))
    return segs


def build_static(en_segs, kr_segs) -> tuple[str, str] | None:
    """숫자가 없는 줄(예: "Upgrades a socketed Rune")은 그대로 1:1 사전에 넣는다."""
    if any(t == "v" for t, _ in en_segs) or any(t == "v" for t, _ in kr_segs):
        return None
    en = norm_space("".join(v for _, v in en_segs))
    kr = norm_space("".join(v for _, v in kr_segs))
    if not en or not kr or not re.search(r"[\uac00-\ud7a3]", kr):
        return None
    if len(en) > 120:
        return None
    return en, kr


def build_template(en_segs, kr_segs) -> tuple[str, str] | None:
    en_vals = [v for t, v in en_segs if t == "v"]
    kr_vals = [v for t, v in kr_segs if t == "v"]
    if not en_vals or len(en_vals) != len(kr_vals):
        return None
    mapping: dict[int, int] = {}
    used: set[int] = set()
    for i, kv in enumerate(kr_vals):
        for j, uv in enumerate(en_vals):
            if j in used:
                continue
            if _dash(uv) == _dash(kv):
                mapping[i] = j
                used.add(j)
                break
    if len(mapping) != len(kr_vals):
        return None
    en_tpl = "".join(v for _, v in en_segs)
    key = shape(en_tpl)
    if "#" not in key:
        return None
    parts = []
    vi = 0
    for t, v in kr_segs:
        if t == "v":
            parts.append("%%%d" % (mapping[vi] + 1))
            vi += 1
        else:
            parts.append(v)
    kr_tpl = norm_space("".join(parts))
    if not kr_tpl or not re.search(r"[\uac00-\ud7a3]", kr_tpl):
        return None
    return key, kr_tpl


BASE_RE = re.compile(r'<a class="whiteitem[^"]*"[^>]*href="([^"]+)">([^<]+)</a>')
MOD_DIV_RE = re.compile(r'<div class="(?:implicitMod|explicitMod)">(.*?)</div>', re.S)


def unique_mod_blocks(raw: str) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    parts = re.split(r'<a class="UniqueItem"[^>]*href="/(?:us|kr)/([^"]+)"', raw)
    for i in range(1, len(parts) - 1, 2):
        slug, body = parts[i], parts[i + 1]
        mods = MOD_DIV_RE.findall(body.split('<div class="col">')[0])
        if mods and slug not in out:
            out[slug] = mods
    return out


def main() -> None:
    mods: dict[str, dict] = {}
    statics: dict[str, str] = {}
    extra: dict[str, str] = {}
    bases: dict[str, str] = {}
    uniques: dict[str, str] = {}
    report = {"classes": [], "conflicts": {}}

    existing_extra = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                  "data", "mods_extra.json")

    for cls in CLASSES:
        try:
            raw_us = fetch("https://poe2db.tw/us/%s" % cls, "%s_us.html" % cls)
            raw_kr = fetch("https://poe2db.tw/kr/%s" % cls, "%s_kr.html" % cls)
        except Exception as e:  # noqa: BLE001
            print("  %-18s 실패: %s" % (cls, str(e)[:60]))
            continue

        # ---- 속성 문구
        added = 0
        us_data = extract_mods_view(raw_us)
        kr_data = extract_mods_view(raw_kr)
        if us_data and kr_data:
            fu, fk = flatten_mods(us_data), flatten_mods(kr_data)
            if len(fu) == len(fk):
                for (gu, eu), (gk, ek) in zip(fu, fk):
                    if gu != gk:
                        continue
                    se, sk = split_segments(eu["str"]), split_segments(ek["str"])
                    built = build_template(se, sk)
                    if not built:
                        static = build_static(se, sk)
                        if static and static[0] not in statics:
                            statics[static[0]] = static[1]
                        continue
                    key, kr_tpl = built
                    prev = mods.get(key)
                    if prev and prev["kr"] != kr_tpl:
                        report["conflicts"].setdefault(key, set()).add(prev["kr"])
                        report["conflicts"][key].add(kr_tpl)
                        continue
                    if not prev:
                        added += 1
                    mods[key] = {"kr": kr_tpl, "n": kr_tpl.count("%")}
            else:
                print("  %-18s 모드 개수 다름 us=%d kr=%d" % (cls, len(fu), len(fk)))

        # ---- 유니크 이름/베이스 + 유니크 전용 문구
        u_add = b_add = 0
        def uniques_of(raw: str, lang: str):
            return {s: (strip_tags(n).strip(), strip_tags(t).strip())
                    for s, n, t in re.findall(
                        r'<a class="UniqueItem"[^>]*href="/%s/([^"]+)"[^>]*>\s*'
                        r'<span class="uniqueName">(.*?)</span>\s*<span class="uniqueTypeLine">(.*?)</span>'
                        % lang, raw, flags=re.S)}

        un_us, un_kr = uniques_of(raw_us, "us"), uniques_of(raw_kr, "kr")
        for slug in sorted(set(un_us) & set(un_kr)):
            en_name, en_base = un_us[slug]
            kr_name, kr_base = un_kr[slug]
            if en_name and kr_name and en_name not in uniques:
                uniques[en_name] = kr_name
                u_add += 1
            if en_base and kr_base and en_base not in bases:
                bases[en_base] = kr_base
                b_add += 1

        us_mods = unique_mod_blocks(raw_us)
        kr_mods = unique_mod_blocks(raw_kr)
        for slug in sorted(set(us_mods) & set(kr_mods)):
            a, b = us_mods[slug], kr_mods[slug]
            if len(a) != len(b):
                continue
            for en_html, kr_html in zip(a, b):
                built = build_template(split_segments(en_html), split_segments(kr_html))
                if not built:
                    continue
                key, kr_tpl = built
                if key not in mods:
                    mods[key] = {"kr": kr_tpl, "n": kr_tpl.count("%")}
                    added += 1

        # ---- 베이스 이름
        def bases_of(raw: str) -> dict[str, str]:
            return {h: strip_tags(n).strip() for h, n in BASE_RE.findall(raw)}

        b_us, b_kr = bases_of(raw_us), bases_of(raw_kr)
        for slug in sorted(set(b_us) & set(b_kr)):
            en, kr = b_us[slug], b_kr[slug]
            if en and kr and en not in bases and re.search(r"[\uac00-\ud7a3]", kr):
                bases[en] = kr
                b_add += 1

        report["classes"].append({"class": cls, "mods": added, "uniques": u_add, "bases": b_add})
        print("  %-18s 모드 +%-4d 유니크 +%-3d 베이스 +%d" % (cls, added, u_add, b_add))

    if os.path.exists(existing_extra):
        extra = load_json("mods_extra.json")

    report["conflicts"] = {k: sorted(v) for k, v in report["conflicts"].items()}
    save_json("mods_exact.json", mods)
    save_json("mods_static.json", statics)
    save_json("bases.json", bases)
    save_json("uniques.json", uniques)
    save_json("items_report.json", report)
    print("합계: 모드 %d / 정적 문구 %d / 베이스 %d / 유니크 %d / 충돌 %d" % (
        len(mods), len(statics), len(bases), len(uniques), len(report["conflicts"])))


if __name__ == "__main__":
    main()
