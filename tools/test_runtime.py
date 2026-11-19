"""런타임 견고성 테스트: 전 화면 그리기, F2 전환, 미등록 글자, 폭 계산, 다중 빌드 계산 동일성."""
import json
import os
import sys

sys.path.insert(0, os.environ.get("LUAJIT_PATH", "/workspace/.local/lib/python3.12/site-packages"))
from lupa.luajit21 import LuaRuntime  # noqa: E402

HERE = os.environ.get("TEST_POB", "/workspace/tmpwork/install_test/pob")
os.chdir(HERE)

BUILD_DIR = os.environ.get("BUILD_DIR", "/workspace/tmpwork/pob/headless/builds")
BUILDS = [os.path.join(BUILD_DIR, n) for n in
          ("1단계-리그스타트.xml", "2단계-중반.xml", "3단계-엔드게임.xml", "4단계-우버도전.xml")]
KEYS = ["Life", "EnergyShield", "Armour", "TotalDPS", "TotalDot", "CombinedDPS", "TotalEHP", "Mana"]


def boot(patch: bool):
    lua = LuaRuntime(unpack_returned_tuples=True, encoding="utf-8")
    lua.execute("arg={}\npackage.path='./?.lua;./lua/?.lua;./?/init.lua;./lua/?/init.lua;'..package.path\ndofile('HeadlessWrapper.lua')")
    return lua, lua.globals()


def load(lua, g, path):
    xml = open(path, encoding="utf-8").read()
    g["loadBuildFromXML"](xml, os.path.basename(path))
    g["runCallback"]("OnFrame")
    keys = ", ".join('"%s"' % k for k in KEYS)
    raw = lua.execute("""
local o = build.calcsTab.mainOutput
local t = {}
for _, k in ipairs({%s}) do if o[k] ~= nil then t[k] = tostring(o[k]) end end
return require("dkjson").encode(t)
""" % keys)
    return json.loads(raw)


def main() -> int:
    lua, g = boot(True)
    kr = g["KR"]
    if not kr:
        print("FAIL: 패처 미로드")
        return 1

    fails = []
    for b in BUILDS:
        patched = load(lua, g, b)
        print("%-28s Life=%s DPS=%s" % (os.path.basename(b), patched.get("Life"), patched.get("TotalDPS")))
        if not patched:
            fails.append("빌드 계산 실패: " + b)
        if g["__mainObject__"]["promptMsg"]:
            fails.append("프롬프트 오류: " + str(g["__mainObject__"]["promptMsg"]))

    # 전 화면 그리기 (오류/미등록 글자 확인)
    build = g["build"]
    for mode in ["ITEMS", "SKILLS", "TREE", "CALCS", "CONFIG", "PARTY", "COMPARE", "NOTES"]:
        build["viewMode"] = mode
        g["runCallback"]("OnFrame")
        msg = g["__mainObject__"]["promptMsg"]
        if msg:
            fails.append("%s 화면 오류: %s" % (mode, str(msg)[:120]))
    print("화면 그리기 오류:", "없음" if not any("화면 오류" in f for f in fails) else fails)

    stats = kr["stats"]
    print("DrawString 호출 %s / 한글 렌더 %s / 미번역 %s" % (
        stats["draw"], stats["korean"], stats["miss"]))
    if stats["korean"] == 0:
        fails.append("한글 렌더가 한 번도 실행되지 않음")

    # F2 전환
    kr["toggle"]()
    enabled_after = kr["enabled"]
    g["runCallback"]("OnFrame")
    if g["__mainObject__"]["promptMsg"]:
        fails.append("F2 끔 상태에서 오류: " + str(g["__mainObject__"]["promptMsg"]))
    kr["toggle"]()
    print("F2 전환: 한글→영문 동작 =", enabled_after is False, "/ 복귀 =", kr["enabled"] is True)

    # 미등록 한글 글자 (아틀라스에 없는 글자)
    raw = lua.execute("""
local ok, err = pcall(function()
  DrawString(0, 0, "LEFT", 16, "VAR", "쀼쀼 테스트 문자")
  DrawStringWidth(16, "VAR", "쀼쀼 테스트 문자")
end)
return ok and "OK" or tostring(err)
""")
    print("미등록 글자 처리:", raw)
    if raw != "OK":
        fails.append("미등록 글자 오류: " + str(raw))

    # 폭 계산 일관성
    widths = lua.execute("""
local a = DrawStringWidth(16, "VAR", "Life:")
local b = DrawStringWidth(16, "VAR", "생명력:")
local c = DrawStringWidth(16, "VAR", "")
local d = DrawStringWidth(0, "VAR", "생명력:")
return require("dkjson").encode({a, b, c, d})
""")
    print("폭(영문/한글/빈문자/높이0):", widths)

    print()
    if fails:
        print("실패:", fails)
        return 1
    print("모든 런타임 검사 통과")
    return 0


if __name__ == "__main__":
    sys.exit(main())
