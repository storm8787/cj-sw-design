"""런처 로컬 설정(사용자 데이터 폴더의 config/). 앱 DATA_DIR과 분리되어 프로젝트 백업 JSON에 섞이지 않는다.

- settings.json: 로그인 비밀번호 해시(scrypt)·선호 포트·모델명. 비밀번호 원문은 저장하지 않는다.
- secret.bin: 세션 서명 키(설치별 무작위, DPAPI 보호).
- openai_key.bin: OpenAI API 키(선택, DPAPI 보호). 브라우저·프로젝트 DB·로그에 넣지 않는다.
"""
from __future__ import annotations

import json
import os
import secrets
from dataclasses import asdict, dataclass
from pathlib import Path

from app.auth import hash_password

from . import keystore
from .paths import Layout, resource

MIN_PASSWORD = 10  # 앱 ADMIN_PASSWORD 규칙과 같다(app/config.py)


class ConfigError(ValueError):
    pass


@dataclass
class LocalConfig:
    password_hash: str = ""
    port: int = 8765
    openai_model: str = ""
    openai_model_fp_candidates: str = ""


def defaults() -> dict:
    d = json.loads(resource("desktop_defaults.json").read_text(encoding="utf-8"))
    return {k: v for k, v in d.items() if not k.startswith("_")}


def _settings_file(lay: Layout) -> Path:
    return lay.config / "settings.json"


def load(lay: Layout) -> LocalConfig:
    cfg = LocalConfig(**defaults())
    f = _settings_file(lay)
    if f.exists():
        raw = json.loads(f.read_text(encoding="utf-8"))
        for k in asdict(cfg):
            if k in raw and raw[k] not in (None, ""):
                setattr(cfg, k, raw[k])
    cfg.port = int(cfg.port)
    return cfg


def save(lay: Layout, cfg: LocalConfig) -> None:
    f = _settings_file(lay)
    tmp = f.with_suffix(".tmp")
    tmp.write_text(json.dumps(asdict(cfg), ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, f)


def check_password(pw: str, again: str | None = None) -> None:
    if len(pw) < MIN_PASSWORD:
        raise ConfigError(f"비밀번호는 {MIN_PASSWORD}자 이상이어야 합니다.")
    if pw.strip() != pw:
        raise ConfigError("비밀번호 앞뒤에 공백을 넣을 수 없습니다.")
    if again is not None and pw != again:
        raise ConfigError("두 번 입력한 비밀번호가 다릅니다.")


def set_password(lay: Layout, cfg: LocalConfig, pw: str) -> None:
    """비밀번호를 바꾸면 세션 키도 새로 만들어 기존 로그인을 끊는다."""
    check_password(pw)
    cfg.password_hash = hash_password(pw)
    save(lay, cfg)
    keystore.save(lay.config / "secret.bin", secrets.token_hex(32))


def secret_key(lay: Layout) -> str:
    f = lay.config / "secret.bin"
    v = keystore.load(f)
    if not v:
        v = secrets.token_hex(32)
        keystore.save(f, v)
    return v


def _key_file(lay: Layout) -> Path:
    return lay.config / "openai_key.bin"


def check_openai_key(key: str) -> str:
    key = key.strip()
    if len(key) < 20 or any(c.isspace() for c in key) or not key.isascii():
        raise ConfigError("API 키 형식이 아닙니다(공백 없는 20자 이상의 영문·숫자).")
    return key


def set_openai_key(lay: Layout, key: str) -> None:
    keystore.save(_key_file(lay), check_openai_key(key))


def openai_key(lay: Layout) -> str | None:
    return keystore.load(_key_file(lay))


def clear_openai_key(lay: Layout) -> None:
    keystore.delete(_key_file(lay))


def mask(key: str | None) -> str:
    if not key:
        return "없음"
    return f"{key[:3]}…{key[-4:]}" if len(key) > 10 else "••••"
