"""여러 AI 연결(OpenAI 기본·Anthropic·OpenAI 호환 LLM·샘플) 설정과 어댑터 검증.

실제 외부 호출은 하지 않는다: HTTP 전송 계층을 가짜(MockTransport)로 바꿔 요청 형식·응답 처리를 확인한다.
"""
import json

import httpx2
import openai
import pytest

from app.ai import schemas as S
from app.ai.provider import AIError, CompatibleProvider, MockProvider, OpenAIProvider, ProviderRegistry, strict_schema
from app.config import AIProfile, ConfigError, Settings, load_settings
from tests.conftest import client_for

AI_ENV = ["AI_PROVIDER", "AI_MODEL", "OPENAI_API_KEY", "OPENAI_MODEL", "OPENAI_BASE_URL", "ANTHROPIC_API_KEY", "ANTHROPIC_MODEL", "ANTHROPIC_BASE_URL", "LLM_BASE_URL", "LLM_API_KEY", "LLM_MODEL", "LLM_JSON_MODE", "LLM_LABEL", "LLM_EXTERNAL"]


@pytest.fixture
def env(monkeypatch, tmp_path):
    for k in AI_ENV:
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("AUTH_DISABLED", "true")
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    return monkeypatch


# ---------------------------------------------------------------- 설정
def test_default_is_openai_when_key_present(env):
    env.setenv("OPENAI_API_KEY", "sk-test")
    env.setenv("OPENAI_MODEL", "my-gpt")
    s = load_settings()
    assert s.ai_default == "openai" and s.ai_profiles["openai"].model == "my-gpt"


def test_default_is_sample_without_keys(env):
    s = load_settings()
    assert s.ai_default == "sample" and set(s.ai_profiles) == {"sample"}


def test_multiple_profiles_and_validation(env):
    env.setenv("OPENAI_API_KEY", "sk-test")
    env.setenv("OPENAI_MODEL", "my-gpt")
    env.setenv("ANTHROPIC_API_KEY", "sk-ant")
    env.setenv("ANTHROPIC_MODEL", "my-claude")
    env.setenv("LLM_BASE_URL", "http://10.0.0.5:8000/v1")
    env.setenv("LLM_MODEL", "local-llm")
    env.setenv("LLM_JSON_MODE", "prompt")
    env.setenv("LLM_EXTERNAL", "false")
    env.setenv("LLM_LABEL", "사내 LLM")
    env.setenv("AI_PROVIDER", "compatible")
    s = load_settings()
    assert set(s.ai_profiles) == {"openai", "anthropic", "compatible", "sample"}
    c = s.ai_profiles["compatible"]
    assert s.ai_default == "compatible" and c.external is False and c.json_mode == "prompt" and c.label == "사내 LLM"


def test_default_profile_must_be_complete(env):
    env.setenv("OPENAI_API_KEY", "sk-test")  # 모델명 없음
    with pytest.raises(ConfigError, match="OPENAI_MODEL"):
        load_settings()
    env.setenv("AI_PROVIDER", "anthropic")  # 키 없음
    with pytest.raises(ConfigError, match="ANTHROPIC_API_KEY"):
        load_settings()


def test_incomplete_extra_profile_listed_but_not_usable(env):
    env.setenv("AI_PROVIDER", "sample")
    env.setenv("LLM_BASE_URL", "ftp://x")
    env.setenv("LLM_MODEL", "m")
    s = load_settings()
    reg = ProviderRegistry(s)
    d = {x["name"]: x for x in reg.describe()}
    assert d["compatible"]["usable"] is False and "compatible" not in reg.providers
    p, note = reg.for_name("compatible")
    assert p.name == "sample" and "설정되어 있지 않아" in note


# ---------------------------------------------------------------- OpenAI 어댑터(가짜 전송)
def completion(content, finish="stop", refusal=None):
    return {"id": "c", "object": "chat.completion", "created": 0, "model": "m", "choices": [{"index": 0, "finish_reason": finish, "message": {"role": "assistant", "content": content, "refusal": refusal}}], "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}}


def make(cls, handler, **prof):
    profile = AIProfile(name=prof.pop("name", "openai"), kind=prof.pop("kind", "openai"), label=prof.pop("label", "OpenAI(ChatGPT)"), model="test-model", api_key="sk-test", **prof)
    client = openai.DefaultHttpxClient(transport=httpx2.MockTransport(handler))
    return cls(profile, Settings(), http_client=client)


def test_openai_request_uses_strict_json_schema():
    seen = {}

    def h(req):
        seen["url"] = str(req.url)
        seen["auth"] = req.headers.get("authorization")
        seen["body"] = json.loads(req.content)
        return httpx2.Response(200, json=completion('{"questions": []}'))

    p = make(OpenAIProvider, h)
    out = p.generate_json("questions", "SYS", "USER", strict_schema(S.QuestionsOut))
    assert out == '{"questions": []}'
    b = seen["body"]
    assert seen["url"].endswith("/chat/completions") and seen["auth"] == "Bearer sk-test"
    assert b["model"] == "test-model" and b["messages"][0] == {"role": "system", "content": "SYS"}
    rf = b["response_format"]
    assert rf["type"] == "json_schema" and rf["json_schema"]["strict"] is True and rf["json_schema"]["name"] == "questions"
    assert rf["json_schema"]["schema"]["additionalProperties"] is False
    assert "maxItems" not in json.dumps(rf["json_schema"]["schema"])  # 공급자별 미지원 제약 제거


@pytest.mark.parametrize("resp,msg", [
    (completion(None, refusal="I can't help"), "거절"),
    (completion('{"a":', finish="length"), "잘렸"),
    (completion("", finish="stop"), "본문이 없"),
])
def test_openai_bad_responses(resp, msg):
    p = make(OpenAIProvider, lambda req: httpx2.Response(200, json=resp))
    with pytest.raises(AIError, match=msg):
        p.generate_json("t", "s", "u", {})


@pytest.mark.parametrize("status,msg", [(401, "인증 실패"), (404, "모델"), (429, "한도"), (500, "서버 오류")])
def test_openai_http_errors_mapped(status, msg):
    p = make(OpenAIProvider, lambda req: httpx2.Response(status, json={"error": {"message": "x", "type": "e"}}))
    p.client = p.client.with_options(max_retries=0)
    with pytest.raises(AIError, match=msg):
        p.generate_json("t", "s", "u", {})


def test_compatible_prompt_mode_extracts_json_and_omits_response_format():
    seen = {}

    def h(req):
        seen["url"] = str(req.url)
        seen["body"] = json.loads(req.content)
        return httpx2.Response(200, json=completion('네, 결과입니다.\n```json\n{"items": []}\n```\n끝'))

    p = make(CompatibleProvider, h, name="compatible", kind="compatible", label="사내 LLM", base_url="http://llm.local/v1", json_mode="prompt", external=False)
    out = p.generate_json("doc_extract", "SYS", "USER", strict_schema(S.RefOut))
    assert json.loads(out) == {"items": []}
    assert seen["url"].startswith("http://llm.local/v1/")
    assert "response_format" not in seen["body"] and '"items"' in seen["body"]["messages"][0]["content"]
    assert p.external is False


def test_compatible_json_object_mode():
    seen = {}

    def h(req):
        seen["body"] = json.loads(req.content)
        return httpx2.Response(200, json=completion('{"items": []}'))

    p = make(CompatibleProvider, h, name="compatible", kind="compatible", label="상용 LLM", base_url="https://llm.example/v1", json_mode="json_object")
    p.generate_json("t", "s", "u", {"type": "object"})
    assert seen["body"]["response_format"] == {"type": "json_object"}


# ---------------------------------------------------------------- API 경로 전체(OpenAI 어댑터 + 공통 검증)
def test_openai_end_to_end_through_api(app_factory):
    q = {"key": "k1", "topic": "이용자", "text": "누가 쓰나요?", "why": "권한 결정", "options": [{"value": "a", "label": "직원", "recommended": True, "adds": []}], "recommended_value": "a", "recommended_reason": "내부 업무"}
    calls = []

    def h(req):
        calls.append(json.loads(req.content))
        return httpx2.Response(200, json=completion(json.dumps({"questions": [q]}, ensure_ascii=False)))

    prov = make(OpenAIProvider, h)
    c = client_for(app_factory(provider=prov))
    pid = c.post("/api/projects", json={"name": "x", "overview": {"idea_text": "교육 신청"}}).json()["project"]["id"]
    assert c.post(f"/api/projects/{pid}/ai/questions", json={}).status_code == 422  # 외부 전송 동의 필요
    prev = c.get(f"/api/projects/{pid}/ai/transmission-preview").json()
    assert prev["external"] and "OpenAI(ChatGPT)" in prev["explanation"]
    j = c.post(f"/api/projects/{pid}/ai/questions", json={"consent": True}).json()["job"]
    assert j["status"] == "succeeded" and j["result"]["source"] == "OpenAI(ChatGPT) · test-model"
    p = c.get(f"/api/projects/{pid}").json()
    assert p["project"]["questions"][0]["text"] == "누가 쓰나요?" and p["project"]["questions"][0]["origin"] == "ai"
    assert p["ai"]["name"] == "openai" and len(calls) == 1
    assert "교육 신청" in calls[0]["messages"][1]["content"]  # 프로젝트 요약이 전송됨(동의 후)


def test_per_project_profile_selection(app_factory):
    mock = MockProvider()
    mock.responses = {"questions": [json.dumps({"questions": []})]}
    app = app_factory(provider=mock)
    c = client_for(app)
    sysinfo = c.get("/api/system").json()
    names = {p["name"] for p in sysinfo["ai_profiles"]}
    assert {"mock", "sample"} <= names and sysinfo["default_profile"] == "mock"
    pid = c.post("/api/projects", json={"name": "x", "overview": {"idea_text": "민원 접수"}}).json()["project"]["id"]
    assert c.patch(f"/api/projects/{pid}", json={"ai_profile": "없는연결"}).status_code == 422
    r = c.patch(f"/api/projects/{pid}", json={"ai_profile": "sample"}).json()
    assert r["ai"]["name"] == "sample"
    j = c.post(f"/api/projects/{pid}/ai/questions", json={}).json()["job"]
    assert j["result"]["mode"] == "sample" and mock.calls == []  # 이 프로젝트는 샘플 연결 사용
    c.patch(f"/api/projects/{pid}", json={"ai_profile": ""})  # 서버 기본(mock)으로 복귀
    j = c.post(f"/api/projects/{pid}/ai/questions", json={}).json()["job"]
    assert j["result"]["mode"] == "ai" and len(mock.calls) == 1


def _objects(node):
    if isinstance(node, dict):
        if node.get("type") == "object" and "properties" in node:
            yield node
        for v in node.values():
            yield from _objects(v)
    elif isinstance(node, list):
        for v in node:
            yield from _objects(v)


@pytest.mark.parametrize("model_cls", [S.QuestionsOut, S.RequirementsOut, S.DesignOut, S.FPOut, S.RefOut])
def test_strict_schema_keeps_fields_named_like_keywords(model_cls):
    """실제 OpenAI 호출에서 발견(2026-10-29): 'title' 필드가 스키마 정리 중 지워져 400 오류가 났다."""
    schema = strict_schema(model_cls)
    objs = list(_objects(schema))
    assert objs
    for o in objs:
        assert set(o["required"]) == set(o["properties"]) and o["additionalProperties"] is False
    assert "title" in strict_schema(S.RequirementsOut)["$defs"]["ReqDraft"]["properties"]


def test_timeout_reported_as_timeout_not_connection():
    def h(req):
        raise httpx2.ReadTimeout("slow", request=req)

    p = make(OpenAIProvider, h)
    p.client = p.client.with_options(max_retries=0)
    with pytest.raises(AIError, match="시간 초과"):
        p.generate_json("t", "s", "u", {})


def test_env_example_starts_without_ai_key(env):
    """`.env.example`을 그대로 복사해도(키 없음) 샘플 모드로 기동해야 한다(PR #3 리뷰 지적)."""
    from pathlib import Path
    for ln in (Path(__file__).resolve().parents[2] / ".env.example").read_text(encoding="utf-8").splitlines():
        if ln.strip() and not ln.lstrip().startswith("#") and "=" in ln:
            k, v = ln.split("=", 1)
            if k.startswith(("AI_", "OPENAI_", "ANTHROPIC_", "LLM_")):
                env.setenv(k.strip(), v.strip())
    s = load_settings()
    assert s.ai_default == "sample"


def test_job_keeps_submitted_profile_on_retry(app_factory):
    """대기·재시도 중 프로젝트 연결이 바뀌어도 제출 때 연결(동의 기준)로 실행, 없어진 연결은 바꾸지 않고 실패(PR #3 리뷰 지적)."""
    class External(MockProvider):
        external = True

    mock = External()
    mock.responses = {"questions": [json.dumps({"questions": []})]}
    app = app_factory(provider=mock)
    c = client_for(app)
    db = app.state.ctx.db
    pid = c.post("/api/projects", json={"name": "x", "overview": {"idea_text": "민원 접수"}}).json()["project"]["id"]
    c.patch(f"/api/projects/{pid}", json={"ai_profile": "sample"})
    j = c.post(f"/api/projects/{pid}/ai/questions", json={}).json()["job"]  # 샘플: 동의 불필요
    assert j["result"]["mode"] == "sample"
    c.patch(f"/api/projects/{pid}", json={"ai_profile": ""})  # 이후 외부 연결(mock)로 변경
    db.execute("UPDATE jobs SET status='failed' WHERE id=?", (j["id"],))
    r = c.post(f"/api/jobs/{j['id']}/retry").json()
    assert r["status"] == "succeeded" and r["result"]["mode"] == "sample" and mock.calls == []  # 동의 없는 외부 전송 없음
    db.execute("UPDATE jobs SET status='failed', params=? WHERE id=?", (json.dumps({"profile": "없어진연결"}), j["id"]))
    r = c.post(f"/api/jobs/{j['id']}/retry").json()
    assert r["status"] == "failed" and "바꾸지 않았습니다" in r["error"] and mock.calls == []
