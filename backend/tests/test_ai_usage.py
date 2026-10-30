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


def test_fp_candidates_retry_when_function_has_no_transaction_candidate(app_factory):
    """처리 후보가 없는 기능(ILF 연결만 있음)은 코드가 찾아 1회 재요청하고, 그래도 남으면 경고로 남긴다."""
    def item(name, t, fids):
        return {"name": name, "fp_type": t, "rationale": "근거", "uncertainty": "", "det": None, "ftr_ret": None, "det_items": [], "ret_groups": [], "requirement_ids": [], "function_ids": fids, "data_ids": []}

    prov = MockProvider()
    app = app_factory(provider=prov)
    c = client_for(app)
    pid = c.post("/api/projects", json={"name": "x"}).json()["project"]["id"]
    f1 = c.post(f"/api/projects/{pid}/items/functions", json={"data": {"name": "교육 신청"}}).json()["item"]["id"]
    f2 = c.post(f"/api/projects/{pid}/items/functions", json={"data": {"name": "교육 신청 취소"}}).json()["item"]["id"]
    miss = {"items": [item("교육 신청", "EI", [f1]), item("신청 정보", "ILF", [f1, f2])]}
    fixed = {"items": [item("교육 신청", "EI", [f1]), item("교육 신청 취소", "EI", [f2]), item("신청 정보", "ILF", [f1, f2])]}
    prov.responses = {"fp_candidates": [json.dumps(miss, ensure_ascii=False), json.dumps(fixed, ensure_ascii=False)]}
    job = c.post(f"/api/projects/{pid}/ai/fp_candidates", json={"consent": True}).json()["job"]
    assert job["usage"]["calls"] == 2  # 첫 응답의 누락을 코드가 찾아 1회 재요청
    names = [i["data"]["name"] for i in c.get(f"/api/projects/{pid}").json()["project"]["proposals"][-1]["items"]]
    assert "교육 신청 취소" in names
    # 재요청 후에도 빠지면 경고(무한 재시도 없음)
    prov.responses = {"fp_candidates": [json.dumps(miss, ensure_ascii=False)] * 2}
    job = c.post(f"/api/projects/{pid}/ai/fp_candidates", json={"consent": True, "force": True}).json()["job"]
    assert job["usage"]["calls"] == 2
    assert any("처리(EI/EO/EQ) 후보가 연결되지 않은 기능" in w for w in job["result"]["warnings"])


def test_display_shows_task_model(monkeypatch):
    from app.ai.provider import build_provider
    from app.config import Settings

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("OPENAI_MODEL", "small-model")
    monkeypatch.setenv("OPENAI_MODEL_FP_CANDIDATES", "big-model")
    prov = build_provider(load_ai_profiles()["openai"], Settings())
    assert prov.model_for("fp_candidates") == "big-model" and prov.model_for("design") == "small-model"
    assert prov.display() == "OpenAI(ChatGPT) · small-model (작업별: FP 후보 big-model)"
