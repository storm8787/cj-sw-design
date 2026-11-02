"""앱 서버: 기존 create_app을 같은 프로세스의 스레드 하나에서 Uvicorn으로 실행한다(reload·다중 worker 없음).

- 127.0.0.1에만 바인딩한다. 선호 포트가 사용 중이면 OS가 고른 빈 포트를 쓴다(다른 프로세스를 끄지 않음).
- 환경변수는 앱 설정 이름만 지운 뒤 런처 값으로 채운다. 개발·CI 셸에 남은 OPENAI_API_KEY 등이 섞이지 않는다.
"""
from __future__ import annotations

import asyncio
import hmac
import json
import logging
import os
import socket
import threading
import time
from typing import Callable

from .config import LocalConfig
from .instance import APP_TAG, probe
from .paths import Layout, resource

log = logging.getLogger("swd.desktop")

APP_KEYS = {
    "APP_ENV", "DATA_DIR", "SECRET_KEY", "ADMIN_PASSWORD", "ADMIN_PASSWORD_HASH", "AUTH_DISABLED", "COOKIE_SECURE",
    "SESSION_MAX_AGE", "FRONTEND_DIST", "EXAMPLES_DIR", "AI_PROVIDER", "AI_MODEL", "AI_TIMEOUT_SEC", "AI_MAX_OUTPUT_TOKENS",
    "MAX_UPLOAD_MB", "MAX_UNCOMPRESSED_MB", "OFFICIAL_SOURCE_ALLOWLIST", "PORT",
}
APP_PREFIXES = ("OPENAI_", "ANTHROPIC_", "LLM_")


def app_environ(lay: Layout, cfg: LocalConfig, secret: str, openai_key: str | None) -> dict[str, str]:
    env = {
        "APP_ENV": "production",  # 인증·CSRF 유지(개발 모드·AUTH_DISABLED 사용 안 함)
        "DATA_DIR": str(lay.data),
        "SECRET_KEY": secret,
        "ADMIN_PASSWORD_HASH": cfg.password_hash,
        "COOKIE_SECURE": "false",  # http://127.0.0.1 로컬 접속. Render(HTTPS)의 true 설정과 무관
        "FRONTEND_DIST": str(resource("frontend_dist")),
        "EXAMPLES_DIR": str(resource("examples")),
        "AI_PROVIDER": "sample",
    }
    if openai_key:
        env.update({"AI_PROVIDER": "openai", "OPENAI_API_KEY": openai_key, "OPENAI_MODEL": cfg.openai_model})
        if cfg.openai_model_fp_candidates:
            env["OPENAI_MODEL_FP_CANDIDATES"] = cfg.openai_model_fp_candidates
    return env


def scrubbed(base: dict[str, str]) -> dict[str, str]:
    return {k: v for k, v in base.items() if k.upper() not in APP_KEYS and not k.upper().startswith(APP_PREFIXES)}


def apply_environ(env: dict[str, str]) -> None:
    keep = scrubbed(dict(os.environ))
    os.environ.clear()
    os.environ.update(keep)
    os.environ.update(env)


def bind(preferred: int) -> socket.socket:
    """선호 포트 → 안 되면 빈 포트. 독점 바인딩이라 다른 프로그램과 같은 포트를 나눠 쓰지 않는다."""
    last: OSError | None = None
    for port in (preferred, 0):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        if os.name == "nt":
            s.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        else:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)  # 재시작 직후 TIME_WAIT(대기 중 리스너는 여전히 거부)
        try:
            s.bind(("127.0.0.1", port))
            return s
        except OSError as e:
            log.info("port %s unavailable: %s", port, e)
            last = e
            s.close()
    raise last or OSError("빈 포트를 찾지 못했습니다.")


class ControlApp:
    """/__desktop/* 만 런처가 처리하고 나머지는 기존 앱으로 넘긴다(기존 인증·CSRF 그대로)."""

    def __init__(self, inner, instance: str, token: str, on_control: Callable[[str], None]):
        self.inner, self.instance, self.token, self.on_control = inner, instance, token, on_control

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or not scope["path"].startswith("/__desktop/"):
            return await self.inner(scope, receive, send)
        status, body = 404, {"detail": "없음"}
        if scope["path"] == "/__desktop/instance" and scope["method"] == "GET":
            status, body = 200, {"app": APP_TAG, "instance": self.instance}
        elif scope["path"] == "/__desktop/control" and scope["method"] == "POST":
            headers = {k.decode().lower(): v.decode() for k, v in scope["headers"]}
            raw = b""
            while True:
                msg = await receive()
                raw += msg.get("body", b"")
                if not msg.get("more_body"):
                    break
            try:
                action = json.loads(raw or b"{}").get("action", "")
            except ValueError:
                action = ""
            if not hmac.compare_digest(headers.get("x-desktop-token", ""), self.token):
                status, body = 403, {"detail": "거부"}
            elif action in ("show", "quit"):
                self.on_control(action)
                status, body = 200, {"ok": True}
            else:
                status, body = 422, {"detail": "알 수 없는 동작"}
        data = json.dumps(body).encode()
        await send({"type": "http.response.start", "status": status, "headers": [(b"content-type", b"application/json"), (b"cache-control", b"no-store")]})
        await send({"type": "http.response.body", "body": data})


class DesktopServer:
    def __init__(self, app, sock: socket.socket, instance: str):
        import uvicorn

        self.app, self.sock, self.instance = app, sock, instance
        self.port = sock.getsockname()[1]
        self.url = f"http://127.0.0.1:{self.port}/"
        cfg = uvicorn.Config(app, log_config=None, access_log=False, lifespan="on", http="h11", loop="asyncio", ws="none",
                             timeout_graceful_shutdown=5)
        self.server = uvicorn.Server(cfg)
        self.error: BaseException | None = None
        self.thread = threading.Thread(target=self._run, name="swd-server", daemon=True)

    def _run(self) -> None:
        try:
            asyncio.run(self.server.serve(sockets=[self.sock]))
        except BaseException as e:  # noqa: BLE001
            self.error = e
            log.exception("server stopped with error")

    def start(self) -> None:
        self.thread.start()

    def wait_ready(self, timeout: float = 60.0) -> bool:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if not self.thread.is_alive():
                return False
            if probe(self.port, self.instance, 1.0):
                return True
            time.sleep(0.3)
        return False

    def stop(self, timeout: float = 15.0) -> None:
        self.server.should_exit = True
        self.thread.join(timeout)
        try:
            self.sock.close()
        except OSError:
            pass


def active_jobs(app) -> int:
    ctx = getattr(getattr(app, "state", None), "ctx", None)
    if not ctx:
        return 0
    return ctx.db.query("SELECT COUNT(*) AS n FROM jobs WHERE status IN ('running','queued')")[0]["n"]


def close_app(app) -> int:
    """종료 정리: 진행 중 작업을 '중단'으로 기록하고(다음 실행에서 재시도 가능) DB를 닫는다. 기록한 작업 수를 돌려준다."""
    ctx = getattr(app.state, "ctx", None)
    if not ctx:
        return 0
    n = active_jobs(app)
    if n:
        from app.store import now

        ctx.db.execute("UPDATE jobs SET status='interrupted', message='프로그램 종료로 중단됨 — 재시도 가능', updated_at=? WHERE status IN ('running','queued')", (now(),))
    ctx.jobs.pool.shutdown(wait=False, cancel_futures=True)
    ctx.db.close()
    return n
