"""AI 사용량 수집. 공급자는 호출마다 record()만 부르고, 작업 실행기가 작업 단위로 모아 저장한다.

토큰 수만 기록한다(프롬프트·응답 본문·키는 기록하지 않는다). 공급자가 주지 않은 값은 None(미측정)으로 둔다.
"""
from __future__ import annotations

import threading
from contextlib import contextmanager
from typing import Any, Iterator

_local = threading.local()
FIELDS = ("input_tokens", "cached_tokens", "output_tokens", "reasoning_tokens")


def record(**entry: Any) -> None:
    sink = getattr(_local, "sink", None)
    if sink is not None:
        sink.append(entry)


@contextmanager
def collect() -> Iterator[list[dict[str, Any]]]:
    prev = getattr(_local, "sink", None)
    _local.sink = []
    try:
        yield _local.sink
    finally:
        _local.sink = prev


def summarize(calls: list[dict[str, Any]]) -> dict[str, Any]:
    """작업 하나의 합계. 하나라도 미측정이면 그 항목 합계는 None(0으로 가정하지 않음)."""
    out: dict[str, Any] = {"calls": len(calls), "models": sorted({c.get("model", "") for c in calls if c.get("model")}),
                           "latency_ms": sum(int(c.get("latency_ms") or 0) for c in calls), "failed_calls": sum(1 for c in calls if c.get("error"))}
    for f in FIELDS:
        vals = [c.get(f) for c in calls]
        out[f] = None if (not calls or any(v is None for v in vals)) else sum(vals)
    out["detail"] = calls
    return out
