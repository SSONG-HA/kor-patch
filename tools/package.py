"""PoB-KR-Patcher ZIP 패키징."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src", "KR")
INSTALLER = os.path.join(ROOT, "installer")
TOOLS = os.path.join(ROOT, "tools")
BUILD = os.path.join(ROOT, "build")
NAME = "PoB-KR-Patcher"
VERSION = "1.0.0"
POB_VERSION = "2.68.1 (PoE1 3.30)"


def copy_tree(src, dst, exclude=("__pycache__", ".part", "cache")):
    for base, dirs, files in os.walk(src):
        dirs[:] = [d for d in dirs if d not in exclude]
        rel = os.path.relpath(base, src)
        target = os.path.join(dst, rel) if rel != "." else dst
        os.makedirs(target, exist_ok=True)
        for f in files:
            if f.endswith((".part", ".pyc")):
                continue
            shutil.copy2(os.path.join(base, f), os.path.join(target, f))


def main() -> None:
    if os.path.exists(BUILD):
        shutil.rmtree(BUILD)
    root = os.path.join(BUILD, NAME)
    os.makedirs(root)

    # 1) 런타임 (KR)
    copy_tree(SRC, os.path.join(root, "KR"))
    with open(os.path.join(root, "KR", "version.txt"), "w", encoding="utf-8") as f:
        f.write("%s (Path of Building %s)\n" % (VERSION, POB_VERSION))

    # 2) 설치 프로그램
    os.makedirs(os.path.join(root, "setup"))
    for f in ("install.ps1", "uninstall.ps1"):
        # PowerShell 5.1 이 한글 메시지를 제대로 읽도록 UTF-8 BOM 으로 저장
        text = open(os.path.join(INSTALLER, f), encoding="utf-8").read()
        with open(os.path.join(root, "setup", f), "w", encoding="utf-8-sig", newline="") as out:
            out.write(text)
    for f in ("한글패치_적용.bat", "영문원본_복구.bat", "사용설명서.txt"):
        shutil.copy2(os.path.join(INSTALLER, f), os.path.join(root, f))

    # 3) 시즌 갱신 도구
    season = os.path.join(root, "시즌갱신")
    os.makedirs(season)
    for f in ("common.py", "gems.py", "passives.py", "items.py", "templates.py",
              "emit_lua.py", "bake_font.py", "verify.py", "run_all.py", "compare_calcs.py"):
        p = os.path.join(TOOLS, f)
        if os.path.exists(p):
            shutil.copy2(p, os.path.join(season, f))
    # 수동 번역/보정 데이터도 함께 담는다 (없으면 UI 가 영문으로 되돌아감)
    os.makedirs(os.path.join(season, "data"), exist_ok=True)
    for f in os.listdir(os.path.join(ROOT, "data")):
        if f in ("ui_ko.json", "overrides_ko.json", "mods_extra.json"):
            shutil.copy2(os.path.join(ROOT, "data", f), os.path.join(season, "data", f))
    with open(os.path.join(season, "사전갱신.bat"), "w", encoding="ascii", newline="") as f:
        f.write("@echo off\r\nchcp 65001 >nul\r\ncd /d \"%~dp0\"\r\n"
                "python run_all.py\r\nif errorlevel 1 echo.\r\necho.\r\npause\r\n")
    with open(os.path.join(season, "README.txt"), "w", encoding="utf-8") as f:
        f.write(
            "시즌 갱신 도구\n"
            "==============\n"
            "poedb.tw 의 최신 한국어 데이터를 받아 KR\\Data 와 KR\\Fonts 를 다시 만듭니다.\n\n"
            "준비물: Python 3.10 이상, pip install pillow lupa requests\n"
            "사용법: 사전갱신.bat 실행 (또는 python run_all.py)\n\n"
            "동작 순서\n"
            "  1) gems.py      젬 이름 사전\n"
            "  2) passives.py  패시브 트리 노드/효과 문구\n"
            "  3) items.py     유니크/베이스 이름, 아이템 옵션 템플릿\n"
            "  4) emit_lua.py  KR\\Data\\*.lua 생성 (data\\ui_ko.json 의 UI 번역 포함)\n"
            "  5) bake_font.py 한글 글리프 아틀라스 생성 (NotoSansKR.ttf 자동 다운로드)\n\n"
            "결과 확인: verify.py 실행\n"
            "적용: 생성된 KR 폴더를 PoB 폴더로 복사한 뒤 한글패치_적용.bat 실행\n")

    # 4) ZIP
    zip_path = os.path.join(BUILD, NAME + ".zip")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for base, dirs, files in os.walk(root):
            for f in files:
                full = os.path.join(base, f)
                rel = os.path.relpath(full, root)
                z.write(full, os.path.join(NAME, rel))
    total = os.path.getsize(zip_path)
    print("zip: %s (%.2f MB)" % (zip_path, total / 1048576))
    n = sum(len(fs) for _, _, fs in os.walk(root))
    print("files: %d" % n)


if __name__ == "__main__":
    main()
