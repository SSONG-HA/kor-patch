"""PoB2 헤드리스 실행 도우미 (테스트·감사 공용).

PoB2 는 SimpleGraphic 런타임 없이 HeadlessWrapper.lua 로 실행됩니다.
이 모듈은 그 실행을 감싸고, Lua 쪽 print 출력이 섞여도 결과를 잃지 않도록
결과를 파일로 받아 옵니다.

환경 변수:
  TEST_POB   테스트용 PoB2 폴더 (KR2 가 설치된 곳)
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.environ.get("LUAJIT_PATH", "/workspace/.local/lib/python3.12/site-packages"))


def boot(pob_dir: str):
    from lupa.luajit21 import LuaRuntime

    os.chdir(pob_dir)
    lua = LuaRuntime(unpack_returned_tuples=True, encoding="utf-8")
    lua.execute("arg={}\npackage.path='./?.lua;./lua/?.lua;./?/init.lua;./lua/?/init.lua;'..package.path\n"
                "dofile('HeadlessWrapper.lua')")
    return lua, lua.globals()


def run_lua_to_json(lua, code: str):
    """Lua 코드를 실행하고, 마지막 return 값을 dkjson 으로 받아 온다."""
    wrapped = ("return (function()\n%s\nend)()" % code)
    raw = lua.execute(
        "local fn = function() %s end\n"
        "local ok, res = pcall(fn)\n"
        "if not ok then return require('dkjson').encode({ error = tostring(res) }) end\n"
        "if type(res) == 'table' then return require('dkjson').encode(res) end\n"
        "return require('dkjson').encode({ value = res })" % code
    )
    try:
        return json.loads(raw)
    except Exception:
        return {"raw": raw}


def result_file(path: str = "/tmp/pob2_result.json") -> str:
    return path
