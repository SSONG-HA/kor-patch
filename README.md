# PoB-KR-Patcher — 제작 노트

Path of Building 의 화면 글자를 인게임 한국어 명칭으로 보여 주는 경량 패처.
**한 실행 파일(PoB-KR-Patcher.exe)** 이 PoE1(PoB Community Fork)과 PoE2(Path of Building PoE2)를
각각 패치합니다.

- 배포: https://github.com/SSONG-HA/kor-patch/releases (v2.0.0 부터 PoE1·PoE2 통합)
- 계산 엔진은 건드리지 않고 `DrawString` / `DrawStringWidth` 만 감싸므로 **계산값은 영문판과 완전히 같습니다.**

## 구조

```
app/                     통합 런처 (C#, net48, 단일 exe)
src/KR/                  PoE1 런타임 + 사전 + 폰트 아틀라스  → 배포 자산 KR-data.zip
src/KR2/                 PoE2 런타임 + 사전 + 폰트 아틀라스  → 배포 자산 KR-data-poe2.zip
  init.lua               후크 설치 (DrawString / DrawStringWidth), F2 전환, 자동 업데이트
  draw.lua               한글 레이아웃·그리기 (색상 이스케이프, 정렬, 개행)
  font.lua               글리프 아틀라스 로딩/선택 (DPI 배율 대응, 전체 음절 폴백)
  shape.lua              숫자 정규화(템플릿 키) — 파이썬 shape() 와 동일 규칙
  Data/exact.lua         영→한 정확 일치 사전
  Data/templates.lua     숫자 자리표시(%1 %2) 문구 템플릿
  Fonts/kr_*.png         크기별 글리프 아틀라스 (12~64px) + kr_full.png(11,172자 폴백)
  Fonts/metrics.lua      아틀라스 메트릭 (반드시 PNG 와 같은 실행에서 생성)
tools/                   PoE1 데이터 파이프라인 (poedb)
poe2/tools/              PoE2 데이터 파이프라인 (poe2db + PoB2 데이터)
scripts/make_payload.py  src/KR·src/KR2 → 내장 payload zip + build json
```

## 동작 방식

- PoB의 모든 텍스트는 전역 `DrawString`/`DrawStringWidth`를 지난다. 이 둘만 덮어쓴다.
- 문자열 → 사전 조회(정확 일치 → 숫자 템플릿 → "이름, 베이스" / 나열형 / "이름 (태그)" 조합)
  → 결과가 ASCII면 엔진 폰트로 그대로, 한글이면 아틀라스 쿼드로 그린다.
- `Modules/Main.lua` 맨 앞에 로더 한 줄을 넣고, 나머지는 각 데이터 폴더(KR / KR2)에만 둔다.

## PoE2 데이터 수집 (`poe2/tools/`)

| 스크립트 | 하는 일 | 결과 |
|---|---|---|
| `tree.py` | poe2db 한글/영문 패시브 트리(JSON) + PoB2 `TreeData/*/tree.lua` 를 **노드 ID** 로 짝짓기 | `tree_names.json`, `tree_stats.json`, `tree_classes.json` |
| `gems.py` | poe2db 젬 목록 4종의 슬러그 ↔ PoB2 `Data/Gems.lua` 이름 | `gems.json` |
| `items.py` | poe2db 아이템 클래스 페이지의 `ModsView` JSON(영/한 같은 순서) → 숫자가 같을 때만 채택. 베이스·유니크 이름도 같은 페이지에서 | `mods_exact.json`, `mods_static.json`, `bases.json`, `uniques.json` |
| `properties.py` | 아이템·젬 창의 고정 문구(슬롯별 문장, 속성 줄) | `properties_exact.json`, `properties_templates.json` |
| `emit_lua.py` | 위 JSON + `ui_ko.json` + `calcs_ko.json` → 런타임 사전 | `src/KR2/Data/exact.lua`, `templates.lua` |
| `bake_font.py` | 사전에 쓰인 **모든 글자**를 스캔해 PNG 아틀라스 + metrics.lua 를 한 번에 생성 | `src/KR2/Fonts/*` |

PoE2 는 노드 ID 체계가 게임과 같아서, PoE1 처럼 슬러그를 추측하지 않고도 트리 문구를 정확히 맞출 수 있습니다.

## 재생성 (PoE2)

```bash
export POB2_SRC=/path/to/PathOfBuilding-PoE2/src      # PoB2 원본 체크아웃
python3 poe2/tools/tree.py
python3 poe2/tools/gems.py
python3 poe2/tools/items.py
python3 poe2/tools/properties.py
python3 poe2/tools/emit_lua.py
python3 poe2/tools/bake_font.py
python3 poe2/tools/verify.py
```

## 검증

```bash
# PoE2 런타임·화면 검증 (PoB2 를 KR2 와 함께 복사해 둔 폴더를 TEST_POB 로 지정)
TEST_POB=/path/to/pob2-with-kr2 python3 poe2/tools/test_runtime.py
TEST_POB=/path/to/pob2-with-kr2 python3 poe2/tools/audit_render.py    # 실제 화면·툴팁 번역률
python3 poe2/tools/verify.py                                          # 문법·폰트 정합성·커버리지
```

- `test_runtime.py` — 한글 켬/끔 계산값 동일, 8개 화면 그리기, F2 전환, 사전 조회 표본, 미등록 글자
- `audit_render.py` — 화면에 실제로 그려지는 문자열과 노드/아이템/젬 툴팁 전부를 모아 번역률 측정
- `verify.py` — v1.1.2 때 한글이 깨진 원인(아틀라스 ↔ metrics 불일치)을 매번 검사

## 알려진 한계

- 젬 툴팁의 능력치 설명 문장(`Data/StatDescriptions` 문장 틀)은 아직 영문입니다.
  poe2db 한글 페이지에 같은 문장 틀이 없어 자동 대조가 어렵습니다.
- 플레이어가 지은 희귀 아이템 이름은 그대로 표시합니다.
- PoB2 가 개발 중(beta)이라 파일 구조가 바뀌면 `verify.py` 의 기준 경로를 갱신해야 합니다.
