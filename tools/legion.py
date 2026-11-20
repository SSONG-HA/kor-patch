"""군단 주얼(무궁한 주얼) 번역 사전 — poedb.tw/kr + PoB 원본 데이터.

poedb 의 Timeless_Jewel 페이지는 군단 주얼이 바꾸는 패시브(AlternatePassiveSkills)
376개와 추가 속성(Passive Additions) 337개를 영어/한국어 페이지에 **같은 순서**로
싣고 있습니다. 이 스크립트는 두 언어 페이지의 같은 탭을 읽어 이름과 스탯 줄을
짝지어 사전을 만듭니다.

만들어지는 파일:
  data/legion_exact.json      {영문: 한글}            숫자가 없는 이름·문구
  data/legion_templates.json  {모양 키: 한글 템플릿}  숫자가 들어간 스탯 줄
  data/legion_report.json     짝짓기 결과와 커버리지 기록

PoB 원본(POB_SRC)이 있으면 `Data/TimelessJewelData/LegionPassives.lua` 와
`Data/Uniques/jewel.lua` 를 읽어, **PoB 가 실제로 화면에 그리는 문자열**을 기준으로
커버리지를 계산합니다. (PoB 는 정복된 노드의 이름과 스탯 줄을 이 두 파일에서
그대로 가져다 그립니다.)
"""
from __future__ import annotations

import html
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import POB, fetch, load_lua_table, lua_to_py, norm_space, save_json  # noqa: E402
from items import NUM_TOKEN_RE, shape  # noqa: E402

PAGE = "https://poedb.tw/%s/Timeless_Jewel"
TAG_RE = re.compile(r"<[^>]+>")
VALUE_RE = re.compile(r"<span class='mod-value'>(.*?)</span>", re.S)

# 탭 이름 (한국어 페이지는 탭 id 까지 번역되어 있다)
TABS = {
    "passives": ("TimelessJewelPassive", "무궁한주얼Passive"),
    "additions": ("TimelessJewelPassiveAdditions", "무궁한주얼PassiveAdditions"),
    "alternate": ("AlternatePassive", "AlternatePassive"),
}

# ── 군단 주얼 아이템 문구 ─────────────────────────────────────────────────────
# 문장 틀은 poedb.tw/kr 의 고유 주얼 카드에서 그대로 가져왔습니다.
#   찬란한 허영심  : 지바콰의 이름으로 희생된 (100—8000)명의 피로 적셔짐
#   잔인한 속박    : 발바라의 아카라에 속한 데카라 (500—8000)명의 봉사 상징
#   치명적인 긍지  : 카옴 휘하 전사 (10000—18000)명에게 지휘권 행사
#   호전적인 신념  : 고위 템플러 막사리우스가 개종시킨 새로운 신도 (2000—10000)명을 찬미하기 위해 조각됨
#   고상한 오만    : 카디로를 기념하기 위해 제작한 주화 (2000—160000)개
#   영웅적인 비극  : 보라나의 핏줄이 행한 노래로 남을 공적 (100—8000)개 추모
# 카드에는 기본 변형 하나만 실려 있으므로, 나머지 변형은 정복자 이름만 바꿔 만듭니다.
JEWEL_SENTENCES = {
    "Glorious Vanity": ("{name}의 이름으로 희생된 %1명의 피로 적셔짐",
                        "반경 내 패시브 스킬은 바알의 지배를 받음"),
    "Brutal Restraint": ("{name}의 아카라에 속한 데카라 %1명의 봉사 상징",
                         "반경 내 패시브 스킬은 마라케스의 지배를 받음"),
    "Lethal Pride": ("{name} 휘하 전사 %1명에게 지휘권 행사",
                     "반경 내 패시브 스킬은 카루이의 지배를 받음"),
    "Militant Faith": ("고위 템플러 {name}가 개종시킨 새로운 신도 %1명을 찬미하기 위해 조각됨",
                       "반경 내 패시브 스킬은 템플러의 지배를 받음"),
    "Elegant Hubris": ("{name}{obj} 기념하기 위해 제작한 주화 %1개",
                       "반경 내 패시브 스킬은 영원한 제국의 지배를 받음"),
    "Heroic Tragedy": ("{name}의 핏줄이 행한 노래로 남을 공적 %1개 추모",
                       "반경 내 패시브 스킬이 칼구르의 지배를 받음"),
    # 3.30 심연(Abyss) 계열 — poedb.tw/kr 의 해당 주얼 카드 문장
    #   짓무르는 복수  : 테크로드의 예속자로 영혼을 (100—8000)개 사로잡음
    #   절망의 손아귀  : 울라만의 예속자로 영혼을 (100—8000)개 사로잡음
    #   사악한 통치    : 쿠르갈의 예속자로 영혼을 (100—8000)개 사로잡음
    #   파멸적인 열망  : 아마나무의 예속자로 영혼을 (100—8000)개 사로잡음
    #   되찾은 악의    : 조라스를 지속시키기 위해 성구함에 영혼을 (100—8000)개 속박함
    "Festering Vengeance": ("{name}의 예속자로 영혼을 %1개 사로잡음",
                            "영향을 받는 패시브들이 심연의 존재에 정복당함"),
    "Extinguishing Grasp": ("{name}의 예속자로 영혼을 %1개 사로잡음",
                            "영향을 받는 패시브들이 심연의 존재에 정복당함"),
    "Baleful Dominion": ("{name}의 예속자로 영혼을 %1개 사로잡음",
                         "영향을 받는 패시브들이 심연의 존재에 정복당함"),
    "Destructive Aspiration": ("{name}의 예속자로 영혼을 %1개 사로잡음",
                               "영향을 받는 패시브들이 심연의 존재에 정복당함"),
    "Reclaimed Malevolence": ("조라스를 지속시키기 위해 성구함에 영혼을 %1개 속박함",
                              "영향을 받는 패시브들이 심연의 존재에 정복당함"),
}

# 정복자 이름의 한국어 표기. 표기 근거를 함께 적어 둡니다.
#   카드  : poedb.tw/kr 의 해당 주얼 카드에 실린 문장
#   표    : poedb.tw/kr AlternatePassive 표 (한국어로 적힌 이름)
#   아이템: poedb.tw/kr 의 같은 인물 이름을 쓰는 고유 아이템
#   DB    : 한국어 DB(PoE2DAT 등)의 같은 문구
# 표기가 확인되지 않은 이름은 원문 표기를 그대로 씁니다. (한국어 클라이언트도
# 일부 이름은 영문으로 두고 있습니다 — 예: poedb 의 Deshret 항목 제목)
CONQUERORS = {
    # 찬란한 허영심 (바알)
    "Xibaqua": ("지바콰", "카드"),
    "Ahuana": ("아후아나", "표"),
    "Doryani": ("도리아니", "DB"),
    "Zerphi": ("제르피", "아이템 Zerphis Last Breath"),
    "Mazcotl": ("Mazcotl", "표기 미확인"),
    # 잔인한 속박 (마라케스)
    "Balbala": ("발바라", "카드"),
    "Asenath": ("아세나스", "아이템 Asenaths Gentle Touch"),
    "Nasima": ("나시마", "DB"),
    "Deshret": ("Deshret", "표기 미확인"),
    # 치명적인 긍지 (카루이)
    "Kaom": ("카옴", "카드"),
    "Rakiata": ("라키아타", "아이템 Rakiatas Dance"),
    "Akoya": ("아코야", "DB"),
    "Kiloava": ("킬로아바", "아이템 Kiloavas Bluster"),
    # 호전적인 신념 (템플러)
    "Avarius": ("아배리우스", "DB"),
    "Dominus": ("도미누스", "표"),
    "Maxarius": ("막사리우스", "카드"),
    "Venarius": ("베나리우스", "아이템 Venarius Astrolabe"),
    # 고상한 오만 (영원한 제국)
    "Cadiro": ("카디로", "카드"),
    "Chitus": ("치투스", "아이템 Chitus Needle"),
    "Victario": ("빅타리오", "아이템 Victarios Influence"),
    "Caspiro": ("카스피로", "DB"),
    # 영웅적인 비극 (칼구르)
    "Vorana": ("보라나", "카드"),
    "Medved": ("메드베드", "DB"),
    "Uhtred": ("Uhtred", "표기 미확인"),
    # 3.30 심연(Abyss) 정복자 — poedb.tw/kr 주얼 카드 문장에 적힌 표기
    "Tecrod": ("테크로드", "카드"),
    "Ulaman": ("울라만", "카드"),
    "Kurgal": ("쿠르갈", "카드"),
    "Amanamu": ("아마나무", "카드"),
    "Zorath": ("조라스", "카드"),
}

# 카드에 실린 "반경 내 패시브 스킬은 …의 지배를 받음" 문구로 확인한 세력 이름
FACTIONS = {
    "Vaal": "바알",
    "Karui": "카루이",
    "Maraketh": "마라케스",
    "Templar": "템플러",
    "Templars": "템플러",
    "Eternal Empire": "영원한 제국",
    "Kalguur": "칼구르",
    "Abyssal": "심연의 존재",
}

# 카드에서 확인한, 숫자가 없는 문구
PLAIN_LINES = {
    "Historic": "역사적인 순간",
    "Radius: Large": "반경: 큼",
    "Radius: Medium": "반경: 중간",
    "Radius: Small": "반경: 작음",
    "Timeless Jewel": "무궁한 주얼",
}

# 숫자가 들어간 문구 (아이템 머리말)
NUMBERED_LINES = {
    "Limited to: #": "중복 사용 제한: #",
}

# 호전적인 신념의 '헌신' 변형 이름 (PoB 변형 목록에 그대로 그려집니다)
DEVOTION_VARIANTS = {
    "Totem Damage": "토템 피해",
    "Brand Damage": "낙인 피해",
    "Channelling Damage": "집중 유지 피해",
    "Area Damage": "범위 피해",
    "Defences from Shield": "방패로 얻는 방어력",
    "Duration of Curses": "저주 지속시간",
    "Effect of non-Damaging Ailments": "비-피해 상태 이상 효과",
    "Elemental Ailment Duration": "원소 상태 이상 지속시간",
    "Elemental Damage": "원소 피해",
    "Elemental Resistances": "모든 원소 저항",
    "Mana Regen": "마나 재생",
    "Minion Attack and Cast Speed": "소환수 공격 및 시전 속도",
    "Minions Accuracy Rating": "소환수 정확도",
    "Non-Curse Aura Effect": "비-저주 오라 효과",
    "Skill Cost": "스킬의 마나 소모",
}

# PoB 데이터와 poedb 문구가 미세하게 달라 짝짓기로는 잡히지 않는 줄.
# (poedb 는 "Gain 1 Endurance Charges …" 복수형, PoB 는 단수형)
# 한국어는 poedb 카드에 실린 문장을 그대로 씁니다.
POB_FIXUPS = {
    "Gain 1 Endurance Charge when Ward Breaks": "수호가 부서질 때 인내 충전 %1 획득",
    "Gain 1 Power Charge when Ward Breaks": "수호가 부서질 때 권능 충전 %1 획득",
    "Gain 1 Frenzy Charge when Ward Breaks": "수호가 부서질 때 격분 충전 %1 획득",
}


# ── 페이지 읽기 ──────────────────────────────────────────────────────────────
def page(lang: str) -> str:
    return fetch(PAGE % lang, "timeless_jewel_%s.html" % lang)


def section(text: str, names: tuple) -> str:
    for name in names:
        m = re.search(r'<div id="%s" class="tab-pane fade">' % re.escape(name), text)
        if not m:
            continue
        start = m.end()
        nxt = re.search(r'<div id="[^"]+" class="tab-pane fade">', text[start:])
        return text[start:start + nxt.start()] if nxt else text[start:]
    return ""


def strip(s: str) -> str:
    s = s.replace('<span class="ndash">\u2014</span>', "\u2014")
    return html.unescape(TAG_RE.sub("", s)).strip()


def segments(raw: str) -> list:
    """poedb 문구 HTML -> [('t', 글), ('v', 굴림값), …]

    굴림값 span 안에는 — 를 그리는 <span class="ndash"> 가 한 번 더 들어 있어,
    먼저 그것을 글자로 바꿔 두지 않으면 span 이 중간에서 끊깁니다.
    """
    raw = raw.replace('<span class="ndash">\u2014</span>', "\u2014")
    raw = raw.replace('<span class="ndash">\u2013</span>', "\u2014")
    out = []
    for i, part in enumerate(VALUE_RE.split(raw)):
        text = html.unescape(TAG_RE.sub("", part if i % 2 == 0 else strip(part)))
        if i % 2 == 1:
            out.append(("v", text.strip()))
        elif text.strip():
            out.append(("t", text))
    return out


def cards(sec: str) -> list:
    """AlternatePassiveSkills 카드 목록 (이름 + 스탯 줄들)"""
    out = []
    for block in sec.split('<div class="col"><div class="d-flex border-top rounded">')[1:]:
        name = re.search(r'<a class="AlternatePassiveSkills"[^>]*href="[^"]*">([^<]*)</a>', block)
        stats = []
        for mod in re.findall(r'<div class="implicitMod">(.*?)</div>', block, re.S):
            if "item_description" in mod:
                continue
            stats += [line for line in re.split(r"<br\s*/?>", mod) if strip(line)]
        out.append({"name": strip(name.group(1)) if name else "", "stats": stats})
    return out


def rows(sec: str) -> list:
    """Code 열이 있는 표 (Passive Additions)"""
    out = []
    for row in re.findall(r"<tr>(.*?)</tr>", sec, re.S):
        cells = re.findall(r"<td>(.*?)</td>", row, re.S)
        if len(cells) >= 4:
            out.append({"code": strip(cells[-1]), "desc": cells[2]})
    return out


# ── 문장 짝짓기 ──────────────────────────────────────────────────────────────
def _dash(s: str) -> str:
    return s.replace("\u2014", "-").replace("\u2013", "-").strip()


def pair_line(en_raw: str, kr_raw: str):
    """영문/한글 한 줄을 짝지어 {"kind","en","key","kr"} 를 돌려줍니다.

    숫자 자리표시는 %1, %2 … 이고 emit_lua 가 templates.lua 로 내보냅니다.
    한국어에만 있는 숫자(예: "1초당")는 그대로 둡니다.
    """
    se, sk = segments(en_raw), segments(kr_raw)
    en_text = norm_space("".join(t for _, t in se))
    kr_text = norm_space("".join(t for _, t in sk))
    if not en_text or not kr_text:
        return None
    key = shape(en_text)
    if "#" not in key:
        return {"kind": "exact", "en": en_text, "kr": kr_text}

    en_slots = [t for kind, t in se if kind == "v"]
    kr_slots = [t for kind, t in sk if kind == "v"]
    if en_slots:
        # 굴림값 span 이 있는 문장: 같은 굴림값을 가진 자리끼리 짝지음
        if len(en_slots) != len(kr_slots):
            return None
        mapping, used = {}, set()
        for i, kv in enumerate(kr_slots):
            for j, uv in enumerate(en_slots):
                if j not in used and _dash(uv) == _dash(kv):
                    mapping[i] = j
                    used.add(j)
                    break
        if len(mapping) != len(kr_slots):
            return None
        parts, vi = [], 0
        for kind, text in sk:
            if kind == "v":
                parts.append("%%%d" % (mapping[vi] + 1))
                vi += 1
            else:
                parts.append(text)
        return {"kind": "tpl", "en": en_text, "key": key, "kr": norm_space("".join(parts))}

    # 굴림값 span 이 없는 문장: 숫자를 값으로 맞춰 자리표시
    en_nums = NUM_TOKEN_RE.findall(_dash(en_text))
    kr_nums = NUM_TOKEN_RE.findall(_dash(kr_text))
    if not en_nums or not kr_nums:
        return None
    mapping, used = [], set()
    for kn in kr_nums:
        value = kn.lstrip("+").strip("()")
        idx = None
        for j, en in enumerate(en_nums):
            if j not in used and en.lstrip("+").strip("()") == value:
                idx = j
                break
        if idx is not None:
            used.add(idx)
        mapping.append(idx)
    if len(used) != len(en_nums):
        return None  # 영문 숫자를 다 설명하지 못하면 건너뜀
    counter = {"n": 0}

    def repl(m):
        idx = mapping[counter["n"]]
        counter["n"] += 1
        return "%%%d" % (idx + 1) if idx is not None else m.group(0)

    return {"kind": "tpl", "en": en_text, "key": key,
            "kr": norm_space(NUM_TOKEN_RE.sub(repl, _dash(kr_text)))}


RANGE_RE = re.compile(r"\((-?\d+(?:\.\d+)?)[-\u2014\u2013](-?\d+(?:\.\d+)?)\)")


def rolled(text: str) -> str:
    """(1-4) 처럼 범위로 적힌 굴림값을 실제 값 하나로 바꾼 문장.

    PoB 는 정복된 패시브의 스탯 줄에서 "(1-4)" 를 굴림값으로 바꿔 그립니다.
    """
    return RANGE_RE.sub(lambda m: m.group(2), text)


def add(pair, exact: dict, templates: dict, report: list, why: str) -> None:
    if not pair:
        report.append(why)
        return
    if pair["kind"] == "exact":
        exact.setdefault(pair["en"], pair["kr"])
        return
    kr = pair["kr"]
    if not kr or "%" not in kr:
        report.append("자리표시 없음: %s" % pair["en"])
        return
    templates.setdefault(pair["key"], kr)
    # 군단 주얼은 정복할 때 "(1-4)" 같은 범위를 실제 굴림값 하나로 바꿔 그립니다.
    # 그렇게 바뀐 문장의 모양 키도 함께 등록합니다.
    alt = shape(rolled(pair["en"]))
    if alt != pair["key"]:
        if alt.count("#") == kr.count("%"):
            templates.setdefault(alt, kr)
        elif kr.count("%") == 2 and alt.count("#") == 1:
            # "(1-4) to (33-35)" 처럼 두 굴림값이 "4-35" 한 덩어리로 바뀌는 줄
            merged = re.sub(r"%1\s*[~\-]\s*%2", "%1", kr)
            if merged != kr:
                templates.setdefault(alt, merged)


# ── 군단 패시브 (poedb) ──────────────────────────────────────────────────────
def build_from_poedb(exact: dict, templates: dict, report: list) -> dict:
    us, kr = page("us"), page("kr")
    stats = {}

    en_cards = cards(section(us, TABS["passives"]))
    kr_cards = cards(section(kr, TABS["passives"]))
    stats["passive_cards"] = {"us": len(en_cards), "kr": len(kr_cards)}
    if len(en_cards) != len(kr_cards):
        report.append("passive 카드 수가 다릅니다: %d/%d" % (len(en_cards), len(kr_cards)))
    for en, ko in zip(en_cards, kr_cards):
        if en["name"] and ko["name"]:
            exact.setdefault(en["name"], ko["name"])
        if len(en["stats"]) != len(ko["stats"]):
            report.append("stat 줄 수 불일치: %s" % en["name"])
            continue
        for a, b in zip(en["stats"], ko["stats"]):
            add(pair_line(a, b), exact, templates, report, "passive: %s / %s" % (en["name"], strip(a)))

    en_rows = rows(section(us, TABS["additions"]))
    kr_rows = rows(section(kr, TABS["additions"]))
    stats["additions"] = {"us": len(en_rows), "kr": len(kr_rows)}
    by_code = {r["code"]: r for r in kr_rows}
    matched = 0
    for en in en_rows:
        ko = by_code.get(en["code"])
        if not ko:
            report.append("additions 코드 없음: %s" % en["code"])
            continue
        matched += 1
        add(pair_line(en["desc"], ko["desc"]), exact, templates, report, "additions: %s" % en["code"])
    stats["additions"]["matched"] = matched

    stats["alternate_rows"] = len(re.findall(r"<tr>", section(kr, TABS["alternate"])))
    return stats


def build_conquerors(exact: dict, templates: dict) -> None:
    for en, (kr, _src) in CONQUERORS.items():
        exact.setdefault(en, kr)
    for en, kr in FACTIONS.items():
        exact.setdefault(en, kr)
    for en, kr in DEVOTION_VARIANTS.items():
        exact.setdefault(en, kr)
    for en, kr in PLAIN_LINES.items():
        exact.setdefault(en, kr)
    for en, kr in NUMBERED_LINES.items():
        templates[shape(en)] = kr.replace("#", "%1")


def obj_particle(name: str) -> str:
    """목적격 조사 (를/을) — 마지막 글자의 받침으로 고릅니다."""
    if not name:
        return "를"
    code = ord(name[-1])
    if 0xAC00 <= code <= 0xD7A3:
        final = (code - 0xAC00) % 28
        return "을" if final and final != 8 else "를"  # ㄹ(8)은 '를'
    return "를"


def variant_name(raw: str) -> str:
    """PoB 변형 이름 -> 정복자 이름.  "Doryani (Corrupted Soul)" -> "Doryani" """
    name = raw.split(" (")[0].strip()
    return name


def devotion_lines() -> list:
    """호전적인 신념의 '헌신' 변형 표 (poedb 의 …속성 부여 표).

    PoB 는 이 16줄을 "Variant: Area Damage" 같은 변형으로 들고 있습니다.
    """
    out = []
    for lang, page_name in (("us", "Militant_Faith"), ("kr", "Militant_Faith")):
        text = fetch("https://poedb.tw/%s/%s" % (lang, page_name), "poedb_%s_%s.html" % (page_name, lang))
        sec = ""
        for m in re.finditer(r'<h5 class="card-header">([^<]+)</h5>', text):
            head = m.group(1)
            if "Modifiers" in head or "속성 부여" in head:
                if "Timeless Jewel" in head or "무궁한 주얼" in head:
                    continue
                start = m.end()
                nxt = text.find('<h5 class="card-header">', start)
                sec = text[start:nxt if nxt > 0 else len(text)]
                break
        lines = [strip(m.group(1)) for m in re.finditer(r'<span class="explicitMod">(.*?)</span>\s*(?:<span class="badge|</td>)', sec, re.S)]
        out.append(lines)
    en, kr = out
    # 표에는 변형 16줄과 함께 "Carved to glorify …" 3줄도 들어 있습니다.
    # 뒤의 3줄은 JEWEL_SENTENCES 에서 만들므로 숫자가 실제로 들어간 줄만 씁니다.
    pairs = [(a, b) for a, b in zip(en, kr) if "#" not in a]
    return pairs


def jewel_data() -> dict:
    """PoB 원본에서 군단 주얼 6종의 변형 줄을 읽습니다. 없으면 내장 목록."""
    blocks = []
    if POB:
        path = os.path.join(POB, "Data", "Uniques", "jewel.lua")
        if os.path.exists(path):
            try:
                table = lua_to_py(load_lua_table(path))
                blocks = [b for b in (table.values() if isinstance(table, dict) else table)
                          if isinstance(b, str)]
            except Exception as exc:  # noqa: BLE001
                print("  (PoB jewel.lua 를 읽지 못했습니다: %s)" % exc)
    out = {}
    meta = ("Rarity:", "League:", "Source:", "Variant:", "Selected Variant:", "Radius:",
            "Limited to:", "Implicits:", "Has Alt", "Item Level:", "Quality:", "Sockets:",
            "LevelReq:", "Corrupted", "Note:")
    for block in blocks:
        lines = [l.strip() for l in block.strip().split("\n")]
        if len(lines) < 2 or lines[0] not in JEWEL_SENTENCES:
            continue
        variants = [l[len("Variant: "):] for l in lines if l.startswith("Variant: ")]
        mods = []
        for line in lines:
            m = re.match(r"^\{variant:(\d+)\}(.+)$", line)
            if m:
                idx = int(m.group(1)) - 1
                if idx < len(variants):
                    mods.append((variants[idx], m.group(2).strip()))
                continue
            if line.startswith(meta) or not line or line in ("Timeless Jewel",):
                continue
            if line == lines[0] or not re.search(r"[A-Za-z]", line):
                continue
            mods.append(("", line))
        if mods:
            out[lines[0]] = mods
    return out


def build_jewel_items(exact: dict, templates: dict, report: list) -> dict:
    data = jewel_data()
    if not data:
        print("  (PoB jewel.lua 없음 — 내장 목록으로 생성합니다)")
        data = {
            "Brutal Restraint": [("Asenath", "Denoted service of (500-8000) dekhara in the akhara of Asenath"),
                                 ("Deshret", "Denoted service of (500-8000) dekhara in the akhara of Deshret"),
                                 ("Nasima", "Denoted service of (500-8000) dekhara in the akhara of Nasima"),
                                 ("Balbala", "Denoted service of (500-8000) dekhara in the akhara of Balbala")],
            "Elegant Hubris": [("Cadiro", "Commissioned (2000-160000) coins to commemorate Cadiro"),
                               ("Chitus", "Commissioned (2000-160000) coins to commemorate Chitus"),
                               ("Victario", "Commissioned (2000-160000) coins to commemorate Victario"),
                               ("Caspiro", "Commissioned (2000-160000) coins to commemorate Caspiro")],
            "Glorious Vanity": [("Doryani", "Bathed in the blood of (100-8000) sacrificed in the name of Doryani"),
                                ("Xibaqua", "Bathed in the blood of (100-8000) sacrificed in the name of Xibaqua"),
                                ("Zerphi", "Bathed in the blood of (100-8000) sacrificed in the name of Zerphi"),
                                ("Mazcotl", "Bathed in the blood of (100-8000) sacrificed in the name of Mazcotl")],
            "Heroic Tragedy": [("Vorana", "Remembrancing (100-8000) songworthy deeds by the line of Vorana"),
                               ("Uhtred", "Remembrancing (100-8000) songworthy deeds by the line of Uhtred"),
                               ("Medved", "Remembrancing (100-8000) songworthy deeds by the line of Medved")],
            "Lethal Pride": [("Kaom", "Commanded leadership over (10000-18000) warriors under Kaom"),
                             ("Kiloava", "Commanded leadership over (10000-18000) warriors under Kiloava"),
                             ("Rakiata", "Commanded leadership over (10000-18000) warriors under Rakiata"),
                             ("Akoya", "Commanded leadership over (10000-18000) warriors under Akoya")],
            "Militant Faith": [("Avarius", "Carved to glorify (2000-10000) new faithful converted by High Templar Avarius"),
                               ("Dominus", "Carved to glorify (2000-10000) new faithful converted by High Templar Dominus"),
                               ("Venarius", "Carved to glorify (2000-10000) new faithful converted by High Templar Venarius"),
                               ("Maxarius", "Carved to glorify (2000-10000) new faithful converted by High Templar Maxarius")],
            # 3.30 심연 주얼 (PoB 원본이 없을 때를 위한 내장 목록)
            "Festering Vengeance": [("", "Subjugating (100-8000) souls in the thrall of Tecrod"),
                                    ("", "Passives affected are Conquered by the Abyssal")],
            "Extinguishing Grasp": [("", "Subjugating (100-8000) souls in the thrall of Ulaman"),
                                    ("", "Passives affected are Conquered by the Abyssal")],
            "Baleful Dominion": [("", "Subjugating (100-8000) souls in the thrall of Kurgal"),
                                 ("", "Passives affected are Conquered by the Abyssal")],
            "Destructive Aspiration": [("", "Subjugating (100-8000) souls in the thrall of Amanamu"),
                                       ("", "Passives affected are Conquered by the Abyssal")],
            "Reclaimed Malevolence": [("", "Binding (100-8000) souls to phylacteries to sustain Zorath"),
                                      ("", "Passives affected are Conquered by the Abyssal")],
        }
    stats = {"jewels": 0, "variants": 0, "devotion": 0, "skipped": []}
    devotion = {}
    for en, kr in devotion_lines():
        devotion[shape(en)] = (en, kr)
        pair = pair_line(en, kr)
        if pair:
            add(pair, exact, templates, report, "devotion: %s" % en)
            stats["devotion"] += 1
        else:
            report.append("devotion 짝짓기 실패: %s" % en)
    for jewel, mods in data.items():
        sentence = JEWEL_SENTENCES.get(jewel)
        if not sentence:
            report.append("문장 틀 없음: %s" % jewel)
            continue
        pattern, conquered = sentence
        stats["jewels"] += 1
        for raw_name, en_line in mods:
            name = variant_name(raw_name)
            if not name:
                # 변형 표시가 없는 줄(3.30 심연 주얼 등)은 문장 속 정복자 이름으로 찾습니다.
                for candidate in CONQUERORS:
                    if re.search(r"\b%s\b" % re.escape(candidate), en_line):
                        name = candidate
                        break
            key = shape(en_line)
            if name in CONQUERORS:
                # 정복자 변형: 주얼 카드에서 확인한 문장 틀 + 정복자 이름
                kr_name, src = CONQUERORS[name]
                # PoB 변형 목록에 그려지는 "Doryani (Corrupted Soul)" 형태
                detailed = re.match(r"^([^()]+?)\s*\(([^()]+?)\)(?:\s*\(Pre[^)]*\))?$", raw_name.strip())
                if detailed:
                    keystone = detailed.group(2).strip()
                    kr_keystone = exact.get(keystone) or CONQUERORS.get(keystone, (None,))[0]
                    if kr_keystone:
                        exact.setdefault("%s (%s)" % (name, keystone), "%s (%s)" % (kr_name, kr_keystone))
                if src == "표기 미확인":
                    stats["skipped"].append("%s %s" % (jewel, name))
                kr_line = pattern.replace("{name}", kr_name).replace("{obj}", obj_particle(kr_name))
                if key.count("#") != kr_line.count("%1"):
                    report.append("숫자 개수 불일치: %s %s" % (jewel, name))
                    continue
                templates.setdefault(key, kr_line)
                exact.setdefault(name, kr_name)
                stats["variants"] += 1
            elif key in devotion:
                # 호전적인 신념의 헌신 변형: poedb 의 속성 부여 표에서 짝지은 문장
                pair = pair_line(*devotion[key])
                if pair:
                    add(pair, exact, templates, report, "devotion variant: %s" % name)
                    stats["variants"] += 1
                else:
                    report.append("헌신 변형 짝짓기 실패: %s" % name)
            elif "Conquered by" in en_line:
                # "Passives affected are Conquered by the Abyssal" 같은 세력 문구
                exact.setdefault(en_line, conquered)
            elif en_line not in PLAIN_LINES and "Historic" not in en_line \
                    and not re.match(r"^[A-Z][A-Za-z' ]*Jewel$", en_line):
                report.append("변형 문장 없음: %s %s" % (jewel, name))
        # "반경 내 패시브 스킬은 …의 지배를 받음" — 카드에 실린 문장을 그대로 씁니다.
        for faction, kr_faction in FACTIONS.items():
            if kr_faction in conquered:
                exact.setdefault("Passives in radius are Conquered by the " + faction, conquered)
    return stats


# ── 일반 패시브 트리의 여러 줄 스탯 (정복된 핵심노드 보완) ────────────────────
def tree_multiline(exact: dict, templates: dict, report: list) -> dict:
    """poedb 트리 데이터의 여러 줄 스탯을 줄 단위로 쪼개 짝짓습니다.

    정복되지 않고 남는 핵심노드(영원한 젊음·비껴내기·바람의 무희·불가지론자·
    자만의 정점)는 일반 트리 노드의 스탯을 그대로 그리는데, 지금까지는 여러 줄이
    한 문자열로 붙어 있어 번역이 적용되지 않았습니다.
    """
    from passives import poedb_tree  # 같은 폴더의 수집 스크립트 재사용

    try:
        us = poedb_tree("us")["nodes"]
        kr = poedb_tree("kr")["nodes"]
    except Exception as exc:  # noqa: BLE001
        report.append("트리 데이터를 읽지 못했습니다: %s" % exc)
        return {"nodes": 0, "lines": 0}

    nodes = lines = 0
    for node_id, node in us.items():
        other = kr.get(node_id)
        if not other:
            continue
        en_lines, kr_lines = [], []
        for s in node.get("stats") or []:
            en_lines += [x for x in str(s).split("\n") if x.strip()]
        for s in other.get("stats") or []:
            kr_lines += [x for x in str(s).split("\n") if x.strip()]
        if len(en_lines) < 2 or len(en_lines) != len(kr_lines):
            continue
        nodes += 1
        for a, b in zip(en_lines, kr_lines):
            add(pair_line(a, b), exact, templates, report, "tree: %s / %s" % (node.get("name"), a))
            lines += 1
    return {"nodes": nodes, "lines": lines}


# ── PoB 기준 커버리지 ────────────────────────────────────────────────────────
def coverage(exact: dict, templates: dict) -> dict:
    """PoB 가 그리는 문자열을 기준으로 계산합니다.

    실제 배포 사전은 exact.lua/templates.lua 로 합쳐지므로, 일반 트리·아이템
    사전(passives_names/passives_stats/mods_exact)도 함께 봅니다.
    """
    if not POB:
        return {"available": False}
    from common import DATA
    merged_exact = dict(exact)
    for name in ("passives_names.json", "passives_stats.json"):
        path = os.path.join(DATA, name)
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                merged_exact.update(json.load(f))
    merged_tpl = dict(templates)
    path = os.path.join(DATA, "mods_exact.json")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            for key, value in json.load(f).items():
                merged_tpl.setdefault(shape(key), value["kr"])
    exact, templates = merged_exact, merged_tpl
    path = os.path.join(POB, "Data", "TimelessJewelData", "LegionPassives.lua")
    if not os.path.exists(path):
        return {"available": False, "reason": "LegionPassives.lua 없음"}
    legion = lua_to_py(load_lua_table(path))

    def hit(text: str) -> bool:
        text = norm_space(text)
        return text in exact or shape(text) in templates

    names = [n.get("dn") or "" for n in legion["nodes"]]
    stats_lines = []
    for n in legion["nodes"] + legion["additions"]:
        stats_lines += [norm_space(s) for s in (n.get("sd") or [])]
    miss_names = [n for n in names if not hit(n) and not hit(n.strip())]
    miss_stats = [s for s in stats_lines if not hit(s)]
    items = {}
    for jewel, mods in jewel_data().items():
        bad = []
        for _name, en in mods:
            if "#" not in shape(en) and "Conquered" not in en and en != "Historic":
                continue  # 베이스 종류 줄 등은 아이템 사전 담당
            if not hit(en):
                bad.append(en)
        items[jewel] = bad
    return {
        "available": True,
        "node_names": {"total": len(names), "missing": [n for n in miss_names]},
        "stat_lines": {"total": len(stats_lines), "missing": sorted(set(miss_stats))},
        "item_lines": {k: v for k, v in items.items() if v},
    }


def main() -> None:
    exact: dict = {}
    templates: dict = {}
    report: list = []

    build_conquerors(exact, templates)
    for en, kr in POB_FIXUPS.items():
        templates.setdefault(shape(en), kr)
    poedb_stats = build_from_poedb(exact, templates, report)
    item_stats = build_jewel_items(exact, templates, report)
    tree_stats = tree_multiline(exact, templates, report)

    # legacy 핵심노드 이름 (정복되지 않고 남는 5종) 은 일반 트리 이름을 그대로 씁니다.
    save_json("legion_exact.json", exact)
    save_json("legion_templates.json", templates)

    cov = coverage(exact, templates)
    record = {"poedb": poedb_stats, "items": item_stats, "tree": tree_stats,
              "size": {"exact": len(exact), "templates": len(templates)},
              "pairing_notes": report, "coverage": cov}
    save_json("legion_report.json", record)

    print("군단 주얼 사전: 이름/문구 %d개, 스탯 템플릿 %d개" % (len(exact), len(templates)))
    print("  정복 패시브 카드 %d개, 추가 속성 %d개(%d 짝짓기)" % (
        poedb_stats.get("passive_cards", {}).get("kr", 0),
        poedb_stats.get("additions", {}).get("kr", 0),
        poedb_stats.get("additions", {}).get("matched", 0)))
    print("  주얼 %d종 변형 %d줄, 트리 여러 줄 스탯 %d줄(%d 노드)" % (
        item_stats["jewels"], item_stats["variants"], tree_stats["lines"], tree_stats["nodes"]))
    if report:
        print("  짝짓기 보류 %d건 (예: %s)" % (len(report), report[:3]))
    if cov.get("available"):
        print("  PoB 기준: 노드 이름 %d개 중 누락 %d, 스탯 줄 %d개 중 누락 %d" % (
            cov["node_names"]["total"], len(cov["node_names"]["missing"]),
            cov["stat_lines"]["total"], len(cov["stat_lines"]["missing"])))
        if cov["node_names"]["missing"]:
            print("    이름 누락:", cov["node_names"]["missing"][:10])
        if cov["stat_lines"]["missing"]:
            print("    스탯 누락:", cov["stat_lines"]["missing"][:10])
        if cov["item_lines"]:
            print("    주얼 문구 누락:", cov["item_lines"])
    else:
        print("  (PoB 원본이 없어 커버리지 계산은 생략했습니다)")
    if item_stats["skipped"]:
        print("  표기 미확인 이름:", sorted(set(item_stats["skipped"])))


if __name__ == "__main__":
    main()
