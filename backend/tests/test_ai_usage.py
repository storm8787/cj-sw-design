"""AI 사용량 기록·작업별 모델 고정(실제 AI 호출 없음)."""
import json

import pytest

from app.ai.provider import MockProvider
from app.config import load_ai_profiles
from app.main import UserFacingError
from tests.conftest import client_for


def test_job_records_usage_including_retry(app_factory):
    prov = MockProvider()
    good = {"questions": []}
    prov.responses = {"questions": ["{bad json", json.dumps(good)]}
    app = app_factory(provider=prov)
    c = client_for(app)
    pid = c.post("/api/projects", json={"name": "x"}).json()["project"]["id"]
    job = c.post(f"/api/projects/{pid}/ai/questions", json={"consent": True}).json()["job"]
    assert job["status"] == "succeeded"
    u = job["usage"]
    assert u["calls"] == 2 and u["models"] == ["mock-model"] and u["input_tokens"] > 0
    assert job["params"]["model"] == "mock-model"  # 제출 때 모델 고정
    assert all("user" not in d and "text" not in d for d in u["detail"])  # 본문은 기록하지 않음


def test_job_refuses_if_model_changed_after_submit(app_factory):
    prov = MockProvider()
    app = app_factory(provider=prov)
    ctx = app.state.ctx
    with pytest.raises(UserFacingError, match="모델 설정이 바뀌었습니다"):
        ctx.provider_for_job(None, {"profile": prov.name, "model": "old-model", "_kind": "design"})
    assert ctx.provider_for_job(None, {"profile": prov.name, "model": "mock-model", "_kind": "design"}) is prov


def test_task_model_and_reasoning_env(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("OPENAI_MODEL", "base-model")
    monkeypatch.setenv("OPENAI_MODEL_DESIGN", "big-model")
    monkeypatch.setenv("OPENAI_REASONING_EFFORT", "low")
    p = load_ai_profiles()["openai"]
    assert p.usable and p.task_models == {"design": "big-model"} and p.reasoning_effort == "low"
    monkeypatch.setenv("OPENAI_REASONING_EFFORT", "turbo")
    assert not load_ai_profiles()["openai"].usable
