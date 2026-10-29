"""FP 계산 엔진. 간이법과 정통법은 서로 다른 계산 경로다(FP_RULES §3, §4).

AI·사용자는 분류·DET/FTR/RET·상태만 입력하고 점수는 이 모듈이 계산한다.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Iterable

from ..models import FPItem, Project

TRANSACTION_TYPES = ("EI", "EO", "EQ")
DATA_TYPES = ("ILF", "EIF")


@dataclass
class ItemResult:
    id: str
    name: str
    fp_type: str | None
    status: str
    counted: bool  # 기준 견적 집계 대상(확정 + 경계 내 + 분류됨)
    simple_weight: Decimal | None
    complexity: str | None
    complexity_source: str  # table | assumed | missing | unclassified
    detailed_weight: int | None
    issues: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "fp_type": self.fp_type,
            "status": self.status,
            "counted": self.counted,
            "simple_weight": str(self.simple_weight) if self.simple_weight is not None else None,
            "complexity": self.complexity,
            "complexity_source": self.complexity_source,
            "detailed_weight": self.detailed_weight,
            "issues": self.issues,
        }


def _band_index(bands: list[list[int | None]], v: int) -> int | None:
    for i, (lo, hi) in enumerate(bands):
        if v >= lo and (hi is None or v <= hi):
            return i
    return None


def complexity_of(std: dict[str, Any], fp_type: str, ftr_ret: int | None, det: int | None) -> tuple[str | None, str]:
    """정통법 복잡도. 반환: (L/A/H 또는 None, 누락 사유)."""
    if det is None or det <= 0:
        return None, "DET 미입력"
    if ftr_ret is None:
        return None, "RET 미입력" if fp_type in DATA_TYPES else "FTR 미입력"
    if fp_type in DATA_TYPES and ftr_ret <= 0:
        return None, "RET는 1 이상이어야 함"
    if ftr_ret < 0:
        return None, "FTR은 0 이상이어야 함"
    table = std["complexity_tables"]["values"][fp_type]
    ri = _band_index(table["ftr_bands"], ftr_ret)
    ci = _band_index(table["det_bands"], det)
    if ri is None or ci is None:
        return None, "복잡도 표 범위 밖"
    return table["matrix"][ri][ci], ""


def normalize_name(name: str) -> str:
    s = unicodedata.normalize("NFKC", name or "").lower()
    s = re.sub(r"\((관리자|사용자|담당자|일반|admin|user)\)", "", s)
    s = re.sub(r"^(관리자|사용자|담당자)\s*", "", s)
    s = re.sub(r"[\s_\-·./]+", "", s)
    return s


def evaluate_items(project: Project, std: dict[str, Any], items: Iterable[FPItem] | None = None) -> list[ItemResult]:
    items = list(project.fp_items if items is None else items)
    boundary = (project.overview.boundary_name or "").strip()
    sw = {k: Decimal(v) for k, v in std["simple_weights"]["values"].items()}
    dw = std["detailed_weights"]["values"]
    results: list[ItemResult] = []

    # 같은 데이터가 ILF·EIF로 동시에 분류되었는지 확인용
    data_names: dict[str, set[str]] = {}
    for it in items:
        if it.status == "excluded" or not it.fp_type:
            continue
        if it.fp_type in DATA_TYPES:
            data_names.setdefault(normalize_name(it.name), set()).add(it.fp_type)

    first_by_key: dict[tuple[str, str, str], str] = {}
    for it in items:
        issues: list[str] = []
        t = it.fp_type
        if it.status == "excluded":
            results.append(ItemResult(it.id, it.name, t, it.status, False, None, None, "excluded", None, ["제외됨"]))
            continue
        if not t:
            results.append(ItemResult(it.id, it.name, None, it.status, False, None, None, "unclassified", None, ["미분류(유형 미지정)"]))
            continue

        app = (it.application or "").strip()
        out_of_boundary = bool(boundary) and bool(app) and app != boundary and t != "EIF"
        if out_of_boundary:
            issues.append(f"경계 확인 필요: 측정 대상 '{boundary}'와 애플리케이션 '{app}'이 다름 → 집계 제외")
        if t == "EIF" and app and boundary and app == boundary:
            issues.append("EIF인데 측정 대상 애플리케이션 소속으로 기재됨 → 다른 시스템이 유지하는 데이터인지 확인")

        key = (app, t, normalize_name(it.name))
        if key in first_by_key:
            issues.append(f"중복 의심: {first_by_key[key]}와 같은 유형·이름(역할 표기만 다른 경우 포함) — 처리·데이터 차이 확인")
        else:
            first_by_key[key] = it.id
        if it.duplicate_of:
            issues.append(f"사용자 표시 중복: {it.duplicate_of}")
        if t in DATA_TYPES and len(data_names.get(normalize_name(it.name), set())) > 1:
            issues.append("같은 데이터가 ILF와 EIF로 동시에 분류됨 — 중복 의심")
        if not it.requirement_ids and not it.function_ids and not it.data_ids:
            issues.append("요구사항·기능·데이터 연결 없음")

        # 간이법
        simple_w = sw[t]
        # 정통법
        cx, why = complexity_of(std, t, it.ftr_ret, it.det)
        if cx:
            src = "table"
        elif it.assumed_complexity:
            cx, src = it.assumed_complexity, "assumed"
            issues.append(f"정통법 가정 복잡도 {cx} 적용({why}){': ' + it.assumption_note if it.assumption_note else ''}")
        else:
            src = "missing"
            issues.append(f"정통법 미확정: {why}")
        det_w = int(dw[t][cx]) if cx else None

        counted = it.status == "confirmed" and not out_of_boundary and not it.duplicate_of
        if it.status != "confirmed":
            issues.append("미확정 항목(확정 전에는 기준 견적에서 제외)")
        results.append(ItemResult(it.id, it.name, t, it.status, counted, simple_w, cx, src, det_w, issues))
    return results


def calc_simple(results: list[ItemResult]) -> dict[str, Any]:
    by_type: dict[str, dict[str, Any]] = {t: {"count": 0, "fp": Decimal(0)} for t in DATA_TYPES + TRANSACTION_TYPES}
    total = Decimal(0)
    for r in results:
        if not r.counted or r.simple_weight is None:
            continue
        by_type[r.fp_type]["count"] += 1
        by_type[r.fp_type]["fp"] += r.simple_weight
        total += r.simple_weight
    return {
        "method": "simple",
        "total_fp": str(total),
        "by_type": {k: {"count": v["count"], "fp": str(v["fp"])} for k, v in by_type.items()},
        "complete": True,
    }


def calc_detailed(results: list[ItemResult]) -> dict[str, Any]:
    by_type: dict[str, dict[str, Any]] = {t: {"count": 0, "fp": 0, "L": 0, "A": 0, "H": 0} for t in DATA_TYPES + TRANSACTION_TYPES}
    total = 0
    missing: list[str] = []
    assumed: list[str] = []
    for r in results:
        if not r.counted:
            continue
        if r.detailed_weight is None:
            missing.append(r.id)
            continue
        if r.complexity_source == "assumed":
            assumed.append(r.id)
        bt = by_type[r.fp_type]
        bt["count"] += 1
        bt["fp"] += r.detailed_weight
        bt[r.complexity] += 1
        total += r.detailed_weight
    return {
        "method": "detailed",
        "total_fp": str(total),
        "by_type": by_type,
        "missing_ids": missing,
        "assumed_ids": assumed,
        "complete": not missing,
    }


def coverage(project: Project, results: list[ItemResult]) -> dict[str, Any]:
    """요구사항 단위 FP 연결 현황."""
    linked: dict[str, list[str]] = {}
    fn_req: dict[str, list[str]] = {f.id: f.requirement_ids for f in project.functions}
    for it in project.fp_items:
        if it.status == "excluded":
            continue
        reqs = set(it.requirement_ids)
        for fid in it.function_ids:
            reqs.update(fn_req.get(fid, []))
        for rid in reqs:
            linked.setdefault(rid, []).append(it.id)
    rows = []
    for r in project.requirements:
        if r.status == "excluded":
            state = "제외"
        elif r.kind == "nonfunctional":
            state = "FP 대상 아님(비기능·검수기준 관리)"
        elif linked.get(r.id):
            state = "FP 연결"
        else:
            state = "FP 미연결"
        rows.append({"requirement_id": r.id, "title": r.title, "kind": r.kind, "state": state, "fp_ids": linked.get(r.id, [])})
    known = {r.id for r in project.requirements}
    dangling = sorted({rid for rid in linked if rid not in known})
    return {
        "rows": rows,
        "unlinked_functional": [x["requirement_id"] for x in rows if x["state"] == "FP 미연결"],
        "nonfunctional": [x["requirement_id"] for x in rows if x["kind"] == "nonfunctional"],
        "dangling_requirement_ids": dangling,
    }


def summary(project: Project, std: dict[str, Any]) -> dict[str, Any]:
    results = evaluate_items(project, std)
    simple = calc_simple(results)
    detailed = calc_detailed(results)
    unconfirmed = [r.id for r in results if r.status in ("draft", "review")]
    unclassified = [r.id for r in results if r.complexity_source == "unclassified"]
    duplicates = [r.id for r in results if any(i.startswith("중복 의심") or i.startswith("같은 데이터") for i in r.issues)]
    boundary = [r.id for r in results if any(i.startswith("경계 확인") for i in r.issues)]
    # 미확정 포함 추정(참고): 확정 + 후보 모두 간이법 가중치 합
    tentative = sum((r.simple_weight for r in results if r.simple_weight is not None and r.status != "excluded"), Decimal(0))
    return {
        "items": [r.as_dict() for r in results],
        "simple": simple,
        "detailed": detailed,
        "tentative_simple_fp_including_unconfirmed": str(tentative),
        "counts": {
            "total": len(results),
            "confirmed_counted": sum(1 for r in results if r.counted),
            "unconfirmed": len(unconfirmed),
            "unclassified": len(unclassified),
            "duplicate_suspects": len(duplicates),
            "boundary_issues": len(boundary),
            "detailed_missing": len(detailed["missing_ids"]),
        },
        "unconfirmed_ids": unconfirmed,
        "unclassified_ids": unclassified,
        "duplicate_ids": duplicates,
        "boundary_ids": boundary,
        "coverage": coverage(project, results),
    }
