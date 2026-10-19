"""의도 파악 학습 데이터 만들기 (손님 말 → 키오스크 표준 문장).

백엔드 규칙(backend/app/services/nlu.py)이 못 알아들은 말을 표준 문장 하나로 바꾸는 모델을 학습하기 위한 데이터.
- 1번 분류 모델(nlu-intent-v1): 손님 말 + 지금 단계 → 표준 문장 18개 중 하나 또는 NONE(모름)
- 2번 생성 모델(nlu-gen-v1): 손님 말 + 지금 단계 → 표준 문장 (메뉴 이름이 들어간 문장까지)

말투 조각(앞말·끝말·사투리·띄어쓰기 없음·인식 오류)을 섞어 늘린다.
시험용 문장(model/scripts/nlu_testset.csv)은 사람이 따로 쓴 것으로, 학습 데이터와 겹치지 않게 뺀다.

    python model/scripts/make_nlu_data.py          # → model/data/nlu/ (cls_*.csv, gen_*.jsonl, gen2_*.jsonl, testset.csv, gen_testset.csv, gen2_meta.json) + nlu_data.zip
"""
import csv
import json
import random
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import nlu_codes  # noqa: E402  생성 모델 v2 의 짧은 답 코드 (서버와 같은 파일)

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "nlu"
TESTSET = Path(__file__).with_name("nlu_testset.csv")
GEN_TESTSET = Path(__file__).with_name("nlu_gen_testset.csv")  # 메뉴 이름이 들어간 시험 문장 (생성 모델용)
SEED = 20261019

STEPS = ["DINE_TYPE", "MENU", "OPTION", "CONFIRM", "COUPON", "PAYMENT"]
# 모델 입력에 넣는 단계 이름 (서버 model/app/nlu_intent.py 와 같아야 함 → 학습 결과 meta.json 에도 저장)
STEP_NAMES = {
    "DINE_TYPE": "식사 장소", "MENU": "메뉴", "OPTION": "세트 옵션",
    "CONFIRM": "주문 확인", "COUPON": "쿠폰", "PAYMENT": "결제",
}
NONE = "NONE"

# ---------- 1. 표준 문장별 손님 말 (단계, 말 목록) ----------
# 표준 문장은 백엔드 규칙이 그대로 알아듣는 문장이다 (backend 에서 확인함).
INTENTS = {
    "매장에서": (["DINE_TYPE", "MENU"], [
        "먹고 갈게요", "여기서 먹을게요", "여기서 먹고 갈래", "앉아서 먹을 거예요", "안에서 먹어요", "가게에서 먹을게",
        "여기 앉아서 먹고 가요", "먹고 갈 거야", "여기서요", "드시고 갈게요", "여기서 묵고 갈끼다", "여서 먹고 가유",
        "먹고 가께요", "안에서요", "자리에서 먹을게요", "여기 자리 있죠 여기서 먹을게", "매장", "매장 식사요",
        "가지고 안 가고 여기서", "포장 말고 먹고 갈게요", "홀에서 먹을게요", "식당에서 먹어요", "앉아서요",
        "여기서 다 먹고 갈 거예요", "손주랑 여기서 먹을 거야", "먹고 가는 거로", "여기서 묵을게요", "안에서 먹고 가요",
    ]),
    "포장": (["DINE_TYPE", "MENU"], [
        "가져갈게요", "싸 주세요", "집에 가서 먹을게요", "들고 갈게요", "포장해 주세요", "가지고 갈게",
        "테이크아웃이요", "봉지에 담아 주세요", "봉투에 넣어 줘", "싸 가지고 갈라고", "가져가서 먹을 거예요",
        "갖고 갈게요", "포장이요", "싸 줘요", "집에 갖고 갈 거야", "들고 가께요", "가 가지고 갈끼다", "싸 가유",
        "차에서 먹을 거예요", "손주 갖다 줄 거라 싸 주세요", "밖에서 먹을게요", "가지고 나갈게요", "담아 주세요 가져가게",
        "포장으로 해 줘", "여기서 안 먹어요", "안 먹고 가요 싸 주세요", "집에서 먹을 거", "봉다리에 싸 줘",
    ]),
    "세트로 주세요": (["OPTION", "MENU"], [
        "세트로요", "세트로 할게요", "음료랑 감자도 같이", "감자랑 콜라 같이 주세요", "세트 메뉴로", "세트요",
        "다 같이 나오는 걸로", "음료수도 같이 주세요", "같이 나오는 거로 해 줘", "세트로 해 주이소", "세트로 줘유",
        "감자튀김이랑 음료 있는 걸로", "묶음으로 주세요", "세뜨로", "셋트로 주세요", "세트로 할래",
    ]),
    "단품으로 주세요": (["OPTION", "MENU"], [
        "그것만 주세요", "햄버거만 주세요", "버거만요", "단품이요", "하나만 따로", "음료는 필요 없어요 버거만",
        "그냥 그거 하나만", "단품으로 할게요", "따로 아무것도 필요 없어요", "감자 음료 빼고 버거만", "딴 건 됐고 그거만",
        "단품으로 줘유", "단품으로 주이소", "버거 하나만 딸랑", "세트 말고 단품", "세트는 됐어요",
    ]),
    "라지로 주세요": (["OPTION"], [
        "큰 걸로 주세요", "크게 해 줘", "큰 거요", "라지요", "제일 큰 사이즈", "양 많이", "넉넉하게 큰 거",
        "큰 사이즈로 할게요", "라지 사이즈", "크게 주이소", "큰 걸로 줘유", "많이 주세요 큰 걸로",
    ]),
    "미디엄으로 주세요": (["OPTION"], [
        "보통으로 주세요", "중간 거요", "기본 사이즈로", "미디엄이요", "보통 크기", "작은 걸로", "그냥 기본으로",
        "중간 사이즈로 할게요", "보통이요", "적당한 걸로", "보통으로 줘유", "기본 크기로 주이소",
    ]),
    "추천해 주세요": (["MENU"], [
        "뭐가 맛있어요", "뭐 먹지", "아무거나 맛있는 걸로", "잘 나가는 거 있어요", "제일 많이 먹는 거", "골라 줘요",
        "뭘 먹어야 될지 모르겠네", "좋은 걸로 알아서 줘요", "사람들이 많이 시키는 거", "처음 와서 잘 몰라요",
        "뭐가 좋아요", "추천 좀 해 줘", "알아서 골라 줘", "맛있는 거 주세요", "인기 있는 거", "뭐 시켜야 돼",
        "어르신들 많이 드시는 거", "손주가 좋아할 만한 거", "안 매운 거 아무거나 추천", "뭐 먹을까요",
    ]),
    "주문할게요": (["MENU"], [
        "다 골랐어요", "이제 됐어요", "이거면 돼요", "그만 고를게요", "끝이요", "이걸로 할게요", "다 됐어",
        "더 안 시켜요", "더는 없어요", "이제 계산해 주세요", "계산이요", "결제할게요", "그거면 됐어", "이대로 주문",
        "이만 할게요", "다 시켰어요", "주문 넣어 주세요", "이걸로 끝", "이제 돈 낼게요", "그만 됐어요",
    ]),
    "맞아요": (["CONFIRM"], [
        "네 그렇게 해 주세요", "그렇게 해 줘", "그래요", "좋아요", "그대로요", "맞게 됐어요", "그걸로 할게요",
        "틀린 거 없어요", "다 맞네", "그거 맞아", "응 그렇게", "예 맞습니다", "그려", "그래 그렇게 해", "됐어 그렇게",
        "맞심더", "맞아유", "어 맞아", "그렇지", "고대로 해 줘", "오케이", "옳지 그거", "맞다 맞다",
    ]),
    "수정할게요": (["CONFIRM"], [
        "틀렸어요", "그거 아니에요", "다시 고를게요", "바꿀래요", "잘못 시켰어", "이거 아닌데", "다르게 할래",
        "고칠게요", "잘못 들어갔어요", "그게 아니고", "아니 바꿔 줘", "안 시켰는데", "그거 말고", "다시 할래요",
        "아닌데요", "틀린데", "아니여 다시", "아이다 다시 할게", "잠깐 바꿀게", "수정이요",
    ]),
    "쿠폰 있어요": (["COUPON"], [
        "쿠폰 있어요", "있어요", "앱에 쿠폰 있어", "할인권 있어요", "바코드 있어요", "쿠폰 쓸게요", "할인 쿠폰 써 줘",
        "폰에 쿠폰 있어", "있지 쿠폰", "쿠폰 있는데", "쿠폰 사용할래요", "쿠폰 보여 줄게요", "있심더", "있어유",
        "손주가 준 쿠폰 있어", "할인되는 거 있어요",
    ]),
    "없어요": (["COUPON"], [
        "없어요", "쿠폰 없어", "그런 거 없어요", "그냥 결제할게요", "쿠폰 없이 할게요", "안 써요", "할인 없어요",
        "없는데요", "앱 안 써요", "몰라요 그냥 할게", "쿠폰 그런 거 몰라", "없슈", "없심더", "업어요", "쿠폰 안 해요",
        "필요 없어요", "그냥 계산해 줘", "패스", "됐어요 그냥 해요", "아니 없어",
    ]),
    "다시 결제할게요": (["PAYMENT"], [
        "다시 해 볼게요", "한 번 더 할게요", "다시 꽂을게요", "카드 다시 넣어 볼게", "다시 결제해 주세요",
        "한 번만 더", "다시요", "다른 카드로 할게요", "다시 해 봐요", "또 해 볼게", "다시 해 보이소", "다시 할게유",
    ]),
    "장바구니 보여줘": (["MENU", "OPTION", "CONFIRM"], [
        "뭐 시켰지", "내가 뭐 골랐어요", "지금까지 뭐 담겼어요", "주문한 거 보여 줘", "뭐 들어갔어요",
        "몇 개 시켰지", "얼마 나왔어요 지금", "담은 거 다시 말해 줘", "고른 거 확인", "주문 목록 보여 줘",
        "뭐 담았는지 모르겠네", "지금 뭐뭐 있어",
    ]),
    "하나 더 주세요": (["MENU"], [
        "그거 하나 더", "똑같은 걸로 하나 더", "한 개 더요", "같은 거 또", "그거 또 하나", "하나 더 추가",
        "그것도 하나 더", "같은 걸로 한 개 더 줘", "하나 더 넣어 줘", "그거 한 개 더 주이소",
    ]),
    "처음으로": (STEPS, [
        "처음부터 다시", "맨 처음으로", "처음 화면으로", "다시 시작할게요", "처음부터 할래", "첨부터 다시",
        "처음으로 돌아가 줘", "앞으로 다시 가 줘 처음", "처음 화면 보여 줘", "새로 할게요 처음부터",
    ]),
    "취소": (STEPS, [
        "안 살래요", "안 먹을래", "그만할래요", "주문 안 할게요", "됐어요 안 사요", "다 취소", "주문 취소해 줘",
        "그만 둘게", "안 할래", "필요 없어 그만", "나중에 올게요", "안 먹어요 그만", "치아라 안 살란다",
    ]),
    "직원 불러줘": (STEPS, [
        "사람 불러 줘요", "여기요", "저기요 좀 도와주세요", "모르겠어요 도와줘요", "어떻게 하는 거야 사람 좀",
        "알바생 불러 줘", "점원 불러 주세요", "사장님 불러 줘", "아가씨 좀 와 봐요", "누구 없어요", "도와주세요",
        "이거 어떻게 해요 사람 불러", "학생 좀 와 봐", "여보세요 사람 좀",
    ]),
}

# 단계에 따라 뜻이 달라지는 짧은 대답
YES = ["응", "어", "그래", "좋아", "예", "네", "그려", "오냐", "됐어", "그렇게 해", "그러지", "그러자", "어어 그래", "웅", "고고"]
NO = ["아니", "아뇨", "아니요", "싫어", "놉", "아녀", "아이다", "됐어 안 해", "노노", "아니야"]
YES_BY_STEP = {"CONFIRM": "맞아요", "COUPON": "쿠폰 있어요", "PAYMENT": "다시 결제할게요"}
NO_BY_STEP = {"CONFIRM": "수정할게요", "COUPON": "없어요"}
# "다 됐어"류는 메뉴 단계에서는 주문하겠다는 뜻
DONE_WORDS = ["됐어", "됐어요", "다 됐다", "그게 다야", "그게 다예요", "이게 끝"]

# 키오스크와 상관없는 말·뜻이 분명하지 않은 말 → NONE (모델이 지어내지 않게)
NONE_TEXTS = [
    "오늘 날씨 좋네", "아이고 허리야", "글씨가 너무 작네", "잠깐만요", "음", "어", "어디 보자", "가만있어 봐", "뭐라고",
    "안 들려요", "다시 말해 봐", "이게 뭐야", "화장실 어디예요", "몇 시까지 해요", "와이파이 비번 뭐예요",
    "우리 손주 몇 살이게", "아 배고프다", "얼마 전에 왔었는데", "이거 신기하네", "기계가 말을 하네", "좀 천천히 말해 줘",
    "목소리가 너무 커", "핸드폰 어디 뒀지", "지갑 어디 갔지", "여보 뭐 먹을래", "애들은 뭐 먹는대", "잠깐 전화 좀",
    "여기 주차 돼요", "물 어디 있어요", "냅킨 좀", "케첩 더 주세요", "빨대 어디", "짜장면 주세요", "김치찌개 하나",
    "떡볶이 있어요", "순대 주세요", "칼국수 하나 줘", "소주 한 병", "피자 주세요", "삼겹살", "라면 있어요",
    "아 그게 아니라 음", "그 뭐냐 그거", "있잖아 그거", "에휴", "참 나", "허허", "어머나", "아이고", "흠",
    "이거 누르면 돼", "화면이 안 보여", "버튼이 어디야", "안경 놓고 왔네", "기다려 봐 생각 좀",
    "옛날에는 이런 거 없었는데", "요새 다 기계네", "우리 때는 말이야", "손이 떨려서", "춥다", "덥네",
]
FOREIGN_MENU = ["짜장면", "김밥", "떡볶이", "라면", "냉면", "비빔밥", "피자", "치킨 한 마리", "돈까스", "우동"]

# ---------- 2. 메뉴 (생성 모델용) ----------
MENUS = {
    "빅맥": (True, ["빅맥", "빅 맥", "빅막", "두 층짜리 큰 버거", "제일 유명한 버거", "빅맥이라는 거", "빅맥 버거"]),
    "맥스파이시 상하이 버거": (True, ["매운 닭고기 버거", "매운 거", "매콤한 치킨 버거", "상하이 그거", "맥스파이시", "매운 버거"]),
    "불고기 버거": (True, ["불고기 들어간 버거", "제일 싼 버거", "달달한 고기 버거", "불고기 햄버거"]),
    "더블 불고기 버거": (True, ["불고기 두 장", "고기 두 장짜리 불고기", "불고기 두 개 들어간 거", "더블 불고기"]),
    "1955 버거": (True, ["천구백오십오 버거", "옛날 버거 그거", "일구오오", "1955"]),
    "쿼터파운더 치즈": (True, ["쿼터 파운드", "두꺼운 고기 치즈 버거", "쿼터파운더", "쿼터 치즈"]),
    "치즈버거": (True, ["치즈 햄버거", "치즈 들어간 작은 버거", "치즈 버거"]),
    "맥치킨": (True, ["그냥 치킨 버거", "안 매운 닭고기 버거", "맥치킨", "닭 버거"]),
    "후렌치 후라이 (M)": (False, ["감자", "감자 튀긴 거", "후렌치 후라이", "프라이", "감자칩 긴 거"]),
    "맥너겟 4조각": (False, ["닭 튀김 조각", "너겟", "치킨 조각"]),
    "치즈스틱 2조각": (False, ["치즈 막대", "늘어나는 치즈", "치즈스틱"]),
    "코카콜라 (M)": (False, ["콜라", "까만 탄산", "코크"]),
    "코카콜라 제로 (M)": (False, ["살 안 찌는 콜라", "설탕 없는 콜라", "다이어트 콜라", "제로 콜라"]),
    "스프라이트 (M)": (False, ["사이다", "투명한 탄산", "칠성사이다 같은 거"]),
    "아메리카노 (M)": (False, ["커피", "블랙커피", "따뜻한 커피", "아메리카노"]),
    "오렌지 주스": (False, ["오렌지", "주스", "오렌지 쥬스"]),
    "맥플러리 오레오": (False, ["오레오 아이스크림", "과자 섞인 아이스크림", "맥플러리"]),
    "아이스크림 콘": (False, ["콘", "아이스크림 하나", "소프트 아이스크림"]),
    "애플파이": (False, ["사과 파이", "파이", "애플 파이"]),
}
DRINK_OPTIONS = {
    "코카콜라": ["콜라", "까만 탄산"], "코카콜라 제로": ["제로", "설탕 없는 콜라", "다이어트 콜라"],
    "스프라이트": ["사이다", "투명한 탄산"], "아메리카노": ["커피", "블랙커피"], "오렌지 주스": ["주스", "오렌지"],
}
QTY = [(1, ["하나", "한 개", "1개", "한 개만"]), (2, ["두 개", "둘", "2개"]),
       (3, ["세 개", "셋", "3개"]), (4, ["네 개", "넷"])]

# ---------- 말투 늘리기 ----------
PREFIXES = ["", "", "", "음 ", "어 ", "저기 ", "그 ", "아 ", "저 ", "여기 ", "학생 ", "아가씨 ", "음 그러니까 ", "어디 보자 "]
SUFFIXES = ["", "", "", " 요", " 응", " 좀", " 빨리", " 그거"]
SWAPS = [("주세요", "주이소"), ("주세요", "줘유"), ("주세요", "줘"), ("할게요", "할께요"), ("할게요", "할라고"),
         ("요", "유"), ("어요", "어유"), ("해 줘", "해 도"), ("거예요", "거여"), ("주세요", "주시오")]
STT_CHARS = {"세": "새", "게": "개", "요": "여", "어": "아", "줘": "저", "포": "토", "장": "짱", "갈": "깔"}


def vary(text: str, rng: random.Random) -> str:
    t = rng.choice(PREFIXES) + text + rng.choice(SUFFIXES)
    if rng.random() < 0.3:
        a, b = rng.choice(SWAPS)
        t = t.replace(a, b, 1)
    r = rng.random()
    if r < 0.2:
        t = t.replace(" ", "")  # 음성 인식이 띄어쓰기를 안 함
    elif r < 0.3:
        words = t.split()
        if len(words) > 1:
            i = rng.randrange(len(words))
            words.insert(i, words[i])  # 말을 되풀이
            t = " ".join(words)
    if rng.random() < 0.12:
        chars = [i for i, c in enumerate(t) if c in STT_CHARS]
        if chars:
            i = rng.choice(chars)
            t = t[:i] + STT_CHARS[t[i]] + t[i + 1:]  # 음성 인식 오류
    return " ".join(t.split()).strip()


def cls_rows(rng: random.Random, per_phrase: int) -> list[tuple[str, str, str]]:
    rows = []
    for label, (steps, phrases) in INTENTS.items():
        for phrase in phrases:
            for _ in range(per_phrase):
                rows.append((rng.choice(steps), vary(phrase, rng), label))
    for _ in range(per_phrase * 3):
        for word in YES:
            step = rng.choice(list(YES_BY_STEP))
            rows.append((step, vary(word, rng), YES_BY_STEP[step]))
        for word in NO:
            step = rng.choice(list(NO_BY_STEP))
            rows.append((step, vary(word, rng), NO_BY_STEP[step]))
        for word in DONE_WORDS:
            rows.append(("MENU", vary(word, rng), "주문할게요"))
    for text in NONE_TEXTS:
        for _ in range(per_phrase * 2):
            rows.append((rng.choice(STEPS), vary(text, rng), NONE))
    for food in FOREIGN_MENU:
        for end in ["주세요", "하나 줘", "있어요", "먹을래", "시킬게요", "두 개요"]:
            rows.append((rng.choice(["MENU", "OPTION"]), vary(f"{food} {end}", rng), NONE))
    return rows


def gen_rows(rng: random.Random, cls: list[tuple[str, str, str]]) -> list[tuple[str, str, str]]:
    """생성 모델용: 분류 데이터(NONE → 빈 문자열) + 메뉴 이름을 써야 하는 문장."""
    rows = [(s, t, "" if label == NONE else label) for s, t, label in cls]
    verbs = ["주세요", "줘", "주이소", "줄래요", "먹을게요", "시킬게요", "할게요", "로 주세요", "요"]
    for full_name, (has_set, names) in MENUS.items():
        menu = full_name.split(" (")[0]  # "후렌치 후라이 (M)" → "후렌치 후라이" (규칙은 둘 다 알아들음)
        for name in names:
            for n, words in QTY:
                for _ in range(2):
                    w = rng.choice(words)
                    v = rng.choice(verbs)
                    if has_set and rng.random() < 0.35:
                        set_word = rng.choice(["세트", "세트로", "음료랑 같이"])
                        rows.append(("MENU", vary(f"{name} {set_word} {w} {v}", rng), f"{menu} 세트 {n}개 주세요"))
                    elif has_set and rng.random() < 0.2:
                        rows.append(("MENU", vary(f"{name} 단품 {w} {v}", rng), f"{menu} 단품 {n}개 주세요"))
                    else:
                        rows.append(("MENU", vary(f"{name} {w} {v}", rng), f"{menu} {n}개 주세요"))
            for end in ["빼 줘", "빼 주세요", "안 먹을래 빼", "취소해 줘", "필요 없어"]:
                rows.append((rng.choice(["MENU", "CONFIRM"]), vary(f"{name} {end}", rng), f"{menu} 빼 주세요"))
            for n, words in QTY[1:]:
                w = rng.choice(words)
                rows.append(("MENU", vary(f"{name} {w}로 바꿔 줘", rng), f"{menu} {n}개로 바꿔 주세요"))
    for a, a_names in DRINK_OPTIONS.items():
        for name in a_names:
            rows.append(("OPTION", vary(f"{name}로 줘", rng), f"{a}로 주세요"))
            rows.append(("OPTION", vary(f"음료는 {name}", rng), f"{a}로 주세요"))
            for b, b_names in DRINK_OPTIONS.items():
                if a != b and rng.random() < 0.5:
                    rows.append((rng.choice(["OPTION", "CONFIRM"]), vary(f"{name} 말고 {rng.choice(b_names)}", rng),
                                 f"{a} 말고 {b}로 바꿔 주세요"))
    return rows


def main() -> None:
    rng = random.Random(SEED)
    OUT.mkdir(parents=True, exist_ok=True)
    test = list(csv.DictReader(TESTSET.open(encoding="utf-8")))
    gen_test = list(csv.DictReader(GEN_TESTSET.open(encoding="utf-8")))
    test_texts = {r["text"].replace(" ", "") for r in test + gen_test}

    def dedupe(rows):
        seen, out = set(), []
        for row in rows:
            key = (row[0], row[1])
            if row[1] and key not in seen and row[1].replace(" ", "") not in test_texts:
                seen.add(key)
                out.append(row)
        rng.shuffle(out)
        return out

    cls = dedupe(cls_rows(rng, per_phrase=6))
    gen = dedupe(gen_rows(rng, cls))
    n_val = len(cls) // 10
    labels = sorted({label for _, _, label in cls} - {NONE}) + [NONE]

    def write_csv(path, rows):
        with path.open("w", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            w.writerow(["step", "text", "label"])
            w.writerows(rows)

    write_csv(OUT / "cls_train.csv", cls[n_val:])
    write_csv(OUT / "cls_val.csv", cls[:n_val])
    g_val = len(gen) // 10
    for name, rows in (("gen_train.jsonl", gen[g_val:]), ("gen_val.jsonl", gen[:g_val])):
        with (OUT / name).open("w", encoding="utf-8") as f:
            for step, text, rewrite in rows:
                f.write(json.dumps({"step": step, "text": text, "rewrite": rewrite}, ensure_ascii=False) + "\n")
    (OUT / "testset.csv").write_bytes(TESTSET.read_bytes())
    (OUT / "gen_testset.csv").write_bytes(GEN_TESTSET.read_bytes())
    # 생성 모델 v2: 같은 문장을 짧은 코드로 ("맥스파이시 상하이 버거 2개 주세요" → "+M02*2"), 입력은 "단계|손님 말" 한 줄
    tab = nlu_codes.tables([n.split(" (")[0] for n in MENUS], list(DRINK_OPTIONS))
    fixed = set(INTENTS)
    to_code = lambda sentence: nlu_codes.encode(sentence, tab, fixed)  # noqa: E731
    for name, rows in (("gen2_train.jsonl", gen[g_val:]), ("gen2_val.jsonl", gen[:g_val])):
        with (OUT / name).open("w", encoding="utf-8") as f:
            for step, text, rewrite in rows:
                f.write(json.dumps({"step": step, "text": text, "code": to_code(rewrite)}, ensure_ascii=False) + "\n")
    with (OUT / "gen2_testset.jsonl").open("w", encoding="utf-8") as f:
        for r in test + gen_test:
            label = "" if r["label"] in (NONE, "") else r["label"]
            f.write(json.dumps({"step": r["step"], "text": r["text"], "code": to_code(label)}, ensure_ascii=False) + "\n")
    (OUT / "gen2_meta.json").write_text(json.dumps(
        {"format": "code-v2", "prompt_format": "{step}|{text}\n", "unknown": nlu_codes.UNKNOWN, "fixed": sorted(fixed), **tab},
        ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT / "meta.json").write_text(json.dumps(
        {"labels": labels, "none_label": NONE, "step_names": STEP_NAMES, "input_format": "{step} | {text}", "seed": SEED},
        ensure_ascii=False, indent=2), encoding="utf-8")

    with zipfile.ZipFile(OUT.parent / "nlu_data.zip", "w", zipfile.ZIP_DEFLATED) as z:
        for p in sorted(OUT.iterdir()):
            z.write(p, f"nlu/{p.name}")

    print(f"분류: 학습 {len(cls) - n_val} · 검증 {n_val} · 표준 문장 {len(labels) - 1}개 + NONE")
    print(f"생성: 학습 {len(gen) - g_val} · 검증 {g_val}")
    print(f"시험(사람이 쓴 처음 보는 말): 분류 {len(test)} · 메뉴 {len(gen_test)}")
    print(f"→ {OUT} , {OUT.parent / 'nlu_data.zip'}")


if __name__ == "__main__":
    main()
