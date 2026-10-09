import re

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import create_app

PW = settings.demo_password


@pytest.fixture()
def app(tmp_path):
    return create_app(f"sqlite:///{tmp_path}/test.db", demo_seed=True)


@pytest.fixture()
def db(app):
    with app.state.db.SessionLocal() as session:
        yield session


@pytest.fixture()
def client(app):
    return TestClient(app)


def csrf_of(html: str) -> str:
    return re.search(r'name="csrf" value="([^"]+)"', html).group(1)


def login(client: TestClient, username: str, password: str = PW):
    page = client.get("/login")
    return client.post("/login", data={"csrf": csrf_of(page.text), "username": username, "password": password}, follow_redirects=False)


@pytest.fixture()
def as_user(app):
    def _make(username: str) -> TestClient:
        c = TestClient(app)
        r = login(c, username)
        assert r.status_code == 303, r.text
        return c

    return _make
