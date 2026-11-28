"""PoB 원문 데이터(Data/Gems.lua, Data/ClusterJewels.lua, TreeData/<ver>/tree.lua)를
내려받아 POB_SRC 트리를 만든다.

시즌 갱신 워크플로우가 이 스크립트로 PoB 데이터를 준비한 뒤 gems.py / passives.py /
cluster.py 를 돌린다. 군주얼 인챈트(cluster.py)는 Data/ClusterJewels.lua 가 없으면
통째로 건너뛰므로, 이 파일도 반드시 함께 받아야 한다 (v2.0.1 누락 사고).
GitHub API 로 최근 TreeData 버전(예: 3_30)을 자동으로 찾으므로, 새 시즌이 나오면 그대로 따라간다.

Usage:
    python tools/fetch_pob.py                       # cache/pobsrc 에 최신 버전 내려받기
    python tools/fetch_pob.py --version 3_30        # 버전 고정
    python tools/fetch_pob.py --dest /tmp/pobsrc

표준출력 마지막 두 줄:
    TREE_VERSION=3_30
    POB_SRC=/abs/path/cache/pobsrc
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import CACHE, fetch  # noqa: E402

RAW = "https://raw.githubusercontent.com/PathOfBuildingCommunity/PathOfBuilding/dev/"
TREE_API = "https://api.github.com/repos/PathOfBuildingCommunity/PathOfBuilding/contents/src/TreeData"
DEFAULT_TREE = "3_30"


def _version_key(name: str) -> tuple:
    out = []
    for part in name.replace(".", "_").split("_"):
        try:
            out.append(int(part))
        except ValueError:
            out.append(0)
    return tuple(out)


PLAIN_VERSION = re.compile(r"^\d+_\d+$")


def latest_tree_version() -> str:
    """GitHub API 로 src/TreeData 안의 최신 버전 폴더 이름을 고른다."""
    try:
        data = json.loads(fetch(TREE_API, "pob_treedata_index.json", force=False))
        names = [d["name"] for d in data if d.get("type") == "dir"]
        # 3_30 같은 일반 버전만 고른다 (3_30_ruthless 같은 변형 제외)
        names = [n for n in names if n and PLAIN_VERSION.match(n)]
        if names:
            return sorted(names, key=_version_key)[-1]
    except Exception as exc:  # noqa: BLE001
        print("  (TreeData 목록을 받지 못했습니다: %s — 기본값 %s 사용)" % (exc, DEFAULT_TREE))
    return DEFAULT_TREE


def download(version: str, dest: str) -> str:
    data_dir = os.path.join(dest, "Data")
    tree_dir = os.path.join(dest, "TreeData", version)
    os.makedirs(data_dir, exist_ok=True)
    os.makedirs(tree_dir, exist_ok=True)

    gems = os.path.join(data_dir, "Gems.lua")
    if not (os.path.exists(gems) and os.path.getsize(gems) > 1024):
        text = fetch(RAW + "src/Data/Gems.lua", "pob_Gems.lua", force=True)
        with open(gems, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)

    tree = os.path.join(tree_dir, "tree.lua")
    if not (os.path.exists(tree) and os.path.getsize(tree) > 1024):
        text = fetch(RAW + "src/TreeData/%s/tree.lua" % version, "pob_tree_%s.lua" % version, force=True)
        with open(tree, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)

    # 군단 주얼(무궁한 주얼) 데이터: 정복된 패시브 이름·스탯과 주얼 변형 문구
    legion_dir = os.path.join(data_dir, "TimelessJewelData")
    os.makedirs(legion_dir, exist_ok=True)
    # 클러스터 주얼(스킬 군 주얼): 인챈트 목록·소형 패시브 효과. cluster.py 가 이 파일로
    # "Added Small Passive Skills grant: …" 61줄을 만든다. 없으면 인챈트가 통째로 빠진다.
    extra = (
        ("src/Data/TimelessJewelData/LegionPassives.lua", os.path.join(legion_dir, "LegionPassives.lua")),
        ("src/Data/Uniques/jewel.lua", os.path.join(data_dir, "Uniques", "jewel.lua")),
        ("src/Data/ClusterJewels.lua", os.path.join(data_dir, "ClusterJewels.lua")),
    )
    for remote, local in extra:
        if os.path.exists(local) and os.path.getsize(local) > 1024:
            continue
        os.makedirs(os.path.dirname(local), exist_ok=True)
        text = fetch(RAW + remote, "pob_" + os.path.basename(local), force=True)
        with open(local, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
    return dest


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dest", default=os.path.join(CACHE, "pobsrc"))
    ap.add_argument("--version", default="")
    args = ap.parse_args()

    version = args.version.strip() or latest_tree_version()
    dest = os.path.abspath(download(version, args.dest))
    print("PoB 데이터: %s (TreeData %s)" % (dest, version))
    print("TREE_VERSION=%s" % version)
    print("POB_SRC=%s" % dest)


if __name__ == "__main__":
    main()
