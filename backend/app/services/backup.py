"""프로젝트 JSON 백업·복원. 복원 파일은 형식·체크섬·스키마·ID 연결을 검증하고 새 프로젝트로 만든다."""
from __future__ import annotations

import hashlib
import json
import secrets
from typing import Any

from pydantic import ValidationError

from ..models import COLLECTIONS, LINK_FIELDS, Project
from ..store import InvalidData, ProjectStore, now

FORMAT = "swd-project-backup"
VERSION = 1
MAX_BYTES = 50 * 1024 * 1024


def _digest(obj: Any) -> str:
    return hashlib.sha256(json.dumps(obj, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def export_project(store: ProjectStore, pid: str) -> dict[str, Any]:
    p, version = store.get(pid)
    project = json.loads(p.model_dump_json())
    chunks = [dict(document_id=r["document_id"], seq=r["seq"], location=r["location"], text=r["text"], analyzed=r["analyzed"]) for r in store.db.query("SELECT * FROM doc_chunks WHERE project_id=? ORDER BY document_id, seq", (pid,))]
    snaps = [dict(id=r["id"], label=r["label"], created_at=r["created_at"], data=json.loads(r["data"])) for r in store.db.query("SELECT * FROM snapshots WHERE project_id=?", (pid,))]
    body = {"project": project, "changes": store.changes(pid, limit=100000), "snapshots": snaps, "doc_chunks": chunks}
    return {
        "format": FORMAT,
        "version": VERSION,
        "exported_at": now(),
        "project_version": version,
        "note": "첨부 원본 파일은 포함하지 않습니다(추출 텍스트·메타데이터만 포함).",
        "sha256": _digest(body),
        **body,
    }


def validate_links(p: Project) -> list[str]:
    errs = []
    ids = {c: {it.id for it in getattr(p, c)} for c in COLLECTIONS}
    for c in COLLECTIONS:
        seen = set()
        for it in getattr(p, c):
            if it.id in seen:
                errs.append(f"{c}: 중복 ID {it.id}")
            seen.add(it.id)
            for f, target in LINK_FIELDS.items():
                for x in getattr(it, f, []) or []:
                    if x not in ids[target]:
                        errs.append(f"{it.id}.{f}: 없는 ID {x}")
    return errs


def restore_project(store: ProjectStore, raw: bytes) -> Project:
    if len(raw) > MAX_BYTES:
        raise InvalidData("백업 파일이 너무 큽니다(50MB 초과).")
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        raise InvalidData("백업 파일이 올바른 JSON이 아닙니다.") from e
    if not isinstance(data, dict) or data.get("format") != FORMAT:
        raise InvalidData("정보화 설계 도우미 백업 파일이 아닙니다.")
    if data.get("version") != VERSION:
        raise InvalidData(f"지원하지 않는 백업 버전: {data.get('version')}")
    body = {k: data.get(k) for k in ("project", "changes", "snapshots", "doc_chunks")}
    if _digest(body) != data.get("sha256"):
        raise InvalidData("백업 파일 체크섬이 맞지 않습니다(파일이 손상되었거나 수정됨).")
    try:
        p = Project.model_validate(body["project"])
    except ValidationError as e:
        raise InvalidData(f"백업 프로젝트 데이터 형식 오류: {e.errors()[0]['loc']} {e.errors()[0]['msg']}") from e
    errs = validate_links(p)
    if errs:
        raise InvalidData("백업 데이터의 ID 연결 오류: " + "; ".join(errs[:5]))
    old_id = p.id
    p.id = "P" + secrets.token_hex(6)
    p.name = (p.name + " (복원)")[:200]
    ts = now()
    p.updated_at = ts
    with store.db.tx() as c:
        c.execute("INSERT INTO projects(id,name,data,version,created_at,updated_at) VALUES(?,?,?,?,?,?)", (p.id, p.name, p.model_dump_json(), 1, p.created_at or ts, ts))
        for ch in body.get("doc_chunks") or []:
            c.execute("INSERT INTO doc_chunks(project_id,document_id,seq,location,text,analyzed) VALUES(?,?,?,?,?,?)", (p.id, str(ch["document_id"]), int(ch["seq"]), str(ch["location"]), str(ch["text"]), int(ch.get("analyzed", 0))))
        for s in body.get("snapshots") or []:
            Project.model_validate(s["data"])
            c.execute("INSERT INTO snapshots(id,project_id,label,created_at,data) VALUES(?,?,?,?,?)", ("SNAP-" + secrets.token_hex(4), p.id, str(s["label"])[:200], str(s["created_at"]), json.dumps(s["data"], ensure_ascii=False)))
        for ch in reversed(body.get("changes") or []):
            c.execute(
                "INSERT INTO change_log(project_id,at,actor,collection,item_id,op,before_json,after_json,affected,needs_review) VALUES(?,?,?,?,?,?,?,?,?,?)",
                (p.id, str(ch["at"]), str(ch["actor"]), str(ch["collection"]), ch.get("item_id"), str(ch["op"]), json.dumps(ch.get("before"), ensure_ascii=False) if ch.get("before") is not None else None, json.dumps(ch.get("after"), ensure_ascii=False) if ch.get("after") is not None else None, json.dumps(ch.get("affected", []), ensure_ascii=False), 1 if ch.get("needs_review") else 0),
            )
        c.execute("INSERT INTO change_log(project_id,at,actor,collection,item_id,op,before_json,after_json,affected,needs_review) VALUES(?,?,?,?,?,?,?,?,?,?)", (p.id, ts, "user", "project", p.id, "restore", None, json.dumps({"from_project": old_id}), "[]", 0))
    store.project_dir(p.id).mkdir(parents=True, exist_ok=True)
    return p
