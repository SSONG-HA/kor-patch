"""계산 동일성 검증: '패치 안 한 PoB' 와 '패치한 PoB' 를 각각 띄워 수치를 비교한다.

- 원본: 로더가 없는 깨끗한 사본
- 패치본: 실제 설치 흐름으로 KR + 로더를 넣은 사본
"""
from __future__ import annotations

import json
import os
import shutil
import sys

sys.path.insert(0, os.environ.get("LUAJIT_PATH", "/workspace/.local/lib/python3.12/site-packages"))
from lupa.luajit21 import LuaRuntime  # noqa: E402

WS = os.environ.get("WORKSPACE", "/workspace")
PATCHED = os.path.join(WS, "tmpwork", "install_test", "pob")
PRISTINE = os.path.join(WS, "tmpwork", "pristine")
BUILD_DIR = os.path.join(WS, "tmpwork", "pob", "headless", "builds")
BUILDS = ["1단계-리그스타트.xml", "2단계-중반.xml", "3단계-엔드게임.xml", "4단계-우버도전.xml"]
KEYS = ["Life", "LifeUnreserved", "EnergyShield", "Ward", "Armour", "Evasion", "Mana",
        "ManaUnreserved", "TotalDPS", "TotalDot", "CombinedDPS", "FullDPS", "TotalEHP",
        "AverageHit", "Speed", "CritChance", "CritMultiplier", "PhysicalMaximumHitTaken",
        "ElementalMaximumHitTaken", "TotalIncrease", "TotalMore"]

MARK = "-- [PoB-KR]"


def make_pristine():
    if os.path.exists(PRISTINE):
        shutil.rmtree(PRISTINE)
    shutil.copytree(PATCHED, PRISTINE,
                    ignore=shutil.ignore_patterns("KR", "builds", "__pycache__"))
    main = os.path.join(PRISTINE, "Modules", "Main.lua")
    text = open(main, encoding="utf-8").read()
    lines = text.split("\n")
    keep = [l for l in lines if not l.startswith(MARK) and "KR_ROOT" not in l]
    open(main, "w", encoding="utf-8", newline="").write("\n".join(keep))


def boot_and_measure(cwd: str):
    os.chdir(cwd)
    lua = LuaRuntime(unpack_returned_tuples=True, encoding="utf-8")
    lua.execute("arg={}\npackage.path='./?.lua;./lua/?.lua;./?/init.lua;./lua/?/init.lua;'..package.path\n"
                "dofile('HeadlessWrapper.lua')")
    g = lua.globals()
    patched = g["KR"] is not None
    keys = ", ".join('"%s"' % k for k in KEYS)
    out = {}
    for b in BUILDS:
        xml = open(os.path.join(BUILD_DIR, b), encoding="utf-8").read()
        g["loadBuildFromXML"](xml, b)
        g["runCallback"]("OnFrame")
        raw = lua.execute("""
local o = build.calcsTab.mainOutput
local t = {}
for _, k in ipairs({%s}) do if o[k] ~= nil then t[k] = tostring(o[k]) end end
return require("dkjson").encode(t)
""" % keys)
        out[b] = json.loads(raw)
        if g["__mainObject__"]["promptMsg"]:
            out[b]["__err"] = str(g["__mainObject__"]["promptMsg"])
    return patched, out


def main() -> int:
    make_pristine()
    print("원본 PoB 실행 (로더 없음)...")
    p0, plain = boot_and_measure(PRISTINE)
    print("   패처 로드됨:", p0)
    print("패치본 PoB 실행...")
    p1, patched = boot_and_measure(PATCHED)
    print("   패처 로드됨:", p1)
    if p0 or not p1:
        print("!! 전제 오류: 원본/패치본이 뒤바뀌었습니다")
        return 1

    total = diffs = 0
    for b in BUILDS:
        d = {k: (plain[b].get(k), patched[b].get(k)) for k in set(plain[b]) | set(patched[b])
             if plain[b].get(k) != patched[b].get(k)}
        total += len(plain[b])
        diffs += len(d)
        print("%-24s 항목 %2d개 비교 → %s" % (b, len(plain[b]), "동일" if not d else "차이 " + str(d)))
        print("    Life=%s  ES=%s  Armour=%s  TotalDPS=%s  DoT=%s" % (
            plain[b].get("Life"), plain[b].get("EnergyShield"), plain[b].get("Armour"),
            plain[b].get("TotalDPS"), plain[b].get("TotalDot")))
    print("\n총 비교 항목: %d, 차이: %d" % (total, diffs))
    return 0 if diffs == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
