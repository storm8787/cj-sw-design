"""변경안(Proposal) 적용·거절, 질문 답변 처리.

사용자가 선택한 항목만 반영한다. 확정된 항목을 바꾸는 변경안은 'conflict'로 두고 명시적 강제 적용 때만 반영한다.
"""
from __future__ import annotations

from typing import Any

from ..models import Assumption, Project, ProposalItem
from ..store import InvalidData, Mutation, NotFound, add_item, find_item, next_id, now, update_item


def _resolve(value: Any, key_map: dict[str, str]) -> tuple[Any, list[str]]:
    dropped: list[str] = []
    if isinstance(value, list):
        out = []
        for v in value:
            if isinstance(v, str) and v.startswith("key:"):
                k = v[4:]
                if k in key_map:
                    out.append(key_map[k])
                else:
                    dropped.append(k)
            else:
                out.append(v)
        return out, dropped
    return value, dropped


def apply_proposal(p: Project, m: Mutation, proposal_id: str, keys: list[str] | None, force: bool = False) -> dict[str, Any]:
    pr = next((x for x in p.proposals if x.id == proposal_id), None)
    if pr is None:
        raise NotFound("변경안을 찾을 수 없습니다.")
    selected = set(keys) if keys is not None else {i.key for i in pr.items if i.status == "pending"}
    key_map = {i.key: i.applied_id for i in pr.items if i.applied_id}
    order = {"data_entities": 0, "interfaces": 1, "requirements": 2, "functions": 3, "screens": 4, "workflows": 5, "fp_items": 6}
    applied, conflicts, notes = [], [], []
    for it in sorted(pr.items, key=lambda x: order.get(x.collection, 9)):
        if it.key not in selected or it.status not in ("pending", "conflict"):
            continue
        data = dict(it.data)
        for f in ("data_ids", "interface_ids", "function_ids", "requirement_ids", "screen_ids"):
            if f in data:
                data[f], dropped = _resolve(data[f], key_map)
                if dropped:
                    notes.append(f"{it.key}: 적용하지 않은 항목({', '.join(dropped)}) 연결은 빠짐")
        if it.op == "add":
            obj = add_item(p, m, it.collection, data)
            it.applied_id = obj.id
            key_map[it.key] = obj.id
        else:
            target = find_item(p, it.collection, it.target_id)
            if getattr(target, "status", "") == "confirmed" and not force:
                it.status = "conflict"
                it.before = {k: getattr(target, k) for k in data if hasattr(target, k)}
                conflicts.append(it.key)
                continue
            update_item(p, m, it.collection, it.target_id, data)
            it.applied_id = it.target_id
        it.status = "applied"
        applied.append(it.key)
    statuses = {i.status for i in pr.items}
    pr.status = "applied" if statuses <= {"applied", "rejected"} and "applied" in statuses else ("rejected" if statuses == {"rejected"} else ("partial" if "applied" in statuses else pr.status))
    m.log("proposals", pr.id, "apply", None, {"applied": applied, "conflicts": conflicts})
    return {"applied": applied, "conflicts": conflicts, "notes": notes, "status": pr.status}


def reject_proposal(p: Project, m: Mutation, proposal_id: str, keys: list[str] | None) -> dict[str, Any]:
    pr = next((x for x in p.proposals if x.id == proposal_id), None)
    if pr is None:
        raise NotFound("변경안을 찾을 수 없습니다.")
    sel = set(keys) if keys is not None else {i.key for i in pr.items}
    for it in pr.items:
        if it.key in sel and it.status in ("pending", "conflict"):
            it.status = "rejected"
    statuses = {i.status for i in pr.items}
    pr.status = "rejected" if statuses == {"rejected"} else ("applied" if statuses <= {"applied", "rejected"} else "partial")
    m.log("proposals", pr.id, "reject", None, {"keys": sorted(sel)})
    return {"status": pr.status}


def answer_question(p: Project, m: Mutation, qid: str, kind: str, value: str, mode: str) -> dict[str, Any]:
    """답변 기록. '모름'이면 권장안을 가정으로 기록. 선택지에 딸린 요구사항은 변경안으로 제시."""
    q = next((x for x in p.questions if x.id == qid), None)
    if q is None:
        raise NotFound("질문 없음")
    if kind not in ("choice", "text", "unknown", "defer"):
        raise InvalidData("답변 종류 오류")
    before = {"answer": q.answer, "status": q.status}
    proposal_id = None
    assumption_id = None
    if kind == "defer":
        q.status = "deferred"
        q.answer_kind = ""
        q.answer = ""
    else:
        if kind == "choice" and not any(o.value == value for o in q.options):
            raise InvalidData("선택지에 없는 값입니다.")
        if kind == "text" and not value.strip():
            raise InvalidData("답변을 입력하세요.")
        q.answer_kind = kind
        q.answer = q.recommended_value if kind == "unknown" else value.strip()[:2000]
        q.status = "answered"
        if kind == "unknown":
            label = next((o.label for o in q.options if o.value == q.recommended_value), q.recommended_value)
            a = Assumption(id=next_id(p, "AS"), text=f"{q.text} → '{label}'(권장안)으로 가정", reason=q.recommended_reason, question_id=q.id, origin=mode if mode in ("ai", "sample") else "system", status="review")
            p.assumptions.append(a)
            assumption_id = a.id
            m.log("assumptions", a.id, "add", None, a.model_dump())
        chosen = q.recommended_value if kind == "unknown" else value
        opt = next((o for o in q.options if o.value == chosen), None) if kind != "text" else None
        if opt and opt.adds_requirements:
            from ..models import Proposal

            existing = {r.title.replace(" ", "") for r in p.requirements}
            items = []
            for i, s in enumerate(opt.adds_requirements):
                k, t, d = (s.split("|", 2) + ["", ""])[:3]
                if t.replace(" ", "") in existing:
                    continue
                items.append(ProposalItem(key=f"a{i}", op="add", collection="requirements", data={"kind": k if k in ("functional", "nonfunctional") else "functional", "title": t, "description": d, "original_text": "", "why": f"질문 '{q.text}' 답변" + (" (모름 → 권장안 가정)" if kind == "unknown" else ""), "origin": q.origin, "status": "draft"}, reason=f"답변 '{opt.label}'에 따른 제안"))
            if items:
                pr = Proposal(id=next_id(p, "PR"), kind="answer", created_at=now(), mode=q.origin, summary=f"{q.id} 답변에 따른 요구사항 제안 {len(items)}건", items=items)
                p.proposals.append(pr)
                proposal_id = pr.id
    m.log("questions", qid, "answer", before, {"answer": q.answer, "kind": kind, "status": q.status})
    return {"question_id": qid, "proposal_id": proposal_id, "assumption_id": assumption_id}
