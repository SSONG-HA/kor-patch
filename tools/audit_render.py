"""렌더링 전수 점검: 실제 PoB 화면·툴팁에 그려지는 문자열을 모아 번역률을 계산합니다.

PoB 를 헤드리스로 띄워 빌드를 읽고, ① 모든 화면(아이템/스킬/트리/계산/설정/파티/비교/메모)을
한 번씩 그리고 ② 트리 노드(숙련 선택지 포함)·장착 아이템·장착 젬의 툴팁을 모두 만들어,
`DrawString` 에 들어가는 문자열이 사전에서 번역되는지 확인합니다.

사용:
    TEST_POB=/path/to/pob BUILD_DIR=/path/to/builds \
    python3 tools/audit_render.py [추가 빌드.xml ...]

결과는 data/audit_report.json 에 저장하고, 영역별 번역률과 남은 미번역(많이 나온 순)을 출력합니다.
"""
from __future__ import annotations

import collections
import json
import os
import re
import sys

sys.path.insert(0, os.environ.get("LUAJIT_PATH", "/workspace/.local/lib/python3.12/site-packages"))
from lupa.luajit21 import LuaRuntime  # noqa: E402

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(HERE, "data")
POB = os.environ.get("TEST_POB", "/workspace/tmpwork/install_test/pob")
BUILD_DIR = os.environ.get("BUILD_DIR", "/workspace/tmpwork/pob/headless/builds")

COLOR_RE = re.compile(r"\^x[0-9A-Fa-f]{6}|\^\d")


def lua_capture() -> str:
    return r"""
local gemTooltip = require("Classes.GemTooltip")
local out, seen = {}, {}
local function rec(text, tag)
  if type(text) ~= "string" or #text == 0 then return end
  local kr = KR.translate and KR.translate(text)
  local key = tag .. "\1" .. text
  if seen[key] then return end
  seen[key] = true
  out[#out+1] = { tag = tag, text = text, hit = kr and true or false }
end
local function scan(t, tag)
  if not t then return end
  for _, l in ipairs(t.lines or {}) do if l.text then rec(l.text, tag) end end
  for _, ct in ipairs(t.childTooltips or {}) do scan(ct, tag) end
end
local build = build
local tt = new("Tooltip"):Tooltip()
for _, mode in ipairs({"ITEMS","SKILLS","TREE","CALCS","CONFIG","PARTY","COMPARE","NOTES"}) do
  build.viewMode = mode
  runCallback("OnFrame")
  for _, tip in ipairs(tooltips or {}) do scan(tip, "screen") end
end
for _, node in pairs(build.spec.tree.nodes) do
  tt:Clear()
  pcall(function() build.treeTab.viewer:AddNodeTooltip(tt, node, build) end)
  scan(tt, "node")
  if node.masteryEffects then
    node.allMasteryOptions = true
    tt:Clear(); pcall(function() build.treeTab.viewer:AddNodeTooltip(tt, node, build) end); scan(tt, "mastery")
    node.allMasteryOptions = nil
    for _, effect in ipairs(node.masteryEffects) do
      local e = build.spec.tree.masteryEffects[effect.effect]
      if e then rec(table.concat(e.sd, " / "), "mastery-popup") end
    end
  end
end
for _, item in ipairs(build.itemsTab.items or {}) do
  if item and item.base then
    tt:Clear(); pcall(function() build.itemsTab:AddItemTooltip(tt, item) end); scan(tt, "item")
  end
end
for _, sg in ipairs(build.skillsTab.socketGroupList or {}) do
  for _, gem in ipairs(sg.gemList or {}) do
    if gem.gemData then
      tt:Clear(); pcall(function() gemTooltip.AddGemTooltip(tt, build, gem) end); scan(tt, "gem")
    end
  end
end
local okcfg = pcall(function()
  for _, c in pairs(build.configTab.controls or {}) do
    if c.list and type(c.list) == "table" then
      for _, it in ipairs(c.list) do
        local label = type(it) == "table" and (it.label or it[1]) or it
        if type(label) == "string" then rec(label, "config") end
      end
    end
  end
end)
return require("dkjson").encode({ list = out })
"""


def classify(text: str) -> str:
    """미번역 문자열의 사유 분류 (보고서에 남길 이유)."""
    plain = COLOR_RE.sub("", text).strip()
    if not re.search(r"[A-Za-z]{2,}", plain):
        return "숫자·기호만 있는 줄"
    if plain.endswith("(Not supported in PoB yet)"):
        return "PoB 미지원 속성 꼬리표"
    if re.match(r"^[+\-]?[\d.,]+", plain):
        return "능력치 비교 줄(라벨 사전 밖)"
    if plain.startswith("("):
        return "힌트 문구(게임 데이터에만 있음)"
    return "기타 문구"


def main() -> int:
    builds = []
    for name in sorted(os.listdir(BUILD_DIR)) if os.path.isdir(BUILD_DIR) else []:
        if name.endswith(".xml"):
            builds.append(os.path.join(BUILD_DIR, name))
    builds += [b for b in sys.argv[1:] if os.path.exists(b)]
    if not builds:
        print("검사할 빌드가 없습니다: BUILD_DIR=%s" % BUILD_DIR)
        return 1
    if not os.path.isdir(POB):
        print("PoB 폴더가 없습니다: TEST_POB=%s" % POB)
        return 1

    os.chdir(POB)
    lua = LuaRuntime(unpack_returned_tuples=True, encoding="utf-8")
    lua.execute("arg={}\npackage.path='./?.lua;./lua/?.lua;./?/init.lua;./lua/?/init.lua;'..package.path\n"
                "dofile('HeadlessWrapper.lua')")
    g = lua.globals()
    if not g["KR"]:
        print("한글 패처가 로드되지 않았습니다 (KR 폴더 확인)")
        return 1

    seen: dict[str, dict] = {}
    for path in builds:
        g["loadBuildFromXML"](open(path, encoding="utf-8").read(), os.path.basename(path))
        g["runCallback"]("OnFrame")
        data = json.loads(lua.execute(lua_capture()))
        for row in data["list"]:
            key = row["tag"] + "\1" + row["text"]
            if key not in seen:
                seen[key] = row
        print("  %s — 현재까지 수집 %d개" % (os.path.basename(path), len(seen)))

    rows = list(seen.values())
    tags = collections.Counter(r["tag"] for r in rows)
    hits = collections.Counter(r["tag"] for r in rows if r["hit"])
    misses = [r for r in rows if not r["hit"]]

    by_area = {}
    for tag, total in tags.most_common():
        by_area[tag] = {"total": total, "hit": hits[tag], "miss": total - hits[tag],
                         "rate": round(100.0 * hits[tag] / total, 1)}
    reasons = collections.Counter(classify(r["text"]) for r in misses)
    top = collections.Counter()
    for r in misses:
        top[(r["tag"], COLOR_RE.sub("", r["text"]).strip())] += 1

    total = sum(tags.values())
    hit_total = sum(hits.values())
    report = {
        "builds": [os.path.basename(b) for b in builds],
        "strings": total,
        "hit": hit_total,
        "miss": total - hit_total,
        "rate": round(100.0 * hit_total / max(1, total), 1),
        "by_area": by_area,
        "reasons": dict(reasons),
        "top_missing": [{"tag": t, "text": s} for (t, s), _ in top.most_common(60)],
    }
    with open(os.path.join(DATA, "audit_report.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=1)

    print("\n[영역별 번역률]")
    for tag, v in by_area.items():
        print("  %-14s %5d/%5d (%5.1f%%)" % (tag, v["hit"], v["total"], v["rate"]))
    print("  전체           %5d/%5d (%5.1f%%)" % (hit_total, total, report["rate"]))
    print("\n[미번역 사유]")
    for why, n in reasons.most_common():
        print("  %-26s %4d" % (why, n))
    print("\n[많이 나온 미번역]")
    for (tag, text), n in top.most_common(15):
        print("  %-10s %3d  %s" % (tag, n, text[:70]))
    print("\ndata/audit_report.json 에 저장했습니다.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
