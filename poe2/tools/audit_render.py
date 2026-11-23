"""PoE2 실제 화면 문자열 번역률 측정.

두 갈래로 모읍니다.
  1) 화면: viewMode 8개를 한 번씩 그리면서 DrawString 에 들어간 모든 문자열
  2) 툴팁: 트리 노드 전부·장착 아이템·장착 젬의 툴팁을 직접 만들어 그 안의 줄

결과는 poe2/data/audit_report.json 에 저장합니다.

사용:
    TEST_POB=/path/to/pob2 python3 poe2/tools/audit_render.py
"""
from __future__ import annotations

import collections
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pob2_harness import boot, run_lua_to_json  # noqa: E402

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(HERE, "data")
TEST_POB = os.environ.get("TEST_POB", "/workspace/work/pob2test")

COLOR_RE = re.compile(r"\^x[0-9A-Fa-f]{6}|\^\d")
MODES = ["ITEMS", "SKILLS", "TREE", "CALCS", "CONFIG", "PARTY", "COMPARE", "NOTES"]

AUDIT_LUA = r"""
local modes = %(modes)s
local out = { rows = {} }
__kr_drawn = {}

local function record(text, tag)
  if type(text) ~= "string" or #text == 0 then return end
  local kr = KR.translate(text)
  out.rows[#out.rows + 1] = { tag = tag, text = text, hit = (kr ~= nil) }
end

local function scan(t, tag)
  for _, line in ipairs(t.lines or {}) do
    if line.text then record(line.text, tag) end
  end
end

local tt = new("Tooltip")
if build then
  -- 트리 노드 (전부)
  local nodeCount = 0
  for _, node in pairs(build.spec.tree.nodes) do
    nodeCount = nodeCount + 1
    if nodeCount %% 2 == 1 then
      tt:Clear()
      local ok = pcall(function() build.treeTab.viewer:AddNodeTooltip(tt, node, build) end)
      if ok then scan(tt, "node") end
    end
  end
  -- 아이템
  for _, item in ipairs(build.itemsTab.items or {}) do
    if item and item.base then
      tt:Clear()
      local ok = pcall(function() build.itemsTab:AddItemTooltip(tt, item) end)
      if ok then scan(tt, "item") end
    end
  end
  -- 젬 (장착한 젬 + 게임 데이터의 젬 표본)
  local gemTooltip = require("Classes.GemTooltip")
  local gemCount = 0
  for _, sg in ipairs(build.skillsTab.socketGroupList or {}) do
    for _, gem in ipairs(sg.gemList or {}) do
      tt:Clear()
      local ok = pcall(function() gemTooltip.AddGemTooltip(tt, build, gem) end)
      if ok then scan(tt, "gem") end
    end
  end
  for _, gemData in pairs(build.data.gems or {}) do
    gemCount = gemCount + 1
    if gemCount %% 4 == 0 then
      local instance = { nameSpec = gemData.nameSpec or gemData.name, level = 20, quality = 0,
                         enabled = true, enableGlobal1 = true, enableGlobal2 = false, count = 1,
                         gemData = gemData, skillId = gemData.grantedEffectId, statSet = {}, statSetCalcs = {} }
      tt:Clear()
      local ok = pcall(function() gemTooltip.AddGemTooltip(tt, build, instance) end)
      if ok then scan(tt, "gem") end
    end
  end
end

-- 화면
if build then
  for _, mode in ipairs(modes) do
    build.viewMode = mode
    __kr_drawn = {}
    pcall(runCallback, "OnFrame")
    for _, row in ipairs(__kr_drawn) do
      record(row, "screen")
    end
  end
  __kr_drawn = {}
end

-- 설정 드롭다운
if build and build.configTab then
  pcall(function()
    for _, control in pairs(build.configTab.controls or {}) do
      if control.list and type(control.list) == "table" then
        for _, item in ipairs(control.list) do
          local label = type(item) == "table" and (item.label or item[1]) or item
          if type(label) == "string" then record(label, "config") end
        end
      end
    end
  end)
end

return out
"""


def classify(text: str) -> str:
    plain = COLOR_RE.sub("", text).strip()
    if not re.search(r"[A-Za-z]{2,}", plain):
        return "숫자·기호만 있는 줄"
    if plain.endswith("(Not supported in PoB yet)"):
        return "PoB 미지원 꼬리표"
    if re.match(r"^[+\-]?[\d.,]", plain):
        return "능력치 비교 줄(라벨 사전 밖)"
    if plain.startswith("("):
        return "힌트 문구(게임 데이터에만 있음)"
    return "기타 문구"


def main() -> int:
    from fixtures import builder_lua, to_lua

    lua, g = boot(TEST_POB)
    lua.execute("print = function() end")
    if not g["KR"]:
        print("한글 패처가 로드되지 않았습니다 (KR2 폴더 확인)")
        return 1

    lua.execute(builder_lua() + "\n__kr_build = applyBuild(spec)")

    # 이미 KR 이 건 DrawString 위에 한 겹 더 씌워 그려진 문자열을 모은다
    lua.execute("""
do
  local before = KR.draw
  local wrapped = function(x, y, align, height, fontName, text)
    if type(text) == "string" and #text > 0 and __kr_drawn then
      __kr_drawn[#__kr_drawn + 1] = text
    end
    return before(x, y, align, height, fontName, text)
  end
  DrawString = wrapped
  KR.draw = wrapped
end
""")

    data = run_lua_to_json(lua, AUDIT_LUA % {"modes": to_lua(MODES)})
    rows = data.get("rows") or []
    if not rows:
        print("수집된 문자열이 없습니다:", str(data)[:300])
        return 1

    seen: dict[str, dict] = {}
    for row in rows:
        key = row["tag"] + "\1" + row["text"]
        seen.setdefault(key, {"tag": row["tag"], "text": row["text"], "hit": bool(row.get("hit"))})

    allrows = list(seen.values())
    tags = collections.Counter(r["tag"] for r in allrows)
    hits = collections.Counter(r["tag"] for r in allrows if r["hit"])
    misses = [r for r in allrows if not r["hit"]]

    by_area = {tag: {"total": n, "hit": hits[tag], "miss": n - hits[tag],
                     "rate": round(100.0 * hits[tag] / n, 1)} for tag, n in tags.most_common()}
    reasons = collections.Counter(classify(r["text"]) for r in misses)
    top = collections.Counter()
    for r in misses:
        top[(r["tag"], COLOR_RE.sub("", r["text"]).strip())] += 1

    total = len(allrows)
    hit_total = sum(hits.values())
    report = {"strings": total, "hit": hit_total, "miss": total - hit_total,
              "rate": round(100.0 * hit_total / max(1, total), 1),
              "by_area": by_area, "reasons": dict(reasons),
              "top_missing": [{"tag": t, "text": s} for (t, s), _ in top.most_common(80)]}
    with open(os.path.join(DATA, "audit_report.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=1)

    print("\n[영역별 번역률]")
    for tag, v in by_area.items():
        print("  %-10s %5d/%5d (%5.1f%%)" % (tag, v["hit"], v["total"], v["rate"]))
    print("  전체        %5d/%5d (%5.1f%%)" % (hit_total, total, report["rate"]))
    print("\n[미번역 사유]")
    for why, n in reasons.most_common():
        print("  %-26s %4d" % (why, n))
    print("\n[많이 나온 미번역]")
    for (tag, text), n in top.most_common(30):
        print("  %-8s %3d  %s" % (tag, n, text[:80]))
    print("\npoe2/data/audit_report.json 저장")
    return 0


if __name__ == "__main__":
    sys.exit(main())
