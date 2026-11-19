"""시즌 데이터가 바뀌었을 때 version.json 의 버전·시즌·PoB 버전을 갱신한다.

- version  : patch +1 (예: 1.0.4 → 1.0.5)
- season   : 트리 버전에서 유도 (3_30 → 3.30). --tree 로 받는다
- pob      : PathOfBuildingCommunity/PathOfBuilding 최신 릴리스 태그 (확인 실패 시 그대로 둠)

Usage:
    python tools/bump_version.py --tree 3_30
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VERSION_FILE = os.path.join(ROOT, "version.json")
POB_RELEASES = "https://api.github.com/repos/PathOfBuildingCommunity/PathOfBuilding/releases/latest"


def latest_pob_version(timeout: float = 15.0) -> str:
    try:
        req = urllib.request.Request(POB_RELEASES, headers={
            "User-Agent": "PoB-KR-Patcher",
            "Accept": "application/vnd.github+json",
        })
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        tag = str(data.get("tag_name") or "").strip()
        return tag.lstrip("vV")
    except Exception as exc:  # noqa: BLE001
        print("  (PoB 최신 버전을 확인하지 못했습니다: %s)" % exc)
        return ""


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tree", default="", help="PoE 트리 버전 (예: 3_30)")
    args = ap.parse_args()

    with open(VERSION_FILE, encoding="utf-8") as f:
        meta = json.load(f)

    parts = [int(p) for p in str(meta.get("version", "1.0.0")).split(".")]
    while len(parts) < 3:
        parts.append(0)
    parts[-1] += 1
    meta["version"] = ".".join(str(p) for p in parts)

    if args.tree:
        meta["season"] = args.tree.replace("_", ".")

    pob = latest_pob_version()
    if pob:
        meta["pob"] = pob

    with open(VERSION_FILE, "w", encoding="utf-8", newline="\n") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
        f.write("\n")

    print(meta["version"])


if __name__ == "__main__":
    main()
