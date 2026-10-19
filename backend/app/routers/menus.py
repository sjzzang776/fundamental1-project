from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..errors import ApiError
from ..models import MenuCategory, MenuItem

router = APIRouter(prefix="/api", tags=["메뉴"])


def _menu(m: MenuItem) -> dict:
    return {
        "id": m.id,
        "category_id": m.category_id,
        "name": m.name,
        "description": m.description,
        "price": m.price,
        "set_price": m.set_price,
        "image_url": m.image_url,
        "calories_kcal": m.calories_kcal,
        "allergens": m.allergens,
        "is_recommended": m.is_recommended,
        "sold_out": not m.is_available,
    }


@router.get("/categories")
def categories(db: Session = Depends(get_db)):
    rows = db.scalars(select(MenuCategory).order_by(MenuCategory.sort_order)).all()
    return [{"id": c.id, "name": c.name, "sort_order": c.sort_order} for c in rows]


@router.get("/menus")
def menus(category_id: int | None = None, recommended: bool | None = None, db: Session = Depends(get_db)):
    query = select(MenuItem).order_by(MenuItem.category_id, MenuItem.id)
    if category_id is not None:
        query = query.where(MenuItem.category_id == category_id)
    if recommended is not None:
        query = query.where(MenuItem.is_recommended == recommended)
    return [_menu(m) for m in db.scalars(query)]


@router.get("/menus/{menu_id}")
def menu_detail(menu_id: int, db: Session = Depends(get_db)):
    m = db.get(MenuItem, menu_id)
    if m is None:
        raise ApiError(404, "MENU_NOT_FOUND", "없는 메뉴입니다", {"menu_id": menu_id})
    body = _menu(m)
    body["aliases"] = [a.alias for a in m.aliases]
    body["option_groups"] = [
        {
            "id": link.group.id,
            "name": link.group.name,
            "applies_to": link.applies_to,
            "is_required": link.group.is_required,
            "max_select": link.group.max_select,
            "items": [{"id": o.id, "name": o.name, "extra_price": o.extra_price} for o in link.group.items],
        }
        for link in m.option_links
    ]
    return body
