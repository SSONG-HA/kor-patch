"""아이템 창·젬 창의 고정 문구 사전을 만든다.

poe2db 에서 뽑은 모드/이름과 달리, "Removing this item from Weapon 2 will give you:" 같은
UI 문장은 PoB 코드가 슬롯 이름을 끼워 만들어 냅니다. 슬롯 이름 조합을 여기서 미리 만들어
data/properties_exact.json (숫자 없는 줄) 으로 저장합니다.

결과:
  data/properties_exact.json    {영문: 한글}
  data/properties_templates.json {영문(숫자 포함): 한글(%1 %2)}
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import save_json, shape  # noqa: E402

SLOTS = {
    "Weapon 1": "무기 1",
    "Weapon 2": "무기 2",
    "Off Hand": "보조 장비",
    "Helmet": "투구",
    "Body Armour": "갑옷",
    "Gloves": "장갑",
    "Boots": "장화",
    "Amulet": "목걸이",
    "Ring 1": "반지 1",
    "Ring 2": "반지 2",
    "Belt": "허리띠",
    "Quiver": "화살통",
    "Flask 1": "플라스크 1",
    "Flask 2": "플라스크 2",
    "Flask 3": "플라스크 3",
    "Jewel": "주얼",
    "Weapon 1 Swap": "무기 1 교체",
    "Weapon 2 Swap": "무기 2 교체",
}

# 숫자가 들어가는 아이템 속성 줄 (영문 견본 → 한글 템플릿)
TEMPLATES: list[tuple[str, str]] = [
    ("Physical Damage: 10-20 (15.0 DPS)", "물리 피해: %1-%2 (%3 DPS)"),
    ("Elemental Damage: 10-20 (15.0 DPS)", "원소 피해: %1-%2 (%3 DPS)"),
    ("Fire Damage: 10-20 (15.0 DPS)", "화염 피해: %1-%2 (%3 DPS)"),
    ("Cold Damage: 10-20 (15.0 DPS)", "냉기 피해: %1-%2 (%3 DPS)"),
    ("Lightning Damage: 10-20 (15.0 DPS)", "번개 피해: %1-%2 (%3 DPS)"),
    ("Chaos Damage: 10-20 (15.0 DPS)", "카오스 피해: %1-%2 (%3 DPS)"),
    ("Total DPS: 15.0", "총 DPS: %1"),
    ("Critical Hit Chance: 5.00%", "치명타 명중 확률: %1%"),
    ("Attacks per Second: 1.20", "초당 공격 횟수: %1"),
    ("Reload Time: 0.80 sec", "재장전 시간: %1초"),
    ("Requires Level 79, 163 Dex", "요구 레벨 %1, 민첩 %2"),
    ("Requires Level 79, 163 Str", "요구 레벨 %1, 힘 %2"),
    ("Requires Level 79, 163 Int", "요구 레벨 %1, 지능 %2"),
    ("Requires Level 79, 163 Dex, 40 Str", "요구 레벨 %1, 민첩 %2, 힘 %3"),
    ("Requires Level 79, 163 Dex, 40 Int", "요구 레벨 %1, 민첩 %2, 지능 %3"),
    ("Requires Level 79, 163 Str, 40 Dex", "요구 레벨 %1, 힘 %2, 민첩 %3"),
    ("Requires Level 79, 163 Str, 40 Int", "요구 레벨 %1, 힘 %2, 지능 %3"),
    ("Requires Level 79, 163 Int, 40 Str", "요구 레벨 %1, 지능 %2, 힘 %3"),
    ("Requires Level 79, 163 Int, 40 Dex", "요구 레벨 %1, 지능 %2, 민첩 %3"),
    ("Level: 65", "레벨: %1"),
    ("Quality: +20%", "품질: +%1%"),
    ("Armour: 123", "방어도: %1"),
    ("Evasion Rating: 123", "회피: %1"),
    ("Energy Shield: 123", "에너지 보호막: %1"),
    ("Deflection Rating: 123", "편향: %1"),
    ("Item Level: 82", "아이템 레벨: %1"),
    ("Stack Size: 1/20", "중첩 개수: %1/%2"),
    ("Sockets: S S", "홈: S S"),
    ("Rune: 1", "룬: %1"),
    ("Cost: 12 Mana", "소모: 마나 %1"),
    ("Cost: 12 Spirit", "소모: 정신력 %1"),
    ("Cast Time: 0.80 sec", "시전 시간: %1초"),
    ("Cooldown Time: 0.50 sec", "재사용 대기시간: %1초"),
    ("Attack Time: 0.80 sec", "공격 시간: %1초"),
    ("Effectiveness of Added Damage: 100%", "추가 피해 효율: %1%"),
    ("Effectiveness of Added Damage: 100% (augmented)", "추가 피해 효율: %1% (증가)"),
    ("Radius: 1.2 metres", "반경: %1미터"),
    ("Experience: 12.3%", "경험치: %1%"),
    ("Runic Ward: 240", "룬 보호: %1"),
    ("Charm Slots: 0", "호신부 슬롯: %1"),
    ("Requires Level 50", "요구 레벨 %1"),
    ("-3.2m AoE Radius", "효과 범위 반경 %1m"),
    ("1.2m AoE Radius", "효과 범위 반경 %1m"),
    # ── 젬 정보 줄
    ("Tier: 1", "등급: %1"),
    ("Level: 20", "레벨: %1"),
    ("Level: 20 (Max)", "레벨: %1 (최대)"),
    ("Attack Speed: 90% of base", "공격 속도: 기본의 %1%"),
    ("Attack Damage: 250% of base", "공격 피해: 기본의 %1%"),
    ("Critical Strike Chance: 8.00%", "치명타 명중 확률: %1%"),
    ("Requires: Level 90, 157 Dex", "요구: 레벨 %1, 민첩 %2"),
    ("Requires: Level 90, 157 Str", "요구: 레벨 %1, 힘 %2"),
    ("Requires: Level 90, 157 Int", "요구: 레벨 %1, 지능 %2"),
    ("Requires: Level 90", "요구: 레벨 %1"),
    ("Cooldown: 1.00 sec", "재사용 대기시간: %1초"),
    ("Reservation: 30 Spirit", "예약: 정신력 %1"),
    ("Reservation: 30% Mana", "예약: 마나 %1%"),
    ("Chains 2 times", "%1회 연쇄"),
    ("Converts 80% of Physical damage to Lightning damage", "물리 피해의 %1%를 번개 피해로 전환"),
    ("Converts 80% of Physical damage to Fire damage", "물리 피해의 %1%를 화염 피해로 전환"),
    ("Converts 80% of Physical damage to Cold damage", "물리 피해의 %1%를 냉기 피해로 전환"),
    ("Converts 80% of Physical damage to Chaos damage", "물리 피해의 %1%를 카오스 피해로 전환"),
    ("Fires beams at up to 4 additional Enemies near the target", "목표 주변의 적 최대 %1명에게 광선을 추가로 발사"),
    ("Beam targeting radius is 3.2 metres", "광선 목표 반경 %1미터"),
    ("40% more chance to Shock", "감전 확률 %1% 증폭"),
]


# 슬롯 이름이 들어가는 문장 (숫자 없음)
SENTENCES = [
    "Removing this item from {slot} will give you:",
    "Equipping this item in {slot} will give you:",
    "Equipping this item in {slot} will give you:",
]

EXTRA_EXACT = {
    "Removing this item will give you:": "이 아이템을 제거하면 다음이 적용됩니다:",
    "Equipping this item will give you:": "이 아이템을 장착하면 다음이 적용됩니다:",
    "Select an item slot to compare": "비교할 아이템 슬롯을 선택하세요",
    "Toggle comparison tooltips": "비교 툴팁 전환",
    "Show tooltips only for affected slots:": "영향받는 슬롯의 툴팁만 표시:",
    "All slots": "모든 슬롯",
    "Bow": "활",
    "Crossbow": "석궁",
    "Staff": "지팡이",
    "Quarterstaff": "봉",
    "Wand": "마법봉",
    "Sceptre": "홀",
    "Spear": "창",
    "Flail": "도리깨",
    "Claw": "발톱",
    "Dagger": "단검",
    "One Hand Sword": "한손 검",
    "One Hand Axe": "한손 도끼",
    "One Hand Mace": "한손 철퇴",
    "Two Hand Sword": "양손 검",
    "Two Hand Axe": "양손 도끼",
    "Two Hand Mace": "양손 철퇴",
    "Shield": "방패",
    "Buckler": "버클러",
    "Focus": "집중구",
    "Quiver": "화살통",
    "Gloves": "장갑",
    "Boots": "장화",
    "Body Armour": "갑옷",
    "Helmet": "투구",
    "Amulet": "목걸이",
    "Ring": "반지",
    "Belt": "허리띠",
    "Life Flask": "생명력 플라스크",
    "Mana Flask": "마나 플라스크",
    "Charm": "호신부",
    "Jewel": "주얼",
    "Rune": "룬",
    "Soul Core": "영혼 핵",
    "Requires: Bow": "요구: 활",
    "Requires: Crossbow": "요구: 석궁",
    "Requires: Quarterstaff": "요구: 봉",
    "Requires: Spear": "요구: 창",
    "Requires: Shield": "요구: 방패",
    "Requires: Buckler": "요구: 버클러",
    "Requires: Focus": "요구: 집중구",
    "Requires: Staff": "요구: 지팡이",
    "Requires: Wand": "요구: 마법봉",
    "Requires: Sceptre": "요구: 홀",
    "Requires: Claw": "요구: 발톱",
    "Requires: Dagger": "요구: 단검",
    "Requires: Sword": "요구: 검",
    "Requires: Axe": "요구: 도끼",
    "Requires: Mace": "요구: 철퇴",
    "Requires: Flail": "요구: 도리깨",
    "Minion Info": "하수인 정보",
    "Culling Strike": "처형 일격",
    "Runic Ward": "룬 보호",
    "Charm Slots": "호신부 슬롯",
    "Cannot Chain": "연쇄 불가",
    "Cast Time: Instant": "시전 시간: 즉시",
    "Requires: Level 90, 86 Dex, 86 Int": "요구: 레벨 90, 민첩 86, 지능 86",
}


def main() -> None:
    exact = dict(EXTRA_EXACT)
    for slot, ko in SLOTS.items():
        exact["Removing this item from %s will give you:" % slot] = "%s 슬롯에서 이 아이템을 제거하면 다음이 적용됩니다:" % ko
        exact["Equipping this item in %s will give you:" % slot] = "%s 슬롯에 이 아이템을 장착하면 다음이 적용됩니다:" % ko
    templates = {}
    for en, ko in TEMPLATES:
        templates[shape(en)] = ko
    save_json("properties_exact.json", exact)
    save_json("properties_templates.json", templates)
    print("속성 문구 %d개 / 템플릿 %d개" % (len(exact), len(templates)))


if __name__ == "__main__":
    main()
