"""환경설정. 모든 비밀값·모델명은 환경변수에서만 읽는다."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


class ConfigError(RuntimeError):
    pass


def _bool(name: str, default: bool = False) -> bool:
    v = os.environ.get(name)
    if v is None:
        return default
    return v.strip().lower() in ("1", "true", "yes", "on")


PROFILE_KINDS = ("openai", "anthropic", "compatible", "sample", "mock")


@dataclass
class AIProfile:
    """AI 연결 하나. 여러 개를 동시에 설정하고 프로젝트마다 골라 쓴다."""

    name: str
    kind: str  # openai | anthropic | compatible | sample | mock
    label: str
    model: str = ""
    api_key: str = ""
    base_url: str = ""
    json_mode: str = "json_schema"  # compatible 전용: json_schema | json_object | prompt
    external: bool = True  # 외부 서버로 데이터가 나가는가(사내 설치형이면 false)
    task_models: dict[str, str] = field(default_factory=dict)  # 작업별 모델(선택, 예: OPENAI_MODEL_DESIGN). 없으면 model
    reasoning_effort: str = ""  # 추론 강도(선택, 지원 모델만). 비우면 모델 기본값
    missing: list[str] = field(default_factory=list)  # 사용 불가 사유(비어 있으면 사용 가능)

    @property
    def usable(self) -> bool:
        return not self.missing


@dataclass
class Settings:
    app_env: str = "production"
    data_dir: Path = Path("./data")
    secret_key: str = ""
    admin_password_hash: str = ""
    admin_password: str = ""
    auth_disabled: bool = False
    cookie_secure: bool = False
    session_max_age: int = 60 * 60 * 12
    # AI: 여러 연결(profile)을 동시에 설정, 기본 연결은 ai_default
    ai_default: str = "sample"
    ai_profiles: dict[str, AIProfile] = field(default_factory=dict)
    ai_timeout_sec: float = 600.0  # 긴 설계 초안은 수 분 걸릴 수 있음(2026-10-29 실측 100초 이상)
    ai_max_output_tokens: int = 32000  # 상한일 뿐 실제 사용량만 과금. 설계 초안 JSON이 8천 토큰을 넘는 경우 확인(2026-10-29)
    # 업로드
    max_upload_mb: int = 30
    max_uncompressed_mb: int = 200
    # 공식 자료 조회 허용 도메인
    official_source_allowlist: list[str] = field(default_factory=list)
    frontend_dist: Path | None = None

    @property
    def is_dev(self) -> bool:
        return self.app_env in ("development", "dev", "local", "test")


def load_settings() -> Settings:
    s = Settings()
    s.app_env = os.environ.get("APP_ENV", "production").strip().lower()
    s.data_dir = Path(os.environ.get("DATA_DIR", "./data")).resolve()
    s.secret_key = os.environ.get("SECRET_KEY", "")
    s.admin_password_hash = os.environ.get("ADMIN_PASSWORD_HASH", "")
    s.admin_password = os.environ.get("ADMIN_PASSWORD", "")
    s.auth_disabled = _bool("AUTH_DISABLED", False)
    s.cookie_secure = _bool("COOKIE_SECURE", False)
    s.ai_timeout_sec = float(os.environ.get("AI_TIMEOUT_SEC", "600"))
    s.ai_max_output_tokens = int(os.environ.get("AI_MAX_OUTPUT_TOKENS", "32000"))
    s.ai_profiles = load_ai_profiles()
    default = os.environ.get("AI_PROVIDER", "").strip().lower()
    if not default:
        # 기본은 ChatGPT(OpenAI) 키. 키가 없으면 샘플 모드. 외부 전송은 요청마다 동의를 받는다.
        default = "openai" if "openai" in s.ai_profiles else "sample"
    s.ai_default = default
    s.max_upload_mb = int(os.environ.get("MAX_UPLOAD_MB", "30"))
    s.max_uncompressed_mb = int(os.environ.get("MAX_UNCOMPRESSED_MB", "200"))
    allow = os.environ.get(
        "OFFICIAL_SOURCE_ALLOWLIST",
        "www.sw.or.kr,sw.or.kr,www.law.go.kr,www.postgresql.org,dev.mysql.com,tomcat.apache.org,"
        "nginx.org,httpd.apache.org,ubuntu.com,access.redhat.com,rockylinux.org,endoflife.date,"
        "spring.io,www.python.org,nodejs.org,www.egovframe.go.kr",
    )
    s.official_source_allowlist = [d.strip().lower() for d in allow.split(",") if d.strip()]
    fd = os.environ.get("FRONTEND_DIST")
    if fd:
        s.frontend_dist = Path(fd).resolve()
    else:
        cand = Path(__file__).resolve().parents[2] / "frontend" / "dist"
        s.frontend_dist = cand if cand.exists() else None

    validate(s)
    return s


def validate(s: Settings) -> None:
    if s.auth_disabled and not s.is_dev:
        raise ConfigError("AUTH_DISABLED=true 는 APP_ENV=development 에서만 허용됩니다.")
    if not s.auth_disabled:
        if len(s.secret_key) < 32:
            raise ConfigError("SECRET_KEY(32자 이상)를 설정해야 합니다. .env.example 참고")
        if not (s.admin_password_hash or s.admin_password):
            raise ConfigError("ADMIN_PASSWORD_HASH 또는 ADMIN_PASSWORD 를 설정해야 합니다.")
        if s.admin_password and len(s.admin_password) < 10:
            raise ConfigError("ADMIN_PASSWORD 는 10자 이상이어야 합니다.")
    s.ai_profiles.setdefault("sample", AIProfile(name="sample", kind="sample", label="샘플 모드(규칙 기반, AI 아님)", external=False))
    if s.ai_default not in s.ai_profiles:
        hint = {"openai": "OPENAI_API_KEY", "anthropic": "ANTHROPIC_API_KEY", "compatible": "LLM_BASE_URL"}.get(s.ai_default, "")
        raise ConfigError(f"AI_PROVIDER={s.ai_default} 연결이 설정되지 않았습니다." + (f" {hint} 를 설정하세요." if hint else " (openai | anthropic | compatible | sample)"))
    prof = s.ai_profiles[s.ai_default]
    if not prof.usable:
        raise ConfigError(f"기본 AI 연결 '{s.ai_default}' 설정이 부족합니다: {', '.join(prof.missing)}")


AI_TASK_NAMES = ("questions", "requirements", "design", "fp_candidates", "doc_extract")
REASONING_EFFORTS = ("", "none", "minimal", "low", "medium", "high", "xhigh")


def _task_options(p: AIProfile, prefix: str) -> None:
    """작업별 모델(<PREFIX>_MODEL_<작업>)·추론 강도(<PREFIX>_REASONING_EFFORT). 둘 다 선택 사항."""
    env = os.environ.get
    for t in AI_TASK_NAMES:
        v = env(f"{prefix}_MODEL_{t.upper()}", "").strip()
        if v:
            p.task_models[t] = v
    p.reasoning_effort = env(f"{prefix}_REASONING_EFFORT", "").strip().lower()
    if p.reasoning_effort not in REASONING_EFFORTS:
        p.missing.append(f"{prefix}_REASONING_EFFORT 값 오류: {p.reasoning_effort}")


def load_ai_profiles() -> dict[str, AIProfile]:
    """환경변수에서 AI 연결을 읽는다. 키(또는 주소)가 있는 연결만 등록한다. 모델명은 여기서만 읽는다."""
    env = os.environ.get
    fallback_model = env("AI_MODEL", "").strip()  # 이전 설정 호환: 기본 연결의 모델명
    default = env("AI_PROVIDER", "").strip().lower()

    def model_of(name: str, var: str) -> str:
        return env(var, "").strip() or (fallback_model if default in ("", name) else "")

    out: dict[str, AIProfile] = {}
    if env("OPENAI_API_KEY"):
        p = AIProfile(name="openai", kind="openai", label="OpenAI(ChatGPT)", api_key=env("OPENAI_API_KEY", ""),
                      model=model_of("openai", "OPENAI_MODEL"), base_url=env("OPENAI_BASE_URL", "").strip().rstrip("/"))
        if not p.model:
            p.missing.append("OPENAI_MODEL(모델명) 미설정")
        _task_options(p, "OPENAI")
        out["openai"] = p
    if env("ANTHROPIC_API_KEY"):
        p = AIProfile(name="anthropic", kind="anthropic", label="Anthropic(Claude)", api_key=env("ANTHROPIC_API_KEY", ""),
                      model=model_of("anthropic", "ANTHROPIC_MODEL"), base_url=env("ANTHROPIC_BASE_URL", "").strip().rstrip("/"))
        if not p.model:
            p.missing.append("ANTHROPIC_MODEL(모델명) 미설정")
        out["anthropic"] = p
    if env("LLM_BASE_URL"):
        mode = env("LLM_JSON_MODE", "json_schema").strip().lower()
        p = AIProfile(name="compatible", kind="compatible", label=env("LLM_LABEL", "").strip() or "OpenAI 호환 LLM",
                      api_key=env("LLM_API_KEY", ""), model=model_of("compatible", "LLM_MODEL"),
                      base_url=env("LLM_BASE_URL", "").strip().rstrip("/"), json_mode=mode, external=_bool("LLM_EXTERNAL", True))
        if not p.model:
            p.missing.append("LLM_MODEL(모델명) 미설정")
        if mode not in ("json_schema", "json_object", "prompt"):
            p.missing.append(f"LLM_JSON_MODE 값 오류: {mode}")
        if not p.base_url.startswith(("http://", "https://")):
            p.missing.append("LLM_BASE_URL은 http(s) 주소여야 함")
        _task_options(p, "LLM")
        out["compatible"] = p
    return out
