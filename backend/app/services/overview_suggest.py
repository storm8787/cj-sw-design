"""사업 개요 빈 항목 갱신 제안(규칙 기반, AI 호출 없음).

프로젝트에 이미 있는 자료(사업명·처음 구상·요구사항·기능의 사용자·연계)에서만 초안을 만든다.
근거가 없는 항목(추진 배경·기관 환경 등)은 지어내지 않고 비워 둔다. 결과는 변경안이며 적용해도 이미 쓴 칸은 바꾸지 않는다.
"""
from __future__ import annotations

import re

from ..models import Project, ProposalItem

_SUFFIX = re.compile(r"\s*(신규\s*)?(구축|개발|고도화|사업|용역)(\s*사업)?\s*$")


def suggestions(p: Project) -> list[ProposalItem]:
    ov = p.overview
    items: list[ProposalItem] = []

    def add(key: str, data: dict, reason: str) -> None:
        items.append(ProposalItem(key=key, op="update", collection="overview", target_id="overview", data=data, reason=reason))

    reqs = [r for r in p.requirements if r.status != "excluded" and r.kind == "functional"]
    if not ov.purpose:
        if ov.idea_text:
            add("purpose", {"purpose": ov.idea_text}, "처음 구상 문장을 목적 초안으로 옮김 — 다듬어 주세요")
        elif reqs:
            titles = "·".join(r.title for r in reqs[:4]) + (" 등" if len(reqs) > 4 else "")
            add("purpose", {"purpose": f"{titles}을(를) 온라인으로 처리하여 업무를 효율화한다."}, f"기능 요구사항 {len(reqs)}건의 제목에서 정리한 초안 — 사업 목적에 맞게 고쳐 주세요")
    if not ov.users:
        actors: list[str] = []
        for f in p.functions:
            if f.status == "excluded":
                continue
            for a in re.split(r"[,，/·]", f.actor or ""):
                a = a.strip()
                if a and a not in actors and "확인" not in a:
                    actors.append(a)
        if actors:
            add("users", {"users": ", ".join(actors[:8])}, "기능설계의 '사용자' 칸에서 모음 — 인원 규모는 직접 보완하세요")
    if not ov.boundary_name:
        base = _SUFFIX.sub("", p.name.replace("[샘플]", "")).strip()
        if base:
            add("boundary_name", {"boundary_name": base}, "사업명에서 '구축' 같은 사업 표현을 뺀 이름 — FP를 셀 시스템(애플리케이션) 이름으로 맞는지 확인하세요")
    if not ov.system_kinds:
        kinds = ["web"] if ov.business_type == "portal" or any("홈페이지" in x or "웹" in x for x in (p.name, ov.idea_text)) else []
        if [i for i in p.interfaces if i.status != "excluded"]:
            kinds.append("integration")
        if kinds:
            add("system_kinds", {"system_kinds": kinds}, "사업 유형(홈페이지·포털)·연계 항목에서 추정 — 모바일 앱·배치 등이 있으면 추가하세요")
    return items
