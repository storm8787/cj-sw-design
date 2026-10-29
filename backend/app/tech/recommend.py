"""HW·SW 구성 추천(규칙 기반 초안).

- 자체 서버: 입력 가정에 근거한 초기 CPU·메모리·저장공간·역할 분리안. 성능 보장 아님(부하시험 후 조정).
- 클라우드: 인스턴스 사양(CPU/RAM)은 제시하지 않고 서비스 구성·저장·백업·운영 방식만 제시(사용자 요청).
- SW 후보의 지원 상태는 공식 출처를 등록·확인하기 전까지 '현재 상태 미확인'.
- 장비·유료 SW 비용은 개발비에 합산하지 않는다(paid_item 표시만).
"""
from __future__ import annotations

import math
from typing import Any

from ..models import OfficialSource, Project, TechRec

UNVERIFIED = "현재 상태 미확인(공식 출처 확인 필요)"

# 공식 정보 확인용 후보 URL(접속·내용 미검증, 등록만)
SUGGESTED_SOURCES = [
    ("PostgreSQL 버전 지원 정책", "https://www.postgresql.org/support/versioning/", "PostgreSQL Global Development Group", "DB"),
    ("Apache Tomcat 버전별 지원 현황", "https://tomcat.apache.org/whichversion.html", "Apache Software Foundation", "WAS"),
    ("Ubuntu 릴리스 주기", "https://ubuntu.com/about/release-cycle", "Canonical", "OS"),
    ("Rocky Linux", "https://rockylinux.org/", "Rocky Enterprise Software Foundation", "OS"),
    ("전자정부 표준프레임워크", "https://www.egovframe.go.kr/", "행정안전부·NIA", "프레임워크"),
    ("nginx", "https://nginx.org/", "nginx", "웹서버"),
    ("제품별 지원 종료일 모음(endoflife.date, 비공식 집계)", "https://endoflife.date/", "endoflife.date", "참고"),
]


def _src_ids(p: Project, area: str) -> tuple[list[str], str]:
    ids, status = [], UNVERIFIED
    for s in p.official_sources:
        if area in s.note or area in s.title:
            ids.append(s.id)
            if s.checked_at and s.status in ("fetched", "verified_by_user") and s.support_status:
                status = f"{s.support_status} (확인일 {s.checked_at}, {s.url})"
    return ids, status


def recommend(p: Project) -> tuple[list[TechRec], list[str]]:
    t = p.tech.inputs
    ov = p.overview
    notes: list[str] = []
    recs: list[TechRec] = []
    conc = t.concurrent_users
    if conc is None:
        conc = 50
        notes.append("동시 접속자 수 미입력 → 50명으로 가정")
    growth = t.data_growth_gb_per_year if t.data_growth_gb_per_year is not None else 10.0
    if t.data_growth_gb_per_year is None:
        notes.append("연간 데이터 증가량 미입력 → 10GB/년으로 가정")
    years = 5
    ha = t.availability == "high"

    def add(area: str, proposal: str, reason: str, assumptions: str = "", alternatives: str = "", compatibility: str = "", license_: str = "", ops: str = "", paid: bool = False, key: str | None = None):
        ids, status = _src_ids(p, key or area)
        recs.append(TechRec(id=f"TR-{len(recs) + 1:03d}", area=area, proposal=proposal, reason=reason, assumptions=assumptions, alternatives=alternatives, compatibility=compatibility, license=license_, support_status=status, ops_difficulty=ops, official_source_ids=ids, paid_item=paid))

    staff = {"none": "운영 전담 인력 없음 → 관리형 서비스·단순 구성 권장", "part_time": "겸임 운영 → 표준 구성·자동 백업 권장", "dedicated": "전담 인력 있음", "unknown": "운영 인력 미확인"}[t.ops_staff]

    if t.deployment in ("onprem", "unknown", "hybrid"):
        if t.deployment == "unknown":
            notes.append("구축 방식 미정 → 자체 서버 기준 초안(클라우드 선택 시 다시 실행)")
        was_cpu = max(4, 2 * math.ceil(conc / 50))
        was_mem = 8 + 4 * math.ceil(conc / 100)
        db_cpu = 4 if conc <= 300 else 8
        db_mem = 16 if conc <= 300 else 32
        data_gb = math.ceil(growth * years * 1.5)
        db_disk = 100 + data_gb
        file_gb = math.ceil(growth * years) if t.file_storage else 0
        roles = "WEB/WAS 겸용 1대 + DB 1대" if not ha and conc <= 100 else ("WEB/WAS 2대(이중화) + DB 2대(Active-Standby) + 부하분산" if ha else "WEB 1대 + WAS 1대 + DB 1대")
        add("서버 구성(자체)", f"{roles}\n- WAS: vCPU {was_cpu}, 메모리 {was_mem}GB (대당)\n- DB: vCPU {db_cpu}, 메모리 {db_mem}GB, 데이터 디스크 {db_disk}GB" + (f"\n- 첨부파일 저장소 {file_gb}GB" if file_gb else ""),
            "동시 접속·데이터 증가 입력값에 따른 초기 산정. 이용 패턴에 따라 크게 달라질 수 있음",
            f"동시 {conc}명, 데이터 {growth}GB/년 × {years}년 × 여유 1.5배. 관측·부하시험 전 추정치이며 성능을 보장하지 않음. 가상화 서버 기준",
            "기관 공용 가상화 자원 활용, 클라우드 전환", ops=staff, key="서버")
        add("백업", f"DB 매일 전체 백업 + 보존 30일, 백업 저장공간 약 {math.ceil(db_disk * 2)}GB(데이터의 2배 가정)", "복구 가능성 확보(복구 절차 문서화·연 1회 복구 훈련)", "백업 대상·보존기간은 기관 지침 확인 필요", "기관 통합 백업 시스템 연계", ops=staff)
    else:
        notes.append("클라우드: 사용자 요청에 따라 인스턴스 CPU/RAM 사양은 제시하지 않음")
        add("클라우드 서비스 구성", "공공기관용 보안인증(CSAP) 받은 클라우드에서\n- 웹·애플리케이션: 가상서버 또는 컨테이너(" + ("2개 이상 + 로드밸런서" if ha else "1개") + ")\n- DB: 관리형 DB 서비스(자동 백업·패치)\n- 첨부파일: 오브젝트 스토리지" + ("(사용)" if t.file_storage else "(필요 시)"),
            "운영 인력 부담을 줄이는 관리형 서비스 중심 구성", "인스턴스 사양은 클라우드 사업자 상담·실측 후 결정", "기관 자체 서버, 공공 클라우드 공동 인프라", license_="클라우드 이용료 별도(개발비 미포함)", ops=staff, paid=True, key="클라우드")
        add("백업·운영(클라우드)", "관리형 DB 자동 백업(보존 30일 이상) + 스냅샷, 오브젝트 스토리지 버전 관리, 모니터링·알림 설정, 접근 권한 최소화", "장애·실수 복구와 운영 가시성 확보", "보존기간은 기관 기록물 지침 확인", ops=staff, key="클라우드")
    # SW
    if t.existing_os:
        add("OS", f"기존 운영 OS({t.existing_os}) 유지", "운영 인력 숙련도·기존 표준과 호환", alternatives="Rocky Linux, Ubuntu LTS, RHEL", compatibility="WAS·DB 지원 버전 확인 필요", license_="기존 라이선스 확인", ops="낮음", key="OS")
    else:
        add("OS", "리눅스 LTS 계열(예: Rocky Linux, Ubuntu LTS) 중 기관 표준", "무상 이용 가능, 장기 지원 버전 선택", alternatives="RHEL(상용 지원 필요 시)", compatibility="선택한 WAS·DB 지원 OS 확인", license_="무상(RHEL은 구독형 유상)", ops="중간(리눅스 운영 경험 필요)", key="OS")
    add("웹서버·WAS", "Nginx(또는 Apache) + Tomcat" if not t.existing_was else f"기존 WAS({t.existing_was}) 유지 검토", "전자정부 표준프레임워크와 호환되는 일반적 구성" if not t.existing_was else "기존 운영 경험·라이선스 활용", alternatives="JEUS, WebLogic(상용 지원 필요 시)", compatibility="프레임워크·JDK 버전 호환 확인", license_="Tomcat·Nginx 무상 / 상용 WAS는 라이선스 별도", ops="중간", paid=bool(t.existing_was) and any(x in t.existing_was for x in ("JEUS", "WebLogic", "웹로직", "제우스")), key="WAS")
    if t.existing_db:
        paid = any(x in t.existing_db for x in ("Oracle", "오라클", "Tibero", "티베로", "MS", "SQL Server"))
        add("DB", f"기존 DB({t.existing_db}) 활용 검토", "기존 라이선스·운영 경험 활용, 연계 단순화", alternatives="PostgreSQL, MariaDB", compatibility="버전·문자셋(UTF-8) 확인", license_="기존 라이선스의 추가 사용 가능 여부(코어 수) 확인 필요" + (" — 상용 라이선스 비용은 개발비 미포함" if paid else ""), ops="중간", paid=paid, key="DB")
    else:
        add("DB", "PostgreSQL(또는 MariaDB)", "무상 오픈소스, 공공 레퍼런스 다수", alternatives="Tibero·Oracle(상용, 기존 라이선스가 있을 때)", compatibility="프레임워크 지원 DB 확인", license_="무상(상용 기술지원은 선택·별도)", ops="중간(DB 백업·튜닝 담당 필요)", key="DB")
    add("개발 프레임워크", "전자정부 표준프레임워크(최신 지원 버전)", "공공 SW사업에서 널리 쓰이며 유지보수 인력 확보가 쉬움", alternatives="Spring Boot 기반 자체 구성", compatibility="JDK·WAS 버전 호환 확인", license_="무상", ops="중간", key="프레임워크")
    kinds = set(ov.system_kinds)
    if "batch" in kinds:
        add("배치 실행", "운영체제 스케줄러(cron/systemd timer) 또는 프레임워크 배치 기능 + 실행 이력·실패 알림", "주기 실행과 실패 재처리 추적", "실행 주기·처리량은 요구사항 기준", "상용 배치 스케줄러(대규모일 때)", ops="중간")
    if "integration" in kinds or p.interfaces:
        add("연계 방식", "상대 시스템이 제공하는 방식 우선(API / 파일 전송 / DB 연계) — 확정 전 상대 기관 확인", "연계 가능 여부는 문서만으로 확정할 수 없음", "연계 대상: " + (", ".join(i.counterpart or i.name for i in p.interfaces) or "미정"), "기관 연계 플랫폼(있을 때)", ops="중간~높음")
    if "desktop" in kinds:
        add("데스크톱 배포", "설치 프로그램 + 자동 업데이트 기능, 지원 OS(Windows 버전) 명시", "구버전 사용 방지", "기관 PC 표준 OS·보안 프로그램과 충돌 여부 확인", "웹 전환", ops="중간")
    if t.network in ("external", "both"):
        add("보안", "웹방화벽(WAF), 웹 취약점 점검, HTTPS 인증서, 개인정보 암호화", "인터넷 서비스 필수 보안 조치", "기관 보유 보안장비 활용 여부 확인", license_="보안장비·인증서 비용 별도(개발비 미포함)", ops="중간", paid=True)
    return recs, notes


def suggested_sources() -> list[OfficialSource]:
    return [OfficialSource(id="", title=t, url=u, publisher=pub, note=area, status="registered_unverified") for t, u, pub, area in SUGGESTED_SOURCES]


def summary_inputs(p: Project) -> dict[str, Any]:
    return p.tech.inputs.model_dump()
