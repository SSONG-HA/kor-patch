"""패키지된 ZIP 을 실제 설치 흐름대로 풀어서 검증한다.

1) build/PoB-KR-Patcher.zip 을 임시 폴더에 해제
2) install.ps1 과 같은 규칙으로 KR 복사 + Modules/Main.lua 로더 삽입
3) 그 사본에서 PoB 헤드리스 실행 → 계산값 동일성, 오류 유무, 번역률 확인
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import zipfile

WS = os.environ.get("WORKSPACE", "/workspace")
ZIP = os.path.join(WS, "pob-kr-patcher", "build", "PoB-KR-Patcher.zip")
WORK = os.path.join(WS, "tmpwork", "install_test")
POB_REF = os.path.join(WS, "tmpwork", "pob", "headless")

LOADER = (
    "-- [PoB-KR] Korean patch loader (PoB-KR-Patcher)\r\n"
    'pcall(function() local p = GetScriptPath and GetScriptPath() or ""; if p == "" then p = "." end; '
    'KR_ROOT = p .. "/KR"; dofile(KR_ROOT .. "/init.lua") end)\r\n'
)


def main() -> int:
    if os.path.exists(WORK):
        shutil.rmtree(WORK)
    os.makedirs(WORK)

    # 1) 압축 해제
    with zipfile.ZipFile(ZIP) as z:
        z.extractall(WORK)
    patch_root = os.path.join(WORK, "PoB-KR-Patcher")
    print("패키지 내용:", sorted(os.listdir(patch_root)))

    # 2) PoB 사본 만들기 (기존 headless 트리를 복사하고 이전 패치 흔적 제거)
    pob = os.path.join(WORK, "pob")
    shutil.copytree(POB_REF, pob, ignore=shutil.ignore_patterns("KR", "builds", "__pycache__"))
    mainLua = os.path.join(pob, "Modules", "Main.lua")
    text = open(mainLua, encoding="utf-8").read()
    if text.startswith("-- [PoB-KR]"):
        text = text.split("\n", 2)[2]
        open(mainLua, "w", encoding="utf-8").write(text)
        print("기존 로더 제거")

    # 3) 설치 흐름 재현 (install.ps1 과 동일)
    shutil.copytree(os.path.join(patch_root, "KR"), os.path.join(pob, "KR"))
    content = open(mainLua, encoding="utf-8").read()
    open(mainLua, "w", encoding="utf-8", newline="").write(LOADER + content)
    print("로더 삽입 완료:", open(mainLua, encoding="utf-8").readline().strip())

    # 4) 헤드리스 검증
    runner = os.path.join(WS, "tmpwork", "pob", "headless", "verify_headless.py")
    env = dict(os.environ)
    r = subprocess.run([sys.executable, "-u", runner, "builds/3단계-엔드게임.xml"],
                       cwd=pob, capture_output=True, text=True, env=env)
    out = r.stdout + r.stderr
    print("\n".join(out.splitlines()[-12:]))
    ok = ("calc diffs: NONE" in out) and ("patcher loaded: True" in out)
    if not ok:
        print("!! 검증 실패")
        return 1

    # 5) 패키지 무결성: 필수 파일 확인
    need = ["KR/init.lua", "KR/draw.lua", "KR/font.lua", "KR/shape.lua", "KR/config.lua",
            "KR/Data/exact.lua", "KR/Data/templates.lua", "KR/Fonts/metrics.lua",
            "KR/version.txt", "setup/install.ps1", "setup/uninstall.ps1",
            "한글패치_적용.bat", "영문원본_복구.bat", "사용설명서.txt"]
    missing = [n for n in need if not os.path.exists(os.path.join(patch_root, n))]
    print("필수 파일 누락:", missing or "없음")
    sizes = {}
    for base, _, files in os.walk(os.path.join(patch_root, "KR")):
        for f in files:
            p = os.path.join(base, f)
            sizes[os.path.relpath(p, patch_root)] = os.path.getsize(p)
    print("KR 폴더 파일 %d개, %.2f MB" % (len(sizes), sum(sizes.values()) / 1048576))
    print("ZIP 크기: %.2f MB" % (os.path.getsize(ZIP) / 1048576))
    return 0 if not missing else 1


if __name__ == "__main__":
    sys.exit(main())
