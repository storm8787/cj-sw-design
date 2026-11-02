"""한 사용자당 한 인스턴스: 잠금 파일 + 실행 정보(run/instance.json).

다른 프로그램이 같은 포트를 쓰고 있어도 우리 앱으로 오인하지 않도록, 실행 정보의 instance 값을
/__desktop/instance 응답과 대조한 뒤에만 기존 화면을 연다. 강제 종료되면 OS가 잠금을 풀어 다음 실행이 이어받는다.
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

APP_TAG = "cj-sw-design"
_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))  # 127.0.0.1 요청에 사내 프록시를 쓰지 않는다


class InstanceLock:
    def __init__(self, path: Path):
        self.path = path
        self._f = None

    def _try(self) -> bool:
        f = open(self.path, "a+b")
        try:
            if os.name == "nt":
                import msvcrt

                f.seek(0)
                msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            f.close()
            return False
        self._f = f
        return True

    def acquire(self, wait: float = 0.0) -> bool:
        deadline = time.monotonic() + wait
        while True:
            if self._try():
                return True
            if time.monotonic() >= deadline:
                return False
            time.sleep(0.25)

    def release(self) -> None:
        if not self._f:
            return
        try:
            if os.name == "nt":
                import msvcrt

                self._f.seek(0)
                msvcrt.locking(self._f.fileno(), msvcrt.LK_UNLCK, 1)
        except OSError:
            pass
        self._f.close()
        self._f = None


def write_info(path: Path, info: dict) -> None:
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(info, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, path)


def read_info(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _get_json(url: str, timeout: float = 2.0, data: bytes | None = None, headers: dict | None = None) -> dict | None:
    req = urllib.request.Request(url, data=data, headers=headers or {}, method="POST" if data is not None else "GET")
    try:
        with _OPENER.open(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except (urllib.error.URLError, OSError, ValueError):
        return None


def probe(port: int, instance: str, timeout: float = 2.0) -> bool:
    """그 포트의 서버가 바로 이 실행 정보의 인스턴스인지 확인한다(다른 웹앱이면 False)."""
    r = _get_json(f"http://127.0.0.1:{port}/__desktop/instance", timeout)
    return bool(r and r.get("app") == APP_TAG and r.get("instance") == instance)


def control(info: dict, action: str, timeout: float = 5.0) -> bool:
    r = _get_json(f"http://127.0.0.1:{info['port']}/__desktop/control", timeout,
                  json.dumps({"action": action}).encode(), {"Content-Type": "application/json", "X-Desktop-Token": info["token"]})
    return bool(r and r.get("ok"))
