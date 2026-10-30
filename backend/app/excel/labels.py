"""화면·엑셀 공통 한국어 표기."""

STATUS = {"draft": "초안", "review": "검토중", "confirmed": "확정", "excluded": "제외"}
ORIGIN = {"user": "사용자", "ai": "AI 제안", "sample": "샘플 규칙 제안(AI 아님)", "document": "참고문서 추출", "system": "시스템"}
KIND = {"functional": "기능", "nonfunctional": "비기능"}
PRIORITY = {"high": "상", "medium": "중", "low": "하"}
BUSINESS_TYPE = {"portal": "홈페이지·포털 신규개발", "system": "일반 SW·정보시스템 신규개발"}
START_MODE = {"idea": "구상 기반", "document": "참고문서 기반", "review": "기존 문서 검토"}
BUDGET_MODE = {"none": "예산 미지정", "target": "개발비 지정(목표예산)"}
VERDICT = {"match": "확인 일치", "diff": "차이 발견", "check": "확인 필요", "insufficient": "근거 부족"}
METHOD = {"simple": "간이법", "detailed": "정통법"}
CX_SOURCE = {"table": "복잡도표(입력값)", "derived": "복잡도표(근거 목록 코드 집계)", "assumed": "가정 적용", "missing": "근거 부족(정통법 미완료)", "unclassified": "미분류", "excluded": "제외"}
SYSTEM_KINDS = {"web": "웹", "mobile": "모바일", "desktop": "데스크톱", "server": "서버 프로그램", "batch": "배치 자동처리", "integration": "시스템 연계"}
FP_TYPE_DESC = {
    "EI": "외부입력: 경계 밖에서 들어온 데이터로 내부 데이터를 등록·수정·삭제하는 처리 (예: 교육 신청 등록)",
    "EO": "외부출력: 계산·집계 등 가공 로직을 거쳐 밖으로 내보내는 처리 (예: 월별 수강 통계)",
    "EQ": "외부조회: 가공 없이 저장된 데이터를 조회해 보여주는 처리 (예: 신청 내역 조회)",
    "ILF": "내부논리파일: 이 시스템이 등록·수정하며 유지하는 논리 데이터 묶음 (예: 교육과정 정보)",
    "EIF": "외부연계파일: 다른 시스템이 유지하고 이 시스템은 참조만 하는 데이터 (예: 인사시스템 직원정보)",
}
