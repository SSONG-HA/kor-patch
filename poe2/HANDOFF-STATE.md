# PoE2 한글 패처 — 작업 상태 (2026-11-23)

## 한 줄 요약

PoE2(Path of Building PoE2) 한글 패처를 **PoE1 과 같은 실행 파일(PoB-KR-Patcher.exe)** 에 통합해
`v2.0.0` 으로 배포했습니다. 실행 파일 한 창에 PoE1/PoE2 칸이 따로 있고, 데이터는 각각
PoB 폴더의 `KR` / `KR2` 로 들어가 섞이지 않습니다.

- 릴리스: https://github.com/SSONG-HA/kor-patch/releases/tag/v2.0.0
- 자산: `PoB-KR-Patcher.exe`, `KR-data.zip`(PoE1), `KR-data-poe2.zip`(PoE2), `latest.json`(poe2 블록), `manual-ko.txt`

## 구성

```
src/KR2/            PoE2 런타임 + 사전 + 폰트 (PoE1 src/KR 과 같은 구조)
poe2/tools/         PoE2 데이터 파이프라인
  tree.py           poe2db 한글/영문 트리(JSON) ↔ PoB2 tree.lua 를 노드 ID 로 짝짓기
  gems.py           poe2db 젬 목록 4종 슬러그 ↔ PoB2 Gems.lua
  items.py          poe2db 아이템 클래스 페이지 ModsView(영/한 같은 순서) + 베이스/유니크
  properties.py     아이템·젬 창 고정 문구(슬롯 문장·속성 줄)
  emit_lua.py       → src/KR2/Data/{exact,templates}.lua
  bake_font.py      사전 전체 글자 스캔 → PNG 아틀라스 + metrics.lua
  verify.py         문법·숫자 정규화·폰트 정합성·커버리지
  test_runtime.py   헤드리스 PoB2: 계산값 동일·화면 8종·F2 후크·사전 표본
  audit_render.py   실제 화면·툴팁 번역률 측정
  fixtures.py       테스트용 빌드 생성기(클래스·노드·젬·아이템)
  pob2_harness.py   헤드리스 실행 도우미
```

## 데이터 규모 (v2.0.0)

| 항목 | 개수 |
|---|---|
| exact 사전 | 9,009 |
| templates 사전 | 1,717 (모드 951 + 계산 비교 문형 704 + 속성/젬 62) |
| 패시브 노드 이름 | 1,993 / 1,995 (99.9%) |
| 패시브 효과 문구 | 2,572 / 2,626 (97.9%) |
| 젬 이름 | 942 / 961 (98.0%) |
| 베이스 아이템 이름 | 2,067 |
| 유니크 아이템 이름 | 424 |
| 폰트 글자 | 861자 × 11크기 + 11,172자 폴백 |

## 화면 감사 (audit_render.py, 테스트 빌드 기준)

| 영역 | 번역률 |
|---|---|
| 트리 노드 툴팁 | 98.8% |
| 아이템 툴팁 | 95.7% |
| 설정 드롭다운 | 72.5% |
| 젬 툴팁 | 39.8% |
| 화면 문자열 | 59.6% |
| 전체 | 50.5% |

- 화면 문자열의 미번역은 대부분 **숫자만 있는 줄**(`163`, `0, 0, 0`)입니다. 숫자는 영문 폰트로 그대로
  그려지므로 실제로는 번역이 필요 없는 항목입니다.
- 젬 툴팁의 남은 부분은 **능력치 설명 문장**(`Deals 2343 to 3453 Chaos Damage`)입니다.

## 알려진 한계 / 다음 과제

1. **젬 능력치 설명 문장** — PoB2 `Data/StatDescriptions/*.lua`(764개 파일)의 문장 틀을 옮겨야 합니다.
   poe2db 한글 젬 페이지에는 같은 문장 틀이 없어 자동 대조가 어렵습니다. (PoE1 과 같은 한계)
2. **플레이어가 지은 희귀 아이템 이름** — 번역하지 않고 그대로 표시.
3. **지역 이름**(`Act 4: Eye of Hinekora`) — 게임 데이터(액트/지역) 사전이 아직 없습니다.
4. **워크플로우 권한** — GitHub App 에 `workflows` 권한이 없어 `.github/workflows/build-release.yml`
   을 저장소에서 고칠 수 없습니다. 그래서
   - 지금 워크플로우는 PoE1 자산만 올립니다. 실행 파일에는 두 게임 데이터가 모두 들어가므로
     PoE2 패치는 동작하지만, `KR-data-poe2.zip` 과 `latest.json` 의 poe2 블록은
     `scripts/publish_extra.py --tag vX.Y.Z` 로 릴리스 뒤에 한 번 올려야 합니다.
   - 통합 워크플로우 전문은 `docs/build-release-poe2.yml` 에 있습니다. 사용자가 GitHub 웹에서
     이 내용으로 바꾸면 `publish_extra.py` 없이도 한 번에 배포됩니다.

## 재생성 절차 (게임 업데이트 시)

```bash
export POB2_SRC=/path/to/PathOfBuilding-PoE2/src
python3 poe2/tools/tree.py && python3 poe2/tools/gems.py && python3 poe2/tools/items.py
python3 poe2/tools/properties.py && python3 poe2/tools/emit_lua.py && python3 poe2/tools/bake_font.py
python3 poe2/tools/verify.py
TEST_POB=/path/to/pob2 TEST_POB=... python3 poe2/tools/test_runtime.py
```

PoB2 원본을 KR2 와 함께 두는 테스트 폴더 만드는 법:

```bash
cp -r <PathOfBuilding-PoE2>/src/* pob2test/          # 런타임
cp -r <repo>/src/KR2 pob2test/KR2
# Modules/Main.lua 맨 앞에 로더 두 줄 삽입 (설치 프로그램이 하는 일과 동일)
```
