"""FastAPI 앱 진입점. 빌드된 화면(frontend/dist)도 같은 출처로 제공한다."""
from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse

from .ai import tasks as ai_tasks
from .ai.provider import AIProvider, ProviderRegistry
from .auth import COOKIE, CSRF_HEADER, CSRF_VALUE, Auth
from .config import Settings, load_settings
from .db import Database
from .docs_extract.extract import UploadRejected
from .fp.cost import CostError
from .fp.standards import StandardError, StandardRegistry
from .jobs import JobRunner, UserFacingError
from .store import Conflict, InvalidData, NotFound, ProjectStore
from .tech.fetch import FetchBlocked

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
for _n in ("httpx", "httpx2"):
    logging.getLogger(_n).setLevel(logging.WARNING)


class AppCtx:
    def __init__(self, settings: Settings, provider: AIProvider | None = None, synchronous_jobs: bool = False):
        self.settings = settings
        settings.data_dir.mkdir(parents=True, exist_ok=True)
        self.db = Database(settings.data_dir / "app.db")
        self.store = ProjectStore(self.db, settings.data_dir)
        self.registry = StandardRegistry(settings.data_dir / "standards")
        self.ai = ProviderRegistry(settings, override=provider)
        self.auth = Auth(settings.secret_key, settings.admin_password_hash, settings.admin_password, settings.session_max_age, settings.auth_disabled)
        self.jobs = JobRunner(self.db, synchronous=synchronous_jobs)
        for kind, fn in (
            ("questions", ai_tasks.task_questions),
            ("requirements", ai_tasks.task_requirements),
            ("design", ai_tasks.task_design),
            ("fp_candidates", ai_tasks.task_fp),
            ("doc_analysis", ai_tasks.task_doc_analysis),
        ):
            self.jobs.register(kind, lambda ctx, params, fn=fn: fn(self, ctx, params))

    def provider_for(self, project) -> AIProvider:
        """프로젝트가 고른 AI 연결(없거나 사라졌으면 서버 기본 연결)."""
        return self.ai.for_name(getattr(project, "ai_profile", ""))[0]

    def provider_for_job(self, project, params) -> AIProvider:
        """작업을 제출할 때 정한 AI 연결(전송 동의도 이 연결 기준). 대기·재시도 중 프로젝트 연결이 바뀌어도 따르지 않고,
        그 연결이 사라졌으면 다른 연결로 몰래 바꾸지 않고 실패한다."""
        name = params.get("profile")
        if not name:
            return self.provider_for(project)
        if name not in self.ai.providers:
            raise UserFacingError(f"작업을 요청한 AI 연결 '{name}'을 지금 쓸 수 없습니다. 다른 연결로 바꾸지 않았습니다. 화면에서 다시 요청하세요.")
        prov = self.ai.providers[name]
        # 제출 때 기록한 모델·추론 설정과 지금 서버 설정이 다르면(배포로 모델 변경 등) 다른 모델로 몰래 실행하지 않는다
        want = params.get("model")
        if want:
            task = "doc_extract" if params.get("document_id") else params.get("_kind", "")
            now_model = prov.model_for(task) if task else prov.model
            if now_model != want or prov.reasoning_effort != params.get("reasoning_effort", prov.reasoning_effort):
                raise UserFacingError(f"작업을 요청한 뒤 AI 모델 설정이 바뀌었습니다(요청 {want} → 현재 {now_model}). 다른 모델로 바꾸지 않았습니다. 화면에서 다시 요청하세요.")
        return prov


PUBLIC = {"/api/health", "/api/auth/login", "/api/auth/me"}
MUTATING = {"POST", "PUT", "PATCH", "DELETE"}


def create_app(settings: Settings | None = None, provider: AIProvider | None = None, synchronous_jobs: bool = False) -> FastAPI:
    settings = settings or load_settings()
    ctx = AppCtx(settings, provider, synchronous_jobs)
    app = FastAPI(title="정보화 설계 도우미", docs_url="/api/docs" if settings.is_dev else None, redoc_url=None, openapi_url="/api/openapi.json" if settings.is_dev else None)
    app.state.ctx = ctx

    @app.middleware("http")
    async def guard(request: Request, call_next):
        path = request.url.path
        if path.startswith("/api/"):
            if request.method in MUTATING and request.headers.get(CSRF_HEADER) != CSRF_VALUE:
                return JSONResponse({"detail": "요청 헤더가 없습니다(X-Requested-With)."}, status_code=403)
            if path not in PUBLIC and not ctx.auth.check(request.cookies.get(COOKIE)):
                return JSONResponse({"detail": "로그인이 필요합니다."}, status_code=401)
        resp = await call_next(request)
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("X-Frame-Options", "DENY")
        resp.headers.setdefault("Referrer-Policy", "same-origin")
        if path.startswith("/api/"):
            resp.headers.setdefault("Cache-Control", "no-store")
        return resp

    for exc, code in ((NotFound, 404), (InvalidData, 422), (StandardError, 422), (CostError, 422), (UploadRejected, 422), (FetchBlocked, 422), (Conflict, 409), (PermissionError, 429)):
        app.add_exception_handler(exc, lambda r, e, code=code: JSONResponse({"detail": str(e)}, status_code=code))

    from .routes import router

    app.include_router(router)

    dist = settings.frontend_dist
    if dist and dist.exists():
        index = dist / "index.html"

        @app.get("/{full_path:path}", include_in_schema=False)
        def spa(full_path: str):
            if full_path.startswith("api/"):
                return JSONResponse({"detail": "없는 API"}, status_code=404)
            f = (dist / full_path).resolve()
            if full_path and dist.resolve() in f.parents and f.is_file():
                return FileResponse(f)
            return FileResponse(index)

    return app
