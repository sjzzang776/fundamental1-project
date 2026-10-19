"""생성 모델 v2(nlu-gen-v2)의 짧은 답 코드 ↔ 키오스크 표준 문장.

v1 은 "맥스파이시 상하이 버거 2개 주세요"(15토큰)를 그대로 썼고, v2 는 "+M02*2"(약 5토큰)만 쓴다 → CPU 에서 답 쓰는 시간이 줄어든다.
모델 서버는 코드를 표준 문장으로 바꿔 백엔드에 넘기므로 백엔드는 v1 과 같다.
학습 데이터(model/scripts/make_nlu_data.py)와 서버(nlu_gen.py)가 이 파일 하나를 같이 쓴다.

코드
- 고정 표준 문장은 그대로 ("포장", "맞아요", "세트로 주세요" …), 모름은 "?"
- +M02*2  → 맥스파이시 상하이 버거 2개 주세요      +M02S*2 → … 세트 2개 주세요      +M02U*1 → … 단품 1개 주세요
- -M09    → 후렌치 후라이 빼 주세요                =M03*2  → 불고기 버거 2개로 바꿔 주세요
- D3      → 스프라이트로 주세요                     D1>D4   → 코카콜라 말고 아메리카노로 바꿔 주세요
메뉴·음료 번호는 학습할 때 meta.json 에 저장된 표를 쓴다 (메뉴가 바뀌면 다시 학습).
"""
import re

UNKNOWN = "?"


def tables(menu_names: list[str], drink_names: list[str]) -> dict:
    return {
        "menus": {f"M{i + 1:02d}": n for i, n in enumerate(menu_names)},
        "drinks": {f"D{i + 1}": n for i, n in enumerate(drink_names)},
    }


def encode(sentence: str, tab: dict, fixed: set[str]) -> str:
    """표준 문장 → 코드 (학습 데이터 만들 때). 모르는 모양이면 ValueError."""
    s = sentence.strip()
    if not s:
        return UNKNOWN
    if s in fixed:
        return s
    menu_code = {n: c for c, n in tab["menus"].items()}
    drink_code = {n: c for c, n in tab["drinks"].items()}
    names = "|".join(sorted(map(re.escape, menu_code), key=len, reverse=True))
    drinks = "|".join(sorted(map(re.escape, drink_code), key=len, reverse=True))
    if m := re.fullmatch(rf"({names}) 세트 (\d+)개 주세요", s):
        return f"+{menu_code[m[1]]}S*{m[2]}"
    if m := re.fullmatch(rf"({names}) 단품 (\d+)개 주세요", s):
        return f"+{menu_code[m[1]]}U*{m[2]}"
    if m := re.fullmatch(rf"({names}) (\d+)개 주세요", s):
        return f"+{menu_code[m[1]]}*{m[2]}"
    if m := re.fullmatch(rf"({names}) 빼 주세요", s):
        return f"-{menu_code[m[1]]}"
    if m := re.fullmatch(rf"({names}) (\d+)개로 바꿔 주세요", s):
        return f"={menu_code[m[1]]}*{m[2]}"
    if m := re.fullmatch(rf"({drinks}) 말고 ({drinks})로 바꿔 주세요", s):
        return f"{drink_code[m[1]]}>{drink_code[m[2]]}"
    if m := re.fullmatch(rf"({drinks})로 주세요", s):
        return drink_code[m[1]]
    raise ValueError(f"코드로 바꿀 수 없는 문장: {s}")


def decode(code: str, tab: dict, fixed: set[str]) -> str:
    """코드 → 표준 문장 (서버). 모르는 코드면 "" (모름)."""
    c = code.strip()
    if not c or c == UNKNOWN:
        return ""
    if c in fixed:
        return c
    menus, drinks = tab["menus"], tab["drinks"]
    if (m := re.fullmatch(r"\+(M\d\d)([SU]?)\*(\d+)", c)) and m[1] in menus:
        kind = {"S": " 세트", "U": " 단품"}.get(m[2], "")
        return f"{menus[m[1]]}{kind} {m[3]}개 주세요"
    if (m := re.fullmatch(r"-(M\d\d)", c)) and m[1] in menus:
        return f"{menus[m[1]]} 빼 주세요"
    if (m := re.fullmatch(r"=(M\d\d)\*(\d+)", c)) and m[1] in menus:
        return f"{menus[m[1]]} {m[2]}개로 바꿔 주세요"
    if (m := re.fullmatch(r"(D\d)>(D\d)", c)) and m[1] in drinks and m[2] in drinks:
        return f"{drinks[m[1]]} 말고 {drinks[m[2]]}로 바꿔 주세요"
    if c in drinks:
        return f"{drinks[c]}로 주세요"
    return ""
