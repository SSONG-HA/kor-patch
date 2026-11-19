"""Build passive-tree dictionaries (node names + stat lines) from poedb tree JSON."""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import (  # noqa: E402
    CACHE, POB, fetch, load_lua_table, lua_to_py, norm_space, numpad, save_json,
)

# poedb 트리 데이터 경로에 쓰이는 시즌 표기 (3_30 → 3.30). 새 시즌에는 이 값을 갱신한다.
TREE_VERSION = os.environ.get("POE_TREE_VERSION", "3_30")
TREE_URL = "https://poedb.tw/data/passive-skill-tree/%s/data_%s.json"


def poedb_tree(lang: str) -> dict:
    path = os.path.join(CACHE, "tree_%s.json" % lang)
    if not os.path.exists(path) or os.path.getsize(path) < 4096:
        version = TREE_VERSION.replace("_", ".")
        fetch(TREE_URL % (version, lang), "tree_%s.json" % lang, force=True)
    if not os.path.exists(path):
        raise SystemExit("패시브 트리 데이터를 받지 못했습니다: %s" % (TREE_URL % (TREE_VERSION.replace("_", "."), lang)))
    return json.load(open(path, encoding="utf-8"))


def pob_tree_nodes() -> dict:
    """PoB 원본(POB_SRC)이 있으면 노드 목록을 읽어 커버리지 계산에 쓴다. 없으면 빈 dict."""
    if not POB:
        return {}
    path = os.path.join(POB, "TreeData", TREE_VERSION, "tree.lua")
    if not os.path.exists(path):
        print("  (PoB TreeData 없음 — 커버리지 계산 생략: %s)" % path)
        return {}
    return lua_to_py(load_lua_table(path))["nodes"]


def main() -> None:
    us = poedb_tree("us")["nodes"]
    kr = poedb_tree("kr")["nodes"]
    pob = pob_tree_nodes()

    names: dict[str, str] = {}
    stats: dict[str, str] = {}
    stat_conflicts: dict[str, set] = {}

    for node_id, node in us.items():
        other = kr.get(node_id)
        if not other:
            continue
        name = norm_space(node.get("name") or "")
        kname = norm_space(other.get("name") or "")
        if name and kname and name != kname:
            names.setdefault(name, kname)
        s_en = node.get("stats") or []
        s_kr = other.get("stats") or []
        if isinstance(s_en, dict):
            s_en = [v for _, v in sorted(s_en.items())]
        if isinstance(s_kr, dict):
            s_kr = [v for _, v in sorted(s_kr.items())]
        if len(s_en) != len(s_kr):
            continue
        for a, b in zip(s_en, s_kr):
            a = norm_space(a)
            b = norm_space(b)
            if not a or not b:
                continue
            prev = stats.get(a)
            if prev is not None and prev != b:
                stat_conflicts.setdefault(a, set()).add(prev)
                stat_conflicts[a].add(b)
                continue
            stats[a] = b

    save_json("passives_names.json", names)
    save_json("passives_stats.json", stats)
    save_json("passive_conflicts.json", {k: sorted(v) for k, v in stat_conflicts.items()})
    print("node names: dict=%d, stat lines: dict=%d, conflicts=%d" % (
        len(names), len(stats), len(stat_conflicts)))

    if not pob:
        return

    # report PoB coverage
    pob_names, pob_stats = set(), set()
    for v in pob.values():
        if not isinstance(v, dict):
            continue
        if v.get("name"):
            pob_names.add(norm_space(v["name"]))
        for s in (v.get("stats") or []) if not isinstance(v.get("stats"), dict) else []:
            if isinstance(s, str) and s.strip():
                pob_stats.add(norm_space(s))

    cov_names = sum(1 for n in pob_names if n in names)
    cov_stats = sum(1 for s in pob_stats if s in stats)
    print("node names: dict=%d, PoB unique=%d, covered=%d (%.1f%%)" % (
        len(names), len(pob_names), cov_names, 100.0 * cov_names / max(1, len(pob_names))))
    print("stat lines: dict=%d, PoB unique=%d, covered=%d (%.1f%%)" % (
        len(stats), len(pob_stats), cov_stats, 100.0 * cov_stats / max(1, len(pob_stats))))
    miss = sorted(n for n in pob_names if n not in names)
    print("missing names sample:", miss[:15])
    miss_stats = sorted(s for s in pob_stats if s not in stats)
    print("missing stats sample:", miss_stats[:15])


if __name__ == "__main__":
    main()
