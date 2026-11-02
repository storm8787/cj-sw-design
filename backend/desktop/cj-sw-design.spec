# -*- mode: python ; coding: utf-8 -*-
# PyInstaller one-folder 빌드 설정(Windows 시험판). 실행: cd backend && uv run --group desktop python -m desktop.build
# 결과: dist/CJ-SW-Design/CJ-SW-Design.exe + _internal/(Python 런타임·의존성·화면·예제·기준값)
from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules

ROOT = Path(SPECPATH).resolve().parents[1]  # 저장소 루트
BACKEND = ROOT / "backend"

datas = [
    (str(ROOT / "frontend" / "dist"), "frontend_dist"),  # 일반 앱 빌드(Pages 시연 빌드 아님)
    (str(ROOT / "examples"), "examples"),
    (str(BACKEND / "app" / "standards"), "app/standards"),  # FP 기준값(app/fp/standards.py가 app/standards에서 읽음)
    (str(BACKEND / "desktop" / "defaults.json"), "desktop"),
    (str(BACKEND / "build" / "build_info.json"), "."),  # build.py가 만든 커밋·빌드 정보
]
hidden = collect_submodules("app") + collect_submodules("desktop", filter=lambda m: m not in ("desktop.build", "desktop.smoke")) + collect_submodules("uvicorn") + collect_submodules("openai") + collect_submodules("anthropic")

a = Analysis(
    [str(BACKEND / "desktop" / "__main__.py")],
    pathex=[str(BACKEND)],
    datas=datas,
    hiddenimports=hidden,
    excludes=["pytest", "_pytest", "PyInstaller", "setuptools", "pip"],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="CJ-SW-Design",
    console=False,  # 직원 PC에서 검은 창 없이 런처 창만 보인다(기록은 사용자 데이터 폴더 logs/)
    upx=False,
    disable_windowed_traceback=False,
)
coll = COLLECT(exe, a.binaries, a.datas, name="CJ-SW-Design", upx=False)
