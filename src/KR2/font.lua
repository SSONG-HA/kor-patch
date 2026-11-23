-- PoB-KR : 한글 글리프 아틀라스
-- 엔진 폰트는 ASCII 비트맵만 지원하므로, 한글은 미리 구운 PNG 아틀라스를 쿼드로 그립니다.
local M = {}

local metrics = dofile((_G.KR_ROOT or "KR2") .. "/Fonts/metrics.lua")
local codes = metrics.codes
local sizes = metrics.sizes

M.screenScale = 1
local loaded = {}     -- size -> {handle=..., map={[cp]={u0,v0,u1,v1,adv}} or nil}
M.ready = false

local function buildIndex(def)
	local map = {}
	local n = #codes
	-- 코드포인트가 정렬되어 있으므로 rank = 목록 위치
	for i = 1, n do
		local cp = codes[i]
		local idx = i - 1
		local col = idx % def.cols
		local row = math.floor(idx / def.cols)
		local u0 = col * def.cw / def.w
		local v0 = row * def.ch / def.h
		map[cp] = {
			u0, v0, (col + 1) * def.cw / def.w, (row + 1) * def.ch / def.h,
			def.adv[i] or def.size,
		}
	end
	return map
end

--- 화면 배율을 반영해 height 에 가장 알맞은 아틀라스를 고릅니다.
function M.pick(height)
	local target = height * M.screenScale
	local best = sizes[1]
	for i = 1, #sizes do
		local s = sizes[i]
		if s.size >= target then
			best = s
			break
		end
		best = s
	end
	return best
end

local function ensure(def)
	local e = loaded[def.size]
	if e then return e end
	e = {def = def}
	loaded[def.size] = e
	local ok, handle = pcall(NewImageHandle)
	if ok and handle then
		e.handle = handle
		pcall(function() handle:Load(((_G.KR_ROOT or "KR2") .. "/Fonts/") .. def.png, "CLAMP") end)
		e.map = buildIndex(def)
		e.base = def.base
		e.cellW = def.cw
		e.cellH = def.ch
		e.size = def.size
		e.pad = def.pad
	end
	return e
end

function M.atlas(height)
	local def = M.pick(height)
	return ensure(def)
end

function M.init()
	M.screenScale = (GetScreenScale and GetScreenScale()) or 1
	-- 자주 쓰는 크기는 미리 로드 (첫 프레임 끊김 방지)
	for _, def in ipairs(sizes) do
		if def.size <= 20 then
			ensure(def)
		end
	end
	M.ready = true
end

--- 글자 폭(논리 픽셀)
function M.advance(height, cp)
	local a = M.atlas(height)
	if not a or not a.map then return height * 0.55 end
	local g = a.map[cp]
	if not g then return height * (a.def.size and 1 or 1) end
	return g[5] * (height / a.size)
end

function M.glyph(height, cp)
	local a = M.atlas(height)
	if not a or not a.map then return nil, nil end
	return a.map[cp], a
end

function M.has(cp)
	local a = M.atlas(16)
	return a and a.map and a.map[cp] ~= nil
end

-- 사전에 없는 한글(사용자 메모 등)을 위한 전체 음절 폴백 아틀라스
local fullAtlas = nil

local function buildFull()
	local def = metrics.full
	if not def then return nil end
	local e = { def = def, size = def.size or 16, base = def.base, pad = def.pad,
		cellW = def.cw, cellH = def.ch, cols = def.cols, from = def.from, count = def.count,
		w = def.w, h = def.h, advs = def.adv }
	local ok, handle = pcall(NewImageHandle)
	if not ok or not handle then return nil end
	e.handle = handle
	pcall(function() handle:Load(((_G.KR_ROOT or "KR2") .. "/Fonts/") .. def.png, "CLAMP") end)
	return e
end

--- 폴백 아틀라스에서 글리프 조회 (없으면 nil)
function M.fallback(cp)
	if not fullAtlas then
		if not metrics.full then return nil end
		fullAtlas = buildFull()
		if not fullAtlas then return nil end
	end
	local a = fullAtlas
	local idx = cp - a.from
	if idx < 0 or idx >= a.count then return nil end
	local col = idx % a.cols
	local row = math.floor(idx / a.cols)
	local g = {
		col * a.cellW / a.w, row * a.cellH / a.h,
		(col + 1) * a.cellW / a.w, (row + 1) * a.cellH / a.h,
		a.advs[idx + 1] or a.size,
	}
	return g, a
end

return M
