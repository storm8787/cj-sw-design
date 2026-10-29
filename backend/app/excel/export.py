"""프로젝트 → 엑셀(.xlsx) 산출물.

- 모든 사용자 텍스트는 문자열 셀로 저장(수식 실행 방지).
- 금액·FP는 Excel 수식 열과 Python 확인값 열을 함께 둔다. openpyxl은 수식 캐시값을 쓰지 못하므로
  통합문서에 '열 때 전체 재계산'을 설정하고, '검산' 시트에서 수식값−Python값 차이를 보여준다.
"""
from __future__ import annotations

import io
from decimal import Decimal
from typing import Any

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.workbook.properties import CalcProperties
from openpyxl.worksheet.worksheet import Worksheet

from ..fp import engine
from ..fp.cost import PHASE_KEYS, PHASE_LABELS
from ..fp.estimates import estimate_state
from ..models import EstimateVersion, Project
from ..services.taskdraft import build_sections
from . import labels as L

HEAD_FILL = PatternFill("solid", fgColor="DCE6F1")
TITLE_FONT = Font(bold=True, size=13)
BOLD = Font(bold=True)
WARN_FONT = Font(color="9C0006", bold=True)
WRAP = Alignment(wrap_text=True, vertical="top")
THIN = Side(style="thin", color="B7B7B7")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
WON = '#,##0'
WON_DEC = '#,##0.00'
RATIO = '0.0000'

SHEET_NAMES = [
    "사업개요", "과업내용", "요구사항", "기능설계", "화면_데이터_연계", "FP_간이법", "FP_정통법",
    "개발비_기준", "목표예산_시나리오", "검토의견", "HW_SW추천", "근거_변경이력", "검산",
]

FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r", "\n")


def put(ws: Worksheet, row: int, col: int, value: Any, *, fmt: str | None = None, bold: bool = False, formula: bool = False):
    """셀 기록. formula=True일 때만 '='로 시작하는 값을 수식으로 둔다. 그 외 문자열은 항상 텍스트."""
    c = ws.cell(row=row, column=col)
    if value is None:
        value = ""
    if isinstance(value, Decimal):
        value = float(value)
    if isinstance(value, bool):
        value = "예" if value else "아니오"
    if isinstance(value, (list, tuple)):
        value = ", ".join(str(x) for x in value)
    c.value = value
    if isinstance(value, str):
        if formula and value.startswith("="):
            pass
        else:
            c.data_type = "s"  # 수식 실행 방지
    if fmt:
        c.number_format = fmt
    c.alignment = WRAP
    c.border = BORDER
    if bold:
        c.font = BOLD
    return c


def header(ws: Worksheet, row: int, titles: list[str], widths: list[int] | None = None):
    for i, t in enumerate(titles, start=1):
        c = put(ws, row, i, t, bold=True)
        c.fill = HEAD_FILL
    if widths:
        for i, w in enumerate(widths, start=1):
            ws.column_dimensions[get_column_letter(i)].width = w


def finish_table(ws: Worksheet, header_row: int, last_row: int, ncols: int, landscape: bool = True):
    ws.freeze_panes = ws.cell(row=header_row + 1, column=2 if ncols > 3 else 1)
    if last_row > header_row:
        ws.auto_filter.ref = f"A{header_row}:{get_column_letter(ncols)}{last_row}"
    ws.print_title_rows = f"{header_row}:{header_row}"
    page_setup(ws, landscape)


def page_setup(ws: Worksheet, landscape: bool = True):
    ws.page_setup.orientation = "landscape" if landscape else "portrait"
    ws.page_setup.paperSize = ws.PAPERSIZE_A4
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.print_options.gridLines = False
    ws.oddFooter.center.text = "&P / &N"


def title(ws: Worksheet, text: str, sub: str = "") -> int:
    c = ws.cell(row=1, column=1, value=text)
    c.data_type = "s"
    c.font = TITLE_FONT
    if sub:
        s = ws.cell(row=2, column=1, value=sub)
        s.data_type = "s"
        s.font = Font(italic=True, color="595959")
    return 4 if sub else 3


def not_run(ws: Worksheet, msg: str):
    r = title(ws, ws.title, "미실행")
    c = put(ws, r, 1, f"미실행: {msg}")
    c.font = WARN_FONT
    ws.column_dimensions["A"].width = 90
    page_setup(ws, False)


def _mode_text(p: Project) -> str:
    origins: dict[str, int] = {}
    for coll in ("requirements", "functions", "fp_items", "screens", "data_entities", "interfaces"):
        for it in getattr(p, coll):
            origins[it.origin] = origins.get(it.origin, 0) + 1
    return ", ".join(f"{L.ORIGIN.get(k, k)} {v}건" for k, v in sorted(origins.items())) or "항목 없음"


def pick_estimate(p: Project, estimate_id: str | None) -> EstimateVersion | None:
    if estimate_id:
        return next((e for e in p.estimates if e.id == estimate_id), None)
    return p.estimates[-1] if p.estimates else None


def build_workbook(p: Project, std: dict[str, Any], changes: list[dict[str, Any]], mode_label: str, estimate_id: str | None = None) -> tuple[Workbook, dict[str, Any]]:
    wb = Workbook()
    wb.remove(wb.active)
    wb.calculation = CalcProperties(fullCalcOnLoad=True)
    sheets = {name: wb.create_sheet(name) for name in SHEET_NAMES}
    fp_sum = engine.summary(p, std)
    est = pick_estimate(p, estimate_id)
    checks: list[dict[str, Any]] = []  # 검산 시트용: (시트, 셀, python값, 설명)

    _overview(sheets["사업개요"], p, fp_sum, est, mode_label)
    _task(sheets["과업내용"], p)
    _requirements(sheets["요구사항"], p, fp_sum)
    _functions(sheets["기능설계"], p)
    _design_lists(sheets["화면_데이터_연계"], p)
    _fp_simple(sheets["FP_간이법"], p, std, fp_sum, checks)
    _fp_detailed(sheets["FP_정통법"], p, std, fp_sum, checks)
    if est:
        cost_cells = _cost(sheets["개발비_기준"], p, est, checks)
        _scenarios(sheets["목표예산_시나리오"], est, cost_cells, checks)
    else:
        not_run(sheets["개발비_기준"], "기준 산정(견적 버전)을 아직 만들지 않았습니다. 'FP·개발비' 단계에서 기준 산정을 실행하세요.")
        not_run(sheets["목표예산_시나리오"], "기준 산정이 없어 목표예산 시나리오를 만들 수 없습니다.")
    _reviews(sheets["검토의견"], p)
    _tech(sheets["HW_SW추천"], p)
    _trace(sheets["근거_변경이력"], p, changes, fp_sum)
    _checks(sheets["검산"], checks)
    meta = {"estimate_id": est.id if est else None, "checks": checks, "fp_summary": {"simple": fp_sum["simple"]["total_fp"], "detailed": fp_sum["detailed"]["total_fp"]}}
    return wb, meta


def to_bytes(wb: Workbook) -> bytes:
    bio = io.BytesIO()
    wb.save(bio)
    return bio.getvalue()


# ---------------------------------------------------------------- 시트별
def _overview(ws, p: Project, fp_sum, est, mode_label: str):
    ov = p.overview
    r = title(ws, f"{p.name} — 사업개요", f"정보화 설계 도우미 산출물 · 생성 모드: {mode_label} · 발주자 검토용 초안")
    header(ws, r, ["항목", "내용"], [28, 100])
    phases = "·".join(PHASE_LABELS[k] for k in PHASE_KEYS if getattr(ov.phases, k)) or "없음"
    rows = [
        ("프로젝트 ID", p.id),
        ("사업명", p.name),
        ("사업 유형", L.BUSINESS_TYPE[ov.business_type]),
        ("시스템 형태", ", ".join(L.SYSTEM_KINDS[k] for k in ov.system_kinds) or "미정"),
        ("시작 방식", L.START_MODE[ov.start_mode]),
        ("처음 구상(원문)", ov.idea_text or "미입력"),
        ("목적", ov.purpose or "미입력"),
        ("추진 배경", ov.background or "미입력"),
        ("이용자", ov.users or "미입력"),
        ("구축 방식", ov.build_method or "미입력"),
        ("사업 기간(개월)", ov.period_months if ov.period_months else "미정"),
        ("금액 조건", L.BUDGET_MODE[ov.budget_mode] + (f" / 목표 {ov.target_amount:,}원 ({'부가세 포함' if ov.target_includes_vat else '부가세 별도'})" if ov.budget_mode == "target" and ov.target_amount else "")),
        ("포함 단계", phases),
        ("기관 환경", ov.org_environment or "미입력"),
        ("FP 측정 대상(애플리케이션 경계)", ov.boundary_name or "미지정(경계 확인 필요)"),
        ("산정 기준 버전", p.cost_settings.standard_id),
        ("장비 구매비", "개발비 합계에서 제외(HW·SW 추천은 설계 보조 정보)"),
        ("항목 출처 구분", _mode_text(p)),
        ("확정 FP(간이법/정통법)", f"{fp_sum['simple']['total_fp']} / {fp_sum['detailed']['total_fp']}" + ("" if fp_sum["detailed"]["complete"] else " (정통법 입력 누락 있음)")),
        ("미확정 FP 항목 수", fp_sum["counts"]["unconfirmed"]),
        ("미분류 FP 항목 수", fp_sum["counts"]["unclassified"]),
        ("미답변 질문 수", sum(1 for q in p.questions if q.status == "open")),
        ("재검토 필요 항목 수", sum(1 for c in ("requirements", "functions", "fp_items") for it in getattr(p, c) if it.needs_review)),
        ("적용 견적 버전", f"{est.id} {est.label} ({est.created_at})" if est else "없음"),
        ("데이터 버전(최종 수정)", p.updated_at),
    ]
    for k, v in rows:
        r += 1
        put(ws, r, 1, k, bold=True)
        put(ws, r, 2, v)
    r += 2
    put(ws, r, 1, "가정 사항", bold=True)
    header(ws, r + 1, ["ID", "가정 내용"])
    r += 1
    if not p.assumptions:
        r += 1
        put(ws, r, 1, "-")
        put(ws, r, 2, "기록된 가정 없음")
    for a in p.assumptions:
        r += 1
        put(ws, r, 1, a.id)
        put(ws, r, 2, f"{a.text} (이유: {a.reason})" if a.reason else a.text)
    page_setup(ws, False)
    ws.freeze_panes = "A5"


def _task(ws, p: Project):
    sections = p.task_draft.sections or build_sections(p)
    sub = "과업지시서 초안(발주자 검토용). " + ("저장된 초안" if p.task_draft.sections else "저장된 초안이 없어 현재 데이터로 자동 구성")
    r = title(ws, f"{p.name} — 과업내용", sub)
    header(ws, r, ["구분", "내용"], [22, 110])
    for s in sections:
        r += 1
        put(ws, r, 1, s.title, bold=True)
        put(ws, r, 2, s.text)
    finish_table(ws, 3 if r > 3 else r, r, 2, landscape=False)


def _requirements(ws, p: Project, fp_sum):
    cov = {x["requirement_id"]: x for x in fp_sum["coverage"]["rows"]}
    srcs = {s.id: s for s in p.sources}
    r = title(ws, "요구사항 목록", "출처 구분: 사용자 / AI 제안 / 샘플 규칙 제안 / 참고문서 추출")
    cols = ["요구사항ID", "구분", "분류", "요구사항명", "사용자 요구 원문", "설명", "우선순위", "검수 기준", "출처", "제안 주체", "상태", "FP 연결", "재검토 필요"]
    header(ws, r, cols, [11, 7, 10, 24, 30, 36, 7, 30, 24, 14, 8, 22, 18])
    h = r
    for q in p.requirements:
        r += 1
        src = "; ".join(f"{srcs[s].file_name} {srcs[s].location}" if s in srcs else s for s in q.source_ids) or "사용자 입력"
        vals = [q.id, L.KIND[q.kind], q.category, q.title, q.original_text, q.description, L.PRIORITY[q.priority], q.acceptance or "검수 기준 미정", src, L.ORIGIN[q.origin], L.STATUS[q.status], cov.get(q.id, {}).get("state", ""), q.review_reason if q.needs_review else ""]
        for i, v in enumerate(vals, 1):
            put(ws, r, i, v)
    finish_table(ws, h, r, len(cols))


def _functions(ws, p: Project):
    r = title(ws, "기능설계", "확인되지 않은 DB·API·기존 시스템 구조는 '확인 필요'로 표시")
    cols = ["기능ID", "기능명", "사용자", "업무 목적", "입력", "출력", "처리 규칙", "예외", "권한", "검수 기준", "요구사항ID", "화면ID", "데이터ID", "연계ID", "제안 주체", "상태"]
    header(ws, r, cols, [9, 20, 12, 24, 22, 22, 30, 22, 16, 24, 14, 12, 12, 10, 14, 8])
    h = r
    for f in p.functions:
        r += 1
        vals = [f.id, f.name, f.actor, f.purpose, f.inputs, f.outputs, f.rules, f.exceptions, f.permissions, f.acceptance or "검수 기준 미정", f.requirement_ids or "요구사항 미연결", f.screen_ids, f.data_ids, f.interface_ids, L.ORIGIN[f.origin], L.STATUS[f.status]]
        for i, v in enumerate(vals, 1):
            put(ws, r, i, v)
    finish_table(ws, h, r, len(cols))


def _design_lists(ws, p: Project):
    r = title(ws, "화면 · 데이터 · 연계 · 업무흐름 목록")
    for i, w in enumerate([10, 24, 16, 40, 20, 18, 16, 14, 10], 1):
        ws.column_dimensions[get_column_letter(i)].width = w
    blocks = [
        ("■ 업무흐름", ["ID", "단계명", "수행자", "설명", "요구사항ID", "상태"], [[w.id, w.name, w.actor, w.description, w.requirement_ids, L.STATUS[w.status]] for w in sorted(p.workflows, key=lambda x: x.order)]),
        ("■ 화면 목록", ["화면ID", "화면명", "이용자", "설명", "기능ID", "상태"], [[s.id, s.name, s.users, s.description, s.function_ids, L.STATUS[s.status]] for s in p.screens]),
        ("■ 데이터 목록·관계", ["데이터ID", "데이터명", "유지 주체", "주요 항목·관계", "기능ID", "개인정보", "보존기간", "상태"], [[d.id, d.name, {"internal": "이 시스템", "external": "외부 시스템", "unknown": "확인 필요"}[d.maintained_by], f"{d.attributes}\n관계: {d.relations}" if d.relations else d.attributes, d.function_ids, d.personal_info, d.retention or "미정", L.STATUS[d.status]] for d in p.data_entities]),
        ("■ 연계 목록", ["연계ID", "연계명", "상대 시스템", "방식·주기", "데이터 항목", "방향", "기관 확인", "기능ID", "상태"], [[i.id, i.name, i.counterpart, f"{i.method} / {i.frequency}", i.data_items, {"inbound": "수신", "outbound": "송신", "both": "양방향", "unknown": "확인 필요"}[i.direction], {"unverified": "미확인(연계 가능성 확인 필요)", "confirmed_by_org": "기관 확인", "confirmed_by_counterpart": "상대기관 확인"}[i.verified], i.function_ids, L.STATUS[i.status]] for i in p.interfaces]),
    ]
    first_header = None
    for name, cols, rows in blocks:
        put(ws, r, 1, name, bold=True)
        r += 1
        header(ws, r, cols)
        first_header = first_header or r
        if not rows:
            r += 1
            put(ws, r, 1, "-")
            put(ws, r, 2, "등록된 항목 없음")
        for row in rows:
            r += 1
            for i, v in enumerate(row, 1):
                put(ws, r, i, v)
        r += 2
    page_setup(ws, True)
    ws.freeze_panes = "B3"


def _weight_formula(type_cell: str) -> str:
    return f'=IF({type_cell}="EI",4,IF({type_cell}="EO",5.2,IF({type_cell}="EQ",3.9,IF({type_cell}="ILF",7.5,IF({type_cell}="EIF",5.4,0)))))'


def _fp_simple(ws, p: Project, std, fp_sum, checks):
    items = {it.id: it for it in p.fp_items}
    r = title(ws, "기능점수 산정(간이법)", f"기준: {std['id']} · 가중치 ILF 7.5 / EIF 5.4 / EI 4.0 / EO 5.2 / EQ 3.9 (산정양식 수식) · '집계'=확정·경계 내 항목만")
    cols = ["FP ID", "애플리케이션", "세부 업무", "단위프로세스·데이터명", "설명", "FP 유형", "분류 근거", "요구사항ID", "상태", "집계", "가중치(수식)", "가중치(Python)", "점수(수식)", "점수(Python)", "확인 사항"]
    header(ws, r, cols, [9, 14, 14, 24, 26, 9, 30, 13, 8, 6, 10, 10, 10, 10, 40])
    h = r
    first = r + 1
    for row in fp_sum["items"]:
        r += 1
        it = items[row["id"]]
        typ = row["fp_type"] or "미분류"
        vals = [it.id, it.application, it.business, it.name, it.description, typ, it.rationale or "근거 미기재", it.requirement_ids, L.STATUS[it.status], "Y" if row["counted"] else "N"]
        for i, v in enumerate(vals, 1):
            put(ws, r, i, v)
        put(ws, r, 11, _weight_formula(f"F{r}"), fmt="0.0", formula=True)
        put(ws, r, 12, Decimal(row["simple_weight"]) if row["simple_weight"] else 0, fmt="0.0")
        put(ws, r, 13, f'=IF(J{r}="Y",K{r},0)', fmt="0.0", formula=True)
        put(ws, r, 14, Decimal(row["simple_weight"]) if row["counted"] and row["simple_weight"] else 0, fmt="0.0")
        put(ws, r, 15, "\n".join(row["issues"]))
    last = r
    r += 1
    put(ws, r, 12, "합계(확정)", bold=True)
    put(ws, r, 13, f"=SUM(M{first}:M{last})" if last >= first else "=0", fmt="0.0", formula=True)
    put(ws, r, 14, Decimal(fp_sum["simple"]["total_fp"]), fmt="0.0", bold=True)
    checks.append({"label": "간이법 총 FP", "sheet": ws.title, "formula_cell": f"M{r}", "python": float(Decimal(fp_sum["simple"]["total_fp"])), "fmt": "0.0"})
    r += 2
    put(ws, r, 1, "유형별 집계", bold=True)
    r += 1
    header(ws, r, ["유형", "기능 수", "FP(Python)", "FP(수식)", "설명"])
    for t in ("ILF", "EIF", "EI", "EO", "EQ"):
        r += 1
        bt = fp_sum["simple"]["by_type"][t]
        put(ws, r, 1, t)
        put(ws, r, 2, bt["count"])
        put(ws, r, 3, Decimal(bt["fp"]), fmt="0.0")
        put(ws, r, 4, f'=SUMIFS(M{first}:M{max(last, first)},F{first}:F{max(last, first)},"{t}")', fmt="0.0", formula=True)
        put(ws, r, 5, L.FP_TYPE_DESC[t])
    finish_table(ws, h, last, len(cols))


def _detailed_weight_formula(t: str, cx: str) -> str:
    return (
        f'=IF({cx}="","",IF({t}="EI",CHOOSE(MATCH({cx},{{"L","A","H"}},0),3,4,6),'
        f'IF({t}="EO",CHOOSE(MATCH({cx},{{"L","A","H"}},0),4,5,7),'
        f'IF({t}="EQ",CHOOSE(MATCH({cx},{{"L","A","H"}},0),3,4,6),'
        f'IF({t}="ILF",CHOOSE(MATCH({cx},{{"L","A","H"}},0),7,10,15),'
        f'IF({t}="EIF",CHOOSE(MATCH({cx},{{"L","A","H"}},0),5,7,10),0))))))'
    )


def _fp_detailed(ws, p: Project, std, fp_sum, checks):
    items = {it.id: it for it in p.fp_items}
    d = fp_sum["detailed"]
    sub = f"기준: {std['id']} · 복잡도는 산정양식 VBA FPR() 표, 가중치는 FPV() 표 · " + ("모든 집계 항목 입력 완료" if d["complete"] else f"입력 누락 {len(d['missing_ids'])}건 → 정통법 미확정")
    r = title(ws, "기능점수 산정(정통법)", sub)
    cols = ["FP ID", "단위프로세스·데이터명", "FP 유형", "FTR/RET", "DET", "복잡도", "복잡도 판정", "상태", "집계", "가중치(수식)", "가중치(Python)", "점수(수식)", "점수(Python)", "누락 정보·가정"]
    header(ws, r, cols, [9, 26, 9, 9, 7, 8, 14, 8, 6, 11, 11, 10, 10, 44])
    h = r
    first = r + 1
    for row in fp_sum["items"]:
        r += 1
        it = items[row["id"]]
        missing = []
        if row["fp_type"] and row["complexity_source"] == "missing":
            missing.append(next((i for i in row["issues"] if i.startswith("정통법 미확정")), "입력 누락"))
        if row["complexity_source"] == "assumed":
            missing.append(f"가정: {it.assumption_note or '사유 미기재'}")
        vals = [it.id, it.name, row["fp_type"] or "미분류", it.ftr_ret if it.ftr_ret is not None else "미입력", it.det if it.det is not None else "미입력", row["complexity"] or "", L.CX_SOURCE[row["complexity_source"]], L.STATUS[it.status], "Y" if row["counted"] else "N"]
        for i, v in enumerate(vals, 1):
            put(ws, r, i, v)
        put(ws, r, 10, _detailed_weight_formula(f"C{r}", f"F{r}"), formula=True)
        put(ws, r, 11, row["detailed_weight"] if row["detailed_weight"] is not None else "")
        put(ws, r, 12, f'=IF(AND(I{r}="Y",ISNUMBER(J{r})),J{r},0)', formula=True)
        put(ws, r, 13, row["detailed_weight"] if row["counted"] and row["detailed_weight"] is not None else 0)
        put(ws, r, 14, "\n".join(missing) or "-")
    last = r
    r += 1
    put(ws, r, 11, "합계(확정·입력완료)", bold=True)
    put(ws, r, 12, f"=SUM(L{first}:L{last})" if last >= first else "=0", formula=True)
    put(ws, r, 13, int(d["total_fp"]), bold=True)
    checks.append({"label": "정통법 총 FP", "sheet": ws.title, "formula_cell": f"L{r}", "python": int(d["total_fp"]), "fmt": "0"})
    r += 1
    put(ws, r, 1, "정통법 상태", bold=True)
    put(ws, r, 2, "확정 가능" if d["complete"] else f"미확정 — 누락 {', '.join(d['missing_ids'])}")
    finish_table(ws, h, last, len(cols))


def _round_formula(expr: str, unit: int, mode: str) -> str:
    if mode == "down":
        return f"ROUNDDOWN(({expr})/{unit},0)*{unit}"
    return f"ROUND(({expr})/{unit},0)*{unit}"


def _cost(ws, p: Project, est: EstimateVersion, checks) -> dict[str, str]:
    m = est.result["money"]
    std = est.standard_snapshot
    state = estimate_state(p, est)
    sub = f"견적 버전 {est.id} '{est.label}' ({est.created_at}) · 방법: {L.METHOD[est.method]} · 기준: {std.get('id')} · " + ("현재 데이터와 일치" if state == "current" else "※ 이후 FP·설정이 바뀜: 갱신 필요")
    r = title(ws, "개발비 산정(기준 산정)", sub)
    header(ws, r, ["구분", "값(수식)", "Python 확인값", "근거·설명"], [30, 20, 20, 80])
    cells: dict[str, str] = {}
    if not m.get("complete"):
        r += 1
        c = put(ws, r, 1, "미완료 견적")
        c.font = WARN_FONT
        put(ws, r, 4, "\n".join(est.warnings))
        page_setup(ws, False)
        return cells

    def row(key: str, label: str, formula: str | None, py: Any, fmt: str, note: str):
        nonlocal r
        r += 1
        put(ws, r, 1, label, bold=True)
        if formula is not None:
            put(ws, r, 2, formula, fmt=fmt, formula=True)
        else:
            put(ws, r, 2, py, fmt=fmt)
        put(ws, r, 3, py, fmt=fmt)
        put(ws, r, 4, note)
        cells[key] = f"B{r}"
        return f"B{r}"

    fp_cell = row("fp", "총 기능점수(FP)", None, Decimal(m["total_fp"]), "0.0#", f"{L.METHOD[est.method]} 확정 항목 {len(est.fp_snapshot)}건 합계(FP 시트 참조)")
    price_cell = row("price", "FP당 단가(원)", None, m["unit_price"], WON, std["unit_price"]["basis"] + (" / 사용자 입력 단가" if m.get("unit_price_source") == "user" else ""))
    sz = row("size", "규모 보정계수", f"=IF({fp_cell}<500,1.28,IF({fp_cell}>3000,1.153,0.4057*(LN({fp_cell})-7.1978)^2+0.8878))", Decimal(m["size_factor"]), RATIO, std["size_factor"]["basis"])
    fcells = []
    for f in m["factors"]:
        fcells.append(row(f["key"], f"{f['label']} 보정계수", None, Decimal(f["value"]), RATIO, f"수준 {f['level']}: {f['level_text']}"))
    pm = row("phase", "단계 비율", None, Decimal(m["phase_multiplier"]), RATIO, m["phase_text"])
    raw = row("dev_raw", "개발원가(보정 후, 끝수 처리 전)", f"={fp_cell}*{price_cell}*{sz}*" + "*".join(fcells) + f"*{pm}", Decimal(m["dev_cost_raw"]), WON_DEC, "총FP × 단가 × 규모 × 연계 × 성능 × 운영환경 × 보안 × 단계비율")
    unit, mode = m["rounding"]["unit"], m["rounding"]["mode"]
    dev = row("dev", "개발원가", "=" + _round_formula(raw, unit, mode), m["dev_cost"], WON, f"끝수 처리: {m['rounding']['label']} (시스템 설정, 공식 규정 미확인)")
    pr = row("profit_rate", "이윤율", None, Decimal(m["profit_rate"]), "0.00%", std["profit_rate"]["basis"])
    profit = row("profit", "이윤", "=" + _round_formula(f"{dev}*{pr}", unit, mode), m["profit"], WON, "개발원가 × 이윤율")
    direct = row("direct", "직접경비", None, m["direct_total"], WON, "; ".join(f"{d['name']} {d['amount']:,}원({d['basis']})" for d in m["direct_expenses"]) or "없음 (장비 구매비 제외)")
    supply = row("supply", "SW개발비(부가세 별도)", f"={dev}+{profit}+{direct}", m["supply"], WON, "개발원가 + 이윤 + 직접경비")
    vr = row("vat_rate", "부가가치세율", None, Decimal(m["vat_rate"]), "0%", std["vat_rate"]["basis"])
    vat = row("vat", "부가가치세", "=" + _round_formula(f"{supply}*{vr}", unit, mode), m["vat"], WON, f"끝수 처리: {m['rounding']['label']}")
    total = row("total", "총액(부가세 포함)", f"={supply}+{vat}", m["total"], WON, "장비 구매비·별도 유료 SW는 포함하지 않음")
    for key, label in (("size", "규모 보정계수"), ("dev_raw", "개발원가(끝수 전)"), ("dev", "개발원가"), ("profit", "이윤"), ("supply", "SW개발비(VAT 별도)"), ("vat", "부가세"), ("total", "총액")):
        cell = cells[key]
        pyc = "C" + cell[1:]
        checks.append({"label": f"개발비 {label}", "sheet": ws.title, "formula_cell": cell, "python_cell": pyc, "python": None, "fmt": WON_DEC if key in ("dev_raw", "size") else WON})
    r += 2
    put(ws, r, 1, "계산 근거", bold=True)
    for line in m["basis"]:
        r += 1
        put(ws, r, 1, "")
        put(ws, r, 4, line)
    if est.warnings:
        r += 2
        put(ws, r, 1, "주의 사항", bold=True).font = WARN_FONT
        for w in est.warnings:
            r += 1
            put(ws, r, 4, w)
    page_setup(ws, False)
    ws.freeze_panes = "A4"
    return cells


def _scenarios(ws, est: EstimateVersion, cost_cells: dict[str, str], checks):
    if not est.scenarios:
        not_run(ws, f"견적 {est.id}에 목표예산 시나리오가 없습니다(예산 미지정 또는 미실행).")
        return
    r = title(ws, "목표예산 시나리오(참고 견적)", "공식 측정 FP가 아닌 예산 대응 참고값 · 기준 FP·분류·가중치·요구 기능은 변경하지 않음")
    header(ws, r, ["구분", "값(수식)", "Python 확인값", "설명"], [32, 20, 20, 80])
    base = "'개발비_기준'!"
    for sc in est.scenarios:
        res = sc.result
        r += 1
        put(ws, r, 1, f"■ {sc.id} ({sc.created_at})", bold=True)
        put(ws, r, 4, res["method_text"])

        def row(label, formula, py, fmt, note=""):
            nonlocal r
            r += 1
            put(ws, r, 1, label, bold=True)
            if formula:
                put(ws, r, 2, formula, fmt=fmt, formula=True)
            else:
                put(ws, r, 2, py, fmt=fmt)
            put(ws, r, 3, py, fmt=fmt)
            put(ws, r, 4, note)
            return f"B{r}"

        tgt = row("목표 금액", None, res["target_amount"], WON, "부가세 포함" if res["target_includes_vat"] else "부가세 별도")
        btot = row("기준 산정 총액", f"={base}{cost_cells['total']}" if "total" in cost_cells else None, res["base_total"], WON, f"견적 {est.id}")
        row("차이(시나리오 총액 − 기준 총액)", None, res["difference_total"], WON)
        sup = row("목표 공급가액(부가세 별도)", None, res["supply"], WON, "부가세 포함 목표액에서 역산" if res["target_includes_vat"] else "")
        dirc = row("직접경비", None, res["direct_total"], WON, "기준과 동일")
        ratio = row("조정률 r", f"=(({sup}-{dirc})/(1+{base}{cost_cells['profit_rate']}))/{base}{cost_cells['dev_raw']}", Decimal(res["adjustment_ratio"]), "0.000000", "(목표 공급가액 − 직접경비) ÷ (1+이윤율) ÷ 기준 개발원가(끝수 전)")
        row("기준 FP(공식 측정, 변경 없음)", f"={base}{cost_cells['fp']}", Decimal(res["base_total_fp"]), "0.0#", "기준 FP 보존")
        row("예산 대응 환산 FP(참고값)", f"={base}{cost_cells['fp']}*{ratio}", Decimal(res["equivalent_fp"]), "0.00", "공식 측정 FP 아님")
        row("예산 대응 환산 FP당 단가(참고값)", f"={base}{cost_cells['price']}*{ratio}", Decimal(res["equivalent_unit_price"]), WON_DEC, "공식 단가 아님")
        row("조정 개발원가", None, res["dev_cost"], WON)
        row("조정 이윤", None, res["profit"], WON)
        row("끝수조정(원 단위 일치용)", None, res["rounding_adjustment"], WON, "가상의 비용 항목이 아니라 원 단위 합계를 맞추기 위한 표시")
        row("공급가액 합계", None, res["supply"], WON)
        row("부가가치세", None, res["vat"], WON)
        tot = row("최종 참고 금액(부가세 포함)", f"={sup}+B{r}", res["total"], WON, ("목표액과 일치" if res["matches_target"] else f"목표액과 {res['vat_residual']:+,}원 차이(부가세 끝수)"))
        checks.append({"label": f"{sc.id} 조정률", "sheet": ws.title, "formula_cell": ratio, "python_cell": "C" + ratio[1:], "python": None, "fmt": "0.000000"})
        checks.append({"label": f"{sc.id} 최종 참고 금액", "sheet": ws.title, "formula_cell": tot, "python_cell": "C" + tot[1:], "python": None, "fmt": WON})
        r += 1
        put(ws, r, 1, "기능 유지 확인")
        put(ws, r, 4, f"시나리오 FP 항목 {len(sc.fp_ids)}건 = 기준 견적 FP 항목 {len(est.fp_snapshot)}건 ({'동일' if sorted(sc.fp_ids) == sorted(x['id'] for x in est.fp_snapshot) else '불일치'})")
        for w in res["warnings"]:
            r += 1
            put(ws, r, 4, "※ " + w)
        r += 1
    page_setup(ws, False)


def _reviews(ws, p: Project):
    if not p.review_run.ran_at:
        not_run(ws, "기존 문서 검토를 실행하지 않았습니다.")
        return
    r = title(ws, "검토의견", f"실행 {p.review_run.ran_at} · 대상 문서 {', '.join(p.review_run.document_ids)} · 자료 일치 검토이며 실제 시스템 성능·연계·보안 검증이 아님")
    cols = ["ID", "검토 분야", "판정", "근거 위치", "원문 값", "비교 값", "판단 이유", "수정안", "업체 확인 질문", "검증 범위"]
    header(ws, r, cols, [8, 16, 10, 26, 22, 22, 36, 30, 30, 18])
    h = r
    for f in p.reviews:
        r += 1
        vals = [f.id, f.category, L.VERDICT[f.verdict], f.location, f.original_value, f.compared_value, f.reason, f.suggestion, f.question_to_vendor, "자료 일치 검토" if f.doc_check_only else "문서로 확정 불가(실제 검증 필요)"]
        for i, v in enumerate(vals, 1):
            put(ws, r, i, v)
    if not p.reviews:
        r += 1
        put(ws, r, 1, "-")
        put(ws, r, 7, "검토 결과 지적 사항 없음")
    finish_table(ws, h, r, len(cols))


def _tech(ws, p: Project):
    t = p.tech
    if not t.ran_at:
        not_run(ws, "HW·SW 구성 추천을 실행하지 않았습니다.")
        return
    srcs = {s.id: s for s in p.official_sources}
    r = title(ws, "HW·SW 구성 추천", f"실행 {t.ran_at} · {t.mode} · 입력 가정 기반 초안이며 성능·용량을 보장하지 않음 · 장비·유료 SW 비용은 개발비에 미포함")
    cols = ["ID", "분야", "구성안", "선정 이유", "가정·제약", "대안", "호환성", "라이선스", "지원 상태", "운영 난도", "공식 출처·확인일", "별도 비용"]
    header(ws, r, cols, [8, 12, 34, 30, 30, 24, 20, 16, 20, 10, 36, 10])
    h = r
    for rec in t.recommendations:
        r += 1
        src_txt = "\n".join(f"{srcs[s].title} {srcs[s].url} (확인일 {srcs[s].checked_at or '미확인'}, {srcs[s].support_status or '상태 미확인'})" for s in rec.official_source_ids if s in srcs) or "공식 출처 미등록 — 현재 상태 미확인"
        vals = [rec.id, rec.area, rec.proposal, rec.reason, rec.assumptions, rec.alternatives, rec.compatibility, rec.license, rec.support_status, rec.ops_difficulty, src_txt, "별도 비용(개발비 미합산)" if rec.paid_item else "-"]
        for i, v in enumerate(vals, 1):
            put(ws, r, i, v)
    finish_table(ws, h, r, len(cols))


def _trace(ws, p: Project, changes: list[dict[str, Any]], fp_sum):
    r = title(ws, "근거 · 변경이력 · 미확정 사항")
    for i, w in enumerate([12, 16, 14, 14, 40, 40, 24, 10], 1):
        ws.column_dimensions[get_column_letter(i)].width = w
    put(ws, r, 1, "■ 원문 출처", bold=True)
    r += 1
    header(ws, r, ["출처ID", "문서ID", "파일명", "위치", "원문 발췌", "추출 상태"])
    h = r
    for s in p.sources:
        r += 1
        for i, v in enumerate([s.id, s.document_id, s.file_name, s.location, s.excerpt[:500], s.extraction_status], 1):
            put(ws, r, i, v)
    if not p.sources:
        r += 1
        put(ws, r, 1, "-")
        put(ws, r, 5, "참고문서 출처 없음")
    r += 2
    put(ws, r, 1, "■ 참고문서 대비 변경 내역", bold=True)
    r += 1
    header(ws, r, ["항목ID", "문서ID", "결정", "위치", "원문", "변경 내용·이유", "기관 고유 조건", "반영 요구사항"])
    for ref in p.reference_items:
        r += 1
        dec = {"pending": "결정 대기", "keep": "유지", "modify": "수정", "exclude": "제외"}[ref.decision]
        for i, v in enumerate([ref.id, ref.document_id, dec, ref.location, ref.text, f"{ref.modified_text} / 이유: {ref.reason}" if ref.decision == "modify" else ref.reason, ref.org_specific, ref.applied_requirement_id], 1):
            put(ws, r, i, v)
    r += 2
    put(ws, r, 1, "■ 미확정 사항", bold=True)
    r += 1
    header(ws, r, ["구분", "ID", "내용"])
    pend = []
    pend += [("미답변 질문", q.id, q.text) for q in p.questions if q.status == "open"]
    pend += [("나중에 결정", q.id, f"{q.text} → 권장안: {q.recommended_value} ({q.recommended_reason})") for q in p.questions if q.status == "deferred"]
    pend += [("미확정 FP", i, "확정 전 기준 견적 제외") for i in fp_sum["unconfirmed_ids"]]
    pend += [("미분류 FP", i, "FP 유형 미지정") for i in fp_sum["unclassified_ids"]]
    pend += [("FP 미연결 요구사항", i, "기능 요구사항에 연결된 FP 없음") for i in fp_sum["coverage"]["unlinked_functional"]]
    pend += [("재검토 필요", it.id, it.review_reason) for c in ("requirements", "functions", "fp_items", "screens", "data_entities", "interfaces") for it in getattr(p, c) if it.needs_review]
    pend += [("연계 미확인", i.id, f"{i.name}: 상대 시스템 연계 가능성 미확인") for i in p.interfaces if i.verified == "unverified"]
    for kind, iid, text in pend or [("-", "-", "미확정 사항 없음")]:
        r += 1
        for i, v in enumerate([kind, iid, text], 1):
            put(ws, r, i, v)
    r += 2
    put(ws, r, 1, "■ 변경 이력(최근 300건)", bold=True)
    r += 1
    header(ws, r, ["시각", "주체", "대상", "ID", "변경 전", "변경 후", "영향 항목", "재검토"])
    for c in changes[:300]:
        r += 1
        vals = [c["at"], L.ORIGIN.get(c["actor"], c["actor"]), c["collection"], c["item_id"], _short(c["before"]), _short(c["after"]), c["affected"], "필요" if c["needs_review"] else ""]
        for i, v in enumerate(vals, 1):
            put(ws, r, i, v)
    ws.freeze_panes = ws.cell(row=h + 1, column=1)
    page_setup(ws, True)


def _short(v: Any) -> str:
    if v is None:
        return ""
    s = str(v)
    return s if len(s) <= 400 else s[:400] + "…"


def _checks(ws, checks: list[dict[str, Any]]):
    r = title(ws, "검산 — Excel 수식값과 Python 계산값 비교", "수식은 Excel에서 열 때 다시 계산됩니다. '차이'가 0이 아니면 산출물을 사용하지 말고 확인하세요.")
    header(ws, r, ["항목", "시트", "수식 셀 값", "Python 확인값", "차이", "판정"], [30, 18, 20, 20, 16, 14])
    h = r
    for c in checks:
        r += 1
        put(ws, r, 1, c["label"])
        put(ws, r, 2, c["sheet"])
        put(ws, r, 3, f"='{c['sheet']}'!{c['formula_cell']}", fmt=c.get("fmt"), formula=True)
        if c.get("python_cell"):
            put(ws, r, 4, f"='{c['sheet']}'!{c['python_cell']}", fmt=c.get("fmt"), formula=True)
        else:
            put(ws, r, 4, c["python"], fmt=c.get("fmt"))
        put(ws, r, 5, f"=C{r}-D{r}", fmt="0.000000", formula=True)
        put(ws, r, 6, f'=IF(ABS(E{r})<0.005,"일치","불일치")', formula=True)
    finish_table(ws, h, r, 6, landscape=False)


# ---------------------------------------------------------------- 미리보기
def preview(wb: Workbook, max_rows: int = 200) -> list[dict[str, Any]]:
    out = []
    for ws in wb.worksheets:
        rows = []
        for row in ws.iter_rows(min_row=1, max_row=min(ws.max_row, max_rows)):
            vals = []
            for c in row:
                v = c.value
                if isinstance(v, str) and c.data_type == "f":
                    v = {"formula": v}
                vals.append(v)
            while vals and vals[-1] in (None, ""):
                vals.pop()
            rows.append(vals)
        out.append({"name": ws.title, "rows": rows, "truncated": ws.max_row > max_rows, "total_rows": ws.max_row})
    return out
