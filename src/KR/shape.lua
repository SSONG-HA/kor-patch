-- PoB-KR : 문자열 정규화 (숫자 자리표시)
-- 파이썬 빌드 도구(tools/items.py 의 shape)와 완전히 같은 규칙을 씁니다.
local M = {}

local byte, sub, find = string.byte, string.sub, string.find

-- UTF-8 다중 바이트 문자를 그대로 통과시키면서, 숫자 토큰만 '#' 로 바꿉니다.
-- 숫자 토큰: [+-]? \(? \d+ (.\d+)? (-\d+ (.\d+)?)? )?
local function matchNumber(s, i, n)
	local j = i
	local c = sub(s, j, j)
	if c == "+" or c == "-" then j = j + 1 end
	if sub(s, j, j) == "(" then j = j + 1 end
	local ds = j
	while j <= n do
		local b = byte(s, j)
		if not b or b < 48 or b > 57 then break end
		j = j + 1
	end
	if j == ds then return nil end
	if sub(s, j, j) == "." then
		local k = j + 1
		local d2 = k
		while k <= n do
			local b = byte(s, k)
			if not b or b < 48 or b > 57 then break end
			k = k + 1
		end
		if k > d2 then j = k end
	end
	if sub(s, j, j) == "-" then
		local k = j + 1
		local d3 = k
		while k <= n do
			local b = byte(s, k)
			if not b or b < 48 or b > 57 then break end
			k = k + 1
		end
		if k > d3 then
			j = k
			if sub(s, j, j) == "." then
				local m = j + 1
				local d4 = m
				while m <= n do
					local b = byte(s, m)
					if not b or b < 48 or b > 57 then break end
					m = m + 1
				end
				if m > d4 then j = m end
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
