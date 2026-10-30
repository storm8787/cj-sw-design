"""FP 계산 엔진. 간이법과 정통법은 서로 다른 계산 경로다(FP_RULES §3, §4).

AI·사용자는 분류·근거 목록(데이터 요소·참조 데이터·하위 그룹)·업무 확인·상태만 정하고,
DET/FTR/RET 집계·복잡도·점수·산정 상태는 이 모듈이 계산한다.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from decimal import Decimal
from difflib import SequenceMatcher
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
    counted: bool  # 집계 대상(확정 또는 업무 확인 + 경계 내 + 분류됨 + 중복 아님)
    simple_weight: Decimal | None
    complexity: str | None
    complexity_source: str  # table(입력값) | derived(근거 목록을 코드가 집계) | assumed | missing | unclassified | excluded
    detailed_weight: int | None
    issues: list[str] = field(default_factory=list)  # 두 방식 공통 확인 사항
    count_basis: str | None = None  # confirmed(기술 검토 완료) | scope(업무 확인만 — 추정) | None(미집계)
    detailed_note: str = ""  # 정통법에만 해당하는 안내(간이법 산출물에는 쓰지 않음)
    det_used: int | None = None
    ftr_ret_used: int | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "fp_type": self.fp_type,
            "status": self.status,
            "counted": self.counted,
            "count_basis": self.count_basis,
            "simple_weight": str(self.simple_weight) if self.simple_weight is not None else None,
            "complexity": self.complexity,
            "complexity_source": self.complexity_source,
            "detailed_weight": self.detailed_weight,
            "det_used": self.det_used,
            "ftr_ret_used": self.ftr_ret_used,
            "detailed_note": self.detailed_note,
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


_KANA = re.compile(r"[\u3040-\u30ff]")
_HAN = re.compile(r"[\u4e00-\u9fff]")
_HANGUL = re.compile(r"[\uac00-\ud7a3]")


def foreign_script(text: str) -> str:
    """한국어 산출물에 섞인 다른 문자(일본어 가나, 한글 없는 한자 문장). 영문 제품명·용어는 대상 아님."""
    if not text:
        return ""
    if _KANA.search(text):
        return "일본어"
    if len(_HAN.findall(text)) >= 2 and not _HANGUL.search(text):
        return "한자(중국어)"
    return ""


def unique_items(items: Iterable[str]) -> list[str]:
    """근거 목록의 중복 제거(공백·기호·대소문자 무시). 같은 항목을 두 번 세지 않는다."""
    seen: dict[str, str] = {}
    for x in items:
        k = re.sub(r"[\s_\-·./()]+", "", unicodedata.normalize("NFKC", x or "").lower())
        if k and k not in seen:
            seen[k] = x.strip()
    return list(seen.values())


_SPLIT = re.compile(r"[,，、;\n]|\s및\s|\s/\s")
_VAGUE = ("확인 필요", "확인필요", "미정", "등등")


def parse_items(text: str) -> list[str]:
    """'성명, 연락처, 신청금액' 같은 항목 목록을 나눈다. '확인 필요'·긴 문장(25자 초과)은 데이터 요소로 세지 않는다."""
    out = []
    for raw in _SPLIT.split(text or ""):
        x = re.sub(r"\s*등$", "", raw.strip(" .·-()[]"))
        if not x or len(x) > 25 or any(v in x for v in _VAGUE):
            continue
        out.append(x)
    return unique_items(out)


@dataclass
class DesignIndex:
    """FP 근거를 찾을 설계 정보(기능의 입력·출력 항목, 데이터의 항목·하위 그룹)."""
    data_ids: set[str]
    fn_inputs: dict[str, list[str]]
    fn_outputs: dict[str, list[str]]
    data_items: dict[str, list[str]]
    data_groups: dict[str, list[str]]
    data_names: dict[str, str]

    def data_names_of(self, ids: list[str]) -> list[str]:
        return [self.data_names[d] for d in ids if d in self.data_names]

    @classmethod
    def of(cls, project: Project) -> "DesignIndex":
        return cls(
            {d.id for d in project.data_entities},
            {f.id: parse_items(f.inputs) for f in project.functions},
            {f.id: parse_items(f.outputs) for f in project.functions},
            {d.id: parse_items(d.attributes) for d in project.data_entities},
            {d.id: unique_items(d.subgroups) for d in project.data_entities},
            {d.id: d.name for d in project.data_entities},
        )


def derive_metrics(it: FPItem, idx: DesignIndex) -> tuple[int | None, int | None, bool, list[str]]:
    """정통법 입력값. 직접 입력(DET·FTR/RET)이 있으면 그 값, 없으면 근거를 코드가 센다(FP_RULES §4-1, 시스템 규칙).
    근거 우선순위: FP 항목의 근거 목록 → 연결된 기능의 입력·출력 항목 / 연결된 데이터의 항목·하위 그룹.
    반환: (DET, FTR/RET, 코드 집계 여부, 집계 설명)."""
    notes: list[str] = []
    derived = False
    t = it.fp_type
    det = it.det if it.det and it.det > 0 else None
    if det is None:
        items, src = unique_items(it.det_items), "FP 근거 목록"
        if not items and t in TRANSACTION_TYPES and it.function_ids:
            pool: list[str] = []
            for fid in it.function_ids:
                pool += idx.fn_inputs.get(fid, [])
                if t in ("EO", "EQ"):
                    pool += idx.fn_outputs.get(fid, [])
            items, src = unique_items(pool), f"기능 {', '.join(it.function_ids)}의 {'입력' if t == 'EI' else '입력·출력'} 항목"
        if not items and t in DATA_TYPES and it.data_ids:
            items = unique_items([x for d in it.data_ids for x in idx.data_items.get(d, [])])
            src = f"데이터 {', '.join(it.data_ids)}의 항목"
        if items:
            det = len(items)
            derived = True
            notes.append(f"DET {det} = {src} {det}개(중복 제거: {', '.join(items[:12])}{' …' if len(items) > 12 else ''})")
    ftr = it.ftr_ret
    if ftr is None and t in TRANSACTION_TYPES:
        refs = sorted({d for d in it.data_ids if d in idx.data_ids})
        if refs:
            ftr = len(refs)
            derived = True
            notes.append(f"FTR {ftr} = 참조·유지 데이터 {', '.join(refs)}")
    elif ftr is None and t in DATA_TYPES and det is not None:
        # RET = 기본 묶음 1 + 추가 하위 그룹 수(예: 신청 정보 + 승인 이력 → 2). 데이터 이름 자체를 적은 것은 기본 묶음으로 본다.
        base = {normalize_name(re.sub(r"\s*정보$", "", x)) for x in [it.name, *idx.data_names_of(it.data_ids)]}
        groups = [g for g in (unique_items(it.ret_groups) or unique_items([g for d in it.data_ids for g in idx.data_groups.get(d, [])])) if normalize_name(re.sub(r"\s*정보$", "", g)) not in base]
        ftr = 1 + len(groups)
        derived = True
        notes.append(f"RET {ftr} = 기본 묶음 1 + 하위 그룹 {len(groups)}개({', '.join(groups)})" if groups else "RET 1 = 기본 묶음만(하위 그룹 없음)")
    return det, ftr, derived, notes


# 이름에 서로 다른 처리 동사가 있으면(예: '과정 등록'과 '과정 수정') 이름이 비슷해도 별개 단위프로세스로 본다.
_DISTINCT_ACTIONS = ("등록", "수정", "삭제", "승인", "반려", "취소")


def _different_action(a: str, b: str) -> bool:
    x = {w for w in _DISTINCT_ACTIONS if w in a}
    y = {w for w in _DISTINCT_ACTIONS if w in b}
    return bool(x) and bool(y) and x != y


def _dup_hints(items: list[FPItem]) -> dict[str, str]:
    """중복 의심: 같은 이름(역할 표기만 다른 경우 포함)이거나, 이름이 비슷하고(유사도 0.6 이상) 연결 기능·요구사항이 겹치는 항목.
    유형이 서로 다르게 정해진 항목(예: EI와 EQ)은 다른 처리로 본다. 자동 삭제하지 않고 표시만 한다."""
    hints: dict[str, str] = {}
    prev: list[tuple[FPItem, str]] = []
    for it in items:
        if it.status == "excluded" or it.duplicate_of:
            continue
        n = normalize_name(it.name)
        for q, qn in prev:
            if (it.application or "").strip() != (q.application or "").strip():
                continue
            if it.fp_type and q.fp_type and it.fp_type != q.fp_type:
                continue
            same = bool(n) and n == qn
            overlap = bool(set(it.function_ids) & set(q.function_ids)) or (bool(it.requirement_ids) and set(it.requirement_ids) == set(q.requirement_ids))
            if same or (overlap and not _different_action(n, qn) and SequenceMatcher(None, n, qn).ratio() >= 0.6):
                hints[it.id] = q.id
                break
        prev.append((it, n))
    return hints


def evaluate_items(project: Project, std: dict[str, Any], items: Iterable[FPItem] | None = None) -> list[ItemResult]:
    items = list(project.fp_items if items is None else items)
    boundary = (project.overview.boundary_name or "").strip()
    sw = {k: Decimal(v) for k, v in std["simple_weights"]["values"].items()}
    dw = std["detailed_weights"]["values"]
    idx = DesignIndex.of(project)
    results: list[ItemResult] = []

    # 같은 데이터가 ILF·EIF로 동시에 분류되었는지 확인용
    data_names: dict[str, set[str]] = {}
    for it in items:
        if it.status == "excluded" or not it.fp_type:
            continue
        if it.fp_type in DATA_TYPES:
            data_names.setdefault(normalize_name(it.name), set()).add(it.fp_type)
    dups = _dup_hints(items)

    for it in items:
        issues: list[str] = []
        t = it.fp_type
        if it.status == "excluded":
            results.append(ItemResult(it.id, it.name, t, it.status, False, None, None, "excluded", None, ["제외됨"]))
            continue
        lang = foreign_script(it.name) or foreign_script(it.rationale)
        if lang:
            issues.append(f"{lang}가 섞인 이름·근거 — 한국어로 고치거나 FP 후보를 다시 만드세요")
        if it.id in dups:
            issues.append(f"중복 의심: {dups[it.id]}와 이름·연결이 비슷함 — 같은 처리면 한쪽을 제외(중복 대상 지정)하세요")
        if it.duplicate_of:
            issues.append(f"사용자 표시 중복: {it.duplicate_of}")
        if not t:
            issues.insert(0, "미분류(유형 미지정)")
            results.append(ItemResult(it.id, it.name, None, it.status, False, None, None, "unclassified", None, issues))
            continue

        app = (it.application or "").strip()
        out_of_boundary = bool(boundary) and bool(app) and app != boundary and t != "EIF"
        if out_of_boundary:
            issues.append(f"경계 확인 필요: 측정 대상 '{boundary}'와 애플리케이션 '{app}'이 다름 → 집계 제외")
        if t == "EIF" and app and boundary and app == boundary:
            issues.append("EIF인데 측정 대상 애플리케이션 소속으로 기재됨 → 다른 시스템이 유지하는 데이터인지 확인")
        if t in DATA_TYPES and len(data_names.get(normalize_name(it.name), set())) > 1:
            issues.append("같은 데이터가 ILF와 EIF로 동시에 분류됨 — 중복 의심")
        if not it.requirement_ids and not it.function_ids and not it.data_ids:
            issues.append("요구사항·기능·데이터 연결 없음")

        # 간이법: 유형만 정해지면 가중치가 정해진다(DET 불필요)
        simple_w = sw[t]
        # 정통법: 입력값 또는 근거 목록 집계 → 복잡도 표
        det, ftr, derived, notes = derive_metrics(it, idx)
        cx, why = complexity_of(std, t, ftr, det)
        if cx:
            src = "derived" if derived else "table"
            note = ("코드 집계: " + "; ".join(notes)) if derived else ""
        elif it.assumed_complexity:
            cx, src = it.assumed_complexity, "assumed"
            note = f"가정 복잡도 {cx} 적용({why}){': ' + it.assumption_note if it.assumption_note else ''}"
        else:
            src = "missing"
            note = f"정통법 근거 부족: {why} — 기능의 입력·출력 항목이나 데이터 항목을 보완하면 코드가 셉니다"
        det_w = int(dw[t][cx]) if cx else None

        unresolved_dup = it.id in dups and it.status != "confirmed"
        in_scope = it.status == "confirmed" or (it.scope_confirmed and it.status in ("draft", "review"))
        counted = in_scope and not out_of_boundary and not it.duplicate_of and not unresolved_dup
        basis = ("confirmed" if it.status == "confirmed" else "scope") if counted else None
        if it.status != "confirmed":
            if counted:
                issues.append("업무 확인 항목(FP 기술 검토 전) — 추정 산정에 포함")
            elif it.scope_confirmed and unresolved_dup:
                issues.append("업무 확인했지만 중복 의심이 풀리지 않아 집계 제외")
            else:
                issues.append("업무 확인 전 후보 — 확인하면 추정 산정에 포함")
        results.append(ItemResult(it.id, it.name, t, it.status, counted, simple_w, cx, src, det_w, issues, basis, note, det, ftr))
    return results


def calc_simple(results: list[ItemResult]) -> dict[str, Any]:
    by_type: dict[str, dict[str, Any]] = {t: {"count": 0, "fp": Decimal(0)} for t in DATA_TYPES + TRANSACTION_TYPES}
    total = Decimal(0)
    counted = 0
    for r in results:
        if not r.counted or r.simple_weight is None:
            continue
        by_type[r.fp_type]["count"] += 1
        by_type[r.fp_type]["fp"] += r.simple_weight
        total += r.simple_weight
        counted += 1
    return {
        "method": "simple",
        "total_fp": str(total),
        "by_type": {k: {"count": v["count"], "fp": str(v["fp"])} for k, v in by_type.items()},
        "counted": counted,
        "complete": counted > 0,  # 집계 대상 0건이면 산정 완료가 아님
    }


def calc_detailed(results: list[ItemResult]) -> dict[str, Any]:
    by_type: dict[str, dict[str, Any]] = {t: {"count": 0, "fp": 0, "L": 0, "A": 0, "H": 0} for t in DATA_TYPES + TRANSACTION_TYPES}
    total = 0
    missing: list[str] = []
    assumed: list[str] = []
    derived: list[str] = []
    counted = 0
    for r in results:
        if not r.counted:
            continue
        counted += 1
        if r.detailed_weight is None:
            missing.append(r.id)
            continue
        if r.complexity_source == "assumed":
            assumed.append(r.id)
        if r.complexity_source == "derived":
            derived.append(r.id)
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
        "derived_ids": derived,
        "counted": counted,
        "complete": counted > 0 and not missing,  # 집계 대상 0건을 '완료'로 보지 않음
    }


def coverage(project: Project, results: list[ItemResult]) -> dict[str, Any]:
    """요구사항 단위 FP 연결 현황."""
    linked: dict[str, list[str]] = {}
    dropped: dict[str, list[str]] = {}  # 업무 확인에서 '없음'으로 제외한 FP만 연결된 요구사항(사용자 결정 — 미연결과 구분)
    fn_req: dict[str, list[str]] = {f.id: f.requirement_ids for f in project.functions}
    for it in project.fp_items:
        reqs = set(it.requirement_ids)
        for fid in it.function_ids:
            reqs.update(fn_req.get(fid, []))
        for rid in reqs:
            (dropped if it.status == "excluded" else linked).setdefault(rid, []).append(it.id)
    rows = []
    for r in project.requirements:
        if r.status == "excluded":
            state = "제외"
        elif r.kind == "nonfunctional":
            state = "FP 대상 아님(비기능·검수기준 관리)"
        elif linked.get(r.id):
            state = "FP 연결"
        elif dropped.get(r.id):
            state = "FP 없음(후보를 제외로 결정)"
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


BASIS_LABEL = {
    "empty": "미산정",
    "partial": "부분 산정",
    "estimated": "추정 산정",
    "confirmed": "확정 산정",
}


def estimate_basis(results: list[ItemResult], cov: dict[str, Any], method: str) -> dict[str, Any]:
    """산정 결과의 성격. 숫자가 나왔다고 완료가 아니다.
    empty: 집계 대상 0건 / partial: 아직 집계에 못 넣은 후보·미분류·중복·FP 미연결 요구사항이 있음 /
    estimated: 업무 확인만 한 후보 또는 가정 복잡도 포함 / confirmed: 집계 항목이 모두 기술 검토 완료이고 남은 후보 없음."""
    live = [r for r in results if r.status != "excluded"]
    counted = [r for r in live if r.counted]
    pending = {
        "unclassified": [r.id for r in live if r.complexity_source == "unclassified"],
        "not_confirmed": [r.id for r in live if r.fp_type and not r.counted and r.status != "confirmed" and not any(i.startswith("중복 의심") for i in r.issues)],
        "duplicates": [r.id for r in live if any(i.startswith("중복 의심") for i in r.issues) and not r.counted],
        "unlinked_requirements": list(cov.get("unlinked_functional", [])),
        "detailed_missing": [r.id for r in counted if r.detailed_weight is None] if method == "detailed" else [],
    }
    scope_only = [r.id for r in counted if r.count_basis == "scope"]
    assumed = [r.id for r in counted if r.complexity_source == "assumed"] if method == "detailed" else []
    if not counted:
        basis = "empty"
    elif any(pending.values()):
        basis = "partial"
    elif scope_only or assumed:
        basis = "estimated"
    else:
        basis = "confirmed"
    reasons = []
    if not counted:
        reasons.append("집계할 FP가 0건입니다. FP 후보의 업무 확인(우리 사업에 있음)부터 진행하세요." if live else "FP 후보가 없습니다. 기능·데이터로 FP 후보를 만드세요.")
    if pending["unclassified"]:
        reasons.append(f"유형이 정해지지 않은 후보 {len(pending['unclassified'])}건")
    if pending["not_confirmed"]:
        reasons.append(f"업무 확인 전 후보 {len(pending['not_confirmed'])}건")
    if pending["duplicates"]:
        reasons.append(f"중복 의심 {len(pending['duplicates'])}건")
    if pending["unlinked_requirements"]:
        reasons.append(f"FP가 연결되지 않은 기능 요구사항 {len(pending['unlinked_requirements'])}건")
    if pending["detailed_missing"]:
        reasons.append(f"정통법 근거 부족 {len(pending['detailed_missing'])}건(입력·출력·데이터 항목 보완 필요)")
    if scope_only:
        reasons.append(f"업무 확인만 한 항목 {len(scope_only)}건(FP 기술 검토 전)")
    if assumed:
        reasons.append(f"가정 복잡도 적용 {len(assumed)}건")
    return {
        "basis": basis,
        "label": BASIS_LABEL[basis],
        "counted": len(counted),
        "scope_only_ids": scope_only,
        "assumed_ids": assumed,
        "pending": pending,
        "reasons": reasons,
    }


def summary(project: Project, std: dict[str, Any]) -> dict[str, Any]:
    results = evaluate_items(project, std)
    simple = calc_simple(results)
    detailed = calc_detailed(results)
    unconfirmed = [r.id for r in results if r.status in ("draft", "review")]
    unclassified = [r.id for r in results if r.complexity_source == "unclassified"]
    duplicates = [r.id for r in results if any(i.startswith("중복 의심") or i.startswith("같은 데이터") for i in r.issues)]
    boundary = [r.id for r in results if any(i.startswith("경계 확인") for i in r.issues)]
    foreign = [r.id for r in results if any("섞인 이름" in i for i in r.issues)]
    # 미확정 포함 추정(참고): 확정 + 후보 모두 간이법 가중치 합
    tentative = sum((r.simple_weight for r in results if r.simple_weight is not None and r.status != "excluded"), Decimal(0))
    cov = coverage(project, results)
    return {
        "items": [r.as_dict() for r in results],
        "simple": simple,
        "detailed": detailed,
        "basis": {"simple": estimate_basis(results, cov, "simple"), "detailed": estimate_basis(results, cov, "detailed")},
        "tentative_simple_fp_including_unconfirmed": str(tentative),
        "counts": {
            "total": len(results),
            "confirmed_counted": sum(1 for r in results if r.counted and r.count_basis == "confirmed"),
            "scope_counted": sum(1 for r in results if r.counted and r.count_basis == "scope"),
            "unconfirmed": len(unconfirmed),
            "awaiting_scope": sum(1 for r in results if r.status in ("draft", "review") and not r.counted),
            "unclassified": len(unclassified),
            "duplicate_suspects": len(duplicates),
            "boundary_issues": len(boundary),
            "foreign_text": len(foreign),
            "detailed_missing": len(detailed["missing_ids"]),
        },
        "unconfirmed_ids": unconfirmed,
        "unclassified_ids": unclassified,
        "duplicate_ids": duplicates,
        "boundary_ids": boundary,
        "foreign_text_ids": foreign,
        "coverage": cov,
    }
