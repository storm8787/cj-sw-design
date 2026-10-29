"""HTTP API. 모든 경로는 main.py의 미들웨어에서 인증·CSRF 검사를 받는다."""
from __future__ import annotations

import hashlib
import json
from typing import Any, Literal
from urllib.parse import quote

from fastapi import APIRouter, File, Form, Request, Response, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from .auth import COOKIE
from .docs_extract import extract as dx
from .excel import export as xl
from .fp import engine
from .fp import estimates as est
from .main import AppCtx
from .models import COLLECTIONS, CostSettings, DocumentMeta, Extraction, Overview, ReferenceItem, TaskDraft, TechInputs
from .review.review import run_review
from .services import backup, proposals, samples, status, taskdraft
from .store import InvalidData, NotFound, add_item, delete_item, find_item, next_id, now, update_item
from .tech import fetch as tfetch
from .tech import recommend as trec

router = APIRouter(prefix="/api")


def C(request: Request) -> AppCtx:
    return request.app.state.ctx


def actor(c: AppCtx) -> str:
    return "user"


def std_of(c: AppCtx, p) -> dict[str, Any]:
    return c.registry.get(p.cost_settings.standard_id)


def ok_project(c: AppCtx, pid: str, version: int | None = None) -> dict[str, Any]:
    p, v = c.store.get(pid)
    return {"project": json.loads(p.model_dump_json()), "version": v, "status": status.project_status(p, std_of(c, p))}


# ---------------------------------------------------------------- 인증·시스템
class LoginIn(BaseModel):
    password: str = Field(max_length=200)


@router.get("/health")
def health():
    return {"ok": True}


@router.post("/auth/login")
def login(body: LoginIn, request: Request, response: Response):
    c = C(request)
    if c.auth.disabled:
        return {"ok": True, "auth_disabled": True}
    token = c.auth.login(request.client.host if request.client else "?", body.password)
    if not token:
        return JSONResponse({"detail": "비밀번호가 맞지 않습니다."}, status_code=401)
    response.set_cookie(COOKIE, token, httponly=True, samesite="strict", secure=c.settings.cookie_secure, max_age=c.settings.session_max_age, path="/")
    return {"ok": True}


@router.post("/auth/logout")
def logout(response: Response):
    response.delete_cookie(COOKIE, path="/")
    return {"ok": True}


@router.get("/auth/me")
def me(request: Request):
    c = C(request)
    return {"authenticated": c.auth.check(request.cookies.get(COOKIE)), "auth_disabled": c.auth.disabled}


@router.get("/system")
def system(request: Request):
    c = C(request)
    return {
        "ai": c.provider.describe(),
        "mode_label": "AI 모드" if c.provider.is_real_ai else "샘플 모드(규칙 기반, AI 아님)",
        "app_env": c.settings.app_env,
        "auth_disabled": c.auth.disabled,
        "max_upload_mb": c.settings.max_upload_mb,
        "allowed_formats": sorted(dx.ALLOWED),
        "standards": c.registry.list(),
        "official_source_allowlist": c.settings.official_source_allowlist,
    }


@router.get("/standards/{sid}")
def get_standard(sid: str, request: Request):
    return C(request).registry.get(sid)


class CustomStdIn(BaseModel):
    base_id: str
    new_id: str
    title: str = ""
    overrides: dict[str, Any] = {}


@router.post("/standards/custom")
def custom_standard(body: CustomStdIn, request: Request):
    return C(request).registry.create_custom(body.base_id, body.new_id, body.title, body.overrides)


# ---------------------------------------------------------------- 프로젝트
class ProjectIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    overview: dict[str, Any] = {}
    sample: Literal["", "education", "complaint"] = ""


@router.get("/projects")
def list_projects(request: Request):
    return C(request).store.list()


@router.post("/projects")
def create_project(body: ProjectIn, request: Request):
    c = C(request)
    ov = dict(body.overview)
    name = body.name
    if body.sample:
        ov = {**samples.SAMPLES[body.sample]["overview"], **ov}
    p = c.store.create(name, ov)
    if body.sample:
        c.store.mutate(p.id, "sample", lambda p, m: samples.populate(p, m, body.sample))
    return ok_project(c, p.id)


@router.get("/projects/{pid}")
def get_project(pid: str, request: Request):
    return ok_project(C(request), pid)


class ProjectPatch(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=200)
    overview: dict[str, Any] | None = None
    version: int | None = None


@router.patch("/projects/{pid}")
def patch_project(pid: str, body: ProjectPatch, request: Request):
    c = C(request)

    def fn(p, m):
        if body.name is not None and body.name != p.name:
            m.log("project", pid, "rename", {"name": p.name}, {"name": body.name})
            p.name = body.name.strip()
        if body.overview is not None:
            before = p.overview.model_dump()
            new = Overview.model_validate({**before, **body.overview})
            changed = {k: v for k, v in new.model_dump().items() if before.get(k) != v}
            if changed:
                p.overview = new
                m.log("overview", pid, "update", {k: before[k] for k in changed}, changed, ["견적·과업 초안 갱신 여부 확인"] if p.estimates or p.task_draft.sections else [])

    c.store.mutate(pid, actor(c), fn, body.version)
    return ok_project(c, pid)


@router.delete("/projects/{pid}")
def delete_project(pid: str, confirm_name: str, request: Request):
    c = C(request)
    p, _ = c.store.get(pid)
    if confirm_name.strip() != p.name:
        raise InvalidData("확인용 프로젝트 이름이 일치하지 않아 삭제하지 않았습니다.")
    c.store.delete(pid)
    return {"deleted": pid}


@router.get("/projects/{pid}/changes")
def changes(pid: str, request: Request, limit: int = 300):
    c = C(request)
    c.store.get(pid)
    return c.store.changes(pid, min(limit, 5000))


class SnapIn(BaseModel):
    label: str = Field("", max_length=200)


@router.post("/projects/{pid}/snapshots")
def snapshot(pid: str, body: SnapIn, request: Request):
    return C(request).store.create_snapshot(pid, body.label or "설계 스냅샷")


@router.get("/projects/{pid}/snapshots")
def snapshots(pid: str, request: Request):
    return C(request).store.list_snapshots(pid)


@router.get("/projects/{pid}/snapshots/{sid}/diff")
def snapshot_diff(pid: str, sid: str, request: Request):
    c = C(request)
    old = c.store.get_snapshot(pid, sid)
    cur, _ = c.store.get(pid)
    return status.diff_projects(old, cur)


# ---------------------------------------------------------------- 항목 편집
class ItemIn(BaseModel):
    data: dict[str, Any]
    version: int | None = None


@router.post("/projects/{pid}/items/{collection}")
def create_item(pid: str, collection: str, body: ItemIn, request: Request):
    c = C(request)
    if collection not in COLLECTIONS:
        raise NotFound("알 수 없는 항목 종류")
    _, v, item = c.store.mutate(pid, actor(c), lambda p, m: add_item(p, m, collection, body.data, origin=body.data.get("origin") or "user"), body.version)
    return {"item": item.model_dump(), **ok_project(c, pid)}


@router.patch("/projects/{pid}/items/{collection}/{iid}")
def patch_item(pid: str, collection: str, iid: str, body: ItemIn, request: Request):
    c = C(request)
    if collection not in COLLECTIONS:
        raise NotFound("알 수 없는 항목 종류")
    if "origin" in body.data:
        raise InvalidData("제안 주체(origin)는 수정할 수 없습니다.")
    _, v, item = c.store.mutate(pid, actor(c), lambda p, m: update_item(p, m, collection, iid, body.data), body.version)
    return {"item": item.model_dump(), **ok_project(c, pid)}


@router.delete("/projects/{pid}/items/{collection}/{iid}")
def remove_item(pid: str, collection: str, iid: str, request: Request, version: int | None = None):
    c = C(request)
    if collection not in COLLECTIONS:
        raise NotFound("알 수 없는 항목 종류")
    c.store.mutate(pid, actor(c), lambda p, m: delete_item(p, m, collection, iid), version)
    return ok_project(c, pid)


# ---------------------------------------------------------------- FP·견적
@router.get("/projects/{pid}/fp")
def fp_summary(pid: str, request: Request):
    c = C(request)
    p, _ = c.store.get(pid)
    std = std_of(c, p)
    return {**engine.summary(p, std), "standard": {"id": std["id"], "title": std["title"], "official_guide_checked": std.get("official_guide_checked", False)}}


@router.put("/projects/{pid}/cost-settings")
def put_cost_settings(pid: str, body: dict[str, Any], request: Request):
    c = C(request)
    version = body.pop("version", None)

    def fn(p, m):
        before = p.cost_settings.model_dump()
        new = CostSettings.model_validate({**before, **body})
        c.registry.get(new.standard_id)
        p.cost_settings = new
        changed = {k: v for k, v in new.model_dump().items() if before.get(k) != v}
        if changed:
            m.log("cost_settings", pid, "update", {k: before[k] for k in changed}, changed, [e.id for e in p.estimates])

    c.store.mutate(pid, actor(c), fn, version)
    return ok_project(c, pid)


@router.get("/projects/{pid}/estimate-preview")
def estimate_preview(pid: str, request: Request):
    c = C(request)
    p, _ = c.store.get(pid)
    r = est.compute(p, std_of(c, p))
    r.pop("fp_snapshot", None)
    return r


class EstIn(BaseModel):
    label: str = Field("", max_length=200)


@router.post("/projects/{pid}/estimates")
def create_estimate(pid: str, body: EstIn, request: Request):
    c = C(request)
    _, _, e = c.store.mutate(pid, actor(c), lambda p, m: est.create_estimate(p, m, std_of(c, p), body.label, "ai" if c.provider.is_real_ai else "sample"))
    return {"estimate": e.model_dump(), **ok_project(c, pid)}


class ScenarioIn(BaseModel):
    target_amount: int = Field(gt=0, le=10**13)
    includes_vat: bool = True
    note: str = Field("", max_length=500)


@router.post("/projects/{pid}/estimates/{eid}/scenarios")
def create_scenario(pid: str, eid: str, body: ScenarioIn, request: Request):
    c = C(request)

    def fn(p, m):
        try:
            return est.add_scenario(p, m, eid, body.target_amount, body.includes_vat, body.note)
        except LookupError as e:
            raise NotFound(str(e)) from e

    _, _, sc = c.store.mutate(pid, actor(c), fn)
    return {"scenario": sc.model_dump(), **ok_project(c, pid)}


# ---------------------------------------------------------------- 과업지시서 초안
@router.post("/projects/{pid}/task-draft/generate")
def gen_task(pid: str, request: Request):
    c = C(request)

    def fn(p, m):
        p.task_draft = taskdraft.regenerate(p)
        m.log("task_draft", pid, "generate", None, {"sections": len(p.task_draft.sections)})

    c.store.mutate(pid, actor(c), fn)
    return ok_project(c, pid)


class TaskEditIn(BaseModel):
    text: str | None = Field(None, max_length=50000)
    accept_candidate: bool = False


@router.patch("/projects/{pid}/task-draft/{key}")
def edit_task(pid: str, key: str, body: TaskEditIn, request: Request):
    c = C(request)

    def fn(p, m):
        s = next((x for x in p.task_draft.sections if x.key == key), None)
        if not s:
            raise NotFound("과업 초안 항목 없음")
        before = s.text
        if body.accept_candidate and s.regenerated_candidate:
            s.text, s.regenerated_candidate, s.user_edited = s.regenerated_candidate, "", False
        elif body.text is not None:
            s.text, s.user_edited = body.text, True
        m.log("task_draft", key, "update", {"text": before}, {"text": s.text})

    c.store.mutate(pid, actor(c), fn)
    return ok_project(c, pid)


# ---------------------------------------------------------------- AI·작업
class AIIn(BaseModel):
    feature_text: str = Field("", max_length=50000)
    consent: bool = False
    force: bool = False


AI_TASKS = {"questions", "requirements", "design", "fp_candidates"}


@router.get("/projects/{pid}/ai/transmission-preview")
def transmission_preview(pid: str, request: Request):
    from .ai.tasks import project_brief

    c = C(request)
    p, _ = c.store.get(pid)
    return {
        "external": c.provider.external,
        "provider": c.provider.describe(),
        "explanation": ("AI 모드에서는 아래 프로젝트 요약(사업 개요·요구사항·질문 답변·기능·데이터·연계 목록)이 외부 AI 서비스로 전송됩니다. 첨부 원문은 문서별로 따로 동의해야 전송됩니다."
                        if c.provider.external else "샘플 모드: 외부로 전송되는 데이터가 없습니다(서버 안의 규칙으로 처리)."),
        "payload": project_brief(p),
    }


@router.post("/projects/{pid}/ai/{task}")
def run_ai(pid: str, task: str, body: AIIn, request: Request):
    c = C(request)
    if task not in AI_TASKS:
        raise NotFound("알 수 없는 작업")
    if c.provider.external and not body.consent:
        raise InvalidData("외부 AI 전송 동의가 필요합니다. 전송 범위를 확인한 뒤 동의하세요.")
    p, v = c.store.get(pid)
    params = {"feature_text": body.feature_text} if task == "requirements" else {}
    data_hash = hashlib.sha256(p.model_dump_json(exclude={"proposals", "updated_at"}).encode()).hexdigest()[:16]
    job, started = c.jobs.submit(task, pid, params, data_hash, force=body.force)
    return {"job": job, "started": started, "reused": not started}


@router.get("/projects/{pid}/jobs")
def project_jobs(pid: str, request: Request):
    return C(request).jobs.list(pid)


@router.get("/jobs/{jid}")
def get_job(jid: str, request: Request):
    j = C(request).jobs.get(jid)
    if not j:
        raise NotFound("작업 없음")
    return j


@router.post("/jobs/{jid}/retry")
def retry_job(jid: str, request: Request):
    try:
        return C(request).jobs.retry(jid)
    except LookupError as e:
        raise NotFound(str(e)) from e
    except ValueError as e:
        raise InvalidData(str(e)) from e


class AnswerIn(BaseModel):
    kind: Literal["choice", "text", "unknown", "defer"]
    value: str = Field("", max_length=2000)


@router.post("/projects/{pid}/questions/{qid}/answer")
def answer(pid: str, qid: str, body: AnswerIn, request: Request):
    c = C(request)
    _, _, r = c.store.mutate(pid, actor(c), lambda p, m: proposals.answer_question(p, m, qid, body.kind, body.value, "ai" if c.provider.is_real_ai else "sample"))
    return {"result": r, **ok_project(c, pid)}


class KeysIn(BaseModel):
    keys: list[str] | None = None
    force: bool = False


@router.post("/projects/{pid}/proposals/{prid}/apply")
def apply_prop(pid: str, prid: str, body: KeysIn, request: Request):
    c = C(request)
    _, _, r = c.store.mutate(pid, actor(c), lambda p, m: proposals.apply_proposal(p, m, prid, body.keys, body.force))
    return {"result": r, **ok_project(c, pid)}


@router.post("/projects/{pid}/proposals/{prid}/reject")
def reject_prop(pid: str, prid: str, body: KeysIn, request: Request):
    c = C(request)
    _, _, r = c.store.mutate(pid, actor(c), lambda p, m: proposals.reject_proposal(p, m, prid, body.keys))
    return {"result": r, **ok_project(c, pid)}


# ---------------------------------------------------------------- 문서
@router.post("/projects/{pid}/documents")
async def upload(pid: str, request: Request, file: UploadFile = File(...), kind: str = Form("reference")):
    c = C(request)
    c.store.get(pid)
    if kind not in ("reference", "vendor_task", "vendor_design", "vendor_fp", "vendor_cost", "other"):
        raise InvalidData("문서 종류 오류")
    limit = c.settings.max_upload_mb * 1024 * 1024
    data = await file.read(limit + 1)
    name = dx.safe_filename(file.filename or "upload")
    ext = dx.check_upload(name, data, limit, c.settings.max_uncompressed_mb * 1024 * 1024)
    ex = dx.extract(ext, data)
    chunks = dx.chunk(ex.segments)
    sha = hashlib.sha256(data).hexdigest()

    def fn(p, m):
        did = next_id(p, "DOC")
        stored = f"{did}.{ext}"
        d = c.store.project_dir(pid) / "files"
        d.mkdir(parents=True, exist_ok=True)
        target = (d / stored).resolve()
        if d.resolve() not in target.parents:
            raise InvalidData("저장 경로 오류")
        target.write_bytes(data)
        doc = DocumentMeta(id=did, file_name=name, stored_name=stored, kind=kind, format=ext, size=len(data), sha256=sha, uploaded_at=now(),
                           extraction=Extraction(status=ex.status, quality=ex.quality, messages=ex.messages, pages=ex.pages, chars=ex.chars, chunks_total=len(chunks)))
        p.documents.append(doc)
        m.log("documents", did, "upload", None, {"file_name": name, "kind": kind, "status": ex.status, "chunks": len(chunks)})
        return doc

    _, _, doc = c.store.mutate(pid, actor(c), fn)
    with c.db.tx() as conn:
        for i, (loc, text) in enumerate(chunks):
            conn.execute("INSERT INTO doc_chunks(project_id,document_id,seq,location,text,analyzed) VALUES(?,?,?,?,?,0)", (pid, doc.id, i, loc, text))
    return {"document": doc.model_dump(), **ok_project(c, pid)}


def doc_path(c: AppCtx, pid: str, d: DocumentMeta):
    """문서 원본 경로. 프로젝트 files 디렉터리 밖이면 거부한다."""
    base = (c.store.project_dir(pid) / "files").resolve()
    f = (base / d.stored_name).resolve()
    if not d.stored_name or base not in f.parents:
        raise NotFound("원본 파일 경로가 올바르지 않습니다.")
    return f


def _doc(p, did: str) -> DocumentMeta:
    d = next((x for x in p.documents if x.id == did), None)
    if not d:
        raise NotFound("문서 없음")
    return d


@router.get("/projects/{pid}/documents/{did}/download")
def download_doc(pid: str, did: str, request: Request):
    c = C(request)
    p, _ = c.store.get(pid)
    d = _doc(p, did)
    f = doc_path(c, pid, d)
    if not f.is_file():
        raise NotFound("원본 파일이 없습니다(백업 복원본은 원본을 포함하지 않음).")
    return Response(f.read_bytes(), media_type="application/octet-stream", headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(d.file_name)}"})


@router.get("/projects/{pid}/documents/{did}/chunks")
def doc_chunks(pid: str, did: str, request: Request, offset: int = 0, limit: int = 20):
    c = C(request)
    p, _ = c.store.get(pid)
    _doc(p, did)
    rows = c.db.query("SELECT seq,location,text,analyzed FROM doc_chunks WHERE project_id=? AND document_id=? ORDER BY seq LIMIT ? OFFSET ?", (pid, did, min(limit, 100), max(offset, 0)))
    return [dict(r) for r in rows]


class ConsentIn(BaseModel):
    consent: bool


@router.post("/projects/{pid}/documents/{did}/consent")
def doc_consent(pid: str, did: str, body: ConsentIn, request: Request):
    c = C(request)

    def fn(p, m):
        d = _doc(p, did)
        m.log("documents", did, "consent", {"ai_consent": d.ai_consent}, {"ai_consent": body.consent})
        d.ai_consent = body.consent

    c.store.mutate(pid, actor(c), fn)
    return ok_project(c, pid)


class AnalyzeIn(BaseModel):
    force: bool = False


@router.post("/projects/{pid}/documents/{did}/analyze")
def analyze_doc(pid: str, did: str, body: AnalyzeIn, request: Request):
    c = C(request)
    p, _ = c.store.get(pid)
    d = _doc(p, did)
    left = c.db.one("SELECT COUNT(*) AS n FROM doc_chunks WHERE project_id=? AND document_id=? AND analyzed=0", (pid, did))["n"]
    job, started = c.jobs.submit("doc_analysis", pid, {"document_id": did}, f"{d.sha256}:{left}", force=body.force)
    return {"job": job, "started": started, "reused": not started}


@router.delete("/projects/{pid}/documents/{did}")
def delete_doc(pid: str, did: str, request: Request):
    c = C(request)

    def fn(p, m):
        d = _doc(p, did)
        p.documents = [x for x in p.documents if x.id != did]
        m.log("documents", did, "delete", {"file_name": d.file_name}, None)
        return d

    f = doc_path(c, pid, _doc(c.store.get(pid)[0], did))
    _, _, d = c.store.mutate(pid, actor(c), fn)
    if f.is_file():
        f.unlink()
    c.db.execute("DELETE FROM doc_chunks WHERE project_id=? AND document_id=?", (pid, did))
    return ok_project(c, pid)


class DecideIn(BaseModel):
    decision: Literal["keep", "modify", "exclude", "pending"]
    modified_text: str = Field("", max_length=5000)
    reason: str = Field("", max_length=2000)


@router.post("/projects/{pid}/reference-items/{rid}/decide")
def decide_ref(pid: str, rid: str, body: DecideIn, request: Request):
    """유지/수정 → 요구사항(초안)으로 반영하고 원문 출처를 연결. 제외 → 사유 기록."""
    c = C(request)

    def fn(p, m):
        ref: ReferenceItem = find_item(p, "reference_items", rid)
        if body.decision == "modify" and not body.modified_text.strip():
            raise InvalidData("수정 내용을 입력하세요.")
        if body.decision in ("modify", "exclude") and not body.reason.strip():
            raise InvalidData("수정·제외 이유를 입력하세요(원문 대비 변경 내역에 남습니다).")
        before = ref.model_dump()
        ref.decision, ref.modified_text, ref.reason = body.decision, body.modified_text, body.reason
        if body.decision in ("keep", "modify") and not ref.applied_requirement_id:
            text = body.modified_text if body.decision == "modify" else ref.text
            kind = "functional" if ref.kind in ("requirement", "function", "interface", "data") else "nonfunctional"
            warn = (" ※ 타 기관 고유 조건 포함(" + ", ".join(ref.org_specific) + ") — 우리 사업 값으로 확인 필요") if ref.org_specific else ""
            r = add_item(p, m, "requirements", {"kind": kind, "category": "참고문서", "title": text[:60], "original_text": ref.text, "description": text, "source_ids": [ref.source_id] if ref.source_id else [], "why": f"참고문서 {ref.location} {'유지' if body.decision == 'keep' else '수정 반영'}{warn}", "note": body.reason, "status": "draft"}, origin="document")
            ref.applied_requirement_id = r.id
        elif body.decision in ("keep", "modify") and ref.applied_requirement_id and body.decision == "modify":
            update_item(p, m, "requirements", ref.applied_requirement_id, {"description": body.modified_text, "note": body.reason})
        m.log("reference_items", rid, "decide", {"decision": before["decision"]}, {"decision": body.decision, "reason": body.reason})

    c.store.mutate(pid, actor(c), fn)
    return ok_project(c, pid)


# ---------------------------------------------------------------- 검토
class ReviewIn(BaseModel):
    document_ids: list[str] = []


@router.post("/projects/{pid}/review/run")
def review(pid: str, body: ReviewIn, request: Request):
    c = C(request)
    p, _ = c.store.get(pid)
    docs = [d for d in p.documents if (not body.document_ids or d.id in body.document_ids)]
    chunks: dict[str, list[tuple[str, str]]] = {}
    files: dict[str, bytes] = {}
    for d in docs:
        chunks[d.id] = [(r["location"], r["text"]) for r in c.db.query("SELECT location,text FROM doc_chunks WHERE project_id=? AND document_id=? ORDER BY seq", (pid, d.id))]
        f = doc_path(c, pid, d)
        if f.is_file() and d.format in ("xlsx", "xlsm"):
            files[d.id] = f.read_bytes()
    findings = run_review(p, docs, chunks, files, std_of(c, p))

    def fn(p, m):
        from .models import ReviewFinding, ReviewRun

        before = len(p.reviews)
        p.reviews = []
        for f in findings:
            p.reviews.append(ReviewFinding(id=next_id(p, "RV"), **f))
        summ: dict[str, int] = {}
        for f in p.reviews:
            summ[f.verdict] = summ.get(f.verdict, 0) + 1
        p.review_run = ReviewRun(ran_at=now(), document_ids=[d.id for d in docs], mode="규칙 기반 대조(자료 일치 검토)", summary=summ)
        m.log("reviews", None, "run", {"count": before}, {"count": len(p.reviews), "summary": summ})

    c.store.mutate(pid, actor(c), fn)
    return ok_project(c, pid)


# ---------------------------------------------------------------- 기술 추천
@router.put("/projects/{pid}/tech/inputs")
def tech_inputs(pid: str, body: dict[str, Any], request: Request):
    c = C(request)

    def fn(p, m):
        before = p.tech.inputs.model_dump()
        p.tech.inputs = TechInputs.model_validate({**before, **body})
        m.log("tech", pid, "inputs", before, p.tech.inputs.model_dump())

    c.store.mutate(pid, actor(c), fn)
    return ok_project(c, pid)


@router.post("/projects/{pid}/tech/recommend")
def tech_recommend(pid: str, request: Request):
    c = C(request)

    def fn(p, m):
        recs, notes = trec.recommend(p)
        p.tech.recommendations = recs
        p.tech.ran_at = now()
        p.tech.mode = "규칙 기반 초안" + (" · 가정: " + "; ".join(notes) if notes else "")
        m.log("tech", pid, "recommend", None, {"count": len(recs)})

    c.store.mutate(pid, actor(c), fn)
    return ok_project(c, pid)


@router.post("/projects/{pid}/official-sources/suggested")
def add_suggested_sources(pid: str, request: Request):
    c = C(request)

    def fn(p, m):
        have = {s.url for s in p.official_sources}
        for s in trec.suggested_sources():
            if s.url not in have:
                add_item(p, m, "official_sources", s.model_dump(exclude={"id"}), origin=None)

    c.store.mutate(pid, actor(c), fn)
    return ok_project(c, pid)


@router.post("/projects/{pid}/official-sources/{sid}/fetch")
def fetch_source(pid: str, sid: str, request: Request):
    c = C(request)
    p, _ = c.store.get(pid)
    src = find_item(p, "official_sources", sid)
    info = tfetch.fetch_title(src.url, c.settings.official_source_allowlist)

    def fn(p, m):
        update_item(p, m, "official_sources", sid, {"checked_at": now()[:10], "status": "fetched", "note": (src.note + f" | 서버 조회 성공: 제목 '{info['title']}' — 버전·지원 상태는 사용자가 확인해 입력").strip(" |")})

    c.store.mutate(pid, actor(c), fn)
    return {"fetched": info, **ok_project(c, pid)}


# ---------------------------------------------------------------- 엑셀·백업
def _workbook(c: AppCtx, pid: str, estimate_id: str | None):
    p, _ = c.store.get(pid)
    if estimate_id and not any(e.id == estimate_id for e in p.estimates):
        raise NotFound("견적 버전 없음")
    return xl.build_workbook(p, std_of(c, p), c.store.changes(pid, 1000), "AI 모드" if c.provider.is_real_ai else "샘플 모드(규칙 기반, AI 아님)", estimate_id), p


@router.get("/projects/{pid}/export.xlsx")
def export_xlsx(pid: str, request: Request, estimate_id: str | None = None):
    c = C(request)
    (wb, meta), p = _workbook(c, pid, estimate_id)
    data = xl.to_bytes(wb)
    fname = f"{p.name}_설계산출물_{now()[:10]}.xlsx"
    return Response(data, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(fname)}"})


@router.get("/projects/{pid}/export/preview")
def export_preview(pid: str, request: Request, estimate_id: str | None = None):
    c = C(request)
    (wb, meta), _ = _workbook(c, pid, estimate_id)
    return {"sheets": xl.preview(wb), "meta": {"estimate_id": meta["estimate_id"], "fp_summary": meta["fp_summary"]}}


@router.get("/projects/{pid}/backup.json")
def export_backup(pid: str, request: Request):
    c = C(request)
    data = backup.export_project(c.store, pid)
    fname = f"{data['project']['name']}_백업_{now()[:10]}.json"
    return Response(json.dumps(data, ensure_ascii=False), media_type="application/json", headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(fname)}"})


@router.post("/projects/restore")
async def restore(request: Request, file: UploadFile = File(...)):
    c = C(request)
    raw = await file.read(backup.MAX_BYTES + 1)
    p = backup.restore_project(c.store, raw)
    return ok_project(c, p.id)
