-- PoB-KR : 초기화 및 후크 설치
-- Path of Building Community Fork 의 화면 그리기 계층만 가로채 한글로 표시합니다.
-- 계산 엔진(파서/수치 계산)은 전혀 건드리지 않습니다.

if KR_PATCHER_LOADED then return end
KR_PATCHER_LOADED = true

local KR = {
	version = "1.0.0",
	enabled = true,
	stats = { draw = 0, korean = 0, miss = 0 },
}
_G.KR = KR

local format = string.format
local ROOT = (_G.KR_ROOT or "KR")

local ok, err = pcall(function()
	local draw = dofile(ROOT .. "/draw.lua")
	local font = draw.font
	local shape = draw.shape
	local fill = draw.fill

	local exact = dofile(ROOT .. "/Data/exact.lua")
	local templates = dofile(ROOT .. "/Data/templates.lua")

	local origDrawString = DrawString
	local origDrawStringWidth = DrawStringWidth
	KR.origDrawString = origDrawString
	KR.origDrawStringWidth = origDrawStringWidth

	pcall(function()
		local cfg = dofile(ROOT .. "/config.lua")
		if type(cfg) == "table" then
			if cfg.enabled ~= nil then KR.enabled = cfg.enabled and true or false end
			if cfg.baseline then KR.baseline = cfg.baseline end
		end
	end)

	local cache = {}

	local function translate(text)
		local t = exact[text]
		if t then return t end
		local key, nums = shape(text)
		local tpl = templates[key]
		if tpl then
			if #nums == 0 then return tpl end
			return fill(tpl, nums)
		end
		-- "고유/베이스 이름, 베이스 종류" 형태: 뒤쪽 베이스 이름만 번역
		local pos = 1
		while true do
			local i = text:find(", ", pos, true)
			if not i then break end
			local tail = text:sub(i + 2)
			local tt = exact[tail]
			if tt then
				return text:sub(1, i + 1) .. tt
			end
			pos = i + 2
		end
		-- "스킬A, 스킬B" 형태: 모든 조각이 번역되면 이어붙임
		if text:find(", ", 1, true) then
			local parts, allHit = {}, true
			for piece in text:gmatch("[^,]+") do
				local p = piece:gsub("^%s+", ""):gsub("%s+$", "")
				local pp = exact[p]
				if not pp then allHit = false break end
				parts[#parts + 1] = pp
			end
			if allHit and #parts > 1 then
				return table.concat(parts, ", ")
			end
		end
		-- "스킬이름 B-G-R" 형태: 앞쪽 이름만 번역
		local head2, cols = text:match("^(.-) ([BGRW%-]+)$")
		if head2 and cols then
			local hh = exact[head2]
			if hh then return hh .. " " .. cols end
		end
		-- "이름 (태그) ..." 형태: 앞쪽 이름만 번역
		local head, rest = text:match("^(.-) %((.*)$")
		if head and rest then
			local hh = exact[head]
			if hh then return hh .. " (" .. rest end
		end
		return nil
	end

	--- 앞쪽 색상 이스케이프를 분리
	local function splitPrefix(text)
		local i, n = 1, #text
		while i <= n do
			local j = draw.readEscape(text, i, n)
			if not j then break end
			i = j
		end
		return text:sub(1, i - 1), text:sub(i)
	end

	--- 색상 이스케이프를 보존한 번역
	local function translateEx(text)
		local c = cache[text]
		if c ~= nil then
			if c == false then return nil end
			return c
		end
		local prefix, body = splitPrefix(text)
		local res = translate(text)
		if not res then
			local plain = text:gsub("%^x%x%x%x%x%x%x", ""):gsub("%^%d", "")
			res = translate(plain)
			if res and prefix == "" and body then
				-- 문자열 중간 색상은 색상 정보 없이 번역문만 사용
			end
		end
		if res then
			if prefix ~= "" then res = prefix .. res end
		else
			res = false
		end
		cache[text] = res
		return res or nil
	end

	KR.translate = translateEx

	local function hasHangul(s)
		-- 한글 음절(U+AC00~U+D7A3), 자모(U+1100~U+11FF), 호환 자모(U+3130~U+318F)
		if s:find("[\234-\237][\128-\191][\128-\191]") then return true end
		if s:find("\225[\132-\133][\128-\191]") then return true end
		if s:find("\227[\132-\133][\128-\191]") then return true end
		return false
	end

	local function screenWidth()
		local w = GetVirtualScreenSize()
		return w or 1920
	end

	function DrawString(x, y, align, height, fontName, text)
		KR.stats.draw = KR.stats.draw + 1
		if type(text) == "number" then text = tostring(text) end
		if type(text) ~= "string" or not KR.enabled or height <= 1 or #text == 0 then
			return origDrawString(x, y, align, height, fontName, text)
		end
		local kr = translateEx(text)
		if not kr then
			KR.stats.miss = KR.stats.miss + 1
			if hasHangul(text) then
				-- 사전에 없는 한글(사용자 메모, 직접 입력한 이름 등)도 아틀라스로 그립니다
				KR.stats.korean = KR.stats.korean + 1
				local r0, g0, b0 = GetDrawColor()
				draw.draw(x, y, align, height, fontName, text, {
					origDraw = origDrawString,
					origWidth = origDrawStringWidth,
					screenW = screenWidth(),
					base = KR.baseline,
					color = { r0 or 1, g0 or 1, b0 or 1 },
				})
				origDrawString(x, y, align, height, fontName, "")
				return
			end
			return origDrawString(x, y, align, height, fontName, text)
		end
		if not hasHangul(kr) then
			return origDrawString(x, y, align, height, fontName, kr)
		end
		KR.stats.korean = KR.stats.korean + 1
		local r, g, b = GetDrawColor()
		local drew = draw.draw(x, y, align, height, fontName, kr, {
			origDraw = origDrawString,
			origWidth = origDrawStringWidth,
			screenW = screenWidth(),
			base = KR.baseline,
			color = { r or 1, g or 1, b or 1 },
		})
		if drew then
			-- 툴팁 색상 추적용 엔진 상태 동기화
			origDrawString(x, y, align, height, fontName, "")
		end
	end

	function DrawStringWidth(height, fontName, text)
		if type(text) == "number" then text = tostring(text) end
		if type(text) ~= "string" or not KR.enabled or height <= 1 then
			return origDrawStringWidth(height, fontName, text)
		end
		local kr = translateEx(text)
		if not kr then
			if hasHangul(text) then
				return draw.width(text, height, fontName, origDrawStringWidth)
			end
			return origDrawStringWidth(height, fontName, text)
		end
		if not hasHangul(kr) then
			return origDrawStringWidth(height, fontName, kr)
		end
		return draw.width(kr, height, fontName, origDrawStringWidth)
	end

	KR.toggle = function()
		KR.enabled = not KR.enabled
		cache = {}
		print(format("[PoB-KR] %s", KR.enabled and "한글 표시 켜짐" or "한글 표시 꺼짐 (영문 원본)"))
	end

	-- F2 로 한/영 전환 (main 객체가 준비된 뒤 한 번만 감쌉니다)
	local function installKeyHook()
		local m = _G.main
		if type(m) == "table" and type(m.OnKeyDown) == "function" then
			local orig = m.OnKeyDown
			m.OnKeyDown = function(self, key, doubleClick)
				if key == "F2" then
					KR.toggle()
					return
				end
				return orig(self, key, doubleClick)
			end
			KR.keyHooked = true
		end
	end

	local baseDraw = DrawString
	function DrawString(x, y, align, height, fontName, text)
		if not KR.keyHooked then installKeyHook() end
		return baseDraw(x, y, align, height, fontName, text)
	end
	KR.draw = baseDraw

	font.init()
	installKeyHook()
	KR.ready = true
	local nExact, nTpl = 0, 0
	for _ in pairs(exact) do nExact = nExact + 1 end
	for _ in pairs(templates) do nTpl = nTpl + 1 end
	KR.counts = { exact = nExact, templates = nTpl }
	print(format("[PoB-KR] 한글 패처 %s 로드 완료 (사전 %d개, 템플릿 %d개)", KR.version, nExact, nTpl))
end)

if not ok then
	print("[PoB-KR] 초기화 실패: " .. tostring(err))
end

return KR
