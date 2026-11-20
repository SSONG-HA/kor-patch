"""아틀라스 PNG + metrics.lua 로 한글 문자열을 실제로 그려 PNG 로 저장합니다.

PoB 런타임(src/KR/draw.lua, src/KR/font.lua)과 같은 규칙만 씁니다.
  - 글자 순번 = metrics.codes 에서의 위치 (1부터)
  - 셀 = (code 위치 % cols, code 위치 // cols) * (cw, ch)
  - 글자 폭 = adv[i] * (그리는 크기 / 아틀라스 크기)

metrics 나 아틀라스가 어긋나 있으면 눈으로 바로 보입니다.
한글 글자만 그립니다(영문은 엔진 폰트 담당이라 이 검사 대상이 아님).

사용:
  python3 tools/render_check.py "생명력 숙련" "정의의 화염" --out /workspace/scratch/label.png
  python3 tools/render_check.py "생명력 숙련" --metrics old/metrics.lua --size 16
"""
from __future__ import annotations

import argparse
import os
import sys

from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import SRC  # noqa: E402

FONTS = os.path.join(SRC, "Fonts")


def load_metrics(path: str) -> dict:
    """metrics.lua 를 lupa 로 읽어 파이썬 dict 로 바꿉니다."""
    try:
        from lupa.luajit21 import LuaRuntime
    except ImportError:
        from lupa import LuaRuntime
    lua = LuaRuntime(unpack_returned_tuples=True, encoding="utf-8")
    return lua.eval("function(p) return dofile(p) end")(path)


def as_list(tbl) -> list:
    if tbl is None:
        return []
    return [tbl[i] for i in range(1, len(tbl) + 1)]


def layout(metrics: dict, text: str, height: int, scale: float = 1.0):
    """(글자, 셀 좌표, 폭) 목록. metrics 에 없는 글자는 None 셀로 표시합니다."""
    codes = [int(c) for c in as_list(metrics["codes"])]
    position = {cp: i for i, cp in enumerate(codes)}
    sizes = as_list(metrics["sizes"])
    target = height * scale
    defn = sizes[0]
    for s in sizes:
        defn = s
        if int(s["size"]) >= target:
            break
    size = int(defn["size"])
    k = height / size
    advs = as_list(defn["adv"])
    cw, ch, cols = int(defn["cw"]), int(defn["ch"]), int(defn["cols"])
    out = []
    for ch_text in text:
        if ch_text == " ":
            out.append((None, None, height * 0.3))
            continue
        cp = ord(ch_text)
        i = position.get(cp)
        cell = None
        adv = height * 0.5
        if i is not None and i < len(advs):
            col, row = i % cols, i // cols
            cell = (col * cw, row * ch, (col + 1) * cw, (row + 1) * ch)
            adv = int(advs[i]) * k
        out.append((ch_text, cell, adv))
    return out, defn, k


def render(texts: list[str], height: int, metrics_path: str, out: str,
           scale: float = 1.0, bg=(32, 34, 38)) -> str:
    metrics = load_metrics(metrics_path)
    rows = []
    width = 0
    for text in texts:
        glyphs, defn, k = layout(metrics, text, height, scale)
        rows.append((text, glyphs, defn, k))
        width = max(width, int(sum(g[2] for g in glyphs)) + 24)
    line_h = int(max(height * 1.6, 20))
    im = Image.new("RGB", (max(width, 80), line_h * len(rows) + 16), bg)
    draw = ImageDraw.Draw(im)
    atlases = {}
    y = 8
    for text, glyphs, defn, k in rows:
        png = os.path.join(FONTS, str(defn["png"]))
        atlas = atlases.get(png)
        if atlas is None:
            atlas = Image.open(png).convert("RGBA")
            atlases[png] = atlas
        pad = int(defn["pad"])
        base = int(defn["base"])
        cw, ch = int(defn["cw"]), int(defn["ch"])
        x = 12.0
        baseline = y + 0.8 * height
        for _ch, cell, adv in glyphs:
            if cell:
                x0, y0, x1, y1 = cell
                glyph = atlas.crop((x0, y0, x1, y1))
                w, h = max(1, int(cw * k)), max(1, int(ch * k))
                glyph = glyph.resize((w, h))
                top = int(round(baseline - base * k))
                left = int(round(x - pad * k))
                im.paste(glyph, (left, top), glyph)
                draw.rectangle((left, top, left + w - 1, top + h - 1),
                               outline=(70, 74, 82))
            else:
                draw.rectangle((int(x), int(baseline - height * 0.6),
                                int(x + adv) - 2, int(baseline - height * 0.6) + 2),
                               fill=(120, 60, 60))
            x += adv
        y += line_h
    im.save(out)
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("texts", nargs="+", help="그려 볼 한글 문자열")
    ap.add_argument("--size", type=int, default=16, help="화면 글자 높이")
    ap.add_argument("--metrics", default=os.path.join(FONTS, "metrics.lua"))
    ap.add_argument("--out", default=os.path.join("/workspace/scratch", "font_check.png"))
    ap.add_argument("--scale", type=float, default=1.0, help="화면 배율")
    args = ap.parse_args()
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    path = render(args.texts, args.size, args.metrics, args.out, args.scale)
    print(path)


if __name__ == "__main__":
    main()
