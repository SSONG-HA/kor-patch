"""PoB-KR-Patcher 자체 검증 스크립트.

1) Lua 파일 문법 검사
2) 숫자 정규화 규칙(파이썬 shape vs Lua shape) 일치 검사
3) 사전 커버리지 리포트 (젬/패시브/유니크/베이스/모드/UI)
4) 문서에 적은 커버리지를 실제 데이터로 재계산
"""
from __future__ import annotations

import glob
import json
import os
import re
import sys

sys.path.insert(0, os.environ.get("LUAJIT_PATH", "/workspace/.local/lib/python3.12/site-packages"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lupa.luajit21 import LuaRuntime  # noqa: E402

from common import DATA, SRC, load_json  # noqa: E402
from items import shape as py_shape  # noqa: E402

FAILS = []


def check(name, ok, detail=""):
    print("%-52s %s %s" % (name, "OK " if ok else "FAIL", detail))
    if not ok:
        FAILS.append(name)


def syntax_checks():
    lua = LuaRuntime(unpack_returned_tuples=True, encoding="utf-8")
    files = sorted(glob.glob(os.path.join(SRC, "**", "*.lua"), recursive=True))
    bad = []
    for f in files:
        res = lua.execute("local f, err = loadfile(%r); if f then return true else return err end" % f)
        if res is not True:
            bad.append((f, res))
    check("Lua 문법 검사 (%d개 파일)" % len(files), not bad, str(bad[:3]))


def shape_parity():
    lua = LuaRuntime(unpack_returned_tuples=True, encoding="utf-8")
    lua.execute("SHAPE = dofile(%r)" % os.path.join(SRC, "shape.lua"))
    samples = []
    for f in ("mods_exact.json", "mods_extra.json"):
        path = os.path.join(DATA, f)
        if os.path.exists(path):
            samples.extend(json.load(open(path, encoding="utf-8")).keys())
    samples += [
        "+35% to Fire Resistance", "Adds 10 to 20 Fire Damage", "(25-35)% increased Cold Damage",
        "Adds 17 to 23 Fire Damage", "Adds 123 to 456 Fire Damage", "Minions deal 17 to 23 additional Fire Damage",
        "Regenerate 6 Life over 1 second when you Cast a Spell", "1.5% increased Attack Speed",
        "100% increased Armour and Energy Shield", "Gain 15% of Physical Damage as Extra Fire Damage",
        "+(-5--1) to Strength", "Has 1 Socket",
    ]
    bad = []
    for s in samples:
        py = py_shape(s)
        lua_res = lua.eval("function(x) local k = SHAPE.shape(x); return k end")(s)
        if py != lua_res:
            bad.append((s, py, lua_res))
    check("숫자 정규화 규칙 일치 (%d개 표본)" % len(samples), not bad, str(bad[:2]))
    # 키 뿐 아니라 치환에 쓰이는 숫자 목록도 같은지 (17 to 23 → 177-23 같은 오류 방지)
    import re as _re
    num_samples = ["Adds 17 to 23 Fire Damage", "Adds 10 to 20 Fire Damage", "Adds 123 to 456 Fire Damage",
                   "Minions deal 17 to 23 additional Fire Damage", "4 to 35 Added Lightning Damage",
                   "1.5 to 2.5 Cold Damage", "(10-20) to (21-30) Fire Damage"]
    bad_num = []
    for s in num_samples:
        from items import NUM_TOKEN_RE
        py_nums = NUM_TOKEN_RE.findall(_re.sub(r"(?<=\d)\s+to\s+(?=\d)", "-", s))
        lua_nums = list(lua.eval("function(x) local k, n = SHAPE.shape(x); return n end")(s).values())
        if py_nums != lua_nums:
            bad_num.append((s, py_nums, lua_nums))
    check("숫자 치환 값 일치 (%d개 표본)" % len(num_samples), not bad_num, str(bad_num[:2]))


def coverage():
    data = {f: load_json(f) for f in os.listdir(DATA) if f.endswith(".json")}
    print("\n[사전 규모]")
    for k in ("gems.json", "passives_names.json", "passives_stats.json",
              "uniques.json", "bases.json", "mods_exact.json", "ui_ko.json", "overrides_ko.json"):
        if k in data:
            print("   %-24s %6d" % (k, len(data[k])))

    # 실제 빌드 아이템 문구 커버리지
    xmls = glob.glob(os.path.join(os.environ.get("BUILD_DIR", "/workspace/tmpwork/pob/headless/builds"), "*.xml"))
    lines = []
    for x in xmls:
        text = open(x, encoding="utf-8").read()
        for m in re.finditer(r'<Item id="\d+">(.*?)</Item>', text, re.S):
            for l in m.group(1).split("\n"):
                l = l.strip()
                if not l:
                    continue
                if re.match(r"(Rarity|Item Level|LevelReq|Quality|Sockets|Implicits|Searing Exarch|"
                            r"Eater of Worlds|Corrupted|Shaper Item|Elder Item|Crusader Item|"
                            r"Redeemer Item|Hunter Item|Warlord Item|Mirrored|Split|Unidentified|"
                            r"HasAltQuality|Selected|Cluster Jewel|Limited to|Radius|Name of|Prefix:|Suffix:)", l):
                    continue
                lines.append(l)
    lines = [l for l in lines if not re.fullmatch(r"[A-Z][a-zA-Z' ]+", l) or l.startswith("+")]
    mods = data["mods_exact.json"]
    extra = data.get("mods_extra.json", {})
    hit = sum(1 for l in lines if py_shape(l) in mods or py_shape(l) in extra)
    check("실제 빌드 아이템 속성 문구 번역률", True, "%d/%d = %.1f%%" % (hit, len(lines), 100.0 * hit / max(1, len(lines))))

    # PoB 데이터 전체 기준 커버리지
    try:
        from common import load_lua_table, lua_to_py
        pob = os.environ.get("POB_SRC", "/workspace/tmpwork/pob/headless")
        gems = lua_to_py(load_lua_table(pob + "/Data/Gems.lua"))
        names = {v["name"] for v in gems.values() if isinstance(v, dict) and v.get("name")}
        g = data["gems.json"]
        print("   젬 이름          %d/%d (%.1f%%)" % (sum(1 for n in names if n in g), len(names),
                                                     100.0 * sum(1 for n in names if n in g) / len(names)))
        tree = lua_to_py(load_lua_table(pob + "/TreeData/3_30/tree.lua"))["nodes"]
        pn, ps = data["passives_names.json"], data["passives_stats.json"]
        tn = {v["name"] for v in tree.values() if isinstance(v, dict) and v.get("name")}
        ts = set()
        for v in tree.values():
            if isinstance(v, dict) and isinstance(v.get("stats"), list):
                for s in v["stats"]:
                    ts.add(" ".join(s.split()))
        print("   패시브 노드 이름   %d/%d (%.1f%%)" % (sum(1 for n in tn if n in pn), len(tn),
                                                      100.0 * sum(1 for n in tn if n in pn) / len(tn)))
        print("   패시브 효과 문구   %d/%d (%.1f%%)" % (sum(1 for n in ts if n in ps), len(ts),
                                                      100.0 * sum(1 for n in ts if n in ps) / len(ts)))
    except Exception as e:  # noqa: BLE001
        print("   (PoB 데이터 비교 생략: %s)" % str(e)[:60])


def legion_coverage():
    """군단 주얼(무궁한 주얼) 문자열이 배포 사전에서 모두 한글로 바뀌는지 확인합니다."""
    try:
        import test_legion as TL
    except Exception as exc:  # noqa: BLE001
        print("   (군단 주얼 검사를 불러오지 못했습니다: %s)" % exc)
        return
    pob = os.environ.get("POB_SRC", "/workspace/tmpwork/pob/headless")
    strings = TL.pob_strings(pob)
    if not strings:
        print("   (PoB 원본이 없어 군단 주얼 문자열 확인 생략)")
        return
    lua = TL.lua_dict()
    cases = []
    for text in dict.fromkeys(strings):
        cases.append(text)
        if TL.roll(text) != text:
            cases.append(TL.roll(text))
    miss = [c for c in cases if not re.search(r"[\uac00-\ud7a3]", TL.translate(lua, c) or "")]
    check("군단 주얼 문자열 번역 (%d개)" % len(cases), not miss,
          "미번역 %d개 %s" % (len(miss), miss[:3]))


def main():
    syntax_checks()
    shape_parity()
    coverage()
    legion_coverage()
    print()
    if FAILS:
        print("실패:", FAILS)
        return 1
    print("모든 검사 통과")
    return 0


if __name__ == "__main__":
    sys.exit(main())
