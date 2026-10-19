"""손님 말 다시 쓰기 (의도 파악 C안: 규칙 먼저, 못 알아들을 때만 LLM).

백엔드 규칙(backend/app/services/nlu.py)이 못 알아들은 말만 여기로 온다.
LLM은 주문을 직접 처리하지 않고, 손님 말을 키오스크 규칙이 알아듣는 짧은 표준 문장 하나로 바꿔 준다.
메뉴·금액·장바구니는 언제나 백엔드가 메뉴 DB로 정한다 (LLM이 틀려도 없는 메뉴가 담기지 않음).

설정 (환경변수)
- ANTHROPIC_API_KEY: 없으면 /nlu 는 503 → 백엔드는 규칙만 쓴다
- NLU_MODEL: 기본 claude-opus-5-5. 더 빠르고 싸게: claude-haiku-5-5
- NLU_EFFORT: 기본 low (짧은 문장 다시 쓰기라 깊게 생각할 필요 없음)
- NLU_TIMEOUT_SEC: 기본 7초
"""
import json
import os

import anthropic

NLU_MODEL = os.getenv("NLU_MODEL", "claude-opus-5-5")
NLU_EFFORT = os.getenv("NLU_EFFORT", "low")
NLU_TIMEOUT_SEC = float(os.getenv("NLU_TIMEOUT_SEC", "7"))

SYSTEM = """너는 패스트푸드점 음성 키오스크의 "말 정리" 담당이다.
손님(주로 디지털 기기가 낯선 어르신)이 한 말을, 키오스크 규칙이 알아듣는 짧은 표준 문장 하나로 바꾼다.

규칙
- 메뉴·옵션은 입력의 "메뉴 이름", "옵션 이름"에 있는 이름만 그대로 쓴다. 없는 메뉴를 지어내지 않는다.
- 손님이 말한 뜻(메뉴, 수량, 세트/단품, 옵션, 하려는 행동)을 바꾸거나 보태지 않는다. 수량은 숫자로 쓴다.
- "지금 단계"와 "최근 대화"(키오스크가 방금 물은 것)를 보고 무엇에 대한 대답인지 판단한다.
- 뜻이 분명하지 않거나 주문과 상관없는 말이면 rewrite 는 빈 문자열, confidence 는 0 으로 한다.
- confidence: 뜻이 분명하면 0.8 이상, 짐작이 섞이면 0.5~0.7.

쓸 수 있는 표준 문장
- 식사 장소: "매장에서" / "포장"
- 담기: "{메뉴} {n}개 주세요" / "{메뉴} 세트 하나 주세요" / "{메뉴} 단품 하나 주세요"
- 옵션 고르기: "{옵션}으로 주세요" / "세트로 주세요" / "단품으로 주세요"
- 바꾸기·빼기: "{메뉴} 빼 주세요" / "{메뉴} {n}개로 바꿔 주세요" / "{옵션} 말고 {옵션}으로 바꿔 주세요"
- 진행: "추천해 주세요" / "주문할게요" / "맞아요" / "수정할게요" / "쿠폰 있어요" / "없어요"
- 언제나: "처음으로" / "취소" / "직원 불러줘"

예
- (DINE_TYPE) "싸가지고 갈라고" → "포장"
- (OPTION, 음료를 묻는 중) "시원한 사이다로" → 옵션에 "스프라이트"가 있으면 "스프라이트로 주세요"
- (MENU) "그 매운 거 두 개" → 메뉴에 "맥스파이시 상하이 버거"가 있으면 "맥스파이시 상하이 버거 2개 주세요"
- (CONFIRM) "그래 그렇게 해" → "맞아요"
- "오늘 날씨 좋네" → rewrite "", confidence 0"""

SCHEMA = {
    "type": "object",
    "properties": {
        "rewrite": {"type": "string", "description": "키오스크 규칙이 알아듣는 표준 문장 하나. 모르면 빈 문자열"},
        "confidence": {"type": "number", "description": "0~1"},
    },
    "required": ["rewrite", "confidence"],
    "additionalProperties": False,
}

_client: anthropic.Anthropic | None = None


class NluUnavailable(Exception):
    """API 키가 없거나 LLM 호출이 실패함 → 백엔드는 규칙만 쓴다."""


def available() -> bool:
    return bool(os.getenv("ANTHROPIC_API_KEY"))


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        # 키오스크는 기다릴 수 없으므로 재시도하지 않고 짧게 끊는다 (실패하면 "다시 말씀해 주세요")
        _client = anthropic.Anthropic(timeout=NLU_TIMEOUT_SEC, max_retries=0)
    return _client


def rewrite(text: str, step: str | None, menus: list[str], options: list[str],
            cart: list[str] | None = None, history: list | None = None) -> dict:
    if not available():
        raise NluUnavailable("ANTHROPIC_API_KEY 가 설정되지 않았습니다")
    payload = {
        "손님 말": text,
        "지금 단계": step,
        "최근 대화": history or [],
        "장바구니": cart or [],
        "메뉴 이름": menus,
        "옵션 이름": options,
    }
    try:
        response = _get_client().beta.messages.create(
            model=NLU_MODEL,
            max_tokens=2048,
            system=SYSTEM,
            messages=[{"role": "user", "content": json.dumps(payload, ensure_ascii=False)}],
            output_config={
                "effort": NLU_EFFORT,
                "format": {"type": "json_schema", "schema": SCHEMA},
            },
            # 안전 분류기가 드물게 거절하면 같은 요청을 알맞은 다른 모델로 다시 돌린다
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
        )
    except anthropic.APIError as e:
        raise NluUnavailable(f"LLM 호출 실패: {type(e).__name__}") from e

    if response.stop_reason == "refusal":
        return {"rewrite": "", "confidence": 0.0}
    text_block = next((b.text for b in response.content if b.type == "text"), None)
    if not text_block:
        return {"rewrite": "", "confidence": 0.0}
    try:
        data = json.loads(text_block)
    except ValueError:
        return {"rewrite": "", "confidence": 0.0}
    return {
        "rewrite": str(data.get("rewrite", "")).strip(),
        "confidence": max(0.0, min(1.0, float(data.get("confidence", 0)))),
        "model": NLU_MODEL,
    }
