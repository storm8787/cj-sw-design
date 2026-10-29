"""샘플 프로젝트(가상 데이터). 화면·엑셀에 '샘플'로 표시된다. 실제 사업 데이터가 아니다."""
from __future__ import annotations

from typing import Any

from ..models import Project
from ..store import Mutation, add_item

SAMPLES: dict[str, dict[str, Any]] = {
    "education": {
        "name": "[샘플] 직원 교육 신청·관리 시스템",
        "overview": {
            "business_type": "system",
            "start_mode": "idea",
            "budget_mode": "none",
            "idea_text": "직원 교육 신청·관리 프로그램이 필요하다.",
            "purpose": "직원 교육 신청·승인·대기자·이수 통계를 전산화하여 수작업(엑셀·전화)을 줄인다.",
            "background": "교육 신청을 메일과 엑셀로 받아 정원 관리·대기자 연락에 담당자 시간이 많이 든다.",
            "users": "본청·사업소 직원(약 1,200명), 교육 담당자 3명",
            "build_method": "외주 신규개발",
            "period_months": 5,
            "org_environment": "내부망 웹, 기존 인사시스템 운영 중",
            "system_kinds": ["web", "integration"],
            "boundary_name": "교육관리시스템",
        },
        "requirements": [
            dict(kind="functional", title="교육과정 등록·관리", original_text="교육과정을 담당자가 등록하고 고칠 수 있어야 함", description="담당자는 교육과정(과정명, 일정, 장소, 정원, 신청기간)을 등록·수정·삭제한다.", priority="high", acceptance="과정 등록·수정·삭제가 목록에 즉시 반영됨"),
            dict(kind="functional", title="교육 신청", original_text="직원이 직접 신청", description="직원은 신청기간 내 과정에 신청한다. 정원 초과 시 대기자로 접수된다.", priority="high", acceptance="신청 시 정원 내 '신청완료', 초과 시 '대기' 상태로 저장"),
            dict(kind="functional", title="신청 취소", original_text="교육 전까지 취소 가능", description="직원은 교육 시작 전까지 본인 신청을 취소한다.", priority="high", acceptance="교육 시작 이후에는 취소 불가 메시지"),
            dict(kind="functional", title="신청 승인·반려", original_text="담당자 승인", description="담당자는 신청을 승인·반려하고 사유를 기록한다.", priority="high", acceptance="반려 시 사유 필수"),
            dict(kind="functional", title="대기자 자동 승계", original_text="취소되면 대기자가 올라가야 함", description="취소·반려로 자리가 나면 대기 1순위를 신청완료로 승계한다.", priority="medium", acceptance="취소 직후 대기 1순위 상태 변경 확인"),
            dict(kind="functional", title="신청 내역 조회", original_text="내 신청 현황 보기", description="직원은 본인 신청 내역과 상태를 조회한다.", priority="medium", acceptance="본인 신청만 조회됨"),
            dict(kind="functional", title="교육 통계", original_text="과정별 통계", description="과정별 신청·승인·이수 인원과 이수율을 집계한다.", priority="medium", acceptance="이수율=이수인원/승인인원 계산값 확인"),
            dict(kind="functional", title="인사시스템 직원정보 참조", original_text="직원정보는 인사시스템 것 사용", description="직원 소속·직급은 인사시스템 데이터를 참조한다(연계 방식 확인 필요).", priority="medium", acceptance="신청 화면에 소속·직급 자동 표시"),
            dict(kind="nonfunctional", category="보안", title="개인정보 보호", description="개인정보 암호화 저장, 접근기록 1년 보관", priority="high", acceptance="DB 암호화 확인, 접근기록 조회"),
            dict(kind="nonfunctional", category="성능", title="응답 시간", description="신청기간 첫날 동시 200명 접속 시 주요 화면 3초 이내 응답", priority="medium", acceptance="부하시험 결과서로 확인"),
            dict(kind="nonfunctional", category="접근성", title="웹 접근성", description="한국형 웹 콘텐츠 접근성 지침 준수", priority="medium", acceptance="접근성 점검 결과"),
        ],
        "data": [
            dict(name="교육과정 정보", description="과정명·일정·장소·정원·신청기간", attributes="과정ID, 과정명, 시작일, 종료일, 장소, 정원, 신청시작, 신청마감 등 15개 항목", maintained_by="internal"),
            dict(name="교육 신청 정보", description="신청·승인·대기·이수 이력", attributes="신청ID, 과정ID, 직원번호, 상태, 대기순번, 승인자, 반려사유 등 22개 항목, 하위 그룹: 승인이력", relations="교육과정 1:N 교육신청", maintained_by="internal", personal_info=True, retention="5년"),
            dict(name="직원 정보(인사시스템)", description="인사시스템이 유지하는 직원 소속·직급", attributes="직원번호, 성명, 소속, 직급 등 8개 항목", maintained_by="external", personal_info=True),
        ],
        "interfaces": [dict(name="인사시스템 직원정보 조회", counterpart="인사시스템", direction="inbound", method="확인 필요(API 또는 DB 뷰)", data_items="직원번호, 성명, 소속, 직급", frequency="실시간 조회 또는 일 1회")],
        "functions": [
            dict(name="교육과정 관리", actor="교육 담당자", purpose="과정 등록·수정·삭제", inputs="과정명, 일정, 장소, 정원, 신청기간", outputs="과정 목록", rules="신청기간은 교육 시작일 이전", exceptions="신청자가 있는 과정은 삭제 대신 폐강 처리", permissions="담당자", req=[0], dat=[0]),
            dict(name="교육 신청·취소", actor="직원", purpose="과정 신청과 취소", inputs="과정 선택", outputs="신청 결과(신청완료/대기)", rules="정원 초과 시 대기 순번 부여, 교육 시작 전까지 취소", exceptions="중복 신청 불가", permissions="본인", req=[1, 2], dat=[1, 2]),
            dict(name="신청 승인·대기자 승계", actor="교육 담당자", purpose="승인·반려, 대기자 승계", inputs="승인/반려, 사유", outputs="처리 결과", rules="자리 발생 시 대기 1순위 자동 승계", exceptions="반려 사유 필수", permissions="담당자", req=[3, 4], dat=[1]),
            dict(name="신청 내역 조회", actor="직원", purpose="본인 신청 현황 확인", inputs="기간", outputs="신청 목록·상태", rules="본인 것만", exceptions="", permissions="본인", req=[5], dat=[1]),
            dict(name="교육 통계", actor="교육 담당자", purpose="과정별 집계", inputs="기간, 과정", outputs="신청·승인·이수 인원, 이수율", rules="이수율 = 이수/승인", exceptions="승인 0명이면 이수율 '-'", permissions="담당자", req=[6], dat=[0, 1]),
        ],
        # (이름, 유형, FTR/RET, DET, 요구사항 index, 데이터 index, 상태, 근거)
        "fp": [
            ("교육과정 정보", "ILF", 1, 15, [0], [0], "confirmed", "담당자가 등록·수정하며 이 시스템이 유지하는 논리 데이터"),
            ("교육 신청 정보", "ILF", 2, 22, [1, 2, 3, 4], [1], "confirmed", "신청·승인 이력을 이 시스템이 유지(하위 그룹 승인이력 → RET 2)"),
            ("직원 정보", "EIF", 1, 8, [7], [2], "confirmed", "인사시스템이 유지, 이 시스템은 참조만"),
            ("교육과정 등록", "EI", 1, 12, [0], [0], "confirmed", "외부 입력으로 ILF(교육과정) 등록"),
            ("교육과정 수정", "EI", 1, 12, [0], [0], "confirmed", "ILF 갱신"),
            ("교육과정 삭제", "EI", 1, 2, [0], [0], "confirmed", "ILF 삭제(폐강 처리)"),
            ("교육 신청", "EI", 3, 10, [1], [1], "confirmed", "신청 ILF 등록, 과정·직원정보 참조(FTR 3)"),
            ("신청 취소", "EI", 2, 4, [2], [1], "confirmed", "신청 상태 변경"),
            ("신청 승인·반려", "EI", 2, 6, [3], [1], "confirmed", "상태·사유 갱신"),
            ("대기자 자동 승계", "EI", 2, 5, [4], [1], "confirmed", "자리 발생 시 대기자 상태 갱신(별도 처리 로직)"),
            ("신청 내역 조회", "EQ", 2, 9, [5], [1], "confirmed", "가공 없이 신청 데이터 조회"),
            ("교육 통계", "EO", 2, 8, [6], [0, 1], "confirmed", "이수율 계산 등 가공 로직 포함 출력"),
            ("교육과정 목록 조회", "EQ", 1, 10, [1], [0], "confirmed", "과정 목록 단순 조회"),
            ("(관리자) 신청 내역 조회", "EQ", None, None, [5], [1], "review", "관리자 화면의 조회 — 직원 조회와 처리·데이터 차이 확인 필요"),
        ],
    },
    "complaint": {
        "name": "[샘플] 민원 접수·처리 및 야간 배치 연계 시스템",
        "overview": {
            "business_type": "portal",
            "start_mode": "idea",
            "budget_mode": "target",
            "target_amount": 80000000,
            "target_includes_vat": True,
            "idea_text": "홈페이지 민원 접수와 담당부서 처리, 야간에 행정시스템으로 결과를 넘기는 배치가 필요하다.",
            "purpose": "온라인 민원 접수·처리 상태를 공개하고 행정시스템과 자동 연계한다.",
            "users": "시민(비회원 포함), 부서 민원담당 약 80명",
            "system_kinds": ["web", "batch", "integration"],
            "boundary_name": "민원포털",
            "period_months": 6,
        },
        "requirements": [
            dict(kind="functional", title="민원 신청", description="시민이 본인확인 후 민원을 신청하고 첨부파일을 올린다.", priority="high"),
            dict(kind="functional", title="담당부서 배정", description="접수 민원을 담당부서에 배정·재배정한다.", priority="high"),
            dict(kind="functional", title="처리 결과 등록", description="담당자가 처리 결과를 등록한다.", priority="high"),
            dict(kind="functional", title="처리 현황 조회", description="시민이 접수번호로 처리 상태를 조회한다.", priority="medium"),
            dict(kind="functional", title="야간 결과 전송 배치", description="매일 02시 처리 완료 건을 행정시스템으로 전송, 실패 건 재전송", priority="high"),
            dict(kind="functional", title="처리기한 초과 현황 보고", description="부서별 처리기한 초과 건수와 평균 처리일수를 집계한다.", priority="medium"),
            dict(kind="nonfunctional", category="가용성", title="배치 실패 알림", description="배치 실패 시 담당자 알림", priority="medium"),
        ],
        "data": [
            dict(name="민원 정보", attributes="접수번호, 신청인, 내용, 첨부, 상태 등 30개 항목", maintained_by="internal", personal_info=True),
            dict(name="부서 배정 정보", attributes="배정ID, 부서, 담당자, 기한 등 9개 항목", maintained_by="internal"),
            dict(name="조직 정보(행정시스템)", attributes="부서코드, 부서명 등 6개 항목", maintained_by="external"),
        ],
        "interfaces": [dict(name="행정시스템 처리결과 전송", counterpart="행정시스템", direction="outbound", method="확인 필요(파일 또는 API)", frequency="일 1회 02시")],
        "functions": [],
        "fp": [
            ("민원 정보", "ILF", 2, 30, [0, 2], [0], "confirmed", "이 시스템이 유지"),
            ("부서 배정 정보", "ILF", 1, 9, [1], [1], "confirmed", "이 시스템이 유지"),
            ("조직 정보", "EIF", 1, 6, [1], [2], "confirmed", "행정시스템 유지"),
            ("민원 신청", "EI", 1, 18, [0], [0], "confirmed", "민원 등록"),
            ("부서 배정", "EI", 3, 7, [1], [1], "confirmed", "배정 등록, 조직정보 참조"),
            ("처리 결과 등록", "EI", 2, 8, [2], [0], "confirmed", "민원 갱신"),
            ("처리 현황 조회", "EQ", 1, 6, [3], [0], "confirmed", "단순 조회"),
            ("처리결과 전송 배치", "EO", 2, 12, [4], [0, 1], "confirmed", "추출·변환 후 외부로 전송(가공 로직 포함)"),
            ("처리기한 초과 보고", "EO", 2, 7, [5], [0, 1], "confirmed", "집계·평균 계산"),
        ],
    },
}


def populate(p: Project, m: Mutation, kind: str) -> None:
    spec = SAMPLES[kind]
    req_ids = [add_item(p, m, "requirements", {**r, "original_text": r.get("original_text") or r["description"], "status": "confirmed"}, origin="sample").id for r in spec["requirements"]]
    dat_ids = [add_item(p, m, "data_entities", {**d, "status": "confirmed"}, origin="sample").id for d in spec["data"]]
    for i in spec["interfaces"]:
        add_item(p, m, "interfaces", {**i, "status": "review"}, origin="sample")
    for f in spec["functions"]:
        f = dict(f)
        req = [req_ids[i] for i in f.pop("req")]
        dat = [dat_ids[i] for i in f.pop("dat")]
        add_item(p, m, "functions", {**f, "requirement_ids": req, "data_ids": dat, "status": "confirmed"}, origin="sample")
    for name, t, ftr, det, ri, di, status, why in spec["fp"]:
        add_item(
            p, m, "fp_items",
            {"name": name, "application": p.overview.boundary_name if t != "EIF" else "", "fp_type": t, "ftr_ret": ftr, "det": det,
             "requirement_ids": [req_ids[i] for i in ri], "data_ids": [dat_ids[i] for i in di], "status": status, "rationale": why},
            origin="sample",
        )
