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
    # AI
    ai_provider: str = "sample"  # sample | anthropic | mock
    ai_model: str = ""
    anthropic_api_key: str = ""
    anthropic_base_url: str = "https://api.anthropic.com"
    ai_timeout_sec: float = 120.0
    ai_max_output_tokens: int = 8000
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
    s.ai_provider = os.environ.get("AI_PROVIDER", "").strip().lower()
    s.ai_model = os.environ.get("AI_MODEL", "").strip()
    s.anthropic_api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    s.anthropic_base_url = os.environ.get("AI_BASE_URL", "https://api.anthropic.com").rstrip("/")
    s.ai_timeout_sec = float(os.environ.get("AI_TIMEOUT_SEC", "120"))
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

    if not s.ai_provider:
        # 외부 전송은 명시적으로 켠 경우에만: 키가 있어도 기본은 샘플 모드
        s.ai_provider = "sample"
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
    if s.ai_provider == "anthropic" and not s.anthropic_api_key:
        raise ConfigError("AI_PROVIDER=anthropic 이면 ANTHROPIC_API_KEY 가 필요합니다.")
    if s.ai_provider == "anthropic" and not s.ai_model:
        raise ConfigError("AI_PROVIDER=anthropic 이면 AI_MODEL 을 지정해야 합니다.")
    if s.ai_provider not in ("sample", "anthropic", "mock"):
        raise ConfigError(f"알 수 없는 AI_PROVIDER: {s.ai_provider}")
