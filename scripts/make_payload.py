#!/usr/bin/env python3
"""src/KR -> app/payload/KR-payload.zip + app/payload/build.json

The zip is embedded in PoB-KR-Patcher.exe and also uploaded to the release as
KR-data.zip (same bytes). Entry names are relative to the PoB install's KR folder,
so the exe can extract it straight into <PoB>\\KR.

Usage:
    python scripts/make_payload.py                 # version.json 사용
    python scripts/make_payload.py --version 1.0.1 --season 3.30 --pob 2.68.1
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src", "KR")
OUT = os.path.join(ROOT, "app", "payload")
ZIP_PATH = os.path.join(OUT, "KR-payload.zip")
BUILD_JSON = os.path.join(OUT, "build.json")

EXCLUDE_DIRS = {"__pycache__", "_설치기록", ".git"}
EXCLUDE_FILES = {"version.txt", ".DS_Store", "Thumbs.db"}
EXCLUDE_SUFFIX = (".pyc", ".part", ".orig", ".tmp")

REQUIRED = (
    "init.lua",
    "config.lua",
    "draw.lua",
    "font.lua",
    "shape.lua",
    "Data/exact.lua",
    "Data/templates.lua",
    "Fonts/metrics.lua",
    "Fonts/kr_full.png",
)


def read_version_file() -> dict:
    path = os.path.join(ROOT, "version.json")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def collect() -> list[tuple[str, str]]:
    entries = []
    for base, dirs, files in os.walk(SRC):
        dirs[:] = sorted(d for d in dirs if d not in EXCLUDE_DIRS)
        for name in sorted(files):
            if name in EXCLUDE_FILES or name.endswith(EXCLUDE_SUFFIX):
                continue
            full = os.path.join(base, name)
            rel = os.path.relpath(full, SRC).replace(os.sep, "/")
            entries.append((full, rel))
    entries.sort(key=lambda e: e[1])
    return entries


def check_required(names: list[str]) -> None:
    missing = [r for r in REQUIRED if r not in names]
    if missing:
        print("[실패] src/KR 에 필요한 파일이 없습니다: %s" % ", ".join(missing))
        print("       tools/emit_lua.py 와 tools/bake_font.py 를 먼저 실행하세요.")
        raise SystemExit(1)


def write_zip(entries: list[tuple[str, str]]) -> None:
    os.makedirs(OUT, exist_ok=True)
    if os.path.exists(ZIP_PATH):
        os.remove(ZIP_PATH)
    with zipfile.ZipFile(ZIP_PATH, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
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
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", default=str(meta.get("version", "0.0.0")))
    ap.add_argument("--season", default=str(meta.get("season", "")))
    ap.add_argument("--pob", default=str(meta.get("pob", "")))
    args = ap.parse_args()

    entries = collect()
    names = [rel for _, rel in entries]
    check_required(names)
    write_zip(entries)

    build = {
        "version": args.version,
        "season": args.season,
        "pob": args.pob,
        "files": len(entries),
        "payload_size": os.path.getsize(ZIP_PATH),
        "payload_sha256": sha256(ZIP_PATH),
    }
    with open(BUILD_JSON, "w", encoding="utf-8", newline="\n") as f:
        json.dump(build, f, ensure_ascii=False, indent=2)
        f.write("\n")

    # KR/version.txt (설치 시 PoB 폴더에 기록되는 문자열과 동일한 형식)
    pretty = "%s (Path of Building %s%s)" % (
        args.version, args.pob, (" · PoE1 " + args.season) if args.season else "")

    print("payload: %s (%.2f MB, %d files)" % (ZIP_PATH, build["payload_size"] / 1048576, len(entries)))
    print("version: %s" % pretty)
    print("sha256 : %s" % build["payload_sha256"])


if __name__ == "__main__":
    main()
