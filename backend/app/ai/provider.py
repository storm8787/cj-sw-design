"""AI 공급자 어댑터 — 여러 AI를 동시에 연결하고 프로젝트마다 바꿔 끼울 수 있다.

- OpenAIProvider: OpenAI(ChatGPT) 공식 SDK, 구조화 출력(json_schema strict). 기본 연결.
- CompatibleProvider: OpenAI 호환 API를 내는 상용·사내 LLM(Azure OpenAI v1, vLLM, Ollama, 국내 LLM 등).
  서버가 지원하는 방식에 따라 json_schema / json_object / prompt(스키마를 지시문에 넣고 응답에서 JSON 추출).
- AnthropicProvider: Anthropic(Claude) 공식 SDK, 구조화 출력.
- SampleProvider: 규칙 기반(외부 전송 없음, AI 아님).
- MockProvider: 테스트용.

모든 공급자는 같은 인터페이스(generate_json)만 구현한다. 응답 검증·재시도·변경안 적용은 공통 코드(tasks.py)가 한다.
모델명·키·주소는 환경설정(config.AIProfile)에서만 받는다. 프롬프트·원문·키는 로그에 남기지 않는다.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any, Callable

from ..config import AIProfile, Settings

log = logging.getLogger("swd.ai")


class AIError(RuntimeError):
    """AI 호출 실패. 메시지는 사용자에게 보여줄 수 있는 한국어."""


class AIProvider:
    name = "base"  # 연결(profile) 이름
    kind = "base"
    label = ""
    external = False  # 외부로 데이터가 전송되는가
    is_real_ai = False
    model = ""

    def generate_json(self, task: str, system: str, user: str, schema: dict[str, Any]) -> str:
        raise NotImplementedError

    def display(self) -> str:
        return f"{self.label} · {self.model}" if self.model else self.label

    def describe(self) -> dict[str, Any]:
        return {"name": self.name, "kind": self.kind, "label": self.label, "model": self.model, "external": self.external, "is_real_ai": self.is_real_ai, "display": self.display(), "usable": True, "missing": []}


class SampleProvider(AIProvider):
    name = kind = "sample"
    label = "샘플 모드(규칙 기반, AI 아님)"

    def generate_json(self, task, system, user, schema):  # pragma: no cover - 샘플은 규칙 함수로 직접 처리
        raise AIError("샘플 모드는 규칙 기반 생성기를 사용합니다.")


class MockProvider(AIProvider):
    """테스트용. responses[task]는 문자열 목록(호출 순서대로 반환) 또는 함수."""

    name = kind = "mock"
    label = "테스트용 가짜 AI"
    is_real_ai = True  # 실제 AI 경로(검증·재시도)를 시험하기 위함
    model = "mock-model"

    def __init__(self) -> None:
        self.responses: dict[str, list[str] | Callable[[str, str], str]] = {}
        self.calls: list[dict[str, Any]] = []

    def generate_json(self, task, system, user, schema):
        self.calls.append({"task": task, "user_len": len(user)})
        r = self.responses.get(task)
        if r is None:
            raise AIError(f"mock 응답 미설정: {task}")
        if callable(r):
            return r(system, user)
        if not r:
            raise AIError("mock 응답 소진")
        return r.pop(0)


def _map_sdk_error(sdk, e: Exception, label: str, model: str) -> AIError:
    """openai·anthropic SDK는 같은 이름의 예외 계층을 쓴다."""
    if isinstance(e, sdk.APITimeoutError):
        return AIError(f"{label} 응답 시간 초과: 결과가 길어 시간이 오래 걸립니다. AI_TIMEOUT_SEC를 늘리거나 범위를 나눠 다시 시도하세요.")
    if isinstance(e, sdk.AuthenticationError):
        return AIError(f"{label} 인증 실패: API 키를 확인하세요.")
    if isinstance(e, sdk.NotFoundError):
        return AIError(f"{label}에서 모델 '{model}'을 찾을 수 없습니다(모델명 설정 확인).")
    if isinstance(e, sdk.RateLimitError):
        return AIError(f"{label} 사용량·요금 한도 초과: 잠시 후 다시 시도하거나 결제 한도를 확인하세요.")
    if isinstance(e, sdk.BadRequestError):
        return AIError(f"{label} 요청 형식 오류: {str(getattr(e, 'message', ''))[:200]}")
    if isinstance(e, sdk.APIStatusError):
        return AIError(f"{label} 서버 오류({e.status_code}): 잠시 후 다시 시도하세요.")
    if isinstance(e, sdk.APIConnectionError):
        return AIError(f"{label} 서버에 연결할 수 없습니다(주소·네트워크 확인).")
    return AIError(f"{label} 호출 실패: {type(e).__name__}")


class OpenAIProvider(AIProvider):
    """OpenAI Chat Completions + 구조화 출력. CompatibleProvider의 기반이기도 하다."""

    kind = "openai"
    external = True
    is_real_ai = True
    json_mode = "json_schema"

    def __init__(self, profile: AIProfile, settings: Settings, http_client: Any = None):
        import openai

        self._sdk = openai
        self.name = profile.name
        self.label = profile.label
        self.model = profile.model
        self.external = profile.external
        self.max_tokens = settings.ai_max_output_tokens
        kwargs: dict[str, Any] = {"api_key": profile.api_key or "not-needed", "timeout": settings.ai_timeout_sec, "max_retries": 1}
        if profile.base_url:
            kwargs["base_url"] = profile.base_url
        if http_client is not None:
            kwargs["http_client"] = http_client
        self.client = openai.OpenAI(**kwargs)

    def _request(self, task: str, system: str, user: str, schema: dict[str, Any]) -> dict[str, Any]:
        req: dict[str, Any] = {"model": self.model, "max_completion_tokens": self.max_tokens}
        if self.json_mode == "json_schema":
            req["response_format"] = {"type": "json_schema", "json_schema": {"name": re.sub(r"[^a-zA-Z0-9_-]", "_", task)[:64], "schema": schema, "strict": True}}
            req["messages"] = [{"role": "system", "content": system}, {"role": "user", "content": user}]
        else:
            # 구조화 출력을 지원하지 않는 서버: 스키마를 지시문에 넣는다(응답은 tasks.py에서 다시 검증)
            guide = "\n\n반드시 아래 JSON 스키마에 맞는 JSON 객체 하나만 출력하라. 설명·코드블록 표시 없이 JSON만.\n" + json.dumps(schema, ensure_ascii=False)
            req["messages"] = [{"role": "system", "content": system + guide}, {"role": "user", "content": user}]
            if self.json_mode == "json_object":
                req["response_format"] = {"type": "json_object"}
        return req

    def generate_json(self, task, system, user, schema):
        try:
            resp = self.client.chat.completions.create(**self._request(task, system, user, schema))
        except self._sdk.APIError as e:
            raise _map_sdk_error(self._sdk, e, self.label, self.model) from e
        usage = getattr(resp, "usage", None)
        choice = resp.choices[0] if resp.choices else None
        log.info("ai profile=%s task=%s model=%s finish=%s in=%s out=%s", self.name, task, self.model, getattr(choice, "finish_reason", None), getattr(usage, "prompt_tokens", None), getattr(usage, "completion_tokens", None))
        if choice is None:
            raise AIError(f"{self.label} 응답이 비어 있습니다.")
        if getattr(choice.message, "refusal", None):
            raise AIError(f"{self.label}가 이 요청 처리를 거절했습니다. 수동으로 작성하거나 내용을 바꿔 다시 시도하세요.")
        if choice.finish_reason == "length":
            raise AIError(f"{self.label} 응답이 너무 길어 잘렸습니다. 범위를 나눠 다시 요청하세요.")
        if choice.finish_reason == "content_filter":
            raise AIError(f"{self.label}의 콘텐츠 필터가 응답을 막았습니다.")
        text = choice.message.content or ""
        if not text.strip():
            raise AIError(f"{self.label} 응답에 본문이 없습니다.")
        return text if self.json_mode == "json_schema" else extract_json(text)


class CompatibleProvider(OpenAIProvider):
    """OpenAI 호환 API(상용·사내 LLM). 주소·모델·JSON 방식·외부 전송 여부를 설정으로 받는다."""

    kind = "compatible"

    def __init__(self, profile: AIProfile, settings: Settings, http_client: Any = None):
        super().__init__(profile, settings, http_client)
        self.json_mode = profile.json_mode


class AnthropicProvider(AIProvider):
    kind = "anthropic"
    external = True
    is_real_ai = True

    def __init__(self, profile: AIProfile, settings: Settings):
        import anthropic

        self._sdk = anthropic
        self.name = profile.name
        self.label = profile.label
        self.model = profile.model
        self.max_tokens = settings.ai_max_output_tokens
        kwargs: dict[str, Any] = {"api_key": profile.api_key, "timeout": settings.ai_timeout_sec, "max_retries": 1}
        if profile.base_url:
            kwargs["base_url"] = profile.base_url
        self.client = anthropic.Anthropic(**kwargs)

    def generate_json(self, task, system, user, schema):
        try:
            resp = self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                system=system,
                messages=[{"role": "user", "content": user}],
                output_config={"format": {"type": "json_schema", "schema": schema}},
            )
        except self._sdk.APIError as e:
            raise _map_sdk_error(self._sdk, e, self.label, self.model) from e
        log.info("ai profile=%s task=%s model=%s stop=%s in=%s out=%s", self.name, task, self.model, resp.stop_reason, resp.usage.input_tokens, resp.usage.output_tokens)
        if resp.stop_reason == "refusal":
            raise AIError(f"{self.label}가 이 요청 처리를 거절했습니다. 수동으로 작성하거나 내용을 바꿔 다시 시도하세요.")
        if resp.stop_reason == "max_tokens":
            raise AIError(f"{self.label} 응답이 너무 길어 잘렸습니다. 범위를 나눠 다시 요청하세요.")
        text = next((b.text for b in resp.content if b.type == "text"), "")
        if not text:
            raise AIError(f"{self.label} 응답에 본문이 없습니다.")
        return text


def build_provider(profile: AIProfile, settings: Settings) -> AIProvider:
    if profile.kind == "openai":
        return OpenAIProvider(profile, settings)
    if profile.kind == "compatible":
        return CompatibleProvider(profile, settings)
    if profile.kind == "anthropic":
        return AnthropicProvider(profile, settings)
    if profile.kind == "mock":
        return MockProvider()
    return SampleProvider()


class ProviderRegistry:
    """설정된 모든 AI 연결. 프로젝트가 고른 연결(없으면 기본 연결)을 돌려준다."""

    def __init__(self, settings: Settings, override: AIProvider | None = None):
        self.providers: dict[str, AIProvider] = {}
        self.unusable: dict[str, AIProfile] = {}
        for name, prof in settings.ai_profiles.items():
            if prof.usable:
                self.providers[name] = build_provider(prof, settings)
            else:
                self.unusable[name] = prof
        self.providers.setdefault("sample", SampleProvider())
        self.default = settings.ai_default
        if override is not None:  # 테스트·내장용: 주어진 공급자를 기본 연결로
            self.providers[override.name] = override
            self.default = override.name

    @property
    def default_provider(self) -> AIProvider:
        return self.providers[self.default]

    def for_name(self, name: str | None) -> tuple[AIProvider, str]:
        """반환: (공급자, 안내 문구). 고른 연결이 없어졌으면 기본 연결로 대체하고 알린다."""
        if not name:
            return self.default_provider, ""
        if name in self.providers:
            return self.providers[name], ""
        return self.default_provider, f"선택한 AI 연결 '{name}'이 서버에 설정되어 있지 않아 기본 연결({self.default_provider.display()})을 사용합니다."

    def describe(self) -> list[dict[str, Any]]:
        out = [p.describe() | {"default": n == self.default} for n, p in self.providers.items()]
        out += [{"name": n, "kind": p.kind, "label": p.label, "model": p.model, "external": p.external, "is_real_ai": True, "display": p.label, "usable": False, "missing": p.missing, "default": False} for n, p in self.unusable.items()]
        return out


# 구조화 출력 스키마에서 공급자별 지원이 제각각인 제약은 빼고 보낸다(응답은 Pydantic으로 다시 검증).
_UNSUPPORTED_KEYS = ("maxItems", "minItems", "maxLength", "minLength", "pattern", "format", "minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum")


def strict_schema(model_cls) -> dict[str, Any]:
    """Pydantic 모델 → 구조화 출력용 JSON 스키마(모든 필드 required, 추가 속성 금지)."""
    schema = model_cls.model_json_schema()

    def fix(node: Any) -> None:
        if isinstance(node, dict):
            if node.get("type") == "object" and "properties" in node:
                node["additionalProperties"] = False
                node["required"] = list(node["properties"].keys())
            for k in ("title", "default", *_UNSUPPORTED_KEYS):
                node.pop(k, None)
            for k, v in node.items():
                if k in ("properties", "$defs"):
                    # 이름→스키마 사전: 키(필드명 'title' 등)는 지우지 않고 각 스키마만 정리
                    for sub in v.values():
                        fix(sub)
                else:
                    fix(v)
        elif isinstance(node, list):
            for v in node:
                fix(v)

    fix(schema)
    return schema


def extract_json(text: str) -> str:
    """구조화 출력이 없는 LLM 응답에서 JSON 객체만 꺼낸다(코드블록·앞뒤 설명 제거)."""
    t = text.strip()
    m = re.search(r"```(?:json)?\s*(.*?)```", t, re.S)
    if m:
        t = m.group(1).strip()
    i, j = t.find("{"), t.rfind("}")
    return t[i : j + 1] if i != -1 and j > i else t


def parse_json(text: str) -> Any:
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise AIError(f"AI 응답이 올바른 JSON이 아닙니다({e.msg}).") from e
