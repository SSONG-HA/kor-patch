"""PoE2 런타임 검증 (헤드리스 PoB2).

1) 패처 로드 여부
2) 한글 켬/끔 상태의 계산값이 완전히 같은지 (엔진을 건드리지 않았다는 증거)
3) 모든 화면(아이템/스킬/트리/계산/설정/파티/비교/메모)을 오류 없이 그리는지
4) F2 한/영 전환
5) 사전 조회 표본 (노드·아이템·젬·비교 줄·태그)
6) 아틀라스에 없는 한글, 폭 계산

사용: TEST_POB=/path/to/pob2 python3 poe2/tools/test_runtime.py
"""
from __future__ import annotations

import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pob2_harness import boot, run_lua_to_json  # noqa: E402

TEST_POB = os.environ.get("TEST_POB", "/workspace/work/pob2test")
MODES = ["ITEMS", "SKILLS", "TREE", "CALCS", "CONFIG", "PARTY", "COMPARE", "NOTES"]

CALC_KEYS = ["Life", "Mana", "EnergyShield", "Armour", "Evasion", "TotalDPS", "CombinedDPS",
             "TotalEHP", "TotalDot", "Spirit", "AverageHit"]

PROBES = {
    "node": "Critical Chance",
    "node2": "+25 to Dexterity",
    "gem": "Lightning Arrow",
    "tag": "Projectile",
    "item": "Stellar Amulet",
    "diff": "+254 Effective Hit Pool (+0.3%)",
    "diffneg": "-1,174 Effective Hit Pool (-6.7%)",
    "property": "Physical Damage: 47-79 (75.6 DPS)",
    "require": "Requires Level 79, 163 Dex",
}


def main() -> int:
    from fixtures import builder_lua

    lua, g = boot(TEST_POB)
    lua.execute("print = function() end")
    if not g["KR"]:
        print("FAIL: 패처가 로드되지 않았습니다")
        return 1
    print("패처 로드:", dict(g["KR"]["counts"].items()))

    lua.execute(builder_lua() + "\n__kr_info = applyBuild(spec)")
    print("빌드:", json.dumps(dict(lua.globals()["__kr_info"].items())))

    fails = []

    def calcs(kr_enabled: bool):
        lua.execute("if KR.enabled ~= %s then KR.toggle() end" % ("true" if kr_enabled else "false"))
        lua.execute("build.buildFlag = true; runCallback('OnFrame')")
        keys = ", ".join('"%s"' % k for k in CALC_KEYS)
        return run_lua_to_json(lua, """
          local o = build.calcsTab.mainOutput or {}
          local t = {}
          for _, k in ipairs({ %s }) do if o[k] ~= nil then t[k] = tostring(o[k]) end end
          return t
        """ % keys)

    on = calcs(True)
    off = calcs(False)
    diff = {k: (on.get(k), off.get(k)) for k in set(on) | set(off) if on.get(k) != off.get(k)}
    print("계산값(한글):", json.dumps(on, ensure_ascii=False)[:160])
    if diff:
        fails.append("한글/영문 계산값이 다름: %s" % diff)

    # 화면 그리기
    lua.execute("if not KR.enabled then KR.toggle() end")
    for mode in MODES:
        res = run_lua_to_json(lua, """
          build.viewMode = "%s"
          local ok, err = pcall(runCallback, "OnFrame")
          return { ok = ok, err = tostring(err), prompt = tostring(launch.promptMsg) }
        """ % mode)
        if not res.get("ok") or res.get("prompt") not in ("nil", "None", None):
            fails.append("%s 화면 오류: %s / %s" % (mode, res.get("err"), res.get("prompt")))
    print("화면 그리기:", "오류 없음" if not any("화면 오류" in f for f in fails) else "오류 있음")

    stats = dict(g["KR"]["stats"].items())
    print("DrawString %s회 / 한글 렌더 %s회 / 미번역 %s회" % (stats["draw"], stats["korean"], stats["miss"]))
    if stats["korean"] == 0:
        fails.append("한글 렌더가 한 번도 실행되지 않음")

    # F2 전환 (실제 키 후크를 태운다)
    keyres = run_lua_to_json(lua, """
      local hooked = KR.keyHooked and true or false
      local before = KR.enabled
      if main and main.OnKeyDown then main:OnKeyDown("F2", false) end
      local after = KR.enabled
      pcall(runCallback, "OnFrame")
      if main and main.OnKeyDown then main:OnKeyDown("F2", false) end
      return { hooked = hooked, before = before, after = after, back = KR.enabled }
    """)
    print("F2 전환: 후크=%s / %s→%s→%s" % (keyres.get("hooked"), keyres.get("before"),
                                        keyres.get("after"), keyres.get("back")))
    if not keyres.get("hooked") or keyres.get("after") is not False or keyres.get("back") is not True:
        fails.append("F2 전환이 동작하지 않음")

    # 사전 표본
    probes = run_lua_to_json(lua, """
      local cases = %s
      local out = {}
      for key, text in pairs(cases) do out[key] = KR.translate(text) or "NIL" end
      return out
    """ % ("{" + ", ".join('%s = "%s"' % (k, v.replace('"', '\\"')) for k, v in PROBES.items()) + "}"))
    print("사전 조회:")
    for key, value in probes.items():
        print("   %-9s %s" % (key, str(value)[:60]))
        if not re.search(r"[\uac00-\ud7a3]", str(value)):
            fails.append("사전 조회 실패: " + key)

    # 미등록 글자·폭 계산
    res = run_lua_to_json(lua, """
      local ok1 = pcall(function()
        DrawString(0, 0, "LEFT", 16, "VAR", "쀼쀼 테스트 문자")
        DrawStringWidth(16, "VAR", "쀼쀼 테스트 문자")
      end)
      local w1 = DrawStringWidth(16, "VAR", "Life:")
      local w2 = DrawStringWidth(16, "VAR", "생명력:")
      local w3 = DrawStringWidth(0, "VAR", "생명력:")
      return { ok = ok1, ascii = w1, korean = w2, zero = w3 }
    """)
    print("미등록 글자/폭:", res)
    if not res.get("ok") or not isinstance(res.get("korean"), (int, float)) or res.get("korean") <= 0:
        fails.append("미등록 글자 또는 폭 계산 오류")

    print()
    if fails:
        print("실패:", fails)
        return 1
    print("모든 런타임 검사 통과")
    return 0


if __name__ == "__main__":
    sys.exit(main())
