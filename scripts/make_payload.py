#!/usr/bin/env python3
"""src/KR (PoE1) 또는 src/KR2 (PoE2) → app/payload/*.zip + build*.json

The zip is embedded in PoB-KR-Patcher.exe and also uploaded to the release as
KR-data.zip (PoE1) / KR-data-poe2.zip (PoE2). Entry names are relative to the
PoB install's KR / KR2 folder, so the exe can extract it straight into
<PoB>\\KR or <PoB>\\KR2.

Usage:
    python scripts/make_payload.py                      # PoE1, version.json 사용
    python scripts/make_payload.py --game poe2          # PoE2
    python scripts/make_payload.py --game poe2 --version 2.0.0 --season 0.5 --pob 0.23.1
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "app", "payload")

GAMES = {
    "poe1": {
        "src": os.path.join(ROOT, "src", "KR"),
        "zip": "KR-payload.zip",
        "meta": "build.json",
        "required": ("init.lua", "config.lua", "draw.lua", "font.lua", "shape.lua",
                     "Data/exact.lua", "Data/templates.lua", "Fonts/metrics.lua",
                     "Fonts/kr_full.png"),
    },
    "poe2": {
        "src": os.path.join(ROOT, "src", "KR2"),
        "zip": "KR2-payload.zip",
        "meta": "build-poe2.json",
        "required": ("init.lua", "config.lua", "draw.lua", "font.lua", "shape.lua",
                     "Data/exact.lua", "Data/templates.lua", "Fonts/metrics.lua",
                     "Fonts/kr_full.png"),
    },
}

EXCLUDE_DIRS = {"__pycache__", "_설치기록", ".git", "_update"}
EXCLUDE_FILES = {"version.txt", ".DS_Store", "Thumbs.db"}
EXCLUDE_SUFFIX = (".pyc", ".part", ".orig", ".tmp")


def read_version_file() -> dict:
    path = os.path.join(ROOT, "version.json")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def collect(src: str) -> list[tuple[str, str]]:
    entries = []
    for base, dirs, files in os.walk(src):
        dirs[:] = sorted(d for d in dirs if d not in EXCLUDE_DIRS)
        for name in sorted(files):
            if name in EXCLUDE_FILES or name.endswith(EXCLUDE_SUFFIX):
                continue
            full = os.path.join(base, name)
            rel = os.path.relpath(full, src).replace(os.sep, "/")
            entries.append((full, rel))
    entries.sort(key=lambda e: e[1])
    return entries


def check_required(src: str, names: list[str], required) -> None:
    missing = [r for r in required if r not in names]
    if missing:
        print("[실패] %s 에 필요한 파일이 없습니다: %s" % (src, ", ".join(missing)))
        print("       poe2/tools 의 생성 스크립트(emit_lua.py, bake_font.py)를 먼저 실행하세요.")
        raise SystemExit(1)


def write_zip(entries: list[tuple[str, str]], path: str) -> None:
    os.makedirs(OUT, exist_ok=True)
    if os.path.exists(path):
        os.remove(path)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for full, rel in entries:
            info = zipfile.ZipInfo(rel, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            with open(full, "rb") as f:
                z.writestr(info, f.read())


def sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> None:
    meta = read_version_file()
    games = meta.get("games") or {}
    ap = argparse.ArgumentParser()
    ap.add_argument("--game", default="", choices=["", "poe1", "poe2"],
                    help="비우면 두 게임 모두 만든다 (기존 워크플로우 호출과 호환)")
    ap.add_argument("--version", default="")
    ap.add_argument("--season", default="")
    ap.add_argument("--pob", default="")
    args = ap.parse_args()

    if not args.game:
        # 인수 없이 부를 때(기존 워크플로우): 두 게임 모두.
        # --season/--pob 는 PoE1 값이므로 PoE2 에는 version.json 의 poe2 값을 쓴다.
        for game in ("poe1", "poe2"):
            if game == "poe2":
                sub = argparse.Namespace(**vars(args))
                sub.season = ""
                sub.pob = ""
                build_one(game, meta, games, sub)
            else:
                build_one(game, meta, games, args)
        return
    build_one(args.game, meta, games, args)


def build_one(game: str, meta: dict, games: dict, args) -> None:
    conf = GAMES[game]
    gmeta = games.get(game, {})
    version = args.version or str(gmeta.get("version") or meta.get("version", "0.0.0"))
    season = args.season or str(gmeta.get("season") or meta.get("season", ""))
    pob = args.pob or str(gmeta.get("pob") or meta.get("pob", ""))

    entries = collect(conf["src"])
    names = [rel for _, rel in entries]
    check_required(conf["src"], names, conf["required"])
    zip_path = os.path.join(OUT, conf["zip"])
    write_zip(entries, zip_path)

    build = {
        "game": game,
        "version": version,
        "season": season,
        "pob": pob,
        "files": len(entries),
        "payload_size": os.path.getsize(zip_path),
        "payload_sha256": sha256(zip_path),
    }
    with open(os.path.join(OUT, conf["meta"]), "w", encoding="utf-8", newline="\n") as f:
        json.dump(build, f, ensure_ascii=False, indent=2)
        f.write("\n")

    pretty = "%s (Path of Building %s%s)" % (
        version, pob, (" · %s %s" % ("PoE2" if game == "poe2" else "PoE1", season)) if season else "")
    print("payload: %s (%.2f MB, %d files)" % (zip_path, build["payload_size"] / 1048576, len(entries)))
    print("version: %s" % pretty)
    print("sha256 : %s" % build["payload_sha256"])


if __name__ == "__main__":
    main()
