-- PoB-KR : 문자열 정규화 (숫자 자리표시)
-- 파이썬 빌드 도구(tools/items.py 의 shape)와 완전히 같은 규칙을 씁니다.
local M = {}

local byte, sub, find = string.byte, string.sub, string.find

-- UTF-8 다중 바이트 문자를 그대로 통과시키면서, 숫자 토큰만 '#' 로 바꿉니다.
-- 숫자 토큰: [+-]? \(? \d+ (.\d+)? (-\d+ (.\d+)?)? )?
-- 숫자 하나 이상을 읽습니다. 천 단위 쉼표(1,234)는 한 덩어리로 봅니다.
-- (파이썬 쪽 NUM_TOKEN_RE 와 같은 규칙이어야 사전 키가 맞습니다)
local function matchDigits(s, j, n)
	local used = false
	while j <= n do
		local b = byte(s, j)
		if b and b >= 48 and b <= 57 then
			j = j + 1
			used = true
		elseif used and b == 44 then
			-- 쉼표 뒤에 숫자 정확히 세 자리가 이어질 때만 천 단위로 인정
			local k, c = j + 1, 0
			while c < 3 do
				local bb = byte(s, k)
				if not bb or bb < 48 or bb > 57 then break end
				k = k + 1
				c = c + 1
			end
			if c < 3 then break end
			j = k
		else
			break
		end
	end
	return j, used
end

local function matchNumber(s, i, n)
	local j = i
	local c = sub(s, j, j)
	if c == "+" or c == "-" then j = j + 1 end
	if sub(s, j, j) == "(" then j = j + 1 end
	local j2, used = matchDigits(s, j, n)
	if not used then return nil end
	j = j2
	if sub(s, j, j) == "." then
		local k, used2 = matchDigits(s, j + 1, n)
		if used2 then j = k end
	end
	if sub(s, j, j) == "-" then
		local k, used3 = matchDigits(s, j + 1, n)
		if used3 then
			j = k
			if sub(s, j, j) == "." then
				local m, used4 = matchDigits(s, j + 1, n)
				if used4 then j = m end
			end
		end
	end
	if sub(s, j, j) == ")" then j = j + 1 end
	return j
end

local function normalizeDashes(s)
	s = s:gsub("\226\128\148", "-")   -- em dash
	s = s:gsub("\226\128\147", "-")   -- en dash
	return s
end

--- 문자열 -> (모양 키, 숫자 목록)
function M.shape(text)
	local s = normalizeDashes(text)
	-- "10 to 20" -> "10-20"
	while true do
		local a, b, d1, d2 = find(s, "(%d)%s+to%s+(%d)")
		if not a then break end
		-- a 는 첫 숫자 '한 글자'의 위치이므로, 그 앞까지 남기고 다시 붙입니다.
		-- (sub(s, 1, a) 로 쓰면 첫 숫자의 끝자리가 한 번 더 붙어 "17 to 23" → "177-23")
		s = sub(s, 1, a - 1) .. d1 .. "-" .. d2 .. sub(s, b + 1)
	end
	local out, nums = {}, {}
	local i, n = 1, #s
	while i <= n do
		local j = matchNumber(s, i, n)
		if j then
			nums[#nums + 1] = sub(s, i, j - 1)
			out[#out + 1] = "#"
			i = j
		else
			out[#out + 1] = sub(s, i, i)
			i = i + 1
		end
	end
	local key = table.concat(out):gsub("%s", ""):gsub("\194\160", "")
	return key, nums
end

--- 템플릿의 %1 %2 를 숫자로 치환
function M.fill(tpl, nums)
	return (tpl:gsub("%%(%d+)", function(idx)
		local v = nums[tonumber(idx)]
		return v or ("%" .. idx)
	end))
end

return M
