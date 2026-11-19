"""Shared helpers for the PoB-KR-Patcher data pipeline."""
from __future__ import annotations

import hashlib
import html
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

# 개발 트리(src/KR) 와 배포판(../KR, 도구는 하위 폴더) 모두에서 동작하도록 경로를 찾는다
if os.path.isdir(os.path.join(ROOT, "src", "KR")):
    SRC = os.path.join(ROOT, "src", "KR")
elif os.path.isdir(os.path.join(ROOT, "KR")):
    SRC = os.path.join(ROOT, "KR")
else:
    SRC = os.path.join(ROOT, "KR")

if os.path.isdir(os.path.join(ROOT, "data")):
    DATA = os.path.join(ROOT, "data")
else:
    DATA = os.path.join(HERE, "data")

CACHE = os.path.join(ROOT, "cache") if not os.path.isdir(os.path.join(HERE, "cache")) else os.path.join(HERE, "cache")
# PoB 영문 원본 소스 (선택). 있으면 젬 목록·T데이터 커버리지 확인에 쓰인다.
#   git clone --depth 1 https://github.com/PathOfBuildingCommunity/PathOfBuilding
POB = os.environ.get("POB_SRC", "").strip()
# lupa 를 별도 경로에 설치한 환경을 위한 보조 경로 (없으면 무시)
LUAJIT_PY = os.environ.get("LUAJIT_PATH", "").strip()

for d in (CACHE, DATA, SRC):
    os.makedirs(d, exist_ok=True)


def fetch(url: str, name: str | None = None, force: bool = False) -> str:
    """Download url into cache/ and return the text."""
    if name is None:
        name = re.sub(r"[^A-Za-z0-9._-]+", "_", url)[-120:]
    path = os.path.join(CACHE, name)
    if os.path.exists(path) and not force and os.path.getsize(path) > 256:
        return open(path, encoding="utf-8", errors="ignore").read()
    tmp = path + ".part"
    for attempt in range(4):
        r = subprocess.run(["curl", "-sSL", "--max-time", "180", "-o", tmp, url], capture_output=True)
        if r.returncode == 0 and os.path.exists(tmp) and os.path.getsize(tmp) > 256:
            os.replace(tmp, path)
            return open(path, encoding="utf-8", errors="ignore").read()
    raise RuntimeError("fetch failed: %s" % url)


def load_lua_table(lua_path: str):
    """Load a PoB data .lua file that 'return's a table, using LuaJIT via lupa."""
    if LUAJIT_PY and os.path.isdir(LUAJIT_PY):
        sys.path.insert(0, LUAJIT_PY)
    try:
        from lupa.luajit21 import LuaRuntime
    except ImportError:
        from lupa import LuaRuntime

    lua = LuaRuntime(unpack_returned_tuples=True, encoding="utf-8")
    lua_dir = os.path.dirname(os.path.abspath(lua_path)).replace("\\", "/")
    lua_path = os.path.abspath(lua_path).replace("\\", "/")
    mod = lua.execute(
        "package.path = %r .. '/?.lua;' .. package.path; local f, err = loadfile(%r); "
        "if not f then error(err) end; return f()" % (lua_dir, lua_path)
    )
    return mod


def lua_to_py(obj):
    """Convert lupa Lua table -> python dict/list/scalar."""
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj
    try:
        items = list(obj.items())
    except AttributeError:
        return obj
    if not items:
        return {}
    keys = [k for k, _ in items]
    if all(isinstance(k, int) for k in keys):
        keys.sort()
        if keys == list(range(1, len(keys) + 1)):
            return [lua_to_py(obj[k]) for k in keys]
    return {k: lua_to_py(v) for k, v in items}


TAG_RE = re.compile(r"<[^>]+>")


def strip_tags(s: str) -> str:
    return html.unescape(TAG_RE.sub("", s))


def page_links(text: str, lang: str) -> dict[str, str]:
    """slug -> link text for /<lang>/... anchors, first occurrence wins."""
    out: dict[str, str] = {}
    for href, body in re.findall(r'<a[^>]+href="(/%s/[^"#?]*)"[^>]*>(.*?)</a>' % lang, text, flags=re.S):
        label = strip_tags(body).strip()
        if not label:
            continue
        slug = href[len(lang) + 2:]
        out.setdefault(slug, label)
    return out


NAV_NOISE = {
    "Keywords", "Bloodline_Ascendancy_class", "Patreon", "Economy", "Items", "Gem",
    "Skill_Gems", "Support_Gems", "Transfigured_Gems", "Exceptional", "Oil", "Keyword",
    "", "poe2db",
}


def clean_pairs(pairs: dict[str, tuple[str, str]]) -> dict[str, tuple[str, str]]:
    return {k: v for k, v in pairs.items() if k not in NAV_NOISE}


def save_json(name: str, obj) -> str:
    path = os.path.join(DATA, name)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=0, sort_keys=True)
    return path


def load_json(name: str):
    with open(os.path.join(DATA, name), encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------- normalization

COLOR_RE = re.compile(r"\^(?:x[0-9A-Fa-f]{6}|[0-9])")


def strip_escapes(s: str) -> str:
    return COLOR_RE.sub("", s)


NUM_RE = re.compile(r"[-+]?\d+(?:\.\d+)?")


def numpad(s: str) -> tuple[str, list[str]]:
    """Replace every numeric token with '#' and return (template, numbers)."""
    nums = NUM_RE.findall(s)
    return NUM_RE.sub("#", s), nums


def norm_space(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def shift_join(s: str) -> str:
    """poedb keeps a stray space before % and around values ('+15 %'); the game does not."""
    s = re.sub(r"\s+%", "%", s)
    s = re.sub(r"%\s+", "%", s)
    s = re.sub(r"\((#[^)]*)\)%", r"(\1)%", s)
    return s
