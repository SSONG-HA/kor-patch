"""Template (number-agnostic) dictionary helpers: '#% increased Life' -> KR template."""
from __future__ import annotations

import re

NUM_RE = re.compile(r"[-+]?\d+(?:\.\d+)?")


def shape_key(s: str) -> str:
    return re.sub(r"\s+", " ", NUM_RE.sub("#", s)).strip()


def make_template(en: str, kr: str) -> tuple[str, str] | None:
    """Return (en_shape, kr_template) where numbers are replaced by '#' in order."""
    en_nums = NUM_RE.findall(en)
    kr_nums = NUM_RE.findall(kr)
    if len(en_nums) != len(kr_nums):
        return None
    en_t = NUM_RE.sub("#", en)
    kr_t = NUM_RE.sub("#", kr)
    # round-trip check: substituting the original numbers back must reproduce kr
    back = kr_t
    for n in kr_nums:
        back = back.replace("#", n, 1)
    if back != kr:
        return None
    return en_t, kr_t


def apply_template(kr_t: str, numbers: list[str]) -> str:
    out = kr_t
    for n in numbers:
        out = out.replace("#", n, 1)
    return out
