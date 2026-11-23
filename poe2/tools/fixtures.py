"""헤드리스 검증용 PoE2 빌드 정의.

PoB2 를 헤드리스로 띄운 뒤 아래 BUILD_SPEC 을 그대로 적용해 빌드를 만듭니다.
(클래스·전직·노드·젬·아이템을 모두 게임 데이터에서 고르므로 사전 커버리지 측정에 적합합니다)
"""
from __future__ import annotations

import json

# 흔히 쓰이는 아이템 속성 줄 (PoB 가 해석하는 영문 표기)
RARE_MODS = [
    "+# to maximum Life",
    "+#% to Fire Resistance",
    "+#% to Cold Resistance",
    "+#% to Lightning Resistance",
    "+# to maximum Mana",
    "+#% increased Attack Speed",
    "+#% increased Cast Speed",
    "+#% increased Movement Speed",
    "#% increased Armour",
    "#% increased Evasion Rating",
    "#% increased Energy Shield",
    "+# to Strength",
    "+# to Dexterity",
    "+# to Intelligence",
    "#% increased Critical Hit Chance",
    "#% increased Damage",
]

ITEM_TEMPLATES = [
    # (슬롯 이름, 게임 아이템 종류(type), 속성 3개)
    ("Weapon 1", "Bow", [0, 5, 14]),
    ("Helmet", "Helmet", [0, 1, 9]),
    ("Body Armour", "Body Armour", [0, 2, 10]),
    ("Gloves", "Gloves", [0, 3, 4]),
    ("Boots", "Boots", [0, 7, 5]),
    ("Amulet", "Amulet", [0, 4, 15]),
    ("Ring 1", "Ring", [1, 2, 3]),
    ("Belt", "Belt", [0, 10, 6]),
]


def rare_item_text(name: str, base: str, mods: list[str]) -> str:
    body = "\n".join(mods)
    return "Rarity: RARE\n%s\n%s\n--------\nItem Level: 82\n--------\n%s\n" % (name, base, body)


def pick_base(bases: dict, wanted: str) -> str:
    """PoB itemBases 에서 원하는 종류의 베이스를 하나 고른다 (높은 레벨 우선)."""
    best = None
    for name, info in bases.items():
        if not isinstance(info, dict) or info.get("type") != wanted:
            continue
        req = (info.get("req") or {}).get("level") or 1
        if best is None or req > best[1]:
            best = (name, req)
    return best[0] if best else None


def build_spec() -> dict:
    items = []
    for i, (slot, base_type, mod_idx) in enumerate(ITEM_TEMPLATES):
        mods = [RARE_MODS[m].replace("#", str(10 + i * 3)) for m in mod_idx]
        items.append({"slot": slot, "baseType": base_type, "name": "테스트 " + slot, "mods": mods})
    return {
        "classId": 8,          # Huntress
        "ascendClassId": 1,
        "treeVersion": "0_5",
        "level": 90,
        "nodes": [],           # 비어 있으면 시작 노드에서 BFS 로 채운다
        "nodeBudget": 60,
        "gems": [
            {"gemId": "Metadata/Items/Gems/SkillGemLightningArrow", "level": 20, "quality": 20},
        ],
        "supports": [],
        "items": items,
    }


LUA_BUILDER = r"""
local spec = %s

local function applyBuild(spec)
  newBuild()
  build.spec.classId = spec.classId
  build.spec.ascendClassId = spec.ascendClassId or 0
  build.spec.treeVersion = spec.treeVersion
  build.buildLevel = spec.level or 90

  -- 노드: 클래스 시작 노드 + 흔한 능력치 노드를 예산만큼 할당
  local tree = build.spec.tree
  local allocated = 0
  local startNode
  for _, node in pairs(tree.nodes) do
    local ci = node.classStartIndex
    if (type(ci) == "table" and (ci[1] == spec.classId or ci[2] == spec.classId))
        or ci == spec.classId then
      startNode = node
      break
    end
  end
  if startNode then
    build.spec:AllocNode(startNode)
    allocated = 1
  end
  build.spec:BuildAllDependsAndPaths()
  local keywords = { "maximum Life", "increased Damage", "Resistance", "Attribute",
                     "Armour", "Evasion", "Energy Shield", "Attack Speed", "Cast Speed" }
  local want = spec.nodeBudget or 0
  for _, node in pairs(tree.nodes) do
    if allocated >= want then break end
    if node.type ~= "ClassStart" and not node.ascendancyName and node.skill then
      local text = table.concat(node.sd or {}, " ")
      for _, kw in ipairs(keywords) do
        if text:find(kw, 1, true) then
          build.spec:AllocNode(node)
          allocated = allocated + 1
          break
        end
      end
    end
  end

  -- 젬
  local st = build.skillsTab
  local node = { elem = "Skill", attrib = { enabled = "true", mainActiveSkill = "1", label = "" } }
  local gemIndex = 0
  local gemList = {}
  for _, g in ipairs(spec.gems or {}) do gemList[#gemList + 1] = g end
  for _, g in ipairs(spec.supports or {}) do gemList[#gemList + 1] = g end
  for _, g in ipairs(gemList) do
    gemIndex = gemIndex + 1
    node[gemIndex] = { elem = "Gem", attrib = {
      gemId = g.gemId, level = tostring(g.level or 20), quality = tostring(g.quality or 0),
      enabled = "true" } }
  end
  if gemIndex > 0 then st:LoadSkill(node, 1) end
  build.spec:BuildAllDependsAndPaths()
  build.buildFlag = true

  -- 아이템: 같은 종류(type)의 베이스를 게임 데이터에서 골라 만든다
  local madeItems = 0
  for _, it in ipairs(spec.items or {}) do
    local baseName
    for name, info in pairs(build.data.itemBases or {}) do
      if info.type == it.baseType then
        if not baseName or ((info.req or {}).level or 0) > ((build.data.itemBases[baseName].req or {}).level or 0) then
          baseName = name
        end
      end
    end
    if baseName then
      local raw = "Rarity: RARE\n" .. it.name .. "\n" .. baseName .. "\n--------\nItem Level: 82\n--------\n"
      for _, m in ipairs(it.mods or {}) do raw = raw .. m .. "\n" end
      local item = new("Item")
      item:ParseRaw(raw)
      if item.base then
        build.itemsTab:AddItem(item)
        madeItems = madeItems + 1
      end
    end
  end

  runCallback("OnFrame")
  return { allocated = allocated, items = #(build.itemsTab.itemOrderList or {}),
           groups = #(build.skillsTab.socketGroupList or {}) }
end
"""


def to_lua(value) -> str:
    """파이썬 값 → Lua 테이블 리터럴."""
    if isinstance(value, dict):
        parts = []
        for k, v in value.items():
            if isinstance(k, str) and not k.isidentifier():
                parts.append("[%s] = %s" % (json.dumps(k, ensure_ascii=False), to_lua(v)))
            else:
                parts.append("%s = %s" % (k, to_lua(v)))
        return "{ " + ", ".join(parts) + " }"
    if isinstance(value, (list, tuple)):
        return "{ " + ", ".join(to_lua(v) for v in value) + " }"
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if value is True:
        return "true"
    if value is False:
        return "false"
    if value is None:
        return "nil"
    return str(value)


def builder_lua(spec: dict | None = None) -> str:
    return LUA_BUILDER % to_lua(spec or build_spec())
