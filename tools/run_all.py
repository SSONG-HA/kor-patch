"""시즌 갱신: poedb 에서 최신 한국어 데이터를 받아 KR 폴더를 다시 만듭니다."""
from __future__ import annotations

import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def run(script: str) -> None:
    print("\n=== %s ===" % script)
    r = subprocess.run([sys.executable, os.path.join(HERE, script)], cwd=HERE)
    if r.returncode != 0:
        raise SystemExit("%s 실패" % script)


def main() -> None:
    for s in ("gems.py", "passives.py", "items.py", "emit_lua.py", "bake_font.py"):
        run(s)
    print("\n완료. KR 폴더를 Path of Building 폴더로 복사한 뒤 한글패치_적용.bat 을 실행하세요.")
    print("(이 도구를 이 폴더에서 실행했다면 상위 폴더의 KR 이 이미 갱신되었습니다)")


if __name__ == "__main__":
    main()
