"""Windows 시험판 진입점. 더블클릭 → (처음이면 비밀번호 설정) → 127.0.0.1 서버 준비 확인 → 기본 브라우저 열기.

시험·자동화용 옵션(직원은 쓰지 않아도 된다, docs/WINDOWS.md):
  --no-gui                    창 없이 실행(--quit로 종료)
  --password-file FILE        처음 실행 비밀번호를 파일에서 읽음(창 없이 시험할 때)
  --set-openai-key-file FILE  OpenAI 키를 보호 저장소에 저장하고 끝냄(실행 중이 아닐 때)
  --clear-openai-key          저장한 키를 지우고 끝냄
  --quit                      실행 중인 인스턴스를 정상 종료
  --no-browser                브라우저를 자동으로 열지 않음

종료 코드: 0 정상 · 2 비밀번호 미설정 · 3 기존 인스턴스 응답 없음 · 4 서버 시작 실패 · 5 설정·보호 저장소 오류
"""
from __future__ import annotations

import argparse
import json
import logging
import logging.handlers
import os
import queue
import secrets
import subprocess
import sys
import time
import webbrowser
from pathlib import Path

from . import config as lc
from .instance import InstanceLock, control, probe, read_info, write_info
from .keystore import KeystoreError
from .paths import Layout, bundle_dir, frozen, home

log = logging.getLogger("swd.desktop")


def build_info() -> dict:
    f = bundle_dir() / "build_info.json"
    try:
        return json.loads(f.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"commit": "source", "built_at": ""}


def setup_logging(lay: Layout) -> None:
    if sys.stdout is None or sys.stderr is None:  # 창 모드 실행파일은 표준 출력이 없다
        stream = open(lay.logs / "console.log", "a", encoding="utf-8", buffering=1)  # noqa: SIM115
        sys.stdout = sys.stdout or stream
        sys.stderr = sys.stderr or stream
    h = logging.handlers.RotatingFileHandler(lay.logs / "launcher.log", maxBytes=1_000_000, backupCount=3, encoding="utf-8")
    h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    root = logging.getLogger()
    root.handlers[:] = [h]
    root.setLevel(logging.INFO)
    for n in ("httpx", "httpcore", "openai", "anthropic"):
        logging.getLogger(n).setLevel(logging.WARNING)


def parse(argv: list[str] | None) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="CJ-SW-Design", add_help=True)
    p.add_argument("--no-gui", action="store_true")
    p.add_argument("--no-browser", action="store_true")
    p.add_argument("--password-file")
    p.add_argument("--set-openai-key-file")
    p.add_argument("--clear-openai-key", action="store_true")
    p.add_argument("--quit", action="store_true")
    p.add_argument("--wait-for-lock", type=float, default=0.0)
    return p.parse_args(argv)


def _read_secret_file(path: str) -> str:
    return Path(path).read_text(encoding="utf-8").rstrip("\r\n")


def cmd_quit(lay: Layout) -> int:
    info = read_info(lay.run / "instance.json")
    if not info or not probe(info["port"], info["instance"]):
        log.info("quit: no running instance")
        return 0
    control(info, "quit")
    lock = InstanceLock(lay.run / "launcher.lock")
    if lock.acquire(wait=30):
        lock.release()
        return 0
    return 3


def open_existing(lay: Layout, args, gui_error) -> int:
    """이미 실행 중: 실행 정보가 가리키는 서버가 우리 인스턴스인지 확인한 뒤 그 화면을 연다."""
    path = lay.run / "instance.json"
    deadline = time.monotonic() + 20  # 막 시작 중일 수 있다
    while time.monotonic() < deadline:
        info = read_info(path)
        if info and probe(info["port"], info["instance"]):
            control(info, "show")
            if not args.no_browser:
                webbrowser.open(info["url"])
            log.info("already running on %s — opened existing", info["url"])
            return 0
        time.sleep(0.5)
    gui_error("이미 실행 중인 정보화 설계 도우미가 응답하지 않습니다.\n"
              "잠시 후 다시 실행하거나, 작업 관리자에서 'CJ-SW-Design'을 끝낸 뒤 다시 실행하세요.\n"
              f"진단 기록: {lay.logs / 'launcher.log'}")
    return 3


def main(argv: list[str] | None = None) -> int:
    args = parse(argv)
    lay = Layout(home()).ensure()
    setup_logging(lay)
    bi = build_info()
    log.info("start frozen=%s commit=%s built=%s bundle=%s home=%s", frozen(), bi.get("commit"), bi.get("built_at"), bundle_dir(), lay.root)
    try:
        import truststore

        truststore.inject_into_ssl()  # Windows 인증서 저장소 사용(기관 프록시 인증서 포함). TLS 검증은 끄지 않는다
    except Exception as e:  # noqa: BLE001
        log.warning("truststore unavailable: %s", type(e).__name__)

    ui = None

    def gui_error(msg: str) -> None:
        log.error("%s", msg.replace("\n", " "))
        if ui:
            ui.error(msg)
        elif not args.no_gui:
            try:
                from .gui import Gui

                Gui().error(msg)
            except Exception:  # noqa: BLE001
                pass

    if args.quit:
        return cmd_quit(lay)

    lock = InstanceLock(lay.run / "launcher.lock")
    if not lock.acquire(wait=args.wait_for_lock):
        return open_existing(lay, args, gui_error)
    try:
        try:
            cfg = lc.load(lay)
        except (OSError, ValueError, TypeError) as e:
            gui_error(f"설정 파일을 읽지 못했습니다({type(e).__name__}).\n{lay.config / 'settings.json'} 을 다른 이름으로 옮긴 뒤 다시 실행하면 "
                      f"비밀번호를 새로 정하고 시작합니다(프로젝트 데이터는 그대로 남습니다).\n진단 기록: {lay.logs / 'launcher.log'}")
            return 5
        if args.set_openai_key_file or args.clear_openai_key:
            try:
                if args.clear_openai_key:
                    lc.clear_openai_key(lay)
                else:
                    lc.set_openai_key(lay, _read_secret_file(args.set_openai_key_file))
            except (lc.ConfigError, KeystoreError, OSError) as e:
                log.error("key setting failed: %s", e)
                return 5
            log.info("openai key %s", "cleared" if args.clear_openai_key else "saved")
            return 0
        if not args.no_gui:
            from .gui import Gui

            ui = Gui()
        if not cfg.password_hash:
            try:
                if args.password_file:
                    pw = _read_secret_file(args.password_file)
                elif ui:
                    pw = ui.ask_first_password()
                    if pw is None:
                        return 0
                else:
                    log.error("first run needs --password-file in --no-gui mode")
                    return 2
                lc.set_password(lay, cfg, pw)
            except (lc.ConfigError, KeystoreError, OSError) as e:
                gui_error(f"비밀번호를 저장하지 못했습니다: {e}")
                return 5
            log.info("password set (first run)")
        action = run(lay, cfg, args, ui, gui_error)
    finally:
        if ui:
            ui.destroy()
        lock.release()
    if action == "restart":
        restart(args)
    return 0 if action in ("quit", "restart") else int(action)


def run(lay: Layout, cfg: lc.LocalConfig, args, ui, gui_error):
    from .server import ControlApp, DesktopServer, active_jobs, app_environ, apply_environ, bind, close_app

    tick = ui.splash("정보화 설계 도우미를 시작하는 중입니다…") if ui else None
    try:
        secret = lc.secret_key(lay)
        try:
            key = lc.openai_key(lay)
        except KeystoreError as e:
            key = None
            log.warning("openai key unreadable, sample mode: %s", e)
        apply_environ(app_environ(lay, cfg, secret, key))
        from app.main import create_app

        app = create_app()
    except Exception as e:  # noqa: BLE001
        log.exception("app setup failed")
        if ui:
            ui.close_splash()
        gui_error(f"프로그램 설정을 읽지 못했습니다({type(e).__name__}: {e}).\n진단 기록: {lay.logs / 'launcher.log'}")
        return 5

    instance, token = secrets.token_hex(16), secrets.token_hex(32)
    events: queue.Queue[str] = queue.Queue()
    srv = None
    try:
        sock = bind(cfg.port)
        srv = DesktopServer(ControlApp(app, instance, token, events.put), sock, instance)
        if srv.port != cfg.port:
            log.info("preferred port %s busy, using %s", cfg.port, srv.port)
        srv.start()
        deadline = time.monotonic() + 60
        ready = False
        while time.monotonic() < deadline and not ready:
            ready = srv.wait_ready(0.5)
            if tick:
                tick()
            if not srv.thread.is_alive():
                break
        if ui:
            ui.close_splash()
        if not ready:
            gui_error(f"서버가 60초 안에 준비되지 않았습니다({type(srv.error).__name__ if srv.error else '응답 없음'}).\n"
                      f"진단 기록: {lay.logs / 'launcher.log'}")
            return 4
        info = {"pid": os.getpid(), "port": srv.port, "url": srv.url, "instance": instance, "token": token,
                "started_at": time.strftime("%Y-%m-%dT%H:%M:%S")}
        write_info(lay.run / "instance.json", info)
        ai = app.state.ctx.ai.default_provider.describe()
        log.info("ready url=%s ai=%s", srv.url, ai.get("kind"))
        if not args.no_browser:
            webbrowser.open(srv.url)
        if ui:
            ai_text = ai.get("display") or ai.get("label")
            if ai.get("kind") == "sample":
                ai_text += " — 외부 AI 전송 없음"
            action = ui.run_main(srv.url, ai_text, lay, cfg, events, lambda: active_jobs(app))
        else:
            action = ""
            while action != "quit":
                action = events.get()
        return action
    finally:
        if srv:
            srv.stop()
        n = close_app(app)
        (lay.run / "instance.json").unlink(missing_ok=True)
        log.info("stopped (interrupted jobs=%s)", n)


def restart(args) -> None:
    from .server import scrubbed

    cmd = [sys.executable] if frozen() else [sys.executable, "-m", "desktop"]
    cmd += ["--wait-for-lock", "30"]
    if args.no_browser:
        cmd.append("--no-browser")
    log.info("restarting")
    subprocess.Popen(cmd, env=scrubbed(dict(os.environ)), cwd=str(Path(sys.executable).parent))  # noqa: S603


def entry() -> None:
    code = 1
    try:
        code = main()
    except SystemExit as e:
        code = int(e.code or 0) if isinstance(e.code, int) else 1
    except Exception:  # noqa: BLE001
        log.exception("launcher crashed")
    finally:
        logging.shutdown()
    os._exit(code)  # 남은 작업 스레드(외부 AI 응답 대기 등)를 기다리지 않고 끝낸다. 작업은 '중단'으로 기록됨
