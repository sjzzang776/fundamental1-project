"""처음 실행할 때 넣는 기본 데이터.

노션 "ERD (데이터 설계)" 6~7번(MVP 메뉴 데이터·테스트 쿠폰, 가정 값)과 같습니다.
메뉴를 바꾸려면 노션 ERD 페이지와 이 파일을 함께 고치세요.
"""
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import (
    Coupon,
    Kiosk,
    MenuAlias,
    MenuCategory,
    MenuItem,
    MenuOptionGroup,
    OptionGroup,
    OptionItem,
)

CATEGORIES = [(1, "버거", 1), (2, "사이드", 2), (3, "음료", 3), (4, "디저트", 4)]

# (카테고리 id, 이름, 단품, 세트, kcal, 알레르기, 추천, 별명)
MENUS = [
    (1, "빅맥", 5500, 7200, 580, "밀, 대두, 우유, 쇠고기, 계란", True, ["빅맥 버거"]),
    (1, "맥스파이시 상하이 버거", 5300, 7000, 500, "밀, 대두, 계란, 닭고기, 토마토", True, ["상하이", "상스치", "매운 치킨버거"]),
    (1, "불고기 버거", 2500, 4500, 400, "밀, 대두, 쇠고기, 돼지고기", True, ["불버거", "불고기"]),
    (1, "더블 불고기 버거", 4000, 5800, 590, "밀, 대두, 쇠고기, 돼지고기", False, ["더블 불고기", "더불"]),
    (1, "1955 버거", 6300, 8000, 540, "밀, 대두, 우유, 쇠고기, 토마토", False, ["천구백오십오", "일구오오"]),
    (1, "쿼터파운더 치즈", 6000, 7700, 530, "밀, 대두, 우유, 쇠고기", False, ["쿼터", "쿼파치"]),
    (1, "치즈버거", 2800, 4700, 310, "밀, 대두, 우유, 쇠고기", False, ["치즈 햄버거"]),
    (1, "맥치킨", 3500, 5300, 480, "밀, 대두, 계란, 닭고기", False, ["치킨버거", "맥치킨 버거"]),
    (2, "후렌치 후라이 (M)", 2300, None, 330, "대두", False, ["감자튀김", "감튀", "프렌치프라이"]),
    (2, "맥너겟 4조각", 2800, None, 190, "밀, 대두, 닭고기", False, ["너겟", "치킨너겟"]),
    (2, "치즈스틱 2조각", 2800, None, 220, "밀, 우유, 대두", False, ["치즈스틱"]),
    (3, "코카콜라 (M)", 1800, None, 140, "없음", False, ["콜라"]),
    (3, "코카콜라 제로 (M)", 1800, None, 0, "없음", False, ["제로콜라", "제로", "콜라 제로"]),
    (3, "스프라이트 (M)", 1800, None, 140, "없음", False, ["사이다"]),
    (3, "아메리카노 (M)", 2000, None, 10, "없음", False, ["커피", "아아"]),
    (3, "오렌지 주스", 2500, None, 110, "없음", False, ["주스", "오렌지"]),
    (4, "맥플러리 오레오", 3500, None, 380, "밀, 대두, 우유", False, ["맥플러리", "오레오 아이스크림"]),
    (4, "아이스크림 콘", 1000, None, 150, "우유", False, ["콘", "소프트콘", "아이스크림"]),
    (4, "애플파이", 1800, None, 250, "밀, 대두", False, ["파이"]),
]

# 세트 옵션: (그룹 이름, 필수, 최대 선택 수, [(선택지, 추가 금액)]) — 첫 번째 0원 선택지가 기본값
OPTION_GROUPS = [
    ("세트 사이즈", True, 1, [("미디엄", 0), ("라지", 800)]),
    ("세트 사이드", True, 1, [("후렌치 후라이", 0), ("맥너겟 4조각", 500), ("치즈스틱 2조각", 500)]),
    ("세트 음료", True, 1, [("코카콜라", 0), ("코카콜라 제로", 0), ("스프라이트", 0), ("아메리카노", 0), ("오렌지 주스", 700)]),
]

# 음성으로 옵션을 고를 때 쓰는 다른 이름
OPTION_ALIASES = {
    "미디엄": ["보통", "중간", "미디움", "작은"],
    "라지": ["큰", "크게", "큰거"],
    "후렌치 후라이": ["감자튀김", "감튀", "프렌치프라이"],
    "맥너겟 4조각": ["너겟", "치킨너겟", "맥너겟"],
    "치즈스틱 2조각": ["치즈스틱"],
    "코카콜라": ["콜라"],
    "코카콜라 제로": ["제로콜라", "제로", "콜라 제로"],
    "스프라이트": ["사이다"],
    "아메리카노": ["커피", "아아"],
    "오렌지 주스": ["주스", "오렌지"],
}


def _dt(text: str) -> datetime:
    return datetime.fromisoformat(text).replace(tzinfo=timezone.utc)


# (바코드, 이름, 할인 종류, 할인 값, 대상 메뉴 이름, 세트만, 최소 주문 금액, 시작, 끝, 사용 시각)
COUPONS = [
    ("TEST0001", "빅맥 세트 1,000원 할인", "fixed", 1000, "빅맥", True, 0, "2026-01-01", "2027-12-31", None),
    ("TEST0002", "후렌치 후라이 무료", "free_item", 0, "후렌치 후라이 (M)", False, 5000, "2026-01-01", "2027-12-31", None),
    ("TEST0003", "전 메뉴 10% 할인", "percent", 10, None, False, 0, "2026-01-01", "2027-12-31", None),
    ("TEST0004", "기간 끝난 쿠폰", "fixed", 1000, None, False, 0, "2025-01-01", "2025-12-31", None),
    ("TEST0005", "이미 쓴 쿠폰", "fixed", 1000, None, False, 0, "2026-01-01", "2027-12-31", "2026-10-01"),
]


def _sync_aliases(db: Session) -> None:
    """이미 메뉴가 들어 있는 DB에도 새로 추가한 별명을 넣는다."""
    for _, name, *_rest, aliases in MENUS:
        item = db.scalar(select(MenuItem).where(MenuItem.name == name))
        if item is None:
            continue
        have = {a.alias for a in item.aliases}
        for alias in aliases:
            if alias not in have:
                item.aliases.append(MenuAlias(alias=alias))
    db.commit()


def seed(db: Session) -> None:
    """메뉴 데이터가 비어 있을 때만 넣는다 (다시 실행해도 중복되지 않음)."""
    if db.scalar(select(MenuCategory.id).limit(1)) is not None:
        _sync_aliases(db)
        return

    for cid, name, order in CATEGORIES:
        db.add(MenuCategory(id=cid, name=name, sort_order=order))
    db.flush()

    menus_by_name = {}
    for cid, name, price, set_price, kcal, allergens, recommended, aliases in MENUS:
        item = MenuItem(
            category_id=cid,
            name=name,
            price=price,
            set_price=set_price,
            calories_kcal=kcal,
            allergens=allergens,
            is_recommended=recommended,
        )
        item.aliases = [MenuAlias(alias=a) for a in aliases]
        db.add(item)
        menus_by_name[name] = item
    db.flush()

    groups = []
    for name, required, max_select, choices in OPTION_GROUPS:
        group = OptionGroup(name=name, is_required=required, max_select=max_select)
        group.items = [OptionItem(name=n, extra_price=p) for n, p in choices]
        db.add(group)
        groups.append(group)
    db.flush()

    for item in menus_by_name.values():
        if item.set_price is not None:
            for group in groups:
                db.add(MenuOptionGroup(menu_item_id=item.id, option_group_id=group.id, applies_to="set"))

    db.add(Kiosk(id=1, name="키오스크 1번", store_name="시연 매장"))

    for barcode, name, dtype, value, target, set_only, min_amount, start, end, used in COUPONS:
        db.add(
            Coupon(
                barcode=barcode,
                name=name,
                discount_type=dtype,
                discount_value=value,
                target_menu_item_id=menus_by_name[target].id if target else None,
                target_set_only=set_only,
                min_order_amount=min_amount,
                valid_from=_dt(start),
                valid_until=_dt(end + "T23:59:59"),
                used_at=_dt(used) if used else None,
            )
        )
    db.commit()
