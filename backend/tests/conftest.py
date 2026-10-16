import os

# 테스트는 메모리 DB(SQLite)와 꺼진 모델 서버 주소로 실행한다 (앱을 불러오기 전에 설정)
os.environ["DATABASE_URL"] = "sqlite+pysqlite:///:memory:"
os.environ["MODEL_URL"] = "http://127.0.0.1:9"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.db import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.seed import seed  # noqa: E402


@pytest.fixture()
def client():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        seed(db)
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def menu_ids(client):
    return {m["name"]: m["id"] for m in client.get("/api/menus").json()}


@pytest.fixture()
def option_ids(client, menu_ids):
    detail = client.get(f"/api/menus/{menu_ids['빅맥']}").json()
    return {o["name"]: o["id"] for g in detail["option_groups"] for o in g["items"]}
