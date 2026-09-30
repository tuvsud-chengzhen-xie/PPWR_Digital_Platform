"""Each test session runs against a throw-away data folder with a fresh seed."""
import os
import sys
import tempfile
from pathlib import Path

os.environ["PPWR_DATA_DIR"] = tempfile.mkdtemp(prefix="ppwr-test-")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest  # noqa: E402

from app import seed  # noqa: E402
from app.db import Base, SessionLocal, engine, init_db  # noqa: E402


@pytest.fixture()
def session():
    Base.metadata.drop_all(engine)
    init_db()
    s = SessionLocal()
    seed.seed(s)
    yield s
    s.close()


@pytest.fixture()
def client(session):
    from fastapi.testclient import TestClient
    from app.main import app
    with TestClient(app) as c:
        yield c


def login(c, username):
    r = c.post("/login", data={"username": username, "password": "demo"}, follow_redirects=False)
    assert r.status_code == 303
    return c
