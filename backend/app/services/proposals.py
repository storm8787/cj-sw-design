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


def match_fp(data: dict[str, Any], candidates: list[dict[str, Any]]) -> tuple[dict[str, Any] | None, str | None]:
    """새 FP 후보와 기존(또는 대기 중) 후보 비교. 반환: (대상, 'same'|'similar'|None).
    same: 정규화한 이름이 같거나, 이름이 매우 비슷하고(0.8 이상) 연결 기능·요구사항·데이터가 겹침 → 기존 항목 갱신안.
    similar: 이름이 비슷하고(0.6 이상) 연결이 겹침 → 비교 후 사용자가 판단. 유형이 서로 다르게 정해졌거나 처리 동사(등록·수정·삭제 등)가 다르면 별개."""
    from difflib import SequenceMatcher

    from ..fp.engine import _different_action, normalize_name

    n = normalize_name(data.get("name", ""))
    best: tuple[dict[str, Any] | None, str | None] = (None, None)
    for c in candidates:
        if data.get("fp_type") and c.get("fp_type") and data["fp_type"] != c["fp_type"]:
            continue
        cn = normalize_name(c.get("name", ""))
        if n and n == cn:
            return c, "same"
        if _different_action(n, cn):
            continue
        overlap = bool(set(data.get("function_ids") or []) & set(c.get("function_ids") or [])) or bool(set(data.get("data_ids") or []) & set(c.get("data_ids") or [])) or (
            bool(data.get("requirement_ids")) and set(data.get("requirement_ids") or []) == set(c.get("requirement_ids") or []))
        if not overlap:
            continue
        r = SequenceMatcher(None, n, cn).ratio()
        if r >= 0.8:
            return c, "same"
        if r >= 0.6 and best[1] is None:
            best = (c, "similar")
    return best


DEDUP_COLLECTIONS = ("requirements", "functions", "data_entities", "interfaces", "screens", "workflows", "fp_items")


def _same_existing(p: Project, collection: str, data: dict[str, Any]):
    """적용 시 중복 방지: 같은 컬렉션에 이름(요구사항은 제목)이 같은 항목이 이미 있으면 그 항목. FP는 유형도 같아야 함."""
    from ..fp.engine import normalize_name

    if collection not in DEDUP_COLLECTIONS:
        return None
    field = "title" if collection == "requirements" else "name"
    n = normalize_name(str(data.get(field, "")))
    if not n:
        return None
    for it in getattr(p, collection):
        if it.status == "excluded" or normalize_name(getattr(it, field, "")) != n:
            continue
        if collection == "fp_items" and data.get("fp_type") and it.fp_type and data["fp_type"] != it.fp_type:
            continue
        return it
    return None


OVERVIEW_FIELDS = ("purpose", "background", "users", "build_method", "org_environment", "boundary_name", "system_kinds", "idea_text")


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
        if it.collection == "overview":
            # 사업 개요 갱신 제안: 비어 있는 칸만 채운다(사용자가 쓴 값은 강제 적용 때만 바꿈)
            ov = p.overview
            filled = {k: v for k, v in data.items() if k in OVERVIEW_FIELDS and (force or not getattr(ov, k))}
            skipped = [k for k in data if k in OVERVIEW_FIELDS and k not in filled]
            if not filled:
                it.status = "conflict"
                it.before = {k: getattr(ov, k) for k in data if k in OVERVIEW_FIELDS}
                conflicts.append(it.key)
                continue
            before = {k: getattr(ov, k) for k in filled}
            for k, v in filled.items():
                setattr(ov, k, v)
            m.log("overview", p.id, "update", before, filled)
            if skipped:
                notes.append(f"{it.key}: 이미 입력된 개요 항목({', '.join(skipped)})은 바꾸지 않음")
            it.applied_id = "overview"
        elif it.op == "add":
            dup = _same_existing(p, it.collection, data)
            if dup is not None:
                # 이미 같은 항목이 있으면 새로 만들지 않고 기존 항목에 연결(변경안 재적용·중복 생성 방지)
                it.status = "merged"
                it.applied_id = dup.id
                key_map[it.key] = dup.id
                notes.append(f"{it.key}: 이미 있는 {dup.id}와 같아 새로 추가하지 않고 연결함")
                continue
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
    statuses = {"applied" if i.status == "merged" else i.status for i in pr.items}
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
    statuses = {"applied" if i.status == "merged" else i.status for i in pr.items}
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
