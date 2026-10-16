"""노션 "ERD (데이터 설계)" 페이지(2026-10-16 확정)를 그대로 옮긴 테이블입니다.

ERD에 없는 컬럼은 '추가' 주석을 달았습니다. (대화 진행 상태 저장 등 백엔드 구현용)
"""
from datetime import date, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base, now_utc, today_kst


class MenuCategory(Base):
    __tablename__ = "menu_category"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    items: Mapped[list["MenuItem"]] = relationship(back_populates="category", order_by="MenuItem.id")


class MenuItem(Base):
    __tablename__ = "menu_item"

    id: Mapped[int] = mapped_column(primary_key=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("menu_category.id"))
    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[str] = mapped_column(Text, default="")
    price: Mapped[int] = mapped_column(Integer)
    set_price: Mapped[int | None] = mapped_column(Integer, nullable=True)
    image_url: Mapped[str | None] = mapped_column(String(300), nullable=True)
    calories_kcal: Mapped[int | None] = mapped_column(Integer, nullable=True)
    allergens: Mapped[str] = mapped_column(String(200), default="")
    is_recommended: Mapped[bool] = mapped_column(Boolean, default=False)
    is_available: Mapped[bool] = mapped_column(Boolean, default=True)

    category: Mapped[MenuCategory] = relationship(back_populates="items")
    aliases: Mapped[list["MenuAlias"]] = relationship(back_populates="menu_item")
    option_links: Mapped[list["MenuOptionGroup"]] = relationship(back_populates="menu_item")


class MenuAlias(Base):
    __tablename__ = "menu_alias"

    id: Mapped[int] = mapped_column(primary_key=True)
    menu_item_id: Mapped[int] = mapped_column(ForeignKey("menu_item.id"))
    alias: Mapped[str] = mapped_column(String(100))

    menu_item: Mapped[MenuItem] = relationship(back_populates="aliases")


class OptionGroup(Base):
    __tablename__ = "option_group"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50))
    is_required: Mapped[bool] = mapped_column(Boolean, default=True)
    max_select: Mapped[int] = mapped_column(Integer, default=1)

    items: Mapped[list["OptionItem"]] = relationship(back_populates="group", order_by="OptionItem.id")


class MenuOptionGroup(Base):
    __tablename__ = "menu_option_group"

    menu_item_id: Mapped[int] = mapped_column(ForeignKey("menu_item.id"), primary_key=True)
    option_group_id: Mapped[int] = mapped_column(ForeignKey("option_group.id"), primary_key=True)
    applies_to: Mapped[str] = mapped_column(String(10), default="set")  # single, set, both

    menu_item: Mapped[MenuItem] = relationship(back_populates="option_links")
    group: Mapped[OptionGroup] = relationship()


class OptionItem(Base):
    __tablename__ = "option_item"

    id: Mapped[int] = mapped_column(primary_key=True)
    option_group_id: Mapped[int] = mapped_column(ForeignKey("option_group.id"))
    name: Mapped[str] = mapped_column(String(50))
    extra_price: Mapped[int] = mapped_column(Integer, default=0)

    group: Mapped[OptionGroup] = relationship(back_populates="items")


class Kiosk(Base):
    __tablename__ = "kiosk"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50))
    store_name: Mapped[str] = mapped_column(String(100))


class KioskSession(Base):
    __tablename__ = "kiosk_session"

    id: Mapped[int] = mapped_column(primary_key=True)
    kiosk_id: Mapped[int] = mapped_column(ForeignKey("kiosk.id"))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    end_reason: Mapped[str | None] = mapped_column(String(20), nullable=True)
    # 추가: 지금 어느 단계인지 (DINE_TYPE, MENU, OPTION, CONFIRM, COUPON, PAYMENT, DONE)
    step: Mapped[str] = mapped_column(String(20), default="DINE_TYPE")
    # 추가: 대화 진행 상태 (고르는 중인 메뉴, 되묻는 중인 질문 등)
    dialog_state: Mapped[dict] = mapped_column(JSON, default=dict)
    # 추가: 마지막으로 손님이 반응한 시각 (오래 반응이 없으면 세션 종료)
    last_active_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)

    kiosk: Mapped[Kiosk] = relationship()
    orders: Mapped[list["Order"]] = relationship(back_populates="session", order_by="Order.id")


class Coupon(Base):
    __tablename__ = "coupon"

    id: Mapped[int] = mapped_column(primary_key=True)
    barcode: Mapped[str] = mapped_column(String(50), unique=True)
    name: Mapped[str] = mapped_column(String(100))
    discount_type: Mapped[str] = mapped_column(String(20))  # fixed, percent, free_item
    discount_value: Mapped[int] = mapped_column(Integer, default=0)
    target_menu_item_id: Mapped[int | None] = mapped_column(ForeignKey("menu_item.id"), nullable=True)
    # 추가: 특정 메뉴 쿠폰이 '세트'일 때만 쓸 수 있는지 (예: 빅맥 세트 1,000원 할인)
    target_set_only: Mapped[bool] = mapped_column(Boolean, default=False)
    min_order_amount: Mapped[int] = mapped_column(Integer, default=0)
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    valid_until: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    target_menu: Mapped[MenuItem | None] = relationship()


class Order(Base):
    __tablename__ = "orders"
    __table_args__ = (UniqueConstraint("order_date", "order_number", name="uq_orders_date_number"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("kiosk_session.id"))
    coupon_id: Mapped[int | None] = mapped_column(ForeignKey("coupon.id"), unique=True, nullable=True)
    order_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    order_date: Mapped[date] = mapped_column(Date, default=today_kst)
    dine_type: Mapped[str | None] = mapped_column(String(10), nullable=True)  # dine_in, takeout
    # cart, pending_payment, paid, cooking, ready, picked_up, cancelled
    status: Mapped[str] = mapped_column(String(20), default="cart")
    subtotal: Mapped[int] = mapped_column(Integer, default=0)
    discount_amount: Mapped[int] = mapped_column(Integer, default=0)
    total_amount: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ready_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    session: Mapped[KioskSession] = relationship(back_populates="orders")
    coupon: Mapped[Coupon | None] = relationship()
    items: Mapped[list["OrderItem"]] = relationship(
        back_populates="order", cascade="all, delete-orphan", order_by="OrderItem.id"
    )
    payments: Mapped[list["Payment"]] = relationship(back_populates="order", order_by="Payment.id")


class OrderItem(Base):
    __tablename__ = "order_item"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"))
    menu_item_id: Mapped[int] = mapped_column(ForeignKey("menu_item.id"))
    is_set: Mapped[bool] = mapped_column(Boolean, default=False)
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    unit_price: Mapped[int] = mapped_column(Integer)  # 주문 당시 가격 (세트·옵션 포함 1개 값)
    line_total: Mapped[int] = mapped_column(Integer)

    order: Mapped[Order] = relationship(back_populates="items")
    menu: Mapped[MenuItem] = relationship()
    options: Mapped[list["OrderItemOption"]] = relationship(
        back_populates="order_item", cascade="all, delete-orphan", order_by="OrderItemOption.id"
    )


class OrderItemOption(Base):
    __tablename__ = "order_item_option"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_item_id: Mapped[int] = mapped_column(ForeignKey("order_item.id"))
    option_item_id: Mapped[int] = mapped_column(ForeignKey("option_item.id"))
    extra_price: Mapped[int] = mapped_column(Integer, default=0)  # 주문 당시 추가 금액

    order_item: Mapped[OrderItem] = relationship(back_populates="options")
    option: Mapped[OptionItem] = relationship()


class Payment(Base):
    __tablename__ = "payment"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"))
    method: Mapped[str] = mapped_column(String(20), default="card")
    amount: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending, approved, failed, cancelled
    idempotency_key: Mapped[str] = mapped_column(String(100), unique=True)
    pg_transaction_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    fail_reason: Mapped[str | None] = mapped_column(String(200), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    order: Mapped[Order] = relationship(back_populates="payments")


class StaffCall(Base):
    __tablename__ = "staff_call"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("kiosk_session.id"))
    reason: Mapped[str] = mapped_column(String(30))  # user_request, payment_failed, barcode_failed
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    session: Mapped[KioskSession] = relationship()


class ConversationLog(Base):
    __tablename__ = "conversation_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("kiosk_session.id"))
    turn_no: Mapped[int] = mapped_column(Integer)
    stt_text: Mapped[str] = mapped_column(Text)
    intent: Mapped[str] = mapped_column(String(30))
    response_text: Mapped[str] = mapped_column(Text)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
