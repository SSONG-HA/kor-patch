# PoB 한글 패처 (PoB-KR-Patcher)

Path of Building Community Fork 를 **인게임 한국어 명칭**으로 보여 주는 경량 패처입니다.
설치 파일 없이 **실행 파일(`PoB-KR-Patcher.exe`) 하나**로 동작하고, 시즌이 바뀌면 스스로 새 데이터를 받아 갱신합니다.

- 대상: PoE1 3.30 / Path of Building Community Fork 2.68.1 (PoB 업데이트 후 다시 실행하면 됩니다)
- 내려받기: **https://github.com/SSONG-HA/kor-patch/releases/latest**

## 사용법 (3단계)

1. 위 링크에서 **`PoB-KR-Patcher.exe`** 하나만 내려받아 아무 폴더에 둡니다. (설치 과정 없음)
2. 실행하고 **[한글 패치 적용 / 업데이트]** 를 누릅니다.
   - Path of Building 폴더는 자동으로 찾습니다. (포터블 폴더, `%LOCALAPPDATA%\Programs\Path of Building Community`, `C:\Program Files\...` 등)
   - 찾지 못하면 폴더 선택 창이 뜨고, 고른 폴더에 `Modules\Main.lua` 가 있으면 바로 진행합니다.
3. Path of Building 을 실행합니다. 게임 안에서 **F2** 를 누르면 한글/영문 표시가 즉시 바뀝니다.

영문으로 되돌리려면 같은 창에서 **[영문 원본으로 복구]** 를 누릅니다.
(원본 `Modules\Main.lua` 는 `KR\_설치기록\Main.lua.orig` 에 백업됩니다.)

> PoB 가 실행 중이면 파일이 잠겨 있으므로, 프로그램이 먼저 알려 주고 중단합니다. PoB 를 닫고 다시 실행하세요.

## 시즌 자동 업데이트

- 실행할 때마다 `https://github.com/SSONG-HA/kor-patch/releases/latest/download/latest.json` 을 확인합니다.
- 새 시즌 데이터가 있으면 (버전 비교) **내려받아 검증(sha256) 후 적용**할지 물어봅니다.
- 데이터만 바뀐 경우에는 exe 를 다시 받지 않아도 됩니다. 새 exe 가 필요하면 같은 창에서 안내합니다.
- 인터넷이 없으면 exe 에 들어 있는 데이터로 그대로 패치합니다. (확인 상자는 `[최신 시즌 데이터를 자동으로 확인합니다]` 로 끌 수 있습니다)

## 무엇이 바뀌나

- 계산 엔진(파서·수치 계산)은 **전혀 건드리지 않습니다.** 화면에 그려지는 문자열만 사전으로 바꿉니다.
  - PoB 의 모든 텍스트는 전역 `DrawString` / `DrawStringWidth` 를 지나므로 이 둘만 감싸고,
    한글은 미리 구운 글리프 아틀라스로 그립니다. (엔진 폰트는 ASCII 비트맵이라 한글이 없습니다)
  - 그래서 DPS·Life 등 계산값은 영문판과 동일합니다. (`tools/compare_calcs.py` 로 검증)
- 사전 범위: 젬(변형 포함)·패시브 노드/효과 문구·유니크/베이스 아이템·아이템 옵션 템플릿·주요 UI 문구.
- 남는 한계: Calcs 의 긴 계산 설명 문단과 플레이어가 지은 희귀 아이템 이름은 영문 그대로입니다.

## 저장소 구조

```
src/KR/                 PoB 폴더로 배포되는 런타임 (Lua + 사전 + 폰트 아틀라스)
  init.lua              DrawString/DrawStringWidth 후크, F2 전환
  draw.lua font.lua     한글 레이아웃 · 글리프 아틀라스 렌더링
  Data/*.lua            영→한 사전 (정확 일치 7천여 개 + 옵션 템플릿)
  Fonts/*.png           크기별 글리프 아틀라스 (Noto Sans KR)
app/                    단일 실행 파일(C# / .NET Framework 4.8) 소스
scripts/make_payload.py src/KR → exe 에 내장되는 payload zip + build.json
scripts/test_exe.ps1    CI 에서 exe 설치/복구 동작을 실제로 검사
tools/                  poedb 데이터 수집 · 사전 생성 · 폰트 굽기 · 버전 갱신
installer/              수동 설치용 PowerShell 스크립트 (선택)
version.json            릴리스 버전 / 시즌 / PoB 버전
```

## 자동 빌드 · 배포

| 워크플로우 | 실행 시점 | 하는 일 |
|---|---|---|
| `build-release.yml` | `main` 푸시, 수동 실행, season-update 가 호출 | payload 생성 → exe 빌드 → exe 동작 테스트 → 릴리스 자산(`PoB-KR-Patcher.exe`, `KR-data.zip`, `latest.json`) 업로드 |
| `season-update.yml` | 매주 수요일 05:00(KST), 수동 실행 | PoB 최신 트리 버전 확인 → poedb 에서 한국어 사전 재생성 → 데이터가 바뀌었으면 버전을 올려 커밋하고 `build-release.yml` 로 새 릴리스 |

## 직접 빌드하기

```bash
python3 scripts/make_payload.py --version 1.0.0     # app/payload/ 생성
dotnet build app/PoB-KR-Patcher.csproj -c Release -o out
# 결과: out/PoB-KR-Patcher.exe (단일 파일, .NET Framework 4.8 — Windows 10/11 기본 포함)
```

exe 동작 테스트(Windows):

```powershell
pwsh -NoProfile -File scripts/test_exe.ps1 -Exe .\out\PoB-KR-Patcher.exe
```

명령줄 모드도 있습니다. (자동화·문제 확인용)

```
PoB-KR-Patcher.exe --apply [--dir "C:\...\Path of Building"] [--no-update] [--force]
PoB-KR-Patcher.exe --restore [--dir ...]
PoB-KR-Patcher.exe --check        # 최신 릴리스 확인
PoB-KR-Patcher.exe --info         # 내장 데이터 / 설치 상태
```

## 데이터 다시 만들기 (시즌 갱신을 직접 할 때)

```bash
pip install pillow lupa
python tools/fetch_pob.py            # PoB 의 Data/Gems.lua, TreeData/<ver>/tree.lua 준비
export POB_SRC=$(...)                # 위 스크립트가 알려 주는 경로
export POE_TREE_VERSION=3_30
python tools/run_all.py              # gems → passives → items → emit_lua → bake_font
python tools/verify.py               # 커버리지/정합성 확인 (개발 환경)
python scripts/make_payload.py       # exe 에 넣을 payload 갱신
```

`poedb.tw` 의 한국어 페이지를 원문으로 사용합니다. (공식 한국 API `poe.game.daum.net` 은 접근이 막혀 있어
동일한 인게임 문자열을 미러링하는 poedb 를 씁니다)

## 수동 설치 (예전 방식, 선택)

`installer/` 의 PowerShell 스크립트로도 설치할 수 있습니다. (`한글패치_적용.bat` / `영문원본_복구.bat`)
exe 와 결과는 같습니다. 특정 폴더에 강제로 설치하려면:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File installer\install.ps1 -Target "D:\Games\Path of Building"
```

## 라이선스 · 출처

- 이 저장소의 패처 코드와 사전: MIT (`LICENSE`)
- 한글 폰트 아틀라스: Noto Sans KR, SIL Open Font License 1.1
- 게임 데이터 명칭: © Grinding Gear Games, 한국어 표기는 poedb.tw 및 게임 내 표기를 따릅니다
- Path of Building Community Fork: 별도 라이선스(MIT)의 오픈소스 프로젝트이며, 이 패처는 그 **파일을 수정 배포하지 않고** 사용자 PC 에서 `KR/` 폴더와 로더 한 줄만 추가합니다
