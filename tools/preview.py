"""아틀라스 셀 배치/베이스라인을 눈으로 확인하기 위한 미리보기 이미지 생성.

Lua 렌더러와 같은 계산(셀 크기, base 비율, 스케일)으로 문자열을 그려 본다.
"""
from __future__ import annotations

import json
import os
import sys

from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FONTS = os.path.join(ROOT, "src", "KR", "Fonts")


def load_metrics():
    text = open(os.path.join(FONTS, "metrics.lua"), encoding="utf-8").read()
    import re
    codes = [int(x) for x in re.search(r"codes=\{(.*?)\}", text, re.S).group(1).split(",")]
    sizes = []
    for m in re.finditer(r'\{size=(\d+),png="([^"]+)",w=(\d+),h=(\d+),cw=(\d+),ch=(\d+),cols=(\d+),base=(\d+),pad=(\d+),adv=\{([^}]*)\}\}', text):
        sizes.append(dict(size=int(m.group(1)), png=m.group(2), w=int(m.group(3)), h=int(m.group(4)),
                          cw=int(m.group(5)), ch=int(m.group(6)), cols=int(m.group(7)),
                          base=int(m.group(8)), pad=int(m.group(9)),
                          adv=[int(v) for v in m.group(10).split(",")]))
    return codes, sizes


def render(lines, size=16, base_ratio=0.80):
    codes, sizes = load_metrics()
    defn = min((s for s in sizes if s["size"] >= size), key=lambda s: s["size"])
    atlas = Image.open(os.path.join(FONTS, defn["png"])).convert("RGBA")
    index = {cp: i for i, cp in enumerate(codes)}
    scale = size / defn["size"]
    cellW, cellH = defn["cw"] * scale, defn["ch"] * scale
    W, lineH = 900, size
    img = Image.new("RGBA", (W, lineH * len(lines) + 60), (16, 16, 16, 255))
    draw = ImageDraw.Draw(img)
    for li, s in enumerate(lines):
        y = 30 + li * lineH
        x = 8.0
        for ch in s:
            cp = ord(ch)
            i = index.get(cp)
            if i is None:
                x += size * 0.5
                continue
            col, row = i % defn["cols"], i // defn["cols"]
            box = (col * defn["cw"], row * defn["ch"], (col + 1) * defn["cw"], (row + 1) * defn["ch"])
            cell = atlas.crop(box).resize((int(cellW), int(cellH)), Image.LANCZOS)
            gx = int(x - defn["pad"] * scale)
            gy = int(y + base_ratio * size - defn["base"] * scale)
            img.alpha_composite(cell, (gx, gy))
            x += defn["adv"][i] * scale
        # 기준선 표시
        draw.line([(0, y + base_ratio * size), (W, y + base_ratio * size)], fill=(80, 80, 200, 255), width=1)
    out = os.path.join(ROOT, "build", "preview.png")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    img.save(out)
    print("preview:", out)


if __name__ == "__main__":
    render([
        "생명력: 3,563   에너지 보호막: 5,332",
        "화염 저항 +35%  냉기 저항 +35%  번개 저항 +40%",
        "지속 카오스 피해 배율 +50%",
        "총 DPS: 145,419.9 (지속 피해 포함)",
        "주요 스킬: 영혼 분리 (액티브)",
    ])
