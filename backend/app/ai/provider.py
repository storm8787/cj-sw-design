"""AI 공급자 어댑터.

- SampleProvider: 규칙 기반(외부 전송 없음, AI 아님). 키가 없을 때 기본.
- AnthropicProvider: 공식 anthropic SDK + 구조화 출력(JSON 스키마). 모델명은 AI_MODEL 환경변수에서만 받는다.
- MockProvider: 테스트용. 미리 정한 응답(잘못된 JSON 포함)을 돌려준다.

프롬프트·원문·키는 로그에 남기지 않는다.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Callable

from ..config import Settings

log = logging.getLogger("swd.ai")


class AIError(RuntimeError):
    """AI 호출 실패(재시도 대상이 아닐 수 있음). 메시지는 사용자에게 보여줄 수 있는 한국어."""


class AIProvider:
    name = "base"
    external = False  # 외부로 데이터가 전송되는가
    is_real_ai = False
    model = ""

    def generate_json(self, task: str, system: str, user: str, schema: dict[str, Any]) -> str:
        raise NotImplementedError

    def describe(self) -> dict[str, Any]:
        return {"provider": self.name, "external": self.external, "is_real_ai": self.is_real_ai, "model": self.model}


class SampleProvider(AIProvider):
    name = "sample"

    def generate_json(self, task, system, user, schema):  # pragma: no cover - 샘플은 규칙 함수로 직접 처리
        raise AIError("샘플 모드는 규칙 기반 생성기를 사용합니다.")


class MockProvider(AIProvider):
    """테스트용. responses[task]는 문자열 목록(호출 순서대로 반환) 또는 함수."""

    name = "mock"
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


class AnthropicProvider(AIProvider):
    name = "anthropic"
    external = True
    is_real_ai = True

    def __init__(self, settings: Settings):
        import anthropic

        self._anthropic = anthropic
        self.model = settings.ai_model
        self.max_tokens = settings.ai_max_output_tokens
        self.client = anthropic.Anthropic(
            api_key=settings.anthropic_api_key,
            base_url=settings.anthropic_base_url,
            timeout=settings.ai_timeout_sec,
            max_retries=2,
        )

    def generate_json(self, task, system, user, schema):
        a = self._anthropic
        try:
            resp = self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                system=system,
                messages=[{"role": "user", "content": user}],
                output_config={"format": {"type": "json_schema", "schema": schema}},
            )
        except a.AuthenticationError as e:
            raise AIError("AI 인증 실패: API 키를 확인하세요.") from e
        except a.NotFoundError as e:
            raise AIError(f"AI 모델 '{self.model}'을 찾을 수 없습니다(AI_MODEL 확인).") from e
        except a.RateLimitError as e:
            raise AIError("AI 사용량 한도 초과: 잠시 후 다시 시도하세요.") from e
        except a.BadRequestError as e:
            raise AIError(f"AI 요청 형식 오류: {getattr(e, 'message', '')[:200]}") from e
        except a.APIStatusError as e:
            raise AIError(f"AI 서버 오류({e.status_code}): 잠시 후 다시 시도하세요.") from e
        except a.APIConnectionError as e:
            raise AIError("AI 서버에 연결할 수 없습니다(네트워크 확인).") from e
        log.info("ai task=%s model=%s stop=%s in=%s out=%s", task, self.model, resp.stop_reason, resp.usage.input_tokens, resp.usage.output_tokens)
        if resp.stop_reason == "refusal":
            raise AIError("AI가 이 요청 처리를 거절했습니다. 수동으로 작성하거나 내용을 바꿔 다시 시도하세요.")
        if resp.stop_reason == "max_tokens":
            raise AIError("AI 응답이 너무 길어 잘렸습니다. 범위를 나눠 다시 요청하세요.")
        text = next((b.text for b in resp.content if b.type == "text"), "")
        if not text:
            raise AIError("AI 응답에 본문이 없습니다.")
        return text


def build_provider(settings: Settings) -> AIProvider:
    if settings.ai_provider == "anthropic":
        return AnthropicProvider(settings)
    if settings.ai_provider == "mock":
        return MockProvider()
    return SampleProvider()


def strict_schema(model_cls) -> dict[str, Any]:
    """Pydantic 모델 → 구조화 출력용 JSON 스키마(모든 필드 required, 추가 속성 금지)."""
    schema = model_cls.model_json_schema()

    def fix(node: Any) -> None:
        if isinstance(node, dict):
            if node.get("type") == "object" and "properties" in node:
                node["additionalProperties"] = False
                node["required"] = list(node["properties"].keys())
            node.pop("title", None)
            node.pop("default", None)
            for v in node.values():
                fix(v)
        elif isinstance(node, list):
            for v in node:
                fix(v)

    fix(schema)
    return schema


def parse_json(text: str) -> Any:
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise AIError(f"AI 응답이 올바른 JSON이 아닙니다({e.msg}).") from e
