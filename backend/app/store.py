"""프로젝트 저장·항목 편집·변경 이력·영향 표시·스냅샷."""
from __future__ import annotations

import hashlib
import json
import secrets
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

from pydantic import ValidationError

from .db import Database
from .models import COLLECTIONS, DEPENDENTS, LABELS, LINK_FIELDS, Project

KST = timezone(timedelta(hours=9))

# 의미가 바뀌는 필드(이 필드가 바뀌면 종속 항목을 '갱신 필요'로 표시)
NON_SEMANTIC = {"note", "needs_review", "review_reason", "status"}


def now() -> str:
    return datetime.now(KST).isoformat(timespec="seconds")


class NotFound(LookupError):
    pass


class Conflict(RuntimeError):
    pass


class InvalidData(ValueError):
    pass


def stable_hash(obj: Any) -> str:
    return hashlib.sha256(json.dumps(obj, ensure_ascii=False, sort_keys=True, default=str).encode()).hexdigest()[:16]


def next_id(p: Project, prefix: str) -> str:
    n = p.counters.get(prefix, 0) + 1
    p.counters[prefix] = n
    return f"{prefix}-{n:03d}"


def get_collection(p: Project, collection: str) -> list:
    if collection not in COLLECTIONS:
        raise NotFound(f"알 수 없는 항목 종류: {collection}")
    return getattr(p, collection)


def find_item(p: Project, collection: str, item_id: str):
    for it in get_collection(p, collection):
        if it.id == item_id:
            return it
    raise NotFound(f"{LABELS.get(collection, collection)} {item_id} 없음")


def all_ids(p: Project, collection: str) -> set[str]:
    return {it.id for it in getattr(p, collection)}


def check_links(p: Project, data: dict[str, Any]) -> None:
    for field, target in LINK_FIELDS.items():
        if field in data:
            known = all_ids(p, target)
            bad = [x for x in data[field] if x not in known]
            if bad:
                raise InvalidData(f"존재하지 않는 {LABELS[target]} ID: {', '.join(bad)}")


class Mutation:
    """한 번의 저장 단위에서 발생한 변경 기록."""

    def __init__(self, actor: str):
        self.actor = actor
        self.entries: list[dict[str, Any]] = []

    def log(self, collection: str, item_id: str | None, op: str, before: Any, after: Any, affected: list[str] | None = None, needs_review: bool = False):
        self.entries.append(
            {
                "collection": collection,
                "item_id": item_id,
                "op": op,
                "before": before,
                "after": after,
                "affected": affected or [],
                "needs_review": needs_review,
            }
        )


def mark_dependents(p: Project, collection: str, item_id: str, reason: str) -> list[str]:
    affected = []
    for dep_coll, field in DEPENDENTS.get(collection, []):
        for it in getattr(p, dep_coll):
            if item_id in getattr(it, field, []):
                it.needs_review = True
                it.review_reason = reason
                affected.append(it.id)
    return affected


class ProjectStore:
    def __init__(self, db: Database, data_dir: Path):
        self.db = db
        self.data_dir = data_dir
        (data_dir / "projects").mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------ 파일 경로
    def project_dir(self, pid: str) -> Path:
        if not pid.startswith("P") or not pid[1:].isalnum():
            raise NotFound("잘못된 프로젝트 ID")
        d = (self.data_dir / "projects" / pid).resolve()
        if (self.data_dir / "projects").resolve() not in d.parents:
            raise NotFound("잘못된 경로")
        return d

    # ------------------------------------------------------------ 프로젝트
    def create(self, name: str, overview: dict[str, Any] | None = None, actor: str = "user") -> Project:
        name = (name or "").strip()
        if not name or len(name) > 200:
            raise InvalidData("프로젝트 이름은 1~200자여야 합니다.")
        pid = "P" + secrets.token_hex(6)
        ts = now()
        try:
            p = Project(id=pid, name=name, created_at=ts, updated_at=ts, overview=overview or {})
        except ValidationError as e:
            raise InvalidData(str(e)) from e
        with self.db.tx() as c:
            c.execute(
                "INSERT INTO projects(id,name,data,version,created_at,updated_at) VALUES(?,?,?,?,?,?)",
                (pid, name, p.model_dump_json(), 1, ts, ts),
            )
            self._log(c, pid, actor, [{"collection": "project", "item_id": pid, "op": "create", "before": None, "after": {"name": name}, "affected": [], "needs_review": False}])
        self.project_dir(pid).mkdir(parents=True, exist_ok=True)
        return p

    def list(self) -> list[dict[str, Any]]:
        rows = self.db.query("SELECT id,name,version,created_at,updated_at,data FROM projects ORDER BY updated_at DESC")
        out = []
        for r in rows:
            d = json.loads(r["data"])
            ov = d.get("overview", {})
            out.append(
                {
                    "id": r["id"],
                    "name": r["name"],
                    "version": r["version"],
                    "created_at": r["created_at"],
                    "updated_at": r["updated_at"],
                    "business_type": ov.get("business_type"),
                    "start_mode": ov.get("start_mode"),
                    "budget_mode": ov.get("budget_mode"),
                    "requirements": len(d.get("requirements", [])),
                    "fp_items": len(d.get("fp_items", [])),
                    "estimates": len(d.get("estimates", [])),
                }
            )
        return out

    def get(self, pid: str) -> tuple[Project, int]:
        r = self.db.one("SELECT data,version FROM projects WHERE id=?", (pid,))
        if not r:
            raise NotFound("프로젝트를 찾을 수 없습니다.")
        return Project.model_validate_json(r["data"]), r["version"]

    def mutate(self, pid: str, actor: str, fn: Callable[[Project, Mutation], Any], expected_version: int | None = None) -> tuple[Project, int, Any]:
        """프로젝트를 읽어 fn으로 수정한 뒤 검증·저장한다. 실패하면 아무것도 바뀌지 않는다."""
        with self.db.tx() as c:
            r = c.execute("SELECT data,version FROM projects WHERE id=?", (pid,)).fetchone()
            if not r:
                raise NotFound("프로젝트를 찾을 수 없습니다.")
            version = r["version"]
            if expected_version is not None and expected_version != version:
                raise Conflict(f"다른 곳에서 먼저 저장되었습니다(현재 버전 {version}). 새로고침 후 다시 시도하세요.")
            p = Project.model_validate_json(r["data"])
            m = Mutation(actor)
            try:
                ret = fn(p, m)
                p = Project.model_validate(p.model_dump())  # 전체 재검증
            except ValidationError as e:
                raise InvalidData(_validation_msg(e)) from e
            p.updated_at = now()
            nv = version + 1
            c.execute("UPDATE projects SET name=?, data=?, version=?, updated_at=? WHERE id=?", (p.name, p.model_dump_json(), nv, p.updated_at, pid))
            self._log(c, pid, actor, m.entries)
        return p, nv, ret

    def delete(self, pid: str) -> None:
        d = self.project_dir(pid)
        with self.db.tx() as c:
            cur = c.execute("DELETE FROM projects WHERE id=?", (pid,))
            if cur.rowcount == 0:
                raise NotFound("프로젝트를 찾을 수 없습니다.")
            c.execute("DELETE FROM change_log WHERE project_id=?", (pid,))
            c.execute("DELETE FROM snapshots WHERE project_id=?", (pid,))
            c.execute("DELETE FROM doc_chunks WHERE project_id=?", (pid,))
            c.execute("DELETE FROM jobs WHERE project_id=?", (pid,))
        if d.exists():
            shutil.rmtree(d)

    # ------------------------------------------------------------ 변경 이력
    def _log(self, c, pid: str, actor: str, entries: list[dict[str, Any]]) -> None:
        ts = now()
        for e in entries:
            c.execute(
                "INSERT INTO change_log(project_id,at,actor,collection,item_id,op,before_json,after_json,affected,needs_review) VALUES(?,?,?,?,?,?,?,?,?,?)",
                (
                    pid,
                    ts,
                    actor,
                    e["collection"],
                    e["item_id"],
                    e["op"],
                    json.dumps(e["before"], ensure_ascii=False, default=str) if e["before"] is not None else None,
                    json.dumps(e["after"], ensure_ascii=False, default=str) if e["after"] is not None else None,
                    json.dumps(e["affected"], ensure_ascii=False),
                    1 if e["needs_review"] else 0,
                ),
            )

    def changes(self, pid: str, limit: int = 500) -> list[dict[str, Any]]:
        rows = self.db.query("SELECT * FROM change_log WHERE project_id=? ORDER BY seq DESC LIMIT ?", (pid, limit))
        return [
            {
                "seq": r["seq"],
                "at": r["at"],
                "actor": r["actor"],
                "collection": r["collection"],
                "item_id": r["item_id"],
                "op": r["op"],
                "before": json.loads(r["before_json"]) if r["before_json"] else None,
                "after": json.loads(r["after_json"]) if r["after_json"] else None,
                "affected": json.loads(r["affected"] or "[]"),
                "needs_review": bool(r["needs_review"]),
            }
            for r in rows
        ]

    # ------------------------------------------------------------ 스냅샷
    def create_snapshot(self, pid: str, label: str) -> dict[str, Any]:
        p, v = self.get(pid)
        sid = "SNAP-" + secrets.token_hex(4)
        ts = now()
        self.db.execute("INSERT INTO snapshots(id,project_id,label,created_at,data) VALUES(?,?,?,?,?)", (sid, pid, (label or "설계 스냅샷")[:200], ts, p.model_dump_json()))
        return {"id": sid, "label": label, "created_at": ts, "project_version": v}

    def list_snapshots(self, pid: str) -> list[dict[str, Any]]:
        return [dict(id=r["id"], label=r["label"], created_at=r["created_at"]) for r in self.db.query("SELECT id,label,created_at FROM snapshots WHERE project_id=? ORDER BY created_at DESC", (pid,))]

    def get_snapshot(self, pid: str, sid: str) -> Project:
        r = self.db.one("SELECT data FROM snapshots WHERE project_id=? AND id=?", (pid, sid))
        if not r:
            raise NotFound("스냅샷 없음")
        return Project.model_validate_json(r["data"])


def _validation_msg(e: ValidationError) -> str:
    parts = []
    for err in e.errors()[:5]:
        loc = ".".join(str(x) for x in err["loc"])
        parts.append(f"{loc}: {err['msg']}")
    return "입력값 오류 — " + "; ".join(parts)


# ---------------------------------------------------------------- 항목 편집 (mutate 콜백 안에서 사용)
def add_item(p: Project, m: Mutation, collection: str, data: dict[str, Any], origin: str | None = None) -> Any:
    model, prefix = COLLECTIONS[collection]
    data = {k: v for k, v in data.items() if k != "id"}
    if origin and "origin" in model.model_fields:
        data["origin"] = origin
    check_links(p, data)
    try:
        item = model.model_validate({**data, "id": "TMP"})
    except ValidationError as e:
        raise InvalidData(_validation_msg(e)) from e
    item.id = next_id(p, prefix)
    get_collection(p, collection).append(item)
    m.log(collection, item.id, "add", None, item.model_dump())
    return item


def update_item(p: Project, m: Mutation, collection: str, item_id: str, patch: dict[str, Any]) -> Any:
    model, _ = COLLECTIONS[collection]
    items = get_collection(p, collection)
    idx = next((i for i, it in enumerate(items) if it.id == item_id), None)
    if idx is None:
        raise NotFound(f"{LABELS[collection]} {item_id} 없음")
    before = items[idx].model_dump()
    patch = {k: v for k, v in patch.items() if k != "id"}
    check_links(p, patch)
    try:
        new = model.model_validate({**before, **patch})
    except ValidationError as e:
        raise InvalidData(_validation_msg(e)) from e
    after = new.model_dump()
    changed = {k for k in after if after[k] != before.get(k)}
    if not changed:
        return items[idx]
    items[idx] = new
    affected: list[str] = []
    if changed - NON_SEMANTIC:
        reason = f"{item_id} 변경({', '.join(sorted(changed - NON_SEMANTIC))}) — 연결 내용 재검토 필요"
        affected = mark_dependents(p, collection, item_id, reason)
    if collection in ("fp_items",) or "fp_items" in [d for d, _ in DEPENDENTS.get(collection, [])]:
        affected += [f"{e.id}(견적 갱신 필요 여부 확인)" for e in p.estimates]
    m.log(collection, item_id, "update", {k: before.get(k) for k in changed}, {k: after[k] for k in changed}, affected, bool(affected))
    return new


def delete_item(p: Project, m: Mutation, collection: str, item_id: str) -> None:
    items = get_collection(p, collection)
    idx = next((i for i, it in enumerate(items) if it.id == item_id), None)
    if idx is None:
        raise NotFound(f"{LABELS[collection]} {item_id} 없음")
    before = items[idx].model_dump()
    del items[idx]
    affected = []
    # 다른 항목의 링크에서 제거하고 재검토 표시
    for field, target in LINK_FIELDS.items():
        if target != collection:
            continue
        for coll in COLLECTIONS:
            for it in getattr(p, coll):
                links = getattr(it, field, None)
                if isinstance(links, list) and item_id in links:
                    setattr(it, field, [x for x in links if x != item_id])
                    it.needs_review = True
                    it.review_reason = f"연결된 {LABELS[collection]} {item_id} 삭제됨"
                    affected.append(it.id)
    m.log(collection, item_id, "delete", before, None, affected, bool(affected))
