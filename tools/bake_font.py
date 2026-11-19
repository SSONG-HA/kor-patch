"""Bake Korean glyph atlases (PNG) + compact metrics for the PoB-KR runtime renderer.

The engine's own fonts are ASCII bitmap atlases, so Korean text is drawn by the Lua
layer as textured quads from these atlases.
"""
from __future__ import annotations

import json
import math
import os
import sys

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import DATA, SRC  # noqa: E402

REQUIRED_INPUTS = ("gems.json", "passives_names.json", "passives_stats.json",
                   "uniques.json", "bases.json", "mods_exact.json")


def check_inputs():
    missing = [f for f in REQUIRED_INPUTS if not os.path.exists(os.path.join(DATA, f))]
    if missing:
        print("먼저 데이터 수집 스크립트를 실행하세요 (gems.py, passives.py, items.py).")
        print("없는 파일:", ", ".join(missing))
        raise SystemExit(1)


FONT_CACHE = os.environ.get("KR_FONT_DIR", os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "cache"))
os.makedirs(FONT_CACHE, exist_ok=True)
FONT_PATH = os.environ.get("KR_FONT", os.path.join(FONT_CACHE, "NotoSansKR.ttf"))
FONT_URL = "https://raw.githubusercontent.com/google/fonts/main/ofl/notosanskr/NotoSansKR%5Bwght%5D.ttf"


def ensure_font() -> str:
    if os.path.exists(FONT_PATH):
        return FONT_PATH
    import subprocess
    target = FONT_PATH
    print("한글 폰트 다운로드:", FONT_URL)
    subprocess.run(["curl", "-sSL", "-o", target, FONT_URL], check=True)
    return target
OUT_DIR = os.path.join(SRC, "Fonts")
# 1x sizes and their 2x/3x counterparts (DPI scaling picks the nearest baked size)
SIZES = [12, 14, 16, 18, 20, 24, 28, 32, 40, 48, 64]
MAX_W, MAX_H = 4096, 2048

os.makedirs(OUT_DIR, exist_ok=True)


def used_chars() -> set[str]:
    chars: set[str] = set()
    for name in ("gems.json", "passives_names.json", "passives_stats.json",
                 "uniques.json", "bases.json", "mods_exact.json", "ui_ko.json",
                 "overrides_ko.json"):
        path = os.path.join(DATA, name)
        if not os.path.exists(path):
            continue
        data = json.load(open(path, encoding="utf-8"))
        values = data.values() if name != "mods_exact.json" else [v["kr"] for v in data.values()]
        for v in values:
            for ch in str(v):
                if ord(ch) > 127:
                    chars.add(ch)
    return chars


def grid(count: int, cw: int, ch: int) -> tuple[int, int]:
    """Pick a column count so that count cells fit inside MAX_W x MAX_H."""
    for cols in range(max(1, count), 0, -1):
        rows = int(math.ceil(count / cols))
        if cols * cw <= MAX_W and rows * ch <= MAX_H:
            return cols, rows
    raise RuntimeError("charset too large for one atlas at this size")


def main() -> None:
    global FONT_PATH
    check_inputs()
    FONT_PATH = ensure_font()
    chars = sorted(used_chars())
    print("distinct non-ASCII chars: %d" % len(chars))
    manifest = []

    for S in SIZES:
        Sf = max(8, int(round(S * 0.94)))   # 가독성을 위해 영문 줄 높이에 맞춘 선명한 크기
        font = ImageFont.truetype(FONT_PATH, Sf)
        try:
            font.set_variation_by_axes([500])  # Medium 굵기 (기본값 100 Thin 방지)
        except Exception:
            pass
        ascent, descent = font.getmetrics()
        maxAdv = max((font.getlength(ch) for ch in chars), default=S)
        cellW = int(math.ceil(maxAdv)) + 4
        cellH = ascent + descent + 2
        cols, rows = grid(len(chars), cellW, cellH)
        W, H = cols * cellW, rows * cellH
        img = Image.new("RGBA", (W, H), (255, 255, 255, 0))
        draw = ImageDraw.Draw(img)
        base_off = ascent
        left_pad = 2
        advs = []
        for i, ch in enumerate(chars):
            col, row = i % cols, i // cols
            draw.text((col * cellW + left_pad, row * cellH + base_off), ch, font=font,
                      fill=(255, 255, 255, 255), anchor="ls")
            advs.append(int(round(font.getlength(ch))))
        png = "kr_%02d.png" % S
        img.save(os.path.join(OUT_DIR, png), optimize=True)
        manifest.append({
            "size": S, "png": png, "w": W, "h": H, "cellW": cellW, "cellH": cellH,
            "cols": cols, "base": base_off, "pad": left_pad, "advs": advs,
        })
        print("  size %2d: %dx%d, %d cells (%.1f KB)" % (
            S, W, H, len(chars), os.path.getsize(os.path.join(OUT_DIR, png)) / 1024))

    # ---- 전체 한글 음절(11,172자) 폴백 아틀라스 (사전에 없는 한글 텍스트용)
    S_FULL = 16
    full_codes = list(range(0xAC00, 0xD7A4))
    Sf_full = max(8, int(round(S_FULL * 0.94)))
    font = ImageFont.truetype(FONT_PATH, Sf_full)
    try:
        font.set_variation_by_axes([500])
    except Exception:
        pass
    ascent_f, descent_f = font.getmetrics()
    maxAdv_f = max((font.getlength(chr(c)) for c in full_codes), default=S_FULL)
    cellW = int(math.ceil(maxAdv_f)) + 4
    cellH = ascent_f + descent_f + 2
    cols, rows = grid(len(full_codes), cellW, cellH)
    W, H = cols * cellW, rows * cellH
    img = Image.new("RGBA", (W, H), (255, 255, 255, 0))
    draw = ImageDraw.Draw(img)
    base_off = ascent_f
    left_pad = 2
    advs = []
    for i, cp in enumerate(full_codes):
        col, row = i % cols, i // cols
        ch = chr(cp)
        draw.text((col * cellW + left_pad, row * cellH + base_off), ch, font=font,
                  fill=(255, 255, 255, 255), anchor="ls")
        advs.append(int(round(font.getlength(ch))))
    img.save(os.path.join(OUT_DIR, "kr_full.png"), optimize=True)
    print("  full: %dx%d, %d syllables (%.1f KB)" % (
        W, H, len(full_codes), os.path.getsize(os.path.join(OUT_DIR, "kr_full.png")) / 1024))

    lines = ["-- PoB-KR : 글리프 메트릭 (자동 생성)", "return {", "codes={"]
    lines.append(",".join(str(ord(c)) for c in chars))
    lines.append("},")
    lines.append("sizes={")
    for m in manifest:
        lines.append('{size=%d,png="%s",w=%d,h=%d,cw=%d,ch=%d,cols=%d,base=%d,pad=%d,adv={%s}},' % (
            m["size"], m["png"], m["w"], m["h"], m["cellW"], m["cellH"], m["cols"],
            m["base"], m["pad"], ",".join(str(a) for a in m["advs"])))
    lines.append("},")
    lines.append('full={png="kr_full.png",w=%d,h=%d,cw=%d,ch=%d,cols=%d,base=%d,pad=%d,from=%d,count=%d,adv={%s}},' % (
        W, H, cellW, cellH, cols, base_off, left_pad, full_codes[0], len(full_codes),
        ",".join(str(a) for a in advs)))
    lines.append("}")
    with open(os.path.join(OUT_DIR, "metrics.lua"), "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + "\n")
    total = sum(os.path.getsize(os.path.join(OUT_DIR, f)) for f in os.listdir(OUT_DIR))
    print("metrics.lua %.1f KB / fonts total %.2f MB" % (
        os.path.getsize(os.path.join(OUT_DIR, "metrics.lua")) / 1024, total / 1048576))


if __name__ == "__main__":
    main()
