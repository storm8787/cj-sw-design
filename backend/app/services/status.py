"""프로젝트 진행 상태: 미확정 수, 갱신 필요 결과물, 다음에 필요한 입력."""
from __future__ import annotations

from typing import Any

from ..fp import engine
from ..fp.estimates import estimate_state
from ..models import COLLECTIONS, Project
from . import checklist as cl
from . import taskdraft


def project_status(p: Project, std: dict[str, Any]) -> dict[str, Any]:
    fp = engine.summary(p, std)
    est_states = {e.id: estimate_state(p, e) for e in p.estimates}
    reqs = [r for r in p.requirements if r.status != "excluded"]
    needs_review = [it.id for c in ("requirements", "workflows", "functions", "screens", "data_entities", "interfaces", "fp_items") for it in getattr(p, c) if it.needs_review]
    pending_props = [pr.id for pr in p.proposals if pr.status in ("pending", "partial")]
    draft_stale = bool(p.task_draft.sections) and p.task_draft.input_hash != taskdraft.input_hash(p)
    nxt: list[dict[str, str]] = []

    def step(target: str, text: str):
        nxt.append({"step": target, "text": text})

    ov = p.overview
    if not (ov.purpose or ov.idea_text):
        step("overview", "사업 목적(또는 처음 구상)을 입력하세요.")
    if not ov.boundary_name:
        step("overview", "FP 측정 대상 애플리케이션 이름(경계)을 정하세요.")
    if ov.start_mode == "document" and not p.documents:
        step("sources", "참고문서를 올리세요.")
    # 항목 추출(유지·수정·제외)은 참고문서 대상. 업체 문서는 검토 단계에서 바로 대조하므로 추출을 요구하지 않는다.
    if any(d.kind == "reference" and d.extraction.analysis_status in ("not_started", "partial") and d.extraction.chunks_total for d in p.documents):
        step("sources", "분석이 끝나지 않은 문서가 있습니다.")
    if sum(1 for r in p.reference_items if r.decision == "pending"):
        step("sources", "참고문서 항목의 유지/수정/제외를 결정하세요.")
    open_q = [q for q in p.questions if q.status == "open"]
    if open_q:
        step("sources", f"답하지 않은 질문 {len(open_q)}개가 있습니다.")
    if pending_props:
        step("requirements", f"검토할 변경안 {len(pending_props)}건이 있습니다.")
    if not reqs:
        step("requirements", "요구사항을 입력하거나 초안을 만드세요.")
    unconf_req = [r.id for r in reqs if r.status != "confirmed"]
    if unconf_req:
        step("requirements", f"확정되지 않은 요구사항 {len(unconf_req)}건")
    if reqs and not p.functions:
        step("design", "기능 설계 초안을 만드세요.")
    if p.functions and not p.fp_items:
        step("fp", "기능·데이터로 FP 후보를 만드세요.")
    if fp["coverage"]["unlinked_functional"]:
        step("fp", f"FP가 연결되지 않은 기능 요구사항 {len(fp['coverage']['unlinked_functional'])}건")
    if fp["counts"]["duplicate_suspects"]:
        step("fp", f"중복 의심 FP {fp['counts']['duplicate_suspects']}건 — 같은 처리인지 확인하세요.")
    if fp["counts"]["unclassified"]:
        step("fp", f"유형이 정해지지 않은 FP 후보 {fp['counts']['unclassified']}건 — FP 후보를 다시 만들거나 검토가 필요합니다.")
    if fp["counts"]["awaiting_scope"]:
        step("fp", f"우리 사업에 있는지 확인할 FP 후보 {fp['counts']['awaiting_scope']}건(업무 확인)")
    method = p.cost_settings.method
    if method == "detailed" and fp["counts"]["detailed_missing"]:
        step("fp", f"정통법 근거가 부족한 항목 {fp['counts']['detailed_missing']}건 — 기능의 입력·출력 항목이나 데이터 항목을 보완하세요.")
    counted = fp["counts"]["confirmed_counted"] + fp["counts"]["scope_counted"]
    if counted and not p.estimates:
        step("fp", "기준 산정을 실행하세요(산정 설정 저장만으로는 견적이 만들어지지 않습니다).")
    if any(s == "stale" for s in est_states.values()):
        step("fp", "최근 견적 이후 FP·설정이 바뀌었습니다. 기준 산정을 다시 실행하세요.")
    if ov.budget_mode == "target" and ov.target_amount and p.estimates and p.estimates[-1].complete and not p.estimates[-1].scenarios:
        step("fp", "목표예산 시나리오를 만드세요.")
    if needs_review:
        step("design", f"연결 항목 변경으로 재검토가 필요한 항목 {len(needs_review)}건")
    if draft_stale:
        step("design", "과업지시서 초안 이후 내용이 바뀌었습니다(갱신 필요).")
    checks = cl.checklist(p, fp)
    return {
        "checklist": checks,
        "checklist_summary": cl.summarize(checks),
        "fp_basis": {"simple": fp["basis"]["simple"], "detailed": fp["basis"]["detailed"], "method": method},
        "counts": {
            "requirements": len(reqs),
            "requirements_unconfirmed": len(unconf_req),
            "questions_open": len(open_q),
            "fp_unconfirmed": fp["counts"]["unconfirmed"],
            "fp_awaiting_scope": fp["counts"]["awaiting_scope"],
            "fp_scope_counted": fp["counts"]["scope_counted"],
            "fp_confirmed_counted": fp["counts"]["confirmed_counted"],
            "fp_unclassified": fp["counts"]["unclassified"],
            "fp_duplicates": fp["counts"]["duplicate_suspects"],
            "needs_review": len(needs_review),
            "pending_proposals": len(pending_props),
            "assumptions": len(p.assumptions),
        },
        "fp_total": {"simple": fp["simple"]["total_fp"], "detailed": fp["detailed"]["total_fp"], "detailed_complete": fp["detailed"]["complete"], "simple_basis": fp["basis"]["simple"]["basis"], "detailed_basis": fp["basis"]["detailed"]["basis"]},
        "estimate_states": est_states,
        "task_draft_stale": draft_stale,
        "needs_review_ids": needs_review,
        "next_steps": nxt,
    }


def diff_projects(old: Project, new: Project) -> dict[str, Any]:
    out = {}
    for c in COLLECTIONS:
        a = {it.id: it.model_dump() for it in getattr(old, c)}
        b = {it.id: it.model_dump() for it in getattr(new, c)}
        changed = []
        for k in a.keys() & b.keys():
            if a[k] != b[k]:
                fields = sorted(f for f in b[k] if a[k].get(f) != b[k].get(f))
                changed.append({"id": k, "fields": fields, "before": {f: a[k].get(f) for f in fields}, "after": {f: b[k].get(f) for f in fields}})
        out[c] = {"added": sorted(b.keys() - a.keys()), "removed": sorted(a.keys() - b.keys()), "changed": sorted(changed, key=lambda x: x["id"])}
    out["overview"] = {k: {"before": v, "after": new.overview.model_dump().get(k)} for k, v in old.overview.model_dump().items() if new.overview.model_dump().get(k) != v}
    return out
