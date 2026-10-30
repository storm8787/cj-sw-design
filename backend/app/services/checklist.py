"""확인 목록: 흩어진 '확인 필요'·가정·미결정·미실행 항목을 한곳에 모은다(화면·과업지시서·엑셀 공통).

구분(사용자가 다음에 할 일이 달라서 나눈다):
- 업무 결정 필요: 답하지 않은 질문, 설계 문장 속 '확인 필요', 비어 있는 사업 개요
- 설계 가정(채택): '모름'에 권장안을 가정으로 채택한 것 등 — 사실로 확인된 것이 아님
- 외부·기관 확인 필요: 미확인 연계, 외부 시스템이 유지하는 데이터
- FP 기술 검토 필요: 미분류·중복 의심·다른 언어 혼입·업무 확인만 한 후보
- 미실행: 기준 산정·목표예산 시나리오·기존 문서 검토를 아직 하지 않음(검토 결과 '문제 없음'과 다름)
"""
from __future__ import annotations

import re
from typing import Any

from ..models import Project

CATEGORIES = ("업무 결정 필요", "설계 가정(채택)", "외부·기관 확인 필요", "FP 기술 검토 필요", "미실행")
_SENT = re.compile(r"[^.\n。]*확인\s?필요[^.\n。]*")


def _snippets(text: str) -> list[str]:
    return [m.group(0).strip(" -·,")[:160] for m in _SENT.finditer(text or "") if m.group(0).strip()]


def checklist(p: Project, fp: dict[str, Any] | None = None) -> list[dict[str, str]]:
    """반환: [{category, ref, text, step}] — step은 해결하러 갈 화면 단계."""
    out: list[dict[str, str]] = []

    def add(cat: str, ref: str, text: str, step: str) -> None:
        out.append({"category": cat, "ref": ref, "text": text, "step": step})

    ov = p.overview
    for field, label in (("purpose", "사업 목적"), ("users", "이용자"), ("boundary_name", "FP 측정 대상(애플리케이션 경계)")):
        if not getattr(ov, field) and not (field == "purpose" and ov.idea_text):
            add("업무 결정 필요", "개요", f"{label} 미입력 — '빈 항목 채우기 제안'으로 초안을 받을 수 있음", "overview")
    for q in p.questions:
        if q.status == "open":
            add("업무 결정 필요", q.id, f"답하지 않은 질문: {q.text}", "sources")
        elif q.status == "deferred":
            add("업무 결정 필요", q.id, f"나중에 결정하기로 한 질문: {q.text}", "sources")
    for r in p.requirements:
        if r.status == "excluded":
            continue
        for s in _snippets(" ".join([r.description, r.acceptance])):
            add("업무 결정 필요", r.id, f"{r.title}: {s}", "requirements")
    for f in p.functions:
        if f.status == "excluded":
            continue
        for s in _snippets(" ".join([f.inputs, f.outputs, f.rules, f.exceptions, f.permissions])):
            add("업무 결정 필요", f.id, f"{f.name}: {s}", "design")
    waiting = [it for it in p.fp_items if it.status in ("draft", "review") and not it.scope_confirmed]
    if waiting:
        ids = ", ".join(it.id for it in waiting[:10]) + (" 외" if len(waiting) > 10 else "")
        add("업무 결정 필요", ids, f"FP 후보 {len(waiting)}건이 우리 사업에 있는 처리·자료인지 답하지 않음(업무 확인: 있음/없음/모름)", "fp")
    for a in p.assumptions:
        if a.status != "excluded":
            add("설계 가정(채택)", a.id, a.text + (f" (이유: {a.reason})" if a.reason else ""), "sources")
    for i in p.interfaces:
        if i.status == "excluded":
            continue
        if i.verified == "unverified":
            add("외부·기관 확인 필요", i.id, f"{i.name}: 상대 시스템({i.counterpart or '미정'})과 연계 가능 여부·방식 미확인", "design")
    for d in p.data_entities:
        if d.status != "excluded" and d.maintained_by in ("external", "unknown"):
            add("외부·기관 확인 필요", d.id, f"{d.name}: {'외부 시스템이 유지하는 데이터 — 제공 범위·방식 확인' if d.maintained_by == 'external' else '유지 주체 미정'}", "design")
    if fp:
        names = {it.id: it.name for it in p.fp_items}
        for fid in fp.get("unclassified_ids", []):
            add("FP 기술 검토 필요", fid, f"{names.get(fid, '')}: 유형 미분류", "fp")
        for fid in fp.get("duplicate_ids", []):
            add("FP 기술 검토 필요", fid, f"{names.get(fid, '')}: 중복 의심", "fp")
        for fid in fp.get("foreign_text_ids", []):
            add("FP 기술 검토 필요", fid, f"{names.get(fid, '')}: 다른 언어가 섞인 이름·근거", "fp")
        scope = [r["id"] for r in fp.get("items", []) if r.get("count_basis") == "scope"]
        if scope:
            add("FP 기술 검토 필요", ", ".join(scope[:10]) + (" 외" if len(scope) > 10 else ""), f"업무 확인만 한 FP {len(scope)}건 — 추정 산정에 포함, 전문가 검토 시 확정", "fp")
    if not p.estimates:
        add("미실행", "-", "기준 산정을 아직 실행하지 않았습니다.", "fp")
    elif ov.budget_mode == "target" and ov.target_amount and not p.estimates[-1].scenarios:
        add("미실행", p.estimates[-1].id, "목표예산 시나리오 미실행(기준 견적과 목표액의 차이를 아직 계산하지 않음)", "fp")
    if not p.review_run.ran_at:
        add("미실행", "-", "기존 문서 검토 미실행 — '문제 없음'이 아니라 검토하지 않은 상태", "review")
    return out


def summarize(items: list[dict[str, str]]) -> dict[str, int]:
    return {c: sum(1 for x in items if x["category"] == c) for c in CATEGORIES}
