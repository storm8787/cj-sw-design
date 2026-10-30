"""긴 작업(AI·문서 분석) 실행기.

- 같은 입력(kind+project+params+데이터 해시)의 작업이 진행 중이거나 이미 성공했으면 새로 실행하지 않고 재사용 → 중복 클릭 비용 방지.
- 서버 기동 시 running/queued 상태는 interrupted로 표시해 사용자가 재시도할 수 있게 한다.
- 실패해도 프로젝트 데이터는 바뀌지 않는다(적용은 별도 단계).
"""
from __future__ import annotations

import json
import logging
import secrets
import threading
import traceback
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable

from .db import Database
from .store import now, stable_hash

log = logging.getLogger("swd.jobs")


class JobContext:
    def __init__(self, runner: "JobRunner", job_id: str):
        self.runner = runner
        self.job_id = job_id

    def progress(self, value: float, message: str = "") -> None:
        self.runner._update(self.job_id, progress=max(0.0, min(1.0, value)), message=message)


class UserFacingError(RuntimeError):
    """사용자에게 그대로 보여줄 수 있는 실패 이유."""


class JobRunner:
    def __init__(self, db: Database, workers: int = 2, synchronous: bool = False):
        self.db = db
        self.synchronous = synchronous
        self.pool = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="swd-job")
        self.handlers: dict[str, Callable[[JobContext, dict[str, Any]], Any]] = {}
        self._lock = threading.Lock()
        n = self.db.query("SELECT COUNT(*) AS n FROM jobs WHERE status IN ('running','queued')")[0]["n"]
        if n:
            self.db.execute("UPDATE jobs SET status='interrupted', message='서버 재시작으로 중단됨 — 재시도 가능', updated_at=? WHERE status IN ('running','queued')", (now(),))
            log.info("marked %s jobs interrupted", n)

    def register(self, kind: str, fn: Callable[[JobContext, dict[str, Any]], Any]) -> None:
        self.handlers[kind] = fn

    def _update(self, job_id: str, **fields: Any) -> None:
        sets = ", ".join(f"{k}=?" for k in fields) + ", updated_at=?"
        self.db.execute(f"UPDATE jobs SET {sets} WHERE id=?", (*fields.values(), now(), job_id))

    def get(self, job_id: str) -> dict[str, Any] | None:
        r = self.db.one("SELECT * FROM jobs WHERE id=?", (job_id,))
        return _row(r) if r else None

    def list(self, project_id: str, limit: int = 50) -> list[dict[str, Any]]:
        return [_row(r) for r in self.db.query("SELECT * FROM jobs WHERE project_id=? ORDER BY created_at DESC LIMIT ?", (project_id, limit))]

    def submit(self, kind: str, project_id: str | None, params: dict[str, Any], data_hash: str = "", force: bool = False) -> tuple[dict[str, Any], bool]:
        """반환: (작업, 새로 시작했는지)."""
        if kind not in self.handlers:
            raise ValueError(f"알 수 없는 작업: {kind}")
        h = stable_hash({"kind": kind, "project": project_id, "params": params, "data": data_hash})
        with self._lock:
            if not force:
                r = self.db.one("SELECT * FROM jobs WHERE input_hash=? AND status IN ('queued','running','succeeded') ORDER BY created_at DESC LIMIT 1", (h,))
                if r:
                    return _row(r), False
            jid = "JOB-" + secrets.token_hex(5)
            ts = now()
            self.db.execute(
                "INSERT INTO jobs(id,project_id,kind,input_hash,status,progress,message,params,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
                (jid, project_id, kind, h, "queued", 0, "대기 중", json.dumps(params, ensure_ascii=False), ts, ts),
            )
        self._start(jid)
        return self.get(jid), True

    def retry(self, job_id: str) -> dict[str, Any]:
        j = self.get(job_id)
        if not j:
            raise LookupError("작업 없음")
        if j["status"] not in ("failed", "interrupted"):
            raise ValueError("실패했거나 중단된 작업만 재시도할 수 있습니다.")
        self._update(job_id, status="queued", progress=0, message="재시도 대기", error=None)
        self._start(job_id)
        return self.get(job_id)

    def _start(self, job_id: str) -> None:
        if self.synchronous:
            self._run(job_id)
        else:
            self.pool.submit(self._run, job_id)

    def _run(self, job_id: str) -> None:
        j = self.get(job_id)
        if not j:
            return
        fn = self.handlers[j["kind"]]
        self.db.execute("UPDATE jobs SET status='running', attempts=attempts+1, message='실행 중', updated_at=? WHERE id=?", (now(), job_id))
        from .ai import usage

        with usage.collect() as calls:  # 성공·실패 모두 AI 사용량(토큰 수만)을 작업에 남긴다
            try:
                result = fn(JobContext(self, job_id), {**j["params"], "_kind": j["kind"], "_project_id": j["project_id"], "_job_id": job_id})
                self._update(job_id, status="succeeded", progress=1.0, message="완료", result=json.dumps(result, ensure_ascii=False, default=str))
            except UserFacingError as e:
                self._update(job_id, status="failed", message="실패", error=str(e))
            except Exception as e:  # noqa: BLE001
                from .ai.provider import AIError

                msg = str(e) if isinstance(e, AIError) else f"처리 중 오류: {type(e).__name__}"
                log.warning("job %s failed: %s", job_id, type(e).__name__)
                log.debug("%s", traceback.format_exc())
                self._update(job_id, status="failed", message="실패", error=msg)
            finally:
                if calls:
                    self._add_usage(job_id, calls)

    def _add_usage(self, job_id: str, calls: list[dict[str, Any]]) -> None:
        from .ai import usage

        r = self.db.one("SELECT usage FROM jobs WHERE id=?", (job_id,))
        prev = json.loads(r["usage"])["detail"] if r and r["usage"] else []  # 재시도한 작업은 이전 실행 사용량도 함께
        self.db.execute("UPDATE jobs SET usage=? WHERE id=?", (json.dumps(usage.summarize(prev + calls), ensure_ascii=False), job_id))


def _row(r) -> dict[str, Any]:
    return {
        "id": r["id"],
        "project_id": r["project_id"],
        "kind": r["kind"],
        "status": r["status"],
        "progress": r["progress"],
        "message": r["message"],
        "error": r["error"],
        "result": json.loads(r["result"]) if r["result"] else None,
        "params": json.loads(r["params"]) if r["params"] else {},
        "attempts": r["attempts"],
        "usage": json.loads(r["usage"]) if "usage" in r.keys() and r["usage"] else None,
        "created_at": r["created_at"],
        "updated_at": r["updated_at"],
    }
