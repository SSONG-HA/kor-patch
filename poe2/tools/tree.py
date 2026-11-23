"""PoE2 패시브 트리 사전 (poe2db 한글 트리 + PoB 영문 트리, 노드 ID 로 짝짓기).

poe2db 는 게임과 같은 노드 ID 로 두 언어 트리를 제공합니다.
  https://poe2db.tw/data/passive-skill-tree/0.5/data_{us,kr}.json
PoB2 의 TreeData/<버전>/tree.lua 도 같은 ID 를 쓰므로, 이름과 효과 줄을
노드 ID 로 정확히 짝지을 수 있습니다 (슬러그 추측이 필요 없습니다).

결과:
  data/tree_names.json  {영문 노드 이름: 한글 이름}
  data/tree_stats.json  {영문 효과 한 줄: 한글 효과 한 줄}
  data/tree_classes.json {영문 클래스/전직 이름: 한글}
  data/tree_report.json
"""
from __future__ import annotations

import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import (POB2, fetch_json, load_lua_table, lua_to_py, save_json,  # noqa: E402
                    strip_ggg)

TREE_VER = os.environ.get("POE2_TREE_DB", "0.5")      # poe2db 경로에 쓰는 버전
POB_TREE = os.environ.get("POE2_POB_TREE", "0_5")     # PoB2 TreeData 폴더 이름
HANGUL_RE = re.compile(r"[\uac00-\ud7a3]")


def num_tokens(s: str) -> list[str]:
    """숫자 토큰 (한국어 문장은 어순이 달라 순서 대신 모음 비교에 쓴다)."""
    return sorted(re.findall(r"-?\d+(?:\.\d+)?", s))


def numbers_match(en: str, ko: str) -> bool:
    """영/한 줄의 숫자가 같은지.

    한국어는 키워드를 풀어 써서 숫자가 더 붙기도 한다
    (`Recently` → `최근 4초 이내`). 그래서 한쪽 숫자 모음이 다른 쪽에
    모두 들어 있으면 같은 줄로 본다.
    """
    a, b = num_tokens(en), num_tokens(ko)
    if not a or not b:
        return not a and not b
    rest = list(b)
    for tok in a:
        if tok in rest:
            rest.remove(tok)
        else:
            break
    else:
        return True
    rest = list(a)
    for tok in b:
        if tok in rest:
            rest.remove(tok)
        else:
            return False
    return True


def lines_of(text: str) -> list[str]:
    return [p.strip() for p in str(text).split("\n") if p.strip()]


def main() -> None:
    kr = fetch_json("https://poe2db.tw/data/passive-skill-tree/%s/data_kr.json" % TREE_VER,
                    "tree_kr_%s.json" % TREE_VER)
    us = fetch_json("https://poe2db.tw/data/passive-skill-tree/%s/data_us.json" % TREE_VER,
                    "tree_us_%s.json" % TREE_VER)
    pob = lua_to_py(load_lua_table(os.path.join(POB2, "TreeData", POB_TREE, "tree.lua")))

    kr_nodes = kr["nodes"]
    us_nodes = us["nodes"]
    pob_nodes = {str(k): v for k, v in pob["nodes"].items()}

    names: dict[str, str] = {}
    stats: dict[str, str] = {}
    report = {"nodes": len(pob_nodes), "papered": 0, "name_add": 0, "stat_add": 0,
              "stat_line_mismatch": [], "stat_number_mismatch": [], "missing_in_db": []}

    for nid, node in pob_nodes.items():
        if not isinstance(node, dict):
            continue
        k = kr_nodes.get(nid)
        if not isinstance(k, dict):
            report["missing_in_db"].append(nid)
            continue
        report["papered"] += 1

        en_name = (node.get("name") or "").strip()
        ko_name = (k.get("name") or "").strip()
        if en_name and ko_name and HANGUL_RE.search(ko_name):
            if names.get(en_name) is None:
                names[en_name] = ko_name
                report["name_add"] += 1

        en_lines = [l for s in (node.get("stats") or []) for l in lines_of(s)]
        ko_lines = [l for s in (k.get("stats") or []) for l in lines_of(strip_ggg(str(s)))]
        if not en_lines or not ko_lines:
            continue
        if len(en_lines) != len(ko_lines):
            report["stat_line_mismatch"].append({"id": nid, "en": en_lines, "ko": ko_lines})
            continue
        for en, ko in zip(en_lines, ko_lines):
            en, ko = en.strip(), ko.strip()
            if not en or not ko or not HANGUL_RE.search(ko):
                continue
            if not numbers_match(en, ko):
                report["stat_number_mismatch"].append({"id": nid, "en": en, "ko": ko})
                continue
            if en not in stats:
                stats[en] = ko
                report["stat_add"] += 1

    # 클래스/전직 이름 (PoB 클래스 integerId == poe2db classes 인덱스)
    classes: dict[str, str] = {}
    kr_classes = kr.get("classes") or []
    for cls in pob.get("classes") or []:
        idx = cls.get("integerId")
        if not isinstance(idx, int) or idx >= len(kr_classes):
            continue
        ko = (kr_classes[idx].get("name") or "").strip()
        en = (cls.get("name") or "").strip()
        if en and ko and HANGUL_RE.search(ko) and en not in classes:
            classes[en] = ko
    # 전직: 전직 시작 노드의 이름끼리 짝짓기 (노드 ID 동일)
    for nid, node in pob_nodes.items():
        if not isinstance(node, dict) or not node.get("isAscendancyStart"):
            continue
        k = kr_nodes.get(nid)
        if not isinstance(k, dict):
            continue
        en = (node.get("name") or "").strip()
        ko = (k.get("name") or "").strip()
        if en and ko and HANGUL_RE.search(ko) and en not in classes:
            classes[en] = ko

    save_json("tree_names.json", names)
    save_json("tree_stats.json", stats)
    save_json("tree_classes.json", classes)
    save_json("tree_report.json", report)
    print("트리 노드 %d개 중 %d개를 poe2db 한글 트리와 짝지음" % (len(pob_nodes), report["papered"]))
    print("  이름 %d개 / 효과 줄 %d개 / 클래스·전직 %d개" % (len(names), len(stats), len(classes)))
    print("  줄 수 불일치 %d / 숫자 불일치 %d / DB에 없음 %d" % (
        len(report["stat_line_mismatch"]), len(report["stat_number_mismatch"]),
        len(report["missing_in_db"])))


if __name__ == "__main__":
    main()
