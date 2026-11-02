"""경로: 읽기 전용 실행 리소스(배포 폴더)와 쓰기 가능한 사용자 데이터(%LOCALAPPDATA%)를 분리한다."""
from __future__ import annotations

import os
import sys
from pathlib import Path

APP_ID = "CJ-SW-Design"
HOME_ENV = "CJSWD_HOME"  # 시험용으로만 사용자 데이터 위치를 바꾼다(docs/WINDOWS.md)


def frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def bundle_dir() -> Path:
    """배포 폴더의 리소스 위치. PyInstaller one-folder에서는 실행파일 옆 _internal(sys._MEIPASS)."""
    if frozen():
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return Path(__file__).resolve().parents[2]  # 소스 실행: 저장소 루트


def resource(name: str) -> Path:
    """frontend_dist·examples·desktop_defaults.json. 소스 실행 때는 저장소의 같은 파일."""
    b = bundle_dir()
    if frozen():  # 배치는 cj-sw-design.spec의 datas와 같다
        return {"frontend_dist": b / "frontend_dist", "examples": b / "examples", "desktop_defaults.json": b / "desktop" / "defaults.json"}[name]
    return {
        "frontend_dist": b / "frontend" / "dist",
        "examples": b / "examples",
        "desktop_defaults.json": b / "backend" / "desktop" / "defaults.json",
    }[name]


def home() -> Path:
    """사용자별 데이터 폴더. 기본 %LOCALAPPDATA%\\CJ-SW-Design. 배포 폴더를 옮기거나 새 ZIP으로 바꿔도 그대로 이어진다."""
    override = os.environ.get(HOME_ENV, "").strip()
    if override:
        h = Path(override)
    elif os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        h = Path(base) / APP_ID
    else:  # 소스 시험용(Linux·macOS)
        h = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share") / APP_ID
    h = h.resolve()
    if frozen() and (h == bundle_dir().parent or bundle_dir().parent in h.parents):
        raise RuntimeError(f"데이터 폴더({h})를 프로그램 폴더 안에 둘 수 없습니다.")
    return h


class Layout:
    """사용자 데이터 폴더 구성."""

    def __init__(self, root: Path):
        self.root = root
        self.data = root / "data"  # 앱 DATA_DIR: SQLite DB·업로드 원본·사용자 정의 기준
        self.config = root / "config"  # 런처 설정·보호 저장한 비밀값(백업 JSON에 들어가지 않음)
        self.logs = root / "logs"
        self.run = root / "run"  # 실행 중 인스턴스 정보·잠금

    def ensure(self) -> "Layout":
        for d in (self.data, self.config, self.logs, self.run):
            d.mkdir(parents=True, exist_ok=True)
        return self
