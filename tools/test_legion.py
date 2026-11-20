"""Check that the deployed dictionaries translate every legion string PoB draws.

Runs the same lookup the runtime uses (exact -> shape key -> template fill) over:
  * LegionPassives.lua node names and stat lines (with rolled values)
  * the six timeless jewels' item lines, incl. every variant
  * item header lines ("Historic", "Passives in radius are Conquered by …")

Usage:
    POB_SRC=<PoB checkout> python tools/test_legion.py
    python tools/test_legion.py --pob /workspace/tmpwork/pob/headless
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join("/workspace/.local/lib/python3.12/site-packages"))
sys.path.insert(0, HERE)

from common import SRC, load_lua_table, lua_to_py, norm_space  # noqa: E402

try:
    from lupa.luajit21 import LuaRuntime
except ImportError:  # pragma: no cover
    from lupa import LuaRuntime


def lua_dict():
    lua = LuaRuntime(unpack_returned_tuples=True, encoding="utf-8")
    lua.execute("""
        SHAPE = dofile(%r)
        EXACT = dofile(%r)
        TPL = dofile(%r)
    """ % (os.path.join(SRC, "shape.lua"),
           os.path.join(SRC, "Data", "exact.lua"),
           os.path.join(SRC, "Data", "templates.lua")))
    return lua


def translate(lua, text):
    res = lua.execute("""
        local function tr(text)
            local exact, tpl, shape, fill = EXACT, TPL, SHAPE.shape, SHAPE.fill
            local t = exact[text]
            if t then return t end
            local trimmed = text:gsub("%s+$", "")
            if trimmed ~= text then
                t = exact[trimmed]
                if t then return t end
            end
            local key, nums = shape(text)
            local tmpl = tpl[key]
            if tmpl then
                if #nums == 0 then return tmpl end
                return fill(tmpl, nums)
            end
            return nil
        end
        return tr(...) or ""
    """, text)
    return res


def pob_strings(pob):
    """Every legion string PoB can draw (names, stats, item lines)."""
    out = []
    path = os.path.join(pob, "Data", "TimelessJewelData", "LegionPassives.lua")
    if os.path.exists(path):
        legion = lua_to_py(load_lua_table(path))
        for node in legion["nodes"]:
            if node.get("dn"):
                out.append(node["dn"])
            for stat in node.get("sd") or []:
                out.append(norm_space(stat))
        for add in legion["additions"]:
            for stat in add.get("sd") or []:
                out.append(norm_space(stat))
    path = os.path.join(pob, "Data", "Uniques", "jewel.lua")
    if os.path.exists(path):
        blocks = lua_to_py(load_lua_table(path))
        for block in (blocks.values() if isinstance(blocks, dict) else blocks):
            if not isinstance(block, str):
                continue
            lines = [l.strip() for l in block.strip().split("\n")]
            if len(lines) < 2 or lines[1] != "Timeless Jewel":
                continue
            for line in lines:
                m = re.match(r"^\{variant:\d+\}(.+)$", line)
                if m:
                    out.append(m.group(1))
                elif not line.startswith(("Variant:", "Selected Variant:", "Implicits:", "Radius:",
                                          "Limited to:", "Source:", "League:", "Has Alt", "Has ")):
                    out.append(line)
            out += ["Radius: Large", "Limited to: 1", "Historic"]
    return out


def roll(text):
    """(7-12) -> 12 처럼 굴림값을 채운 실제 표시 문장으로 바꿉니다."""
    def repl(m):
        parts = m.group(1).split("-")
        return parts[-1]
    return re.sub(r"\((-?\d+(?:-\d+)?)\)", repl, text)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pob", default=os.environ.get("POB_SRC", "/workspace/tmpwork/pob/headless"))
    args = ap.parse_args()

    strings = pob_strings(args.pob)
    if not strings:
        print("PoB 데이터를 찾지 못했습니다: %s" % args.pob)
        return 1
    lua = lua_dict()
    miss = []
    cases = []
    for text in dict.fromkeys(strings):
        cases.append(text)
        if roll(text) != text:
            # 찬란한 허영심은 굴림값을 실제 숫자로 바꿔 그립니다.
            cases.append(roll(text))
    for drawn in cases:
        out = translate(lua, drawn)
        if not out or not re.search(r"[\uac00-\ud7a3]", out):
            miss.append(drawn)
    total = len(cases)
    print("군단 주얼 문자열 %d개 중 번역 %d개 (%.1f%%)" % (
        total, total - len(miss), 100.0 * (total - len(miss)) / total))
    for text in miss:
        print("  미번역:", text)
    return 0 if not miss else 2


if __name__ == "__main__":
    sys.exit(main())
