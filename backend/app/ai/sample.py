"""샘플 모드 규칙 엔진(AI 아님). 외부 전송 없이 질문·초안·FP 후보를 만든다.

결과 형식은 AI 응답 스키마(app.ai.schemas)와 같아서 같은 검증·적용 경로를 탄다.
질문은 시스템 목적의 키워드로 고르며, 교육 관련 질문을 모든 사업에 고정 적용하지 않는다.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from ..models import Project
from . import schemas as S


@dataclass
class QT:
    key: str
    topic: str
    text: str
    why: str
    options: list[tuple[str, str, bool, list[tuple[str, str, str]]]]  # value, label, recommended, adds[(title, kind, desc)]
    reason: str
    priority: int
    triggers: tuple[str, ...] = ()  # 비어 있으면 모든 사업에 적용
    portal_only: bool = False
    kinds: tuple[str, ...] = ()  # system_kinds 중 하나가 있으면 적용
    excludes: tuple[str, ...] = ()
    requires: tuple[str, ...] = field(default_factory=tuple)


F, N = "functional", "nonfunctional"

BANK: list[QT] = [
    QT("users", "이용자", "누가 이 시스템을 사용하나요?", "이용자 범위에 따라 로그인·권한·개인정보 요구가 달라집니다.",
       [("internal", "기관 내부 직원만", True, []), ("public", "시민(외부) 포함", False, [("시민 이용 화면", F, "시민이 인터넷에서 이용하는 화면과 절차를 제공한다.")]), ("both", "직원과 시민 모두", False, [("이용자 구분 권한", F, "직원·시민 이용자를 구분해 메뉴와 권한을 다르게 제공한다.")])],
       "대부분의 업무시스템은 내부 직원용으로 시작합니다.", 100),
    QT("auth", "권한", "로그인은 어떻게 하나요?", "로그인 방식은 연계·보안 요구와 개발 범위에 영향을 줍니다.",
       [("sso", "기관 통합로그인(SSO) 연계", True, [("통합로그인 연계", F, "기관 통합로그인(SSO)과 연계해 별도 계정 없이 로그인한다.")]), ("own", "이 시스템 자체 계정", False, [("사용자 계정 관리", F, "관리자가 사용자 계정·권한을 등록·수정·삭제한다.")]), ("cert", "본인인증(휴대폰·공동인증 등)", False, [("본인인증 연계", F, "외부 본인인증 서비스로 신원을 확인한다.")])],
       "직원용이면 기존 통합로그인 연계가 일반적입니다(연계 가능 여부 확인 필요).", 95),
    QT("roles", "권한", "담당자·관리자·일반 사용자가 할 수 있는 일이 다른가요?", "역할별 권한을 정해야 같은 기능의 중복 계산을 피하고 화면을 나눌 수 있습니다.",
       [("yes", "역할별로 다르다", True, [("역할별 권한 관리", F, "역할(일반·담당자·관리자)별로 메뉴·기능 권한을 부여한다.")]), ("no", "모두 같다", False, [])],
       "업무시스템은 보통 담당자와 일반 사용자의 권한이 다릅니다.", 90),
    QT("personal", "데이터", "이름·연락처·주민등록번호 같은 개인정보를 저장하나요?", "개인정보를 저장하면 암호화·접근기록·보존기간 요구가 추가됩니다.",
       [("yes", "저장한다", True, [("개인정보 암호화·접근기록", N, "개인정보는 암호화 저장하고 조회·다운로드 기록을 남긴다.")]), ("no", "저장하지 않는다", False, [])],
       "신청·접수형 업무는 대부분 이름·연락처를 저장합니다.", 88),
    QT("integration", "연계", "다른 시스템의 자료를 가져오거나 보내야 하나요?", "연계는 개발비(연계복잡성 보정)와 일정에 큰 영향을 주며, 상대 시스템 확인이 필요합니다.",
       [("none", "연계 없음", False, []), ("read", "다른 시스템 자료를 조회만 한다", True, [("타 시스템 자료 조회 연계", F, "다른 시스템이 관리하는 자료를 조회해 화면에 사용한다(연계 방식 확인 필요).")]), ("send", "다른 시스템으로 자료를 보낸다", False, [("타 시스템 자료 전송 연계", F, "처리 결과를 다른 시스템으로 전송한다(연계 방식 확인 필요).")])],
       "직원정보·조직정보는 보통 기존 인사·행정시스템 자료를 사용합니다.", 85),
    QT("volume", "처리량", "이용자 수와 가장 바쁠 때 동시에 쓰는 사람 수는 대략 얼마인가요?", "서버 구성 추천과 성능 요구수준(보정계수) 판단에 필요합니다.",
       [("small", "동시 50명 이하", True, []), ("mid", "동시 50~300명", False, [("피크 시간 응답 성능", N, "피크 시간대 동시 접속에서 주요 화면 3초 이내 응답")]), ("large", "동시 300명 초과", False, [("대량 동시 접속 대응", N, "대량 동시 접속을 위한 부하 분산과 성능시험 수행")])],
       "내부 업무시스템은 대체로 동시 50명 이하입니다.", 70),
    QT("network", "환경", "어디에서 접속하나요?", "내부망/인터넷 여부에 따라 보안·서버 배치·인증 방식이 달라집니다.",
       [("internal", "기관 내부망", True, []), ("external", "인터넷", False, [("웹 취약점 점검·조치", N, "인터넷 서비스로 웹 취약점 점검 및 조치를 수행한다.")]), ("both", "둘 다", False, [("망 구분 접속 구성", N, "내부망·인터넷 접속 경로와 권한을 구분한다.")])],
       "직원용은 내부망이 일반적입니다.", 68),
    QT("approval", "업무절차", "신청(접수)을 담당자가 승인해야 하나요?", "승인 단계가 있으면 승인·반려 처리와 상태 관리가 필요합니다.",
       [("yes", "담당자 승인 필요", True, [("신청 승인·반려", F, "담당자가 신청을 승인·반려하고 사유를 기록한다.")]), ("auto", "신청 즉시 확정", False, [])],
       "정원·자격 확인이 필요한 신청은 승인 단계를 둡니다.", 92, ("신청", "접수", "예약", "대관")),
    QT("cancel", "업무절차", "신청 후 취소할 수 있나요? 언제까지 가능한가요?", "취소 기한과 취소 후 처리(대기자 승계 등)가 업무 규칙이 됩니다.",
       [("until_start", "시작 전까지 취소 가능", True, [("신청 취소", F, "이용자는 정해진 기한까지 본인 신청을 취소한다.")]), ("no", "취소 불가", False, []), ("approval", "담당자 승인 후 취소", False, [("취소 요청·승인", F, "이용자가 취소를 요청하고 담당자가 승인한다.")])],
       "보통 시작 전까지 본인 취소를 허용합니다.", 87, ("신청", "예약", "대관", "접수")),
    QT("capacity", "업무절차", "정원이 있나요? 정원이 차면 대기자를 받나요?", "대기자를 받으면 순번 관리와 자동 승계 규칙이 필요합니다.",
       [("waitlist", "정원 있음, 대기자 받음(취소 시 자동 승계)", True, [("대기자 등록·자동 승계", F, "정원 초과 시 대기 순번을 부여하고 자리가 나면 1순위를 자동 승계한다.")]), ("close", "정원 차면 마감", False, [("정원 마감 처리", F, "정원 도달 시 신청을 마감한다.")]), ("none", "정원 없음", False, [])],
       "인기 과정·시설은 대기자 관리가 민원을 줄입니다.", 84, ("교육", "강좌", "과정", "행사", "프로그램", "예약", "대관")),
    QT("completion", "업무절차", "교육 이수(출석) 여부를 관리하나요?", "이수 처리가 있으면 출석·이수 등록과 이수증 발급 여부를 정해야 합니다.",
       [("yes", "이수 처리함", True, [("이수 처리", F, "담당자가 출석·이수 여부를 등록한다.")]), ("cert", "이수 처리 + 이수증 출력", False, [("이수 처리", F, "담당자가 출석·이수 여부를 등록한다."), ("이수증 출력", F, "이수자가 이수증을 출력한다.")]), ("no", "관리 안 함", False, [])],
       "교육 업무는 이수 관리가 일반적입니다.", 80, ("교육", "강좌", "과정", "연수")),
    QT("reservation_unit", "업무절차", "예약은 어떤 단위로 하나요?", "예약 단위에 따라 중복 예약 검사 방식이 달라집니다.",
       [("hour", "시간 단위", True, [("중복 예약 방지", F, "같은 시설·시간대의 중복 예약을 막는다.")]), ("day", "일 단위", False, [("중복 예약 방지", F, "같은 시설·날짜의 중복 예약을 막는다.")])],
       "회의실·시설은 시간 단위 예약이 일반적입니다.", 83, ("예약", "대관", "시설")),
    QT("fee", "업무절차", "사용료·수수료를 받나요?", "요금 계산·결제(PG) 연계는 별도 기능과 계약이 필요합니다.",
       [("none", "무료", True, []), ("calc", "요금 계산만(납부는 별도)", False, [("이용요금 계산", F, "이용 시간·감면 기준으로 요금을 계산해 안내한다.")]), ("pay", "온라인 결제까지", False, [("이용요금 계산", F, "이용 시간·감면 기준으로 요금을 계산해 안내한다."), ("전자결제 연계", F, "전자결제(PG) 서비스와 연계해 결제·환불한다(별도 계약 필요).")])],
       "결제 연계는 별도 계약·보안 심사가 필요해 처음에는 제외하는 경우가 많습니다.", 75, ("예약", "대관", "사용료", "수수료", "결제", "요금")),
    QT("deadline", "업무절차", "처리 기한을 관리하나요?", "기한 관리가 있으면 기한 계산·초과 알림·현황 집계가 필요합니다.",
       [("yes", "기한 관리·초과 알림", True, [("처리기한 관리", F, "접수일 기준 처리기한을 계산하고 초과 건을 알린다.")]), ("no", "관리 안 함", False, [])],
       "민원은 법정 처리기한이 있어 기한 관리가 일반적입니다.", 86, ("민원", "접수", "처리", "청구")),
    QT("assign", "업무절차", "접수 건을 담당 부서·담당자에게 배정하나요?", "배정·재배정 규칙은 권한·이력 관리에 영향을 줍니다.",
       [("manual", "담당자가 수동 배정", True, [("담당 배정·재배정", F, "접수 건을 담당 부서·담당자에게 배정·재배정하고 이력을 남긴다.")]), ("auto", "유형별 자동 배정", False, [("유형별 자동 배정", F, "접수 유형에 따라 담당 부서를 자동 배정한다.")]), ("none", "배정 없음", False, [])],
       "처음에는 수동 배정으로 시작하고 규칙이 정리되면 자동화합니다.", 82, ("민원", "접수", "신고", "건의")),
    QT("stats", "출력", "통계·현황은 단순 목록인가요, 계산(집계·비율)이 필요한가요?", "계산·집계가 있으면 FP에서 외부출력(EO), 단순 조회면 외부조회(EQ)로 분류됩니다.",
       [("calc", "건수·비율 등 집계·계산 필요", True, [("통계 집계", F, "기간·구분별 건수와 비율을 집계해 보여주고 엑셀로 내려받는다.")]), ("list", "목록 조회만", False, [("현황 목록 조회", F, "조건별 현황 목록을 조회한다.")]), ("none", "필요 없음", False, [])],
       "관리자 통계는 대부분 집계 계산을 포함합니다.", 78, ("통계", "현황", "보고", "집계", "실적")),
    QT("notify", "출력", "처리 결과를 이용자에게 알려야 하나요?", "알림(문자·메일·알림톡)은 외부 서비스 연계와 비용이 따를 수 있습니다.",
       [("screen", "화면 안내만", True, []), ("mail", "메일 발송", False, [("메일 알림", F, "처리 결과를 메일로 알린다.")]), ("sms", "문자·알림톡", False, [("문자·알림톡 알림", F, "처리 결과를 문자·알림톡으로 알린다(발송 서비스 비용 별도).")])],
       "문자 발송은 기관 문자 서비스 연계 여부를 먼저 확인합니다.", 60),
    QT("batch_schedule", "처리량", "자동 처리(배치)는 언제, 얼마나 자주 실행하나요?", "주기·처리 시간대는 서버 자원과 연계 상대 시스템 일정에 영향을 줍니다.",
       [("daily", "매일 야간 1회", True, [("정기 배치 실행", F, "매일 야간 정해진 시각에 자동 처리를 실행하고 결과를 기록한다.")]), ("hourly", "매시간", False, [("정기 배치 실행", F, "매시간 자동 처리를 실행하고 결과를 기록한다.")]), ("manual", "담당자가 필요할 때 실행", False, [("배치 수동 실행", F, "담당자가 화면에서 자동 처리를 실행한다.")])],
       "대부분의 연계 배치는 업무 영향이 적은 야간에 실행합니다.", 89, ("배치", "자동", "야간", "주기", "정기", "일괄")),
    QT("batch_failure", "업무절차", "자동 처리가 실패하면 어떻게 하나요?", "실패 재처리·알림이 없으면 누락이 생겨도 알 수 없습니다.",
       [("retry_alert", "자동 재시도 + 담당자 알림", True, [("배치 실패 재처리·알림", F, "실패 건을 기록하고 재처리하며 담당자에게 알린다.")]), ("log", "기록만 남김", False, [("배치 실행 이력 조회", F, "배치 실행 결과와 실패 건을 조회한다.")])],
       "실패 알림이 없으면 연계 누락을 늦게 발견합니다.", 81, ("배치", "자동", "전송", "연계")),
    QT("interface_method", "연계", "연계 상대 시스템과 방식이 정해져 있나요?", "연계 방식(API·파일·DB)은 상대 기관 확인 전까지 확정할 수 없습니다.",
       [("unknown", "아직 모름(확인 필요)", True, []), ("api", "API로 주고받음", False, []), ("file", "파일 전송", False, [])],
       "상대 시스템 담당자에게 제공 가능한 방식을 먼저 확인해야 합니다.", 77, ("연계", "API", "전송", "수신", "인사시스템", "행정시스템", "외부 시스템")),
    QT("desktop_deploy", "환경", "프로그램을 PC에 설치하나요? 업데이트는 어떻게 배포하나요?", "설치형 프로그램은 배포·자동 업데이트·PC 환경(OS) 조건이 필요합니다.",
       [("auto_update", "설치 + 자동 업데이트", True, [("프로그램 자동 업데이트", F, "새 버전이 나오면 PC 프로그램을 자동으로 업데이트한다.")]), ("manual", "설치 파일 수동 배포", False, [])],
       "자동 업데이트가 없으면 구버전 사용 문제가 생깁니다.", 79, ("데스크톱", "설치", "PC 프로그램", "윈도우"), kinds=("desktop",)),
    QT("gis", "데이터", "지도 위에 위치를 표시하거나 좌표를 저장하나요?", "지도 기능은 공간정보 서비스 연계와 좌표 데이터가 필요합니다.",
       [("view", "지도에 위치 표시", True, [("지도 위치 표시", F, "등록된 위치를 지도에 표시한다(지도 서비스 연계 확인 필요).")]), ("no", "필요 없음", False, [])],
       "지도는 공개 지도 API 이용 조건 확인이 필요합니다.", 72, ("지도", "위치", "GIS", "좌표")),
    QT("attach", "데이터", "첨부파일을 올리나요? 허용 형식과 크기는?", "첨부는 저장공간·악성파일 검사·보존기간에 영향을 줍니다.",
       [("yes", "첨부 허용(문서·이미지, 건당 10MB)", True, [("첨부파일 관리", F, "허용 형식·크기의 첨부파일을 등록·내려받기 한다."), ("첨부파일 보안 검사", N, "첨부파일 확장자·크기 검사, 악성코드 점검")]), ("no", "첨부 없음", False, [])],
       "신청·민원 업무는 증빙 첨부가 흔합니다.", 74, ("첨부", "파일", "증빙", "서류", "민원", "신청")),
    QT("board", "업무절차", "공지사항·자료실 같은 게시판이 필요한가요?", "홈페이지·포털은 게시판·콘텐츠 관리가 기본 기능입니다.",
       [("notice", "공지사항", True, [("공지사항 게시판", F, "관리자가 공지를 등록하고 이용자가 조회한다.")]), ("multi", "공지·자료실·FAQ", False, [("공지사항 게시판", F, "관리자가 공지를 등록하고 이용자가 조회한다."), ("자료실", F, "자료를 등록·내려받는다."), ("FAQ", F, "자주 묻는 질문을 관리·조회한다.")]), ("none", "필요 없음", False, [])],
       "포털은 최소 공지사항이 필요합니다.", 76, (), portal_only=True),
    QT("accessibility", "비기능", "웹 접근성 인증(품질마크)이 필요한가요?", "공공 홈페이지는 웹 접근성 준수가 요구됩니다.",
       [("yes", "필요", True, [("웹 접근성 준수", N, "한국형 웹 콘텐츠 접근성 지침을 준수하고 점검 결과를 제출한다.")]), ("no", "내부 시스템이라 불필요", False, [])],
       "공공 웹사이트는 접근성 준수가 원칙입니다.", 73, (), portal_only=True),
    QT("retention", "데이터", "자료를 얼마 동안 보관해야 하나요?", "보존기간은 저장공간 산정과 파기 기능 요구에 필요합니다.",
       [("5y", "5년", True, [("보존기간 경과 자료 파기", F, "보존기간이 지난 자료를 파기하고 기록을 남긴다.")]), ("3y", "3년", False, [("보존기간 경과 자료 파기", F, "보존기간이 지난 자료를 파기하고 기록을 남긴다.")]), ("perm", "영구", False, [])],
       "기록물 관리 기준에 따르되 확인 전까지 5년으로 가정합니다.", 55),
]

LABEL_TO_KEY = {q.key: q for q in BANK}


def _text_of(p: Project) -> str:
    ov = p.overview
    parts = [ov.idea_text, ov.purpose, ov.background, ov.users, p.name]
    parts += [f"{r.title} {r.description} {r.original_text}" for r in p.requirements]
    parts += [q.answer for q in p.questions if q.answer]
    return " ".join(x for x in parts if x)


def matching_templates(p: Project) -> list[QT]:
    text = _text_of(p)
    out = []
    for q in BANK:
        if q.portal_only and p.overview.business_type != "portal":
            continue
        if q.kinds and not any(k in p.overview.system_kinds for k in q.kinds) and not any(t in text for t in q.triggers):
            continue
        if q.triggers and not q.kinds and not any(t in text for t in q.triggers):
            continue
        out.append(q)
    return sorted(out, key=lambda q: -q.priority)


def questions(p: Project, max_n: int = 5) -> S.QuestionsOut:
    asked = {q.topic.split(":")[0] for q in p.questions}
    picked = [q for q in matching_templates(p) if q.key not in asked][:max_n]
    return S.QuestionsOut(
        questions=[
            S.QuestionOut(
                key=q.key,
                topic=q.topic,
                text=q.text,
                why=q.why,
                options=[S.OptionOut(value=v, label=lab, recommended=rec, adds=[S.SuggestedReq(title=t, kind=k, description=d) for t, k, d in adds]) for v, lab, rec, adds in q.options],
                recommended_value=next(v for v, _, rec, _ in q.options if rec),
                recommended_reason=q.reason,
            )
            for q in picked
        ]
    )


# ---------------------------------------------------------------- 요구사항 초안
NFR_BASE = [
    ("접근 권한 통제", "보안", "역할별 접근 권한을 적용하고 권한 없는 기능 접근을 차단한다."),
    ("데이터 백업", "운영", "데이터를 매일 백업하고 복구 절차를 문서화한다."),
    ("감사 로그", "보안", "로그인·주요 데이터 변경 이력을 기록한다."),
]


def split_feature_lines(text: str) -> list[tuple[str, str]]:
    """자유문장·목록·표(탭 구분)를 (제목, 설명) 목록으로."""
    out = []
    for raw in (text or "").splitlines():
        line = raw.strip().lstrip("-*•·0123456789.) ").strip()
        if not line:
            continue
        if "\t" in raw:
            cells = [c.strip() for c in raw.split("\t") if c.strip()]
            if len(cells) >= 2:
                out.append((cells[0][:80], " ".join(cells[1:])))
                continue
        title = re.split(r"[:：]|(?<=다)\.|,", line, maxsplit=1)[0].strip()
        out.append((title[:80] or line[:80], line))
    return out


def requirements(p: Project, feature_text: str) -> S.RequirementsOut:
    items = []
    for title, desc in split_feature_lines(feature_text):
        items.append(S.ReqDraft(title=title, kind="functional", category="", description=desc, original_text=desc, priority="medium", acceptance="", why="사용자가 직접 요청한 기능", from_user=True))
    existing = {re.sub(r"\s", "", r.title) for r in p.requirements} | {re.sub(r"\s", "", i.title) for i in items}
    sugg: list[S.ReqDraft] = []
    text = _text_of(p) + " " + feature_text
    if any(w in text for w in ("신청", "접수", "예약")) and not any("조회" in x for x in existing):
        sugg.append(S.ReqDraft(title="신청(접수) 내역 조회", kind="functional", category="", description="이용자가 본인 신청 내역과 처리 상태를 조회한다.", original_text="", priority="medium", acceptance="", why="신청형 업무에 일반적으로 필요한 기능(빠진 기능 제안)", from_user=False))
    for t, c, d in NFR_BASE:
        if re.sub(r"\s", "", t) not in existing:
            sugg.append(S.ReqDraft(title=t, kind="nonfunctional", category=c, description=d, original_text="", priority="medium", acceptance="", why="공공 정보시스템 공통 비기능 요구(제안)", from_user=False))
    return S.RequirementsOut(requirements=items + sugg)


# ---------------------------------------------------------------- 설계 초안
VERBS = r"(등록|수정|삭제|조회|관리|신청|취소|승인|반려|처리|통계|현황|목록|검색|출력|전송|배정|재배정|계산|집계|보고|알림|발송|입력|변경|확인|실행|자동|승계|연계|참조|내역|발급|파기|업로드|내려받기|화면|기능|및|·|,)"


# 업무 대상이기도 한 동사형 명사(신청 정보, 접수 정보 등)는 남긴다
_ACTION_WORDS = set(VERBS.strip("()").split("|")) - {"신청", "접수", "·", ","}


_OBJ = re.compile(r"^(.+?)(?:을|를)(?:\s|$)")
_GENERIC = {"정보", "신청", "관리", "내역", "현황", "월별", "본인", "온라인", "업무", "데이터", "자료", "시스템"}


def short_title(text: str) -> str:
    """요구사항 문장 → 짧은 제목. 예: 'SFR-001 관광객이 경비 환급을 신청하는 기능을 제공하여야 한다' → '경비 환급을 신청'.
    원문은 original_text에 그대로 보존하고 제목만 줄인다."""
    s = REQ_ID.sub("", text or "").strip(" -:·\t")
    s = re.sub(r"^[가-힣]{1,8}(이|가|은|는)\s+", "", s)
    s = re.sub(r"\s*(하는|할 수 있는|하기 위한|하는\s*등의)?\s*기능(을|를)?\s*(제공|지원|구현|구축)?\s*(하여야|해야)\s*(한다|함)\.?$", "", s)
    s = re.sub(r"\s*(을|를)?\s*(제공|지원)?(하여야|해야)\s*(한다|함)\.?$", "", s)
    return (s.strip() or (text or "").strip())[:60]


def base_noun(title: str) -> str:
    """요구사항·기능명에서 업무 대상 명사를 뽑는다. 예: '신청 승인·반려' → '신청', '교육과정 등록·관리' → '교육과정'.
    문장형('환급 신청을 심사하여 승인')이면 목적어(을/를 앞)에서 뽑는다."""
    m = _OBJ.match(title.strip())
    if m:
        title = re.split(r"(?:과|와)\s", re.sub(r"^[가-힣]+의\s+", "", m.group(1)), maxsplit=1)[0]
    words = [w for w in re.split(r"[\s·,/()\[\]:]+", title) if w]
    kept = [w for w in words if w not in _ACTION_WORDS and not any(w.endswith(v) and len(w) > len(v) + 1 and v in ("등록", "조회", "관리", "처리") for v in _ACTION_WORDS)]
    return " ".join(kept) or (words[0] if words else title.strip())


def _tokens(noun: str) -> set[str]:
    return {w for w in noun.split() if len(w) >= 2 and w not in _GENERIC}


def _read_only(text: str) -> bool:
    """조회·통계처럼 자료를 바꾸지 않는 요구사항(새 데이터 묶음을 만들지 않는다)."""
    reads = any(w in text for w in ("조회", "통계", "현황", "목록", "검색", "집계", "보고"))
    writes = any(w in text for w in ("등록", "수정", "삭제", "승인", "반려", "취소", "입력", "변경", "접수"))
    return reads and not writes


def actor_of(text: str) -> str:
    if any(w in text for w in ("관리자", "담당자", "승인", "반려", "배정", "통계", "집계", "현황 보고")):
        return "담당자"
    if any(w in text for w in ("배치", "자동", "야간")):
        return "시스템(자동)"
    return "이용자"


def design(p: Project) -> S.DesignOut:
    reqs = [r for r in p.requirements if r.kind == "functional" and r.status != "excluded"]
    funcs, datas, ifs, screens, flows = [], [], [], [], []
    data_keys: dict[str, str] = {}
    existing_data = {base_noun(d.name): d.id for d in p.data_entities}
    for i, r in enumerate(reqs):
        text = f"{r.title} {r.description}"
        noun = base_noun(r.title)
        dkeys: list[str] = []
        if any(w in text for w in ("연계", "전송", "인사시스템", "행정시스템", "외부 시스템", "참조")):
            ikey = f"if{i}"
            ifs.append(S.IfDraft(key=ikey, name=f"{r.title} 연계", counterpart="확인 필요", direction="outbound" if "전송" in text else "inbound", method="확인 필요", data_items="확인 필요", requirement_ids=[r.id], reason="요구사항에 연계 표현이 있음 — 상대 시스템·방식은 확인 전까지 미정"))
        elif noun and noun not in existing_data:
            # 같은 업무 대상(핵심 낱말이 겹침)은 데이터 하나로 묶고, 조회·통계는 기존 데이터를 참조만 한다
            same = next((k for n, k in data_keys.items() if _tokens(n) & _tokens(noun)), None)
            if same:
                data_keys.setdefault(noun, same)
            elif not _read_only(text) and noun not in data_keys:
                key = f"d{len(datas)}"
                data_keys[noun] = key
                datas.append(S.DataDraft(key=key, name=noun if noun.endswith("정보") else f"{noun} 정보", description=f"{noun} 관련 업무 데이터(항목은 확인 필요)", maintained_by="internal", personal_info=any(w in text for w in ("신청", "회원", "민원", "개인")), requirement_ids=[r.id], reason="요구사항의 업무 대상 명사를 데이터 후보로 추출 — 테이블 수와 FP 수는 다를 수 있음"))
            if noun in data_keys:
                dkeys.append(data_keys[noun])
        fkey = f"f{i}"
        funcs.append(S.FuncDraft(key=fkey, name=r.title, actor=actor_of(text), purpose=r.description or r.title, inputs="확인 필요", outputs="확인 필요", rules="확인 필요", exceptions="확인 필요", permissions=actor_of(text), acceptance=r.acceptance or "", requirement_ids=[r.id], data_keys=dkeys, existing_data_ids=[existing_data[noun]] if noun in existing_data else [], interface_keys=[f"if{i}"] if any(x.key == f"if{i}" for x in ifs) else [], reason="요구사항 1건을 기능 1건 초안으로 구성 — 세부 입력·출력·규칙은 사용자 확인 필요"))
        screens.append(S.ScreenDraft(key=f"s{i}", name=f"{r.title} 화면", users=actor_of(text), description="화면 구성 초안", function_keys=[fkey], reason="기능별 화면 초안(화면 수는 FP 수와 무관)"))
        flows.append(S.FlowDraft(key=f"w{i}", order=i + 1, name=r.title, actor=actor_of(text), description=r.description or r.title, requirement_ids=[r.id]))
    return S.DesignOut(functions=funcs, data_entities=datas, interfaces=ifs, screens=screens, workflows=flows)


# ---------------------------------------------------------------- FP 후보
TX_RULES = [
    (("통계", "집계", "보고", "계산", "출력", "전송", "배치", "이수증", "발급"), "EO", "계산·집계·가공 후 밖으로 내보내는 처리"),
    (("조회", "검색", "목록", "내역", "현황", "보기"), "EQ", "가공 없이 저장 데이터를 조회"),
    (("등록", "신청", "접수", "입력", "수정", "변경", "삭제", "취소", "승인", "반려", "배정", "처리", "승계", "업로드", "파기"), "EI", "외부 입력으로 내부 데이터를 등록·수정·삭제"),
]


def fp_candidates(p: Project) -> S.FPOut:
    from ..fp.engine import normalize_name

    existing = {normalize_name(f.name) for f in p.fp_items}
    out: list[S.FPDraft] = []

    def add(d: S.FPDraft):
        n = normalize_name(d.name)
        if n in existing:
            return
        existing.add(n)
        out.append(d)

    for d in p.data_entities:
        if d.status == "excluded":
            continue
        t = "EIF" if d.maintained_by == "external" else ("ILF" if d.maintained_by == "internal" else None)
        add(S.FPDraft(name=d.name, fp_type=t, rationale=("다른 시스템이 유지하고 참조만 하는 데이터" if t == "EIF" else "이 시스템이 등록·수정하며 유지하는 데이터") if t else "유지 주체 미확인", uncertainty="RET·DET 미입력(정통법 전 확인 필요). 여러 테이블이 하나의 논리 데이터일 수 있음" + ("" if t else " / 유지 주체 확인 필요"), det=None, ftr_ret=None, requirement_ids=[], function_ids=d.function_ids, data_ids=[d.id]))
    for f in p.functions:
        if f.status == "excluded":
            continue
        text = f"{f.name} {f.purpose} {f.rules}"
        hits = []
        for words, t, why in TX_RULES:
            for w in words:
                if w in text:
                    hits.append((w, t, why))
        if "관리" in f.name and not any(w in f.name for w in ("등록", "수정", "삭제", "조회")):
            base = base_noun(f.name)
            for verb, t in (("등록", "EI"), ("수정", "EI"), ("삭제", "EI"), ("조회", "EQ")):
                add(S.FPDraft(name=f"{base} {verb}", fp_type=t, rationale=f"'관리'를 {verb} 처리로 분해한 후보", uncertainty="'관리'에 실제로 포함되는 처리 범위 확인 필요(메뉴 수로 FP를 정하지 않음)", det=None, ftr_ret=None, requirement_ids=f.requirement_ids, function_ids=[f.id], data_ids=f.data_ids))
            continue
        if not hits:
            add(S.FPDraft(name=f.name, fp_type=None, rationale="", uncertainty="처리 유형을 판단할 표현이 없어 미분류 — 입력/조회/출력 중 무엇인지 확인 필요", det=None, ftr_ret=None, requirement_ids=f.requirement_ids, function_ids=[f.id], data_ids=f.data_ids))
            continue
        # 기능명에 명시된 등록·수정·삭제·승인·반려는 각각 별도 처리로, 그 밖에는 유형별 1건으로 만든다
        crud = [v for v in ("등록", "수정", "삭제", "승인", "반려") if v in f.name]
        if len(crud) > 1:
            for v in crud:
                add(S.FPDraft(name=f"{base_noun(f.name)} {v}", fp_type="EI", rationale=f"기능명의 '{v}' → 내부 데이터를 바꾸는 별도 처리", uncertainty="DET·FTR 미입력(정통법 전 확인 필요)", det=None, ftr_ret=None, requirement_ids=f.requirement_ids, function_ids=[f.id], data_ids=f.data_ids))
            continue
        # '신청 내역 조회'의 '신청', '처리 상태'의 '처리'처럼 업무 대상 명사로 쓰인 낱말은 입력 처리로 보지 않는다
        if any(t in ("EQ", "EO") for _, t, _ in hits) and all(w in ("신청", "접수", "처리") for w, t, _ in hits if t == "EI"):
            hits = [h for h in hits if h[1] != "EI"]
        # 통계·집계 출력의 '현황·내역·목록'은 출력 내용이므로 별도 조회로 나누지 않는다
        if any(t == "EO" for _, t, _ in hits) and all(w in ("현황", "내역", "목록") for w, t, _ in hits if t == "EQ"):
            hits = [h for h in hits if h[1] != "EQ"]
        by_type: dict[str, tuple[str, str]] = {}
        for w, t, why in hits:
            by_type.setdefault(t, (w, why))
        for t, (w, why) in by_type.items():
            name = f.name if len(by_type) == 1 else f"{f.name}({ {'EI': '입력', 'EO': '출력', 'EQ': '조회'}[t]})"
            add(S.FPDraft(name=name, fp_type=t, rationale=f"'{w}' 표현 → {why}", uncertainty="DET·FTR 미입력(정통법 전 확인 필요)" + (" / 한 기능에 여러 유형 표현 — 실제 처리 단위 확인" if len(by_type) > 1 else ""), det=None, ftr_ret=None, requirement_ids=f.requirement_ids, function_ids=[f.id], data_ids=f.data_ids))
    return S.FPOut(items=out)


# ---------------------------------------------------------------- 참고문서 항목 추출(규칙)
REQ_ID = re.compile(r"\b([A-Z]{2,4}-\d{2,4})\b")
REQ_HINT = re.compile(r"(하여야\s*한다|해야\s*한다|하여야\s*함|하여야함|해야\s*함|할\s*것|기능|지원|제공|구축|개발)")
ORG_RULES = {
    "budget": re.compile(r"(\d[\d,]*\s*(원|천원|백만원|억원)|예산|사업비|소요\s*금액)"),
    "period": re.compile(r"(\d+\s*개월|사업\s*기간|계약일로부터|\d{4}\s*[.년]\s*\d{1,2})"),
    "personal_info": re.compile(r"(주민등록번호|개인정보|성명|연락처|생년월일)"),
    "product": re.compile(r"(Oracle|오라클|Tibero|티베로|WebLogic|웹로직|JEUS|제우스|MS-?SQL|SAP|특정\s*제품)", re.I),
    "org_name": re.compile(r"([가-힣]{2,10}(특별시|광역시|도청|시청|군청|구청|교육청))"),
}


def classify_line(line: str) -> tuple[str, list[str]] | None:
    s = line.strip()
    if len(s) < 8 or len(s) > 600:
        return None
    if re.search(r"(과업\s*지시서|제안\s*요청서|과업\s*내용서)", s) and not REQ_ID.search(s) and not re.search(r"(하여야|해야)", s):
        return None  # 문서 제목 줄
    org = [k for k, rx in ORG_RULES.items() if rx.search(s)]
    if not (REQ_ID.search(s) or REQ_HINT.search(s)) and not set(org) & {"budget", "period", "org_name"}:
        return None
    if re.search(r"(연계|인터페이스|API|송수신|전송)", s):
        kind = "interface"
    elif re.search(r"(데이터|DB|테이블|자료\s*구축|이관)", s):
        kind = "data"
    elif org and (set(org) & {"budget", "period"} or (set(org) & {"product", "org_name"} and not REQ_HINT.search(s))):
        kind = "condition"
    else:
        kind = "requirement"
    return kind, org
