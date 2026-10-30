"""과업지시서 초안 구성(규칙 기반). 프로젝트 데이터만 사용하며 확인되지 않은 사실을 만들지 않는다."""
from __future__ import annotations

from ..fp.cost import PHASE_KEYS, PHASE_LABELS
from ..models import Project, TaskDraft, TaskSection
from ..store import now, stable_hash

KINDS = {"web": "웹", "mobile": "모바일", "desktop": "데스크톱 프로그램", "server": "서버 프로그램", "batch": "배치 자동처리", "integration": "시스템 연계"}
BT = {"portal": "홈페이지·포털 신규개발", "system": "일반 소프트웨어·정보시스템 신규개발"}

DELIVERABLES = {
    "analysis": ["요구사항 정의서", "요구사항 추적표"],
    "design": ["화면 설계서", "데이터베이스 설계서", "인터페이스(연계) 설계서", "아키텍처 설계서"],
    "implementation": ["프로그램 소스코드 및 실행 파일", "단위시험 결과서"],
    "test": ["통합시험 계획·결과서", "사용자·운영자 매뉴얼", "보안약점 진단 결과(해당 시)"],
}


def _bullets(lines: list[str], empty: str) -> str:
    return "\n".join(f"- {x}" for x in lines) if lines else f"- {empty}"


def input_hash(p: Project) -> str:
    return stable_hash(
        {
            "ov": p.overview.model_dump(),
            "name": p.name,
            "req": [r.model_dump() for r in p.requirements],
            "fn": [f.model_dump() for f in p.functions],
            "if": [i.model_dump() for i in p.interfaces],
            "dat": [d.model_dump() for d in p.data_entities],
            "as": [a.model_dump() for a in p.assumptions],
            "q": [(q.id, q.status) for q in p.questions],
        }
    )


def build_sections(p: Project) -> list[TaskSection]:
    ov = p.overview
    reqs = [r for r in p.requirements if r.status != "excluded"]
    fr = [r for r in reqs if r.kind == "functional"]
    nfr = [r for r in reqs if r.kind == "nonfunctional"]
    phases = [k for k in PHASE_KEYS if getattr(ov.phases, k)]
    s: list[TaskSection] = []
    s.append(TaskSection(key="overview", title="1. 사업 개요", text="\n".join([
        f"- 사업명: {p.name}",
        f"- 사업 유형: {BT[ov.business_type]}",
        f"- 시스템 형태: {', '.join(KINDS[k] for k in ov.system_kinds) or '확인 필요'}",
        f"- 사업 기간: {str(ov.period_months) + '개월' if ov.period_months else '확인 필요'}",
        f"- 이용자: {ov.users or '확인 필요'}",
    ])))
    s.append(TaskSection(key="purpose", title="2. 추진 목적 및 배경", text="\n".join([
        f"- 목적: {ov.purpose or ov.idea_text or '확인 필요'}",
        f"- 배경: {ov.background or '확인 필요'}",
    ])))
    scope = [
        f"FP 측정 대상 애플리케이션: {ov.boundary_name or '확인 필요'}",
        f"포함 단계: {'·'.join(PHASE_LABELS[k] for k in phases) or '확인 필요'}",
        "주요 기능: " + (", ".join(f"{f.name}({f.id})" for f in p.functions if f.status != "excluded") or "기능 설계 진행 중"),
        "제외: 장비(HW) 구매, 별도 상용 SW 라이선스 구매(필요 시 별도 사업·예산으로 검토)",
    ]
    s.append(TaskSection(key="scope", title="3. 사업 범위", text=_bullets(scope, "")))
    s.append(TaskSection(key="functional", title="4. 상세 요구사항(기능)", text=_bullets([f"[{r.id}] {r.title}: {r.description or r.original_text}" for r in fr], "기능 요구사항 미정")))
    s.append(TaskSection(key="nonfunctional", title="5. 비기능 요구사항", text=_bullets([f"[{r.id}] ({r.category or '비기능'}) {r.title}: {r.description}" for r in nfr], "비기능 요구사항 미정(성능·보안·개인정보·접근성 등 확인 필요)")))
    dl = [f"[{d.id}] {d.name}{' (개인정보 포함)' if d.personal_info else ''}{' — 외부 시스템 유지' if d.maintained_by == 'external' else ''}" for d in p.data_entities]
    il = [f"[{i.id}] {i.name}: 상대 {i.counterpart or '확인 필요'}, 방식 {i.method or '확인 필요'}" + (" — 연계 가능성·방식 미확인(착수 전 상대기관 확인 필요)" if i.verified == "unverified" else "") for i in p.interfaces]
    s.append(TaskSection(key="data", title="6. 데이터 및 연계 요구사항", text="■ 데이터\n" + _bullets(dl, "데이터 설계 진행 중") + "\n■ 연계\n" + _bullets(il, "연계 없음 또는 미정")))
    sched = [f"{PHASE_LABELS[k]} 단계" for k in phases]
    s.append(TaskSection(key="schedule", title="7. 추진 일정(초안)", text=_bullets(sched, "확인 필요") + "\n- 세부 일정은 착수 시 발주기관과 협의하여 확정"))
    dels = [d for k in phases for d in DELIVERABLES[k]]
    s.append(TaskSection(key="deliverables", title="8. 산출물", text=_bullets(dels, "확인 필요")))
    s.append(TaskSection(key="acceptance", title="9. 검수 기준", text=acceptance_text(p)))
    from .checklist import checklist

    items = [x for x in checklist(p) if x["category"] in ("업무 결정 필요", "설계 가정(채택)", "외부·기관 확인 필요")]
    lines = []
    for cat in ("업무 결정 필요", "설계 가정(채택)", "외부·기관 확인 필요"):
        sub = [x for x in items if x["category"] == cat]
        if sub:
            lines.append(f"■ {cat} {len(sub)}건")
            lines += [f"- [{x['ref']}] {x['text']}" for x in sub]
    s.append(TaskSection(key="open", title="10. 확인 필요 사항 및 가정", text="\n".join(lines) or "- 확인 목록에 남은 항목 없음"))
    return s


def acceptance_text(p: Project) -> str:
    """요구사항별 검수 기준. 요구사항에 기준이 없으면 연결된 기능의 검수 기준을 함께 보여 준다(추적 가능)."""
    lines: list[str] = []
    missing: list[str] = []
    fns = [f for f in p.functions if f.status != "excluded"]
    for r in p.requirements:
        if r.status == "excluded":
            continue
        linked = [f for f in fns if r.id in f.requirement_ids and f.acceptance]
        if r.acceptance:
            lines.append(f"[{r.id}] {r.acceptance}")
        elif linked:
            lines.append(f"[{r.id}] 요구사항 기준 미정 — 기능 검수 기준으로 확인: " + "; ".join(f"{f.id} {f.acceptance}" for f in linked))
        else:
            missing.append(r.id)
    orphan = [f for f in fns if f.acceptance and not f.requirement_ids]
    lines += [f"[{f.id}] {f.acceptance} (요구사항 미연결 기능)" for f in orphan]
    text = _bullets(lines, "요구사항별 검수 기준 미정")
    if missing:
        text += f"\n- 검수 기준이 요구사항·기능 어디에도 없음: {', '.join(missing)}"
    return text


def regenerate(p: Project) -> TaskDraft:
    """사용자가 직접 고친 절은 덮어쓰지 않고 새 후보만 기록한다."""
    new = build_sections(p)
    old = {x.key: x for x in p.task_draft.sections}
    out = []
    for s in new:
        o = old.get(s.key)
        if o and o.user_edited:
            o.regenerated_candidate = s.text if s.text != o.text else ""
            out.append(o)
        else:
            out.append(s)
    return TaskDraft(generated_at=now(), input_hash=input_hash(p), sections=out)
