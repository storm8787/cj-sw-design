"""Windows 시험판 런처(desktop/)의 플랫폼 공통 논리. 실제 Windows 패키지 실행은 desktop/smoke.py(Windows CI)에서 확인한다."""
import json

import pytest
from fastapi.testclient import TestClient

from desktop import config as lc
from desktop.paths import Layout
from desktop.server import ControlApp, app_environ, apply_environ, close_app, scrubbed


@pytest.fixture
def lay(tmp_path, monkeypatch):
    import os

    saved = dict(os.environ)  # apply_environ이 os.environ을 바꾸므로 다른 테스트에 남지 않게 되돌린다
    monkeypatch.setenv("CJSWD_INSECURE_KEYSTORE", "1")
    yield Layout(tmp_path / "홈 폴더").ensure()
    os.environ.clear()
    os.environ.update(saved)


def test_inherited_app_env_is_scrubbed():
    env = scrubbed({"PATH": "x", "HTTPS_PROXY": "http://p", "OPENAI_API_KEY": "sk-1", "openai_model": "m", "AUTH_DISABLED": "true",
                    "APP_ENV": "development", "LLM_BASE_URL": "http://l", "ANTHROPIC_API_KEY": "a", "DATA_DIR": "/x", "CJSWD_HOME": "/h"})
    assert env == {"PATH": "x", "HTTPS_PROXY": "http://p", "CJSWD_HOME": "/h"}


def test_app_environ_sample_then_openai(lay, monkeypatch):
    cfg = lc.load(lay)
    lc.set_password(lay, cfg, "로컬비밀번호-123")
    env = app_environ(lay, cfg, lc.secret_key(lay), None)
    assert env["APP_ENV"] == "production" and env["COOKIE_SECURE"] == "false" and env["AI_PROVIDER"] == "sample"
    assert "AUTH_DISABLED" not in env and env["ADMIN_PASSWORD_HASH"].startswith("scrypt$")
    defaults = json.loads((lc.resource("desktop_defaults.json")).read_text(encoding="utf-8"))
    env = app_environ(lay, cfg, "s" * 64, "sk-test-" + "0" * 20)
    assert env["OPENAI_MODEL"] == defaults["openai_model"] and env["OPENAI_MODEL_FP_CANDIDATES"] == defaults["openai_model_fp_candidates"]
    monkeypatch.setenv("AUTH_DISABLED", "true")  # 상속값은 apply_environ이 지운다
    apply_environ(env)
    from app.config import load_settings

    s = load_settings()
    assert not s.auth_disabled and s.ai_default == "openai" and s.ai_profiles["openai"].task_models["fp_candidates"] == defaults["openai_model_fp_candidates"]


def test_password_and_key_rules(lay):
    cfg = lc.load(lay)
    with pytest.raises(lc.ConfigError):
        lc.check_password("short")
    with pytest.raises(lc.ConfigError):
        lc.check_password("abcdefghijk", "abcdefghijx")
    lc.set_password(lay, cfg, "첫비밀번호-abcdef")
    first = lc.secret_key(lay)
    lc.set_password(lay, cfg, "새비밀번호-abcdef")
    assert lc.secret_key(lay) != first  # 비밀번호를 바꾸면 기존 로그인 세션 무효
    saved = json.loads((lay.config / "settings.json").read_text(encoding="utf-8"))
    assert "새비밀번호" not in json.dumps(saved, ensure_ascii=False) and saved["password_hash"].startswith("scrypt$")
    with pytest.raises(lc.ConfigError):
        lc.set_openai_key(lay, "sk with space")
    lc.set_openai_key(lay, "  sk-abcdefghijklmnopqrstuvwxyz1234  ")
    assert lc.openai_key(lay) == "sk-abcdefghijklmnopqrstuvwxyz1234" and lc.mask(lc.openai_key(lay)) == "sk-…1234"
    lc.clear_openai_key(lay)
    assert lc.openai_key(lay) is None and lc.mask(None) == "없음"


def test_control_endpoint_token_and_passthrough(lay):
    from app.config import Settings
    from app.main import create_app

    app = create_app(Settings(data_dir=lay.data, secret_key="k" * 40, admin_password="관리자비밀번호-1234"))
    got = []
    client = TestClient(ControlApp(app, "inst-1", "tok-1", got.append))
    assert client.get("/__desktop/instance").json() == {"app": "cj-sw-design", "instance": "inst-1"}
    assert client.post("/__desktop/control", json={"action": "quit"}).status_code == 403
    assert client.post("/__desktop/control", json={"action": "quit"}, headers={"X-Desktop-Token": "wrong"}).status_code == 403
    assert client.post("/__desktop/control", json={"action": "quit"}, headers={"X-Desktop-Token": "tok-1"}).json() == {"ok": True}
    assert got == ["quit"]
    assert client.get("/api/projects").status_code == 401  # 나머지는 기존 앱 인증 그대로
    assert client.get("/api/health").json() == {"ok": True}


def test_close_app_marks_running_jobs_interrupted(lay):
    from app.config import Settings
    from app.main import create_app

    s = Settings(data_dir=lay.data, secret_key="k" * 40, admin_password="관리자비밀번호-1234")
    app = create_app(s)
    app.state.ctx.db.execute("INSERT INTO jobs(id,project_id,kind,input_hash,status,created_at,updated_at) VALUES('J1',NULL,'questions','h','running','t','t')")
    assert close_app(app) == 1
    app2 = create_app(s)
    assert app2.state.ctx.db.one("SELECT status FROM jobs WHERE id='J1'")["status"] == "interrupted"
