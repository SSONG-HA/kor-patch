-- PoB-KR : 한글 텍스트 레이아웃/그리기
local M = {}

local ROOT = (_G.KR_ROOT or "KR")
local font = dofile(ROOT .. "/font.lua")
local shapeMod = dofile(ROOT .. "/shape.lua")

M.font = font
M.shape = shapeMod.shape
M.fill = shapeMod.fill

local byte, sub, find = string.byte, string.sub, string.find

-- 엔진 색상 팔레트 (SimpleGraphic common.h)
local PALETTE = {
	[0] = { 0.0, 0.0, 0.0 },
	[1] = { 1.0, 0.0, 0.0 },
	[2] = { 0.0, 1.0, 0.0 },
	[3] = { 0.0, 0.0, 1.0 },
	[4] = { 1.0, 1.0, 0.0 },
	[5] = { 1.0, 0.0, 1.0 },
	[6] = { 0.0, 1.0, 1.0 },
	[7] = { 1.0, 1.0, 1.0 },
	[8] = { 0.7, 0.7, 0.7 },
	[9] = { 0.4, 0.4, 0.4 },
}
M.PALETTE = PALETTE

local function hexVal(s, i)
	local b = byte(s, i)
	if not b then return nil end
	if b >= 48 and b <= 57 then return b - 48 end
	if b >= 97 and b <= 102 then return b - 87 end
	if b >= 65 and b <= 70 then return b - 55 end
	return nil
end

--- i 위치의 색상 이스케이프를 읽습니다 -> (다음 위치, 색상)
function M.readEscape(s, i, n)
	if sub(s, i, i) ~= "^" then return nil end
	local d = byte(s, i + 1)
	if d and d >= 48 and d <= 57 then
		return i + 2, PALETTE[d - 48]
	end
	local c = sub(s, i + 1, i + 1)
	if c == "x" or c == "X" then
		if i + 7 > n then return nil end
		local r, g, b = 0, 0, 0
		for k = 0, 5 do
			local v = hexVal(s, i + 2 + k)
			if not v then return nil end
			if k < 2 then r = r * 16 + v elseif k < 4 then g = g * 16 + v else b = b * 16 + v end
		end
		return i + 8, { r / 255, g / 255, b / 255 }
	end
	return nil
end

--- UTF-8 한 글자 디코드 -> (다음 위치, 코드포인트, 바이트 길이)
local function decode(s, i)
	local b = byte(s, i)
	if not b then return nil end
	if b < 0x80 then return i + 1, b, 1 end
	if b >= 0xF0 then
		local b2, b3, b4 = byte(s, i + 1), byte(s, i + 2), byte(s, i + 3)
		if not b4 then return i + 1, b, 1 end
		return i + 4, (b - 0xF0) * 0x40000 + (b2 - 0x80) * 0x1000 + (b3 - 0x80) * 0x40 + (b4 - 0x80), 4
	elseif b >= 0xE0 then
		local b2, b3 = byte(s, i + 1), byte(s, i + 2)
		if not b3 then return i + 1, b, 1 end
		return i + 3, (b - 0xE0) * 0x1000 + (b2 - 0x80) * 0x40 + (b3 - 0x80), 3
	else
		local b2 = byte(s, i + 1)
		if not b2 then return i + 1, b, 1 end
		return i + 2, (b - 0xC0) * 0x40 + (b2 - 0x80), 2
	end
end

local asciiWidthCache = {}

function M.asciiWidth(height, fontName, run, origWidth)
	local key = height .. "|" .. fontName .. "|" .. run
	local w = asciiWidthCache[key]
	if w then return w end
	w = origWidth(height, fontName, run)
	asciiWidthCache[key] = w
	return w
end

local layoutCache = {}
local layoutCount = 0

--- 문자열을 줄/색상/글리프 단위로 배치합니다.
function M.layout(text, height, fontName, origWidth)
	local key = height .. "|" .. fontName .. "|" .. text
	local cached = layoutCache[key]
	if cached then return cached end

	local l = { lines = {}, width = 0 }
	local color = nil
	local line = { segs = {}, width = 0 }
	local seg = nil
	local i, n = 1, #text

	local function newSeg()
		seg = { c = color, items = {} }
		line.segs[#line.segs + 1] = seg
	end

	local function addAscii(s)
		if s == "" then return end
		if not seg then newSeg() end
		local items = seg.items
		local last = items[#items]
		if last and last.ascii then
			last.ascii = last.ascii .. s
		else
			items[#items + 1] = { ascii = s }
		end
		line.width = line.width + M.asciiWidth(height, fontName, s, origWidth)
	end

	while i <= n do
		local ch = sub(text, i, i)
		if ch == "^" then
			local j, col = M.readEscape(text, i, n)
			if j then
				color = col
				seg = nil
				i = j
			else
				addAscii(ch)
				i = i + 1
			end
		elseif ch == "\n" then
			l.lines[#l.lines + 1] = line
			if line.width > l.width then l.width = line.width end
			line = { segs = {}, width = 0 }
			seg = nil
			i = i + 1
		elseif ch == "\t" then
			addAscii("    ")
			i = i + 1
		else
			local j, cp, size = decode(text, i)
			if size == 1 then
				local k = i
				while k <= n do
					local b = byte(text, k)
					if not b or b >= 0x80 then break end
					local c = sub(text, k, k)
					if c == "^" or c == "\n" or c == "\t" then break end
					k = k + 1
				end
				addAscii(sub(text, i, k - 1))
				i = k
			else
				local g, atlas = font.glyph(height, cp)
				if not g then
					g, atlas = font.fallback(cp)
				end
				if g then
					if not seg then newSeg() end
					seg.items[#seg.items + 1] = { g = g, atlas = atlas }
					line.width = line.width + g[5] * (height / atlas.size)
				else
					addAscii("?")
				end
				i = j
			end
		end
	end
	l.lines[#l.lines + 1] = line
	if line.width > l.width then l.width = line.width end

	layoutCount = layoutCount + 1
	if layoutCount > 6000 then
		layoutCache = {}
		layoutCount = 0
	end
	layoutCache[key] = l
	return l
end

--- 폭 계산 (엔진 DrawStringWidth 대체)
function M.width(text, height, fontName, origWidth)
	if height <= 1 then return origWidth(height, fontName, text) end
	local l = M.layout(text, height, fontName, origWidth)
	return math.ceil(l.width)
end

--- 문자열 그리기 (엔진 DrawString 대체)
-- ctx: { origDraw, origWidth, screenW, base = baseline 비율 }
function M.draw(x, y, align, height, fontName, text, ctx)
	local origDraw, origWidth, screenW = ctx.origDraw, ctx.origWidth, ctx.screenW
	local baseRatio = ctx.base or 0.80
	local l = M.layout(text, height, fontName, origWidth)
	local r, g, b = ctx.color[1], ctx.color[2], ctx.color[3]
	local y0 = math.floor(y)
	local anyGlyph = false

	for li = 1, #l.lines do
		local line = l.lines[li]
		local lx = x
		if align == "CENTER" then
			lx = math.floor((screenW - line.width) / 2 + x)
		elseif align == "RIGHT" then
			lx = math.floor(screenW - line.width - x)
		elseif align == "CENTER_X" then
			lx = math.floor(x - line.width / 2)
		elseif align == "RIGHT_X" then
			lx = math.floor(x - line.width)
		end
		local ly = y0 + (li - 1) * height
		local px = lx
		local cr, cg, cb = r, g, b
		for si = 1, #line.segs do
			local seg = line.segs[si]
			if seg.c then
				cr, cg, cb = seg.c[1], seg.c[2], seg.c[3]
			else
				cr, cg, cb = r, g, b
			end
			SetDrawColor(cr, cg, cb, 1)
			local items = seg.items
			for ii = 1, #items do
				local it = items[ii]
				if it.ascii then
					origDraw(px, ly, "LEFT", height, fontName, it.ascii)
					px = px + M.asciiWidth(height, fontName, it.ascii, origWidth)
				else
					local gl, atlas = it.g, it.atlas
					local k = height / atlas.size
					DrawImage(atlas.handle, px - atlas.pad * k, ly + baseRatio * height - atlas.base * k,
						atlas.cellW * k, atlas.cellH * k, gl[1], gl[2], gl[3], gl[4])
					px = px + gl[5] * k
					anyGlyph = true
				end
			end
		end
	end
	return anyGlyph
end

return M
