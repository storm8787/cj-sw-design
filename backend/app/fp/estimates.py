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
    basis = engine.estimate_basis(results, engine.coverage(p, results), method)
    total_fp = Decimal(fp_res["total_fp"])
    warnings: list[str] = []
    complete = True
    pend = basis["pending"]
    if basis["basis"] == "empty":
        complete = False
        warnings.append("미산정: 집계할 FP가 0건이라 금액을 계산하지 않았습니다(0원은 견적이 아님). FP 후보의 업무 확인부터 진행하세요.")
    if pend["not_confirmed"]:
        warnings.append(f"업무 확인 전 후보 {len(pend['not_confirmed'])}건은 집계에서 빠짐: {', '.join(pend['not_confirmed'][:20])}")
    if pend["unclassified"]:
        warnings.append(f"유형 미분류 {len(pend['unclassified'])}건은 집계에서 빠짐: {', '.join(pend['unclassified'][:20])}")
    if pend["duplicates"]:
        warnings.append(f"중복 의심 {len(pend['duplicates'])}건은 해결 전 집계에서 빠짐: {', '.join(pend['duplicates'][:20])}")
    if pend["unlinked_requirements"]:
        warnings.append(f"FP가 연결되지 않은 기능 요구사항 {len(pend['unlinked_requirements'])}건: {', '.join(pend['unlinked_requirements'][:20])}")
    if basis["scope_only_ids"]:
        warnings.append(f"업무 확인만 한 항목 {len(basis['scope_only_ids'])}건 포함(FP 기술 검토 전 — 추정): {', '.join(basis['scope_only_ids'][:20])}")
    if method == "detailed" and fp_res["missing_ids"]:
        complete = False
        warnings.append(f"정통법 근거 부족 {len(fp_res['missing_ids'])}건 → 정통법 산정 미완료(입력·출력·데이터 항목을 보완하면 코드가 셈): {', '.join(fp_res['missing_ids'][:20])}")
    if method == "detailed" and fp_res["assumed_ids"]:
        warnings.append(f"가정 복잡도 적용 {len(fp_res['assumed_ids'])}건: {', '.join(fp_res['assumed_ids'][:20])}")
    if method == "detailed" and fp_res.get("derived_ids"):
        warnings.append(f"DET·FTR/RET을 근거 목록에서 코드로 집계한 항목 {len(fp_res['derived_ids'])}건(근거 목록 검토 권장)")
    money = cost.compute_cost(std, p.cost_settings, p.overview, total_fp)
    if basis["basis"] == "empty":
        money["complete"] = False  # 0FP로 계산한 0원을 정상 금액처럼 보이지 않게 함
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
        "basis": basis,
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
        result={"fp": res["fp"], "money": res["money"], "basis": res["basis"]},
        warnings=res["warnings"],
        complete=res["complete"],
        mode=mode,
    )
    p.estimates.append(est)
    m.log("estimates", est.id, "add", None, {"label": est.label, "method": est.method, "total": res["money"].get("total"), "complete": est.complete, "basis": res["basis"]["basis"]})
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
    base_basis = (est.result.get("basis") or {}).get("basis", "")
    result["base_basis"] = base_basis  # 기준 견적의 성격(부분·추정이면 시나리오도 그 위에서 만든 참고값)
    if base_basis in ("partial", "estimated"):
        result.setdefault("warnings", []).append(f"기준 견적이 '{engine.BASIS_LABEL[base_basis]}' 상태입니다 — 이 시나리오도 그 기준에서 만든 참고값입니다.")
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
