"""견적 버전 생성·상태 판정·목표예산 시나리오."""
from __future__ import annotations

import copy
from decimal import Decimal
from typing import Any

from ..models import EstimateVersion, Project, Scenario
from ..store import Mutation, next_id, now, stable_hash
from . import cost, engine


def _fp_fields(p: Project) -> list[dict[str, Any]]:
    return [
        {k: getattr(it, k) for k in ("id", "fp_type", "status", "det", "ftr_ret", "assumed_complexity", "application", "duplicate_of", "name")}
        for it in p.fp_items
    ]


def input_hash(p: Project, std: dict[str, Any], method: str) -> str:
    return stable_hash(
        {
            "fp": _fp_fields(p),
            "settings": p.cost_settings.model_dump(),
            "phases": p.overview.phases.model_dump(),
            "ratios": p.overview.phase_ratios.model_dump(),
            "boundary": p.overview.boundary_name,
            "std": std.get("id"),
            "method": method,
        }
    )


def compute(p: Project, std: dict[str, Any], method: str | None = None) -> dict[str, Any]:
    method = method or p.cost_settings.method
    results = engine.evaluate_items(p, std)
    fp_res = engine.calc_simple(results) if method == "simple" else engine.calc_detailed(results)
    total_fp = Decimal(fp_res["total_fp"])
    warnings: list[str] = []
    complete = True
    unconfirmed = [r.id for r in results if r.status in ("draft", "review")]
    if unconfirmed:
        warnings.append(f"미확정 FP 항목 {len(unconfirmed)}건은 기준 산정에서 제외됨: {', '.join(unconfirmed[:20])}")
    unclassified = [r.id for r in results if r.complexity_source == "unclassified"]
    if unclassified:
        warnings.append(f"미분류 항목 {len(unclassified)}건: {', '.join(unclassified[:20])}")
    if method == "detailed" and fp_res["missing_ids"]:
        complete = False
        warnings.append(f"정통법 DET/FTR/RET 누락 {len(fp_res['missing_ids'])}건 → 확정 산정 불가: {', '.join(fp_res['missing_ids'][:20])}")
    if method == "detailed" and fp_res["assumed_ids"]:
        warnings.append(f"가정 복잡도 적용 {len(fp_res['assumed_ids'])}건: {', '.join(fp_res['assumed_ids'][:20])}")
    if total_fp == 0:
        complete = False
        warnings.append("확정된 FP 항목이 없습니다.")
    money = cost.compute_cost(std, p.cost_settings, p.overview, total_fp)
    if not money.get("complete"):
        complete = False
    warnings += money.get("warnings", [])
    fp_snapshot = [
        {**r.as_dict(), "simple_weight": r.as_dict()["simple_weight"]}
        for r in results
        if r.counted
    ]
    return {
        "method": method,
        "fp": fp_res,
        "money": money,
        "complete": complete,
        "warnings": warnings,
        "fp_snapshot": fp_snapshot,
        "input_hash": input_hash(p, std, method),
    }


def create_estimate(p: Project, m: Mutation, std: dict[str, Any], label: str, mode: str) -> EstimateVersion:
    res = compute(p, std)
    est = EstimateVersion(
        id=next_id(p, "EST"),
        created_at=now(),
        label=label or f"기준 산정 {len(p.estimates) + 1}",
        method=res["method"],
        standard_snapshot=copy.deepcopy({k: v for k, v in std.items() if not k.startswith("_")}),
        settings_snapshot=p.cost_settings.model_dump(),
        phases_snapshot={"phases": p.overview.phases.model_dump(), "ratios": p.overview.phase_ratios.model_dump()},
        fp_snapshot=res["fp_snapshot"],
        input_hash=res["input_hash"],
        result={"fp": res["fp"], "money": res["money"]},
        warnings=res["warnings"],
        complete=res["complete"],
        mode=mode,
    )
    p.estimates.append(est)
    m.log("estimates", est.id, "add", None, {"label": est.label, "method": est.method, "total": res["money"].get("total"), "complete": est.complete})
    return est


def estimate_state(p: Project, est: EstimateVersion) -> str:
    """current: 현재 입력과 동일 / stale: FP·설정이 바뀌어 갱신 필요."""
    return "current" if input_hash(p, est.standard_snapshot, est.method) == est.input_hash else "stale"


def add_scenario(p: Project, m: Mutation, est_id: str, target_amount: int, includes_vat: bool, note: str = "") -> Scenario:
    est = next((e for e in p.estimates if e.id == est_id), None)
    if est is None:
        raise LookupError("견적 버전을 찾을 수 없습니다.")
    if not est.complete:
        raise cost.CostError("미완료(미확정 포함) 견적에는 목표예산 시나리오를 만들 수 없습니다.")
    result = cost.target_scenario(est.result["money"], target_amount, includes_vat)
    sc = Scenario(
        id=next_id(p, "SCN"),
        created_at=now(),
        target_amount=target_amount,
        target_includes_vat=includes_vat,
        fp_ids=[x["id"] for x in est.fp_snapshot],  # 기준과 동일한 FP 집합(기능 삭제·추가 없음)
        result=result,
        note=note,
    )
    est.scenarios.append(sc)
    m.log("scenarios", sc.id, "add", None, {"estimate": est_id, "target": target_amount, "ratio": result["adjustment_ratio"]})
    return sc
