from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app

STD_PATH = Path(__file__).resolve().parents[1] / "app" / "standards" / "KOSA-FORM-2024G-241231.json"
PASSWORD = "test-password-1234"


@pytest.fixture
def std():
    return json.loads(STD_PATH.read_text(encoding="utf-8"))


def make_settings(tmp: Path, **kw) -> Settings:
    s = Settings()
    s.app_env = "test"
    s.data_dir = tmp
    s.secret_key = "x" * 40
    s.admin_password = PASSWORD
    s.ai_provider = "sample"
    s.frontend_dist = None
    s.official_source_allowlist = ["www.postgresql.org", "example.org"]
    for k, v in kw.items():
        setattr(s, k, v)
    return s


def client_for(app, login: bool = True) -> TestClient:
    c = TestClient(app, headers={"X-Requested-With": "swd"})
    if login:
        r = c.post("/api/auth/login", json={"password": PASSWORD})
        assert r.status_code == 200, r.text
    return c


@pytest.fixture
def app_factory(tmp_path):
    def make(provider=None, synchronous=True, **kw):
        return create_app(make_settings(tmp_path, **kw), provider=provider, synchronous_jobs=synchronous)

    return make


@pytest.fixture
def client(app_factory):
    return client_for(app_factory())
