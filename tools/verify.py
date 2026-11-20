"""PoB-KR-Patcher 자체 검증 스크립트.

1) Lua 파일 문법 검사
2) 숫자 정규화 규칙(파이썬 shape vs Lua shape) 일치 검사
3) 사전 커버리지 리포트 (젬/패시브/유니크/베이스/모드/UI)
4) 문서에 적은 커버리지를 실제 데이터로 재계산
"""
from __future__ import annotations

import glob
import json
import os
import re
import sys

sys.path.insert(0, os.environ.get("LUAJIT_PATH", "/workspace/.local/lib/python3.12/site-packages"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lupa.luajit21 import LuaRuntime  # noqa: E402

from common import DATA, SRC, load_json  # noqa: E402
from items import shape as py_shape  # noqa: E402

FAILS = []


def check(name, ok, detail=""):
    print("%-52s %s %s" % (name, "OK " if ok else "FAIL", detail))
    if not ok:
        FAILS.append(name)


def syntax_checks():
    lua = LuaRuntime(unpack_returned_tuples=True, encoding="utf-8")
    files = sorted(glob.glob(os.path.join(SRC, "**", "*.lua"), recursive=True))
    bad = []
    for f in files:
        res = lua.execute("local f, err = loadfile(%r); if f then return true else return err end" % f)
        if res is not True:
            bad.append((f, res))
    check("Lua 문법 검사 (%d개 파일)" % len(files), not bad, str(bad[:3]))


def shape_parity():
    lua = LuaRuntime(unpack_returned_tuples=True, encoding="utf-8")
    lua.execute("SHAPE = dofile(%r)" % os.path.join(SRC, "shape.lua"))
    samples = []
    for f in ("mods_exact.json", "mods_extra.json"):
        path = os.path.join(DATA, f)
        if os.path.exists(path):
            samples.extend(json.load(open(path, encoding="utf-8")).keys())
    samples += [
        "+35% to Fire Resistance", "Adds 10 to 20 Fire Damage", "(25-35)% increased Cold Damage",
        "Adds 17 to 23 Fire Damage", "Adds 123 to 456 Fire Damage", "Minions deal 17 to 23 additional Fire Damage",
        "Regenerate 6 Life over 1 second when you Cast a Spell", "1.5% increased Attack Speed",
        "100% increased Armour and Energy Shield", "Gain 15% of Physical Damage as Extra Fire Damage",
        "+(-5--1) to Strength", "Has 1 Socket",
        # 큰 수는 화면에 1,234 처럼 그려지므로 천 단위 쉼표도 한 숫자로 봐야 한다
        "-1,174 Effective Hit Pool (-6.7%)", "+73,867.1 Hit DPS (+0.8%)",
        "Adds 1,234 to 5,678 Fire Damage", "1,047,662.8 total DoT",
    ]
    bad = []
    for s in samples:
        py = py_shape(s)
        lua_res = lua.eval("function(x) local k = SHAPE.shape(x); return k end")(s)
        if py != lua_res:
            bad.append((s, py, lua_res))
    check("숫자 정규화 규칙 일치 (%d개 표본)" % len(samples), not bad, str(bad[:2]))
    # 키 뿐 아니라 치환에 쓰이는 숫자 목록도 같은지 (17 to 23 → 177-23 같은 오류 방지)
    import re as _re
    num_samples = ["Adds 17 to 23 Fire Damage", "Adds 10 to 20 Fire Damage", "Adds 123 to 456 Fire Damage",
                   "Minions deal 17 to 23 additional Fire Damage", "4 to 35 Added Lightning Damage",
                   "1.5 to 2.5 Cold Damage", "(10-20) to (21-30) Fire Damage",
                   "+73,867.1 Hit DPS (+0.8%)", "Adds 1,234 to 5,678 Fire Damage"]
    bad_num = []
    for s in num_samples:
        from items import NUM_TOKEN_RE
        py_nums = NUM_TOKEN_RE.findall(_re.sub(r"(?<=\d)\s+to\s+(?=\d)", "-", s))
        lua_nums = list(lua.eval("function(x) local k, n = SHAPE.shape(x); return n end")(s).values())
        if py_nums != lua_nums:
            bad_num.append((s, py_nums, lua_nums))
    check("숫자 치환 값 일치 (%d개 표본)" % len(num_samples), not bad_num, str(bad_num[:2]))


def coverage():
    data = {f: load_json(f) for f in os.listdir(DATA) if f.endswith(".json")}
    print("\n[사전 규모]")
    for k in ("gems.json", "passives_names.json", "passives_stats.json",
              "uniques.json", "bases.json", "mods_exact.json", "ui_ko.json", "overrides_ko.json"):
        if k in data:
            print("   %-24s %6d" % (k, len(data[k])))

    # 실제 빌드 아이템 문구 커버리지
    xmls = glob.glob(os.path.join(os.environ.get("BUILD_DIR", "/workspace/tmpwork/pob/headless/builds"), "*.xml"))
    lines = []
    for x in xmls:
        text = open(x, encoding="utf-8").read()
        for m in re.finditer(r'<Item id="\d+">(.*?)</Item>', text, re.S):
            for l in m.group(1).split("\n"):
                l = l.strip()
                if not l:
                    continue
                if re.match(r"(Rarity|Item Level|LevelReq|Quality|Sockets|Implicits|Searing Exarch|"
                            r"Eater of Worlds|Corrupted|Shaper Item|Elder Item|Crusader Item|"
                            r"Redeemer Item|Hunter Item|Warlord Item|Mirrored|Split|Unidentified|"
                            r"HasAltQuality|Selected|Cluster Jewel|Limited to|Radius|Name of|Prefix:|Suffix:)", l):
                    continue
                lines.append(l)
    lines = [l for l in lines if not re.fullmatch(r"[A-Z][a-zA-Z' ]+", l) or l.startswith("+")]
    mods = data["mods_exact.json"]
    extra = data.get("mods_extra.json", {})
    hit = sum(1 for l in lines if py_shape(l) in mods or py_shape(l) in extra)
    check("실제 빌드 아이템 속성 문구 번역률", True, "%d/%d = %.1f%%" % (hit, len(lines), 100.0 * hit / max(1, len(lines))))

    # PoB 데이터 전체 기준 커버리지
    try:
        from common import load_lua_table, lua_to_py
        pob = os.environ.get("POB_SRC", "/workspace/tmpwork/pob/headless")
        gems = lua_to_py(load_lua_table(pob + "/Data/Gems.lua"))
        names = {v["name"] for v in gems.values() if isinstance(v, dict) and v.get("name")}
        g = data["gems.json"]
        print("   젬 이름          %d/%d (%.1f%%)" % (sum(1 for n in names if n in g), len(names),
                                                     100.0 * sum(1 for n in names if n in g) / len(names)))
        tree = lua_to_py(load_lua_table(pob + "/TreeData/3_30/tree.lua"))["nodes"]
        pn, ps = data["passives_names.json"], data["passives_stats.json"]
        tn = {v["name"] for v in tree.values() if isinstance(v, dict) and v.get("name")}
        ts = set()
        for v in tree.values():
            if isinstance(v, dict) and isinstance(v.get("stats"), list):
                for s in v["stats"]:
                    ts.add(" ".join(s.split()))
        print("   패시브 노드 이름   %d/%d (%.1f%%)" % (sum(1 for n in tn if n in pn), len(tn),
                                                      100.0 * sum(1 for n in tn if n in pn) / len(tn)))
        print("   패시브 효과 문구   %d/%d (%.1f%%)" % (sum(1 for n in ts if n in ps), len(ts),
                                                      100.0 * sum(1 for n in ts if n in ps) / len(ts)))
    except Exception as e:  # noqa: BLE001
        print("   (PoB 데이터 비교 생략: %s)" % str(e)[:60])


def legion_coverage():
    """군단 주얼(무궁한 주얼) 문자열이 배포 사전에서 모두 한글로 바뀌는지 확인합니다."""
    try:
        import test_legion as TL
    except Exception as exc:  # noqa: BLE001
        print("   (군단 주얼 검사를 불러오지 못했습니다: %s)" % exc)
        return
    pob = os.environ.get("POB_SRC", "/workspace/tmpwork/pob/headless")
    strings = TL.pob_strings(pob)
    if not strings:
        print("   (PoB 원본이 없어 군단 주얼 문자열 확인 생략)")
        return
    lua = TL.lua_dict()
    cases = []
    for text in dict.fromkeys(strings):
        cases.append(text)
        if TL.roll(text) != text:
            cases.append(TL.roll(text))
    miss = [c for c in cases if not re.search(r"[\uac00-\ud7a3]", TL.translate(lua, c) or "")]
    check("군단 주얼 문자열 번역 (%d개)" % len(cases), not miss,
          "미번역 %d개 %s" % (len(miss), miss[:3]))


def shipped_dicts():
    """배포 사전(exact.lua/templates.lua)을 그대로 읽어 런타임과 같은 규칙으로 조회합니다."""
    from common import norm_space
    lua = LuaRuntime(unpack_returned_tuples=True, encoding="utf-8")
    lua.execute("SHAPE = dofile(%r)" % os.path.join(SRC, "shape.lua"))
    exact = lua.eval("function(p) return dofile(p) end")(os.path.join(SRC, "Data", "exact.lua"))
    templates = lua.eval("function(p) return dofile(p) end")(os.path.join(SRC, "Data", "templates.lua"))

    def hit(text: str) -> bool:
        text = norm_space(text or "")
        if not text:
            return False
        if exact[text] is not None or exact[text.rstrip()] is not None:
            return True
        key = lua.eval("function(x) return (SHAPE.shape(x)) end")(text)
        return templates[key] is not None

    return hit


def tree_shipped_coverage():
    """PoB 트리 데이터 전체(일반·주요·핵심·숙련·전직·힌트·플레이버) 기준 번역률."""
    from common import load_lua_table, lua_to_py
    pob = os.environ.get("POB_SRC", "/workspace/tmpwork/pob/headless")
    path = os.path.join(pob, "TreeData", "3_30", "tree.lua")
    if not os.path.exists(path):
        print("   (PoB 트리 데이터가 없어 트리 커버리지 생략)")
        return
    nodes = lua_to_py(load_lua_table(path))["nodes"]
    hit = shipped_dicts()

    def kind(node):
        if node.get("isMastery"):
            return "숙련"
        if node.get("ascendancyName") or node.get("isAscendancyStart"):
            return "전직"
        if node.get("isKeystone") or node.get("ks"):
            return "핵심노드"
        if node.get("isNotable") or node.get("notable"):
            return "주요노드"
        return "일반"

    names, stats, mastery, hints = {}, {}, {}, {}
    for node in nodes.values():
        if not isinstance(node, dict):
            continue
        k = kind(node)
        if node.get("name"):
            names.setdefault(k, set()).add(" ".join(str(node["name"]).split()))
        for line in node.get("stats") or []:
            for piece in str(line).split("\n"):
                if piece.strip():
                    stats.setdefault(k, set()).add(" ".join(piece.split()))
        for effect in node.get("masteryEffects") or []:
            if not isinstance(effect, dict):
                continue
            for line in effect.get("stats") or []:
                for piece in str(line).split("\n"):
                    if piece.strip():
                        mastery.setdefault("숙련 선택지", set()).add(" ".join(piece.split()))
        for line in node.get("reminderText") or []:
            hints.setdefault("힌트 문구", set()).add(" ".join(str(line).split()))

    problems = []
    for label, groups, floor in (("노드 이름", names, 0.995), ("노드 효과", stats, 0.99),
                                 ("숙련 선택지", mastery, 0.99), ("힌트 문구", hints, 0.98)):
        for k, values in sorted(groups.items()):
            good = sum(1 for v in values if hit(v))
            rate = good / max(1, len(values))
            check("%s %s" % (label, k), rate >= floor,
                  "%d/%d (%.1f%%)" % (good, len(values), 100 * rate))
            if rate < floor:
                problems.append((k, sorted(v for v in values if not hit(v))[:3]))
    if problems:
        print("   미달 상세:", problems[:3])


def cluster_coverage():
    """클러스터 주얼: 주요 패시브 이름·효과 줄·인챈트가 배포 사전에 있는지."""
    from common import load_lua_table, lua_to_py
    pob = os.environ.get("POB_SRC", "/workspace/tmpwork/pob/headless")
    path = os.path.join(pob, "Data", "ClusterJewels.lua")
    if not os.path.exists(path):
        print("   (PoB ClusterJewels 데이터가 없어 클러스터 주얼 커버리지 생략)")
        return
    data = lua_to_py(load_lua_table(path))
    hit = shipped_dicts()
    enchants, stats = set(), set()
    for jewel in (data.get("jewels") or {}).values():
        for skill in ((jewel or {}).get("skills") or {}).values():
            if not isinstance(skill, dict):
                continue
            for line in skill.get("enchant") or []:
                enchants.add(" ".join(str(line).split()))
            for line in skill.get("stats") or []:
                stats.add(" ".join(str(line).split()))
    for label, values, floor in (("클러스터 인챈트", enchants, 0.9), ("클러스터 소형 패시브 효과", stats, 0.95)):
        good = sum(1 for v in values if hit(v))
        rate = good / max(1, len(values))
        check("%s" % label, rate >= floor, "%d/%d (%.1f%%)" % (good, len(values), 100 * rate))


def font_metrics():
    """아틀라스 PNG 와 metrics.lua 가 한 세트인지 검사합니다.

    v1.1.2 는 871글자 PNG 에 829글자 metrics.lua 를 함께 배포해 모든 한글이
    다른 글자로 어긋났습니다. 같은 실수를 다시 배포하지 않도록 개수·좌표·폭을
    실제 파일과 대조합니다.
    """
    from PIL import Image

    import bake_font

    fonts = os.path.join(SRC, "Fonts")
    path = os.path.join(fonts, "metrics.lua")
    if not os.path.exists(path):
        check("폰트 메트릭 파일 존재", False, path)
        return
    lua = LuaRuntime(unpack_returned_tuples=True, encoding="utf-8")
    metrics = lua.eval("function(p) return dofile(p) end")(path)

    def as_list(tbl):
        return [tbl[i] for i in range(1, len(tbl) + 1)] if tbl is not None else []

    codes = [int(c) for c in as_list(metrics["codes"])]
    want = {ord(ch) for ch in bake_font.used_chars()}
    have = set(codes)
    check("metrics 글자 수 == 사전 글자 수 (%d)" % len(want), len(codes) == len(want) and have == want,
          "metrics %d / 사전 %d, 빠짐 %d, 남음 %d" % (
              len(codes), len(want), len(want - have), len(have - want)))
    check("metrics codes 정렬", codes == sorted(codes), str(codes[:3]))

    sizes = as_list(metrics["sizes"])
    check("아틀라스 크기 종류", len(sizes) > 0, "%d종" % len(sizes))
    problems = []
    for defn in sizes:
        size = int(defn["size"])
        png = str(defn["png"])
        adv = as_list(defn["adv"])
        target = os.path.join(fonts, png)
        if not os.path.exists(target):
            problems.append("%s 없음" % png)
            continue
        with Image.open(target) as im:
            actual = im.size
        expect = (int(defn["w"]), int(defn["h"]))
        if actual != expect:
            problems.append("%s 크기 %s != metrics %s" % (png, actual, expect))
        if len(adv) != len(codes):
            problems.append("%s adv %d개 != 글자 %d개" % (png, len(adv), len(codes)))
        cw, chh, cols = int(defn["cw"]), int(defn["ch"]), int(defn["cols"])
        rows = -(-len(codes) // cols) if cols else 0
        if cols * cw > expect[0] or rows * chh > expect[1]:
            problems.append("%s 격자 %dx%d 이 이미지 %s 밖" % (png, cols, rows, expect))
        if not (0 < int(defn["base"]) <= chh):
            problems.append("%s baseline %s 가 셀 높이 %d 밖" % (png, defn["base"], chh))
    check("아틀라스 PNG == metrics (%d종)" % len(sizes), not problems, str(problems[:3]))

    full = metrics["full"]
    if full is None:
        check("폴백 아틀라스 정의", False, "metrics.full 없음")
        return
    target = os.path.join(fonts, str(full["png"]))
    if not os.path.exists(target):
        check("폴백 아틀라스 파일", False, target)
        return
    with Image.open(target) as im:
        actual = im.size
    expect = (int(full["w"]), int(full["h"]))
    adv = as_list(full["adv"])
    ok = actual == expect and len(adv) == int(full["count"]) and int(full["from"]) == 0xAC00 \
        and int(full["count"]) == 0xD7A4 - 0xAC00
    check("폴백 아틀라스 (한글 음절 %d자)" % int(full["count"]), ok,
          "png %s / metrics %s, adv %d개" % (actual, expect, len(adv)))


def main():
    syntax_checks()
    shape_parity()
    font_metrics()
    coverage()
    print("\n[배포 사전 기준 커버리지]")
    tree_shipped_coverage()
    cluster_coverage()
    legion_coverage()
    print()
    if FAILS:
        print("실패:", FAILS)
        return 1
    print("모든 검사 통과")
    return 0


if __name__ == "__main__":
    sys.exit(main())
