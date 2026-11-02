"""Windows 시험판 빌드: PyInstaller one-folder → 금지 파일 검사 → 시험용 ZIP + SHA-256.

실행(Windows, 저장소 루트에서 화면을 먼저 빌드):
    cd frontend && npm ci && npm run build
    cd backend && uv sync --frozen --group desktop && uv run --group desktop python -m desktop.build
결과: backend/dist/CJ-SW-Design-windows-x64-<커밋>.zip, .sha256, build_info.json
대상 PC에는 Python·Node·uv가 필요 없다(빌드 PC에만 필요).
"""
from __future__ import annotations

import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import time
import zipfile
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
ROOT = BACKEND.parent
DIST = BACKEND / "dist"
APP = "CJ-SW-Design"
# 배포 폴더에 있으면 안 되는 것: 개발 설정·사용자 DB·기록·실행 정보
FORBIDDEN_NAMES = {".env", "app.db", "launcher.log", "console.log", "instance.json", "launcher.lock", "settings.json", "secret.bin", "openai_key.bin"}
FORBIDDEN_SUFFIXES = (".db", ".db-wal", ".db-shm", ".sqlite", ".log", ".env")
SECRET_ENV = ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "LLM_API_KEY", "ADMIN_PASSWORD", "SECRET_KEY", "E2E_PASSWORD")


def git(*args: str) -> str:
    try:
        return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return ""


def build_info() -> dict:
    import PyInstaller

    # PR 실행의 GITHUB_SHA는 임시 병합 커밋이므로 워크플로가 넘기는 PR 머리 커밋(BUILD_COMMIT)을 먼저 쓴다
    commit = os.environ.get("BUILD_COMMIT") or os.environ.get("GITHUB_SHA") or git("rev-parse", "HEAD") or "unknown"
    return {
        "app": APP,
        "commit": commit,
        "dirty": bool(git("status", "--porcelain", "--untracked-files=no")),
        "built_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "python": platform.python_version(),
        "pyinstaller": PyInstaller.__version__,
        "platform": platform.platform(),
        "machine": platform.machine(),
        "ci_run": os.environ.get("GITHUB_RUN_ID", ""),
        "signed": False,
    }


def check_tree(folder: Path) -> list[str]:
    problems = []
    secrets_now = [os.environ[k] for k in SECRET_ENV if len(os.environ.get(k, "")) >= 8]
    for f in folder.rglob("*"):
        if not f.is_file():
            continue
        rel = f.relative_to(folder).as_posix()
        if f.name in FORBIDDEN_NAMES or f.name.endswith(FORBIDDEN_SUFFIXES):
            problems.append(f"금지 파일: {rel}")
        if secrets_now and f.stat().st_size < 50_000_000:
            data = f.read_bytes()
            if any(s.encode() in data for s in secrets_now):
                problems.append(f"빌드 환경의 비밀값이 들어 있음: {rel}")
    dist = folder / "_internal" / "frontend_dist"
    if not (dist / "index.html").exists():
        problems.append("화면 빌드(frontend_dist/index.html) 없음")
    if (dist / "demo-data").exists():
        problems.append("Pages 시연 빌드가 들어 있음(일반 빌드여야 함)")
    return problems


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    if not (ROOT / "frontend" / "dist" / "index.html").exists():
        print("frontend/dist가 없습니다. 먼저 cd frontend && npm ci && npm run build", file=sys.stderr)
        return 1
    info = build_info()
    (BACKEND / "build").mkdir(exist_ok=True)
    (BACKEND / "build" / "build_info.json").write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")
    shutil.rmtree(DIST / APP, ignore_errors=True)
    import PyInstaller.__main__

    PyInstaller.__main__.run([str(BACKEND / "desktop" / "cj-sw-design.spec"), "--noconfirm", "--clean",
                              "--distpath", str(DIST), "--workpath", str(BACKEND / "build" / "pyinstaller")])
    folder = DIST / APP
    shutil.copy(BACKEND / "desktop" / "README_WINDOWS.txt", folder / "README.txt")
    problems = check_tree(folder)
    if problems:
        print("\n".join(problems), file=sys.stderr)
        return 2
    short = info["commit"][:7]
    tag = "windows-x64" if os.name == "nt" else f"{sys.platform}-test-only"  # Windows에서 빌드한 것만 Windows판이라 부른다
    zpath = DIST / f"{APP}-{tag}-{short}.zip"
    zpath.unlink(missing_ok=True)
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for f in sorted(folder.rglob("*")):
            if f.is_file():
                z.write(f, Path(APP) / f.relative_to(folder))
    digest = sha256(zpath)
    (DIST / (zpath.name + ".sha256")).write_text(f"{digest}  {zpath.name}\n", encoding="utf-8")
    info |= {"zip": zpath.name, "zip_bytes": zpath.stat().st_size, "sha256": digest}
    (DIST / "build_info.json").write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(info, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
