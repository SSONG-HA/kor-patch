"""PoE2 한글 패처 자체 검증.

1) Lua 문법 검사 (src/KR2)
2) 숫자 정규화 규칙(파이썬 shape vs shape.lua) 일치
3) 폰트 아틀라스 ↔ metrics.lua 정합성 (v1.1.2 때 한글이 깨진 원인 재발 방지)
4) 사전 커버리지 (트리·젬·아이템·UI)
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

from common import DATA, POB2, SRC, load_json, load_lua_table, lua_to_py, shape as py_shape  # noqa: E402

FAILS = []


def check(name, ok, detail=""):
    print("%-54s %s %s" % (name, "OK " if ok else "FAIL", detail))
    if not ok:
        FAILS.append(name)


def syntax_checks():
    lua = LuaRuntime(unpack_returned_tuples=True, encoding="utf-8")
    files = sorted(glob.glob(os.path.join(SRC, "**", "*.lua"), recursive=True))
    bad = []
    for f in files:
        res = lua.execute("local f, err = loadfile(%r); if f then return true else return err end" % f)
        if res is not True:
            bad.append((os.path.basename(f), res))
    check("Lua 문법 검사 (%d개 파일)" % len(files), not bad, str(bad[:3]))


def shape_parity():
    lua = LuaRuntime(unpack_returned_tuples=True, encoding="utf-8")
    lua.execute("SHAPE = dofile(%r)" % os.path.join(SRC, "shape.lua"))
    samples = []
    for name in ("mods_exact.json",):
        if os.path.exists(os.path.join(DATA, name)):
            samples.extend(json.load(open(os.path.join(DATA, name), encoding="utf-8")).keys())
    samples += [
        "+35% to Fire Resistance", "Adds 10 to 20 Fire Damage", "(25-35)% increased Cold Damage",
        "Adds 1,234 to 5,678 Fire Damage", "-1,174 Effective Hit Pool (-6.7%)",
        "+73,867.1 Hit DPS (+0.8%)", "Requires Level 79, 163 Dex", "Sockets: S S",
        "Tier: 1", "Level: 20 (Max)", "Removing this item from Weapon 1 will give you:",
    ]
    lua_shape = lua.eval("function(x) local k = SHAPE.shape(x); return k end")
    bad = []
    for s in samples:
        if py_shape(s) != lua_shape(s):
            bad.append((s, py_shape(s), lua_shape(s)))
    check("숫자 정규화 규칙 일치 (%d개 표본)" % len(samples), not bad, str(bad[:2]))


def font_metrics():
    from PIL import Image

    import bake_font

    fonts = os.path.join(SRC, "Fonts")
    path = os.path.join(fonts, "metrics.lua")
    if not os.path.exists(path):
        check("폰트 메트릭 파일 존재", False, path)
        return
    lua = LuaRuntime(unpack_returned_tuples=True, encoding="utf-8")
    metrics = lua.eval("function(p) return dofile(p) end")(path)

    def as_list(tbl):
        return [tbl[i] for i in range(1, len(tbl) + 1)] if tbl is not None else []

    codes = [int(c) for c in as_list(metrics["codes"])]
    want = {ord(ch) for ch in bake_font.used_chars()}
    have = set(codes)
    check("metrics 글자 수 == 사전 글자 수 (%d)" % len(want), len(codes) == len(want) and have == want,
          "metrics %d / 사전 %d, 빠짐 %d, 남음 %d" % (len(codes), len(want), len(want - have), len(have - want)))
    check("metrics codes 정렬", codes == sorted(codes))

    sizes = as_list(metrics["sizes"])
    check("아틀라스 크기 종류", len(sizes) > 0, "%d종" % len(sizes))
    problems = []
    for defn in sizes:
        png = str(defn["png"])
        adv = as_list(defn["adv"])
        target = os.path.join(fonts, png)
        if not os.path.exists(target):
            problems.append("%s 없음" % png)
            continue
        with Image.open(target) as im:
            actual = im.size
        expect = (int(defn["w"]), int(defn["h"]))
        if actual != expect:
            problems.append("%s 크기 %s != metrics %s" % (png, actual, expect))
        if len(adv) != len(codes):
            problems.append("%s adv %d개 != 글자 %d개" % (png, len(adv), len(codes)))
        if not (0 < int(defn["base"]) <= int(defn["ch"])):
            problems.append("%s baseline 이상" % png)
    check("아틀라스 PNG == metrics (%d종)" % len(sizes), not problems, str(problems[:3]))

    full = metrics["full"]
    target = os.path.join(fonts, str(full["png"])) if full else None
    if not full or not os.path.exists(target or ""):
        check("폴백 아틀라스", False)
        return
    with Image.open(target) as im:
        actual = im.size
    ok = actual == (int(full["w"]), int(full["h"])) and len(as_list(full["adv"])) == int(full["count"])
    check("폴백 아틀라스 (한글 음절 %d자)" % int(full["count"]), ok)


def coverage():
    def hit_factory():
        lua = LuaRuntime(unpack_returned_tuples=True, encoding="utf-8")
        lua.execute("SHAPE = dofile(%r)" % os.path.join(SRC, "shape.lua"))
        exact = lua.eval("function(p) return dofile(p) end")(os.path.join(SRC, "Data", "exact.lua"))
        templates = lua.eval("function(p) return dofile(p) end")(os.path.join(SRC, "Data", "templates.lua"))
        shape = lua.eval("function(x) return (SHAPE.shape(x)) end")

        def hit(text):
            if not text:
                return False
            if exact[text] is not None or exact[text.rstrip()] is not None:
                return True
            return templates[shape(text)] is not None

        return hit

    hit = hit_factory()
    tree_path = os.path.join(POB2, "TreeData", "0_5", "tree.lua")
    if os.path.exists(tree_path):
        nodes = lua_to_py(load_lua_table(tree_path))["nodes"]
        names, lines = set(), set()
        for node in nodes.values():
            if not isinstance(node, dict):
                continue
            if node.get("name"):
                names.add(" ".join(str(node["name"]).split()))
            for s in node.get("stats") or []:
                for piece in str(s).split("\n"):
                    if piece.strip():
                        lines.add(" ".join(piece.split()))
        gn = sum(1 for n in names if hit(n))
        gl = sum(1 for line in lines if hit(line))
        check("트리 노드 이름 번역률", gn / max(1, len(names)) >= 0.98,
              "%d/%d (%.1f%%)" % (gn, len(names), 100.0 * gn / max(1, len(names))))
        check("트리 효과 문구 번역률", gl / max(1, len(lines)) >= 0.95,
              "%d/%d (%.1f%%)" % (gl, len(lines), 100.0 * gl / max(1, len(lines))))
    else:
        print("   (PoB2 트리 데이터가 없어 트리 커버리지 생략: %s)" % tree_path)

    gems_path = os.path.join(POB2, "Data", "Gems.lua")
    if os.path.exists(gems_path):
        gems = lua_to_py(load_lua_table(gems_path))
        names = {v["name"] for v in gems.values() if isinstance(v, dict) and v.get("name")}
        g = sum(1 for n in names if hit(n))
        check("젬 이름 번역률", g / max(1, len(names)) >= 0.95,
              "%d/%d (%.1f%%)" % (g, len(names), 100.0 * g / max(1, len(names))))

    for label, name in (("베이스 아이템", "bases.json"), ("유니크 아이템", "uniques.json")):
        path = os.path.join(DATA, name)
        if os.path.exists(path):
            data = load_json(name)
            print("   %-12s %d개" % (label, len(data)))


def main() -> int:
    syntax_checks()
    shape_parity()
    font_metrics()
    coverage()
    print()
    if FAILS:
        print("실패:", FAILS)
        return 1
    print("모든 검사 통과")
    return 0


if __name__ == "__main__":
    sys.exit(main())
