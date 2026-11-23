#!/usr/bin/env python3
"""릴리스에 PoE2 자산을 덧붙인다 (워크플로우 권한 보완용).

`.github/workflows/build-release.yml` 는 GitHub App 의 workflows 권한이 없어
저장소에서 고칠 수 없습니다. 그래서 지금 워크플로우는 PoE1 자산만 올립니다.
이 스크립트는 방금 만들어진 릴리스에 다음을 추가/갱신합니다.

  · KR-data-poe2.zip   (app/payload/KR2-payload.zip 을 그대로 올림)
  · manual-ko.txt      (installer/manual-ko.txt)
  · latest.json        (기존 latest.json + poe2 블록)

릴리스 직후 한 번 실행하면 됩니다. (여러 번 실행해도 안전 — --clobber)

    python3 scripts/publish_extra.py --tag v2.0.0

워크플로우를 docs/build-release-poe2.yml 로 바꾸면 이 스크립트는 필요 없어집니다.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO = "SSONG-HA/kor-patch"


def sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def run(cmd: list[str]) -> None:
    print("  $", " ".join(cmd))
    subprocess.run(cmd, check=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", required=True)
    ap.add_argument("--repo", default=REPO)
    args = ap.parse_args()

    meta = json.load(open(os.path.join(ROOT, "version.json"), encoding="utf-8"))
    poe2 = (meta.get("games") or {}).get("poe2") or {}
    version = str(poe2.get("version") or meta.get("version"))

    work = tempfile.mkdtemp(prefix="pob-kr2-extra-")
    payload_zip = os.path.join(ROOT, "app", "payload", "KR2-payload.zip")
    if not os.path.exists(payload_zip):
        print("[실패] %s 가 없습니다. 먼저 make_payload.py 를 실행하세요." % payload_zip)
        return 1
    target_zip = os.path.join(work, "KR-data-poe2.zip")
    shutil.copyfile(payload_zip, target_zip)

    manual = os.path.join(ROOT, "installer", "manual-ko.txt")
    target_manual = os.path.join(work, "manual-ko.txt")
    shutil.copyfile(manual, target_manual)

    base = "https://github.com/%s/releases/download/%s" % (args.repo, args.tag)
    target_json = os.path.join(work, "latest.json")
    run(["curl", "-sSL", "-o", target_json, base + "/latest.json"])
    data = json.load(open(target_json, encoding="utf-8"))
    if not data.get("version"):
        print("[실패] latest.json 을 읽지 못했습니다.")
        return 1
    data["schema"] = 2
    data["notes"] = "PoE1 %s / PoE2 %s 대응 한글 데이터" % (data.get("season", ""), poe2.get("season", ""))
    data["poe2"] = {
        "version": version,
        "season": str(poe2.get("season", "")),
        "pob": str(poe2.get("pob", "")),
        "data": {
            "file": "KR-data-poe2.zip",
            "url": base + "/KR-data-poe2.zip",
            "size": os.path.getsize(target_zip),
            "sha256": sha256(target_zip),
        },
    }
    with open(target_json, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    run(["gh", "release", "upload", args.tag, target_zip, target_manual, target_json,
         "-R", args.repo, "--clobber"])
    print("완료: %s 에 PoE2 자산 3개를 올렸습니다." % args.tag)
    print("  KR-data-poe2.zip %d bytes sha256 %s" % (os.path.getsize(target_zip), sha256(target_zip)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
