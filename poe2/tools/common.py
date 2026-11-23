"""PoE2 한글 패처 데이터 파이프라인 공용 도우미.

PoE1(kor-patch)의 tools/common.py 와 같은 규칙을 쓰되, 경로만 PoE2(/src/KR2, poe2/data)로
바꿨습니다. 숫자 정규화(shape)는 런타임 shape.lua 와 반드시 같아야 합니다.
"""
from __future__ import annotations

import html
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))     # 저장소 루트
SRC = os.path.join(ROOT, "src", "KR2")
DATA = os.path.join(ROOT, "poe2", "data")
CACHE = os.path.join(ROOT, "poe2", "cache")

# PoB2 영문 원본 소스 (헤드리스 실행·데이터 대조에 쓴다)
POB2 = os.environ.get("POB2_SRC", "/workspace/work/pob2m/src")

for d in (CACHE, DATA, SRC):
    os.makedirs(d, exist_ok=True)


def fetch(url: str, name: str | None = None, force: bool = False) -> str:
    """url 을 cache/ 에 저장하고 텍스트를 돌려준다."""
    if name is None:
        name = re.sub(r"[^A-Za-z0-9._-]+", "_", url)[-120:]
    path = os.path.join(CACHE, name)
    if os.path.exists(path) and not force and os.path.getsize(path) > 256:
        return open(path, encoding="utf-8", errors="ignore").read()
    tmp = path + ".part"
    for _ in range(4):
        r = subprocess.run(["curl", "-sSL", "--max-time", "180", "-o", tmp, url], capture_output=True)
        if r.returncode == 0 and os.path.exists(tmp) and os.path.getsize(tmp) > 256:
            os.replace(tmp, path)
            return open(path, encoding="utf-8", errors="ignore").read()
    raise RuntimeError("fetch failed: %s" % url)


def fetch_json(url: str, name: str, force: bool = False):
    return json.loads(fetch(url, name, force))


def save_json(name: str, obj) -> str:
    path = os.path.join(DATA, name)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=0, sort_keys=True)
    return path


def load_json(name: str):
    with open(os.path.join(DATA, name), encoding="utf-8") as f:
        return json.load(f)


def load_lua_table(lua_path: str):
    """'return { ... }' 형태의 PoB 데이터 .lua 를 LuaJIT 으로 읽는다."""
    sys.path.insert(0, os.environ.get("LUAJIT_PATH", "/workspace/.local/lib/python3.12/site-packages"))
    try:
        from lupa.luajit21 import LuaRuntime
    except ImportError:  # pragma: no cover
        from lupa import LuaRuntime

    lua = LuaRuntime(unpack_returned_tuples=True, encoding="utf-8")
    lua_dir = os.path.dirname(os.path.abspath(lua_path)).replace("\\", "/")
    lua_path = os.path.abspath(lua_path).replace("\\", "/")
    return lua.execute(
        "package.path = %r .. '/?.lua;' .. package.path; local f, err = loadfile(%r); "
        "if not f then error(err) end; return f(...)" % (lua_dir, lua_path)
    )


def load_pob_item_bases() -> dict:
    """PoB2 Data/Bases/*.lua 를 모두 읽어 {베이스 이름: {...}} 로 합친다."""
    folder = os.path.join(POB2, "Data", "Bases")
    out = {}
    lua = _lua()
    lua.execute("""
function __load_bases(path)
  local itemBases = {}
  local chunk = assert(loadfile(path))
  chunk(itemBases)
  return itemBases
end
""")
    for name in sorted(os.listdir(folder)):
        if not name.endswith(".lua"):
            continue
        table = lua.globals()["__load_bases"](os.path.join(folder, name))
        out.update(lua_to_py(table))
    return out


def _lua():
    sys.path.insert(0, os.environ.get("LUAJIT_PATH", "/workspace/.local/lib/python3.12/site-packages"))
    from lupa.luajit21 import LuaRuntime

    return LuaRuntime(unpack_returned_tuples=True, encoding="utf-8")


def lua_to_py(obj):
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


# GGG 문자열 태그: "[Critical|Critical Hit]" → "Critical Hit", "[Blind]" → "Blind"
GGG_PIPE_RE = re.compile(r"\[([^\[\]|]*)\|([^\[\]]*)\]")
GGG_BARE_RE = re.compile(r"\[([^\[\]]*)\]")
GGG_TAG_RE = re.compile(r"<[^>]+>\{([^}]+)\}")


def strip_ggg(s: str) -> str:
    """게임/PoB 가 화면에 그릴 때 지우는 `[키워드|표시문]` 태그를 지운다."""
    s = GGG_TAG_RE.sub(r"\1", s)
    for _ in range(4):
        new = GGG_PIPE_RE.sub(r"\2", s)
        new = GGG_BARE_RE.sub(r"\1", new)
        if new == s:
            break
        s = new
    # poedb 가 대괄호를 빼고 남긴 `Key|표시문` 꼬리표 정리
    s = re.sub(r"(?<![A-Za-z0-9])([A-Za-z][A-Za-z0-9_]*)\|", "", s)
    return s


def page_links(text: str, lang: str) -> dict[str, str]:
    """slug -> 링크 텍스트 (첫 등장 우선)."""
    out: dict[str, str] = {}
    for href, body in re.findall(r'<a[^>]+href="(/%s/[^"#?]*)"[^>]*>(.*?)</a>' % lang, text, flags=re.S):
        label = strip_tags(body).strip()
        if not label:
            continue
        slug = href[len(lang) + 2:]
        out.setdefault(slug, label)
    return out


def page_slugs(text: str, lang: str) -> list[str]:
    """링크가 걸린 slug 목록 (등장 순서, 중복 제거)."""
    out: list[str] = []
    seen = set()
    for slug in re.findall(r'href="/%s/([^"#?]+)"' % lang, text):
        if slug not in seen:
            seen.add(slug)
            out.append(slug)
    return out


# ---------------------------------------------------------------- normalization

COLOR_RE = re.compile(r"\^(?:x[0-9A-Fa-f]{6}|[0-9])")


def strip_escapes(s: str) -> str:
    return COLOR_RE.sub("", s)


_DIGITS = r"(?:\d{1,3}(?:,\d{3})+|\d+)"
NUM_TOKEN_RE = re.compile(r"[+-]?\(?%s(?:\.\d+)?(?:-%s(?:\.\d+)?)?\)?" % (_DIGITS, _DIGITS))


def _dash(s: str) -> str:
    return s.replace("\u2014", "-").replace("\u2013", "-")


def shape(text: str) -> str:
    """조회 키: 숫자(부호·괄호·범위 포함)를 '#' 로, 'X to Y' 는 'X-Y' 로."""
    s = _dash(text)
    s = re.sub(r"(?<=\d)\s+to\s+(?=\d)", "-", s)
    out = []
    i, n = 0, len(s)
    while i < n:
        m = NUM_TOKEN_RE.match(s, i)
        if m and m.end() > i:
            out.append("#")
            i = m.end()
            continue
        out.append(s[i])
        i += 1
    return "".join(out).replace(" ", "").replace("\u00a0", "")


def norm_space(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()
