"""프로젝트 공통 데이터 모델.

모든 산출물(요구사항·설계·FP·견적·엑셀)은 이 문서 하나에서 만들어진다.
항목은 접두어+일련번호 ID(REQ-001 등)로 연결하며 ID는 재사용하지 않는다.
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

SCHEMA_VERSION = 1

Origin = Literal["user", "ai", "sample", "document", "system"]
ItemStatus = Literal["draft", "review", "confirmed", "excluded"]
FPType = Literal["EI", "EO", "EQ", "ILF", "EIF"]
Complexity = Literal["L", "A", "H"]


class M(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class Tracked(M):
    """사용자 확인 여부와 영향 표시를 갖는 항목 공통 필드."""

    id: str = ""
    origin: Origin = "user"
    status: ItemStatus = "draft"
    needs_review: bool = False
    review_reason: str = ""
    source_ids: list[str] = Field(default_factory=list)
    note: str = ""


# ---------------------------------------------------------------- 개요
class Phases(M):
    analysis: bool = True
    design: bool = True
    implementation: bool = True
    test: bool = True


class PhaseRatios(M):
    """단계별 비율. 공식 표 미확인 → 사용자 입력(FP_RULES §5)."""

    analysis: str | None = None
    design: str | None = None
    implementation: str | None = None
    test: str | None = None


class Overview(M):
    business_type: Literal["portal", "system"] = "system"
    start_mode: Literal["idea", "document", "review"] = "idea"
    budget_mode: Literal["none", "target"] = "none"
    target_amount: int | None = None
    target_includes_vat: bool = True
    phases: Phases = Field(default_factory=Phases)
    phase_ratios: PhaseRatios = Field(default_factory=PhaseRatios)
    idea_text: str = ""
    purpose: str = ""
    background: str = ""
    users: str = ""
    build_method: str = ""
    period_months: int | None = None
    org_environment: str = ""
    system_kinds: list[Literal["web", "mobile", "desktop", "server", "batch", "integration"]] = Field(default_factory=list)
    boundary_name: str = ""
    boundary_note: str = ""


# ---------------------------------------------------------------- 설계 항목
class Requirement(Tracked):
    kind: Literal["functional", "nonfunctional"] = "functional"
    category: str = ""  # 비기능 분류(성능/보안/…)나 업무 구분
    title: str = ""
    original_text: str = ""  # 사용자 요구 원문(수정하지 않음)
    description: str = ""
    priority: Literal["high", "medium", "low"] = "medium"
    acceptance: str = ""  # 검수 기준
    why: str = ""  # 왜 필요한가(쉬운 설명)


class WorkflowStep(Tracked):
    order: int = 0
    name: str = ""
    actor: str = ""
    description: str = ""
    requirement_ids: list[str] = Field(default_factory=list)


class FunctionDesign(Tracked):
    name: str = ""
    actor: str = ""
    purpose: str = ""
    inputs: str = ""
    outputs: str = ""
    rules: str = ""
    exceptions: str = ""
    permissions: str = ""
    acceptance: str = ""
    requirement_ids: list[str] = Field(default_factory=list)
    screen_ids: list[str] = Field(default_factory=list)
    data_ids: list[str] = Field(default_factory=list)
    interface_ids: list[str] = Field(default_factory=list)


class Screen(Tracked):
    name: str = ""
    users: str = ""
    description: str = ""
    function_ids: list[str] = Field(default_factory=list)


class DataEntity(Tracked):
    name: str = ""
    description: str = ""
    attributes: str = ""
    relations: str = ""
    maintained_by: Literal["internal", "external", "unknown"] = "internal"
    personal_info: bool = False
    retention: str = ""
    function_ids: list[str] = Field(default_factory=list)


class Interface(Tracked):
    name: str = ""
    counterpart: str = ""
    direction: Literal["inbound", "outbound", "both", "unknown"] = "unknown"
    method: str = ""  # API, 파일, DB링크 등
    data_items: str = ""
    frequency: str = ""
    verified: Literal["unverified", "confirmed_by_org", "confirmed_by_counterpart"] = "unverified"
    function_ids: list[str] = Field(default_factory=list)


class FPItem(Tracked):
    name: str = ""  # 단위프로세스명 또는 데이터 기능명
    application: str = ""  # 애플리케이션명(경계)
    business: str = ""  # 세부 업무명
    description: str = ""
    fp_type: FPType | None = None  # None = 미분류
    rationale: str = ""  # 분류 근거
    uncertainty: str = ""  # 미확정 이유
    det: int | None = None
    ftr_ret: int | None = None  # 트랜잭션은 FTR, 데이터 기능은 RET
    assumed_complexity: Complexity | None = None
    assumption_note: str = ""
    requirement_ids: list[str] = Field(default_factory=list)
    function_ids: list[str] = Field(default_factory=list)
    data_ids: list[str] = Field(default_factory=list)
    duplicate_of: str = ""


# ---------------------------------------------------------------- 질문·가정
class QuestionOption(M):
    value: str
    label: str
    recommended: bool = False
    adds_requirements: list[str] = Field(default_factory=list)  # 선택 시 제안할 요구사항 제목


class Question(M):
    id: str = ""
    topic: str = ""
    text: str = ""
    why: str = ""
    options: list[QuestionOption] = Field(default_factory=list)
    allow_text: bool = True
    recommended_value: str = ""
    recommended_reason: str = ""
    answer: str = ""
    answer_kind: Literal["", "choice", "text", "unknown"] = ""
    status: Literal["open", "answered", "deferred"] = "open"
    origin: Origin = "sample"
    batch: int = 0


class Assumption(Tracked):
    text: str = ""
    reason: str = ""
    question_id: str = ""


# ---------------------------------------------------------------- 문서·출처
class Extraction(M):
    status: Literal["pending", "ok", "partial", "failed", "unsupported", "scanned", "encrypted"] = "pending"
    quality: Literal["", "high", "medium", "low", "none"] = ""
    messages: list[str] = Field(default_factory=list)
    pages: int | None = None
    chars: int = 0
    chunks_total: int = 0
    chunks_analyzed: int = 0
    analysis_status: Literal["not_started", "partial", "complete", "failed"] = "not_started"


class DocumentMeta(M):
    id: str = ""
    file_name: str = ""
    stored_name: str = Field("", pattern=r"^(DOC-\d{3,}\.(pdf|hwpx|hwp|docx|xlsx|xlsm|txt|md))?$")  # 서버가 만든 이름만 허용(복원 파일 경로 조작 방지)
    kind: Literal["reference", "vendor_task", "vendor_design", "vendor_fp", "vendor_cost", "other"] = "reference"
    format: str = ""
    size: int = 0
    sha256: str = ""
    uploaded_at: str = ""
    extraction: Extraction = Field(default_factory=Extraction)
    ai_consent: bool = False


class SourceRef(M):
    id: str = ""
    document_id: str = ""
    file_name: str = ""
    location: str = ""
    excerpt: str = ""
    extraction_status: str = ""


class ReferenceItem(M):
    """참고문서에서 추출한 항목. 우리 기관 기준으로 유지/수정/제외/추가를 결정한다."""

    id: str = ""
    document_id: str = ""
    source_id: str = ""
    kind: Literal["requirement", "function", "data", "interface", "condition", "other"] = "requirement"
    text: str = ""
    location: str = ""
    decision: Literal["pending", "keep", "modify", "exclude"] = "pending"
    modified_text: str = ""
    reason: str = ""
    org_specific: list[str] = Field(default_factory=list)  # budget/period/personal_info/product/org_name
    applied_requirement_id: str = ""
    origin: Origin = "document"


# ---------------------------------------------------------------- 개발비 설정·견적
class DirectExpense(M):
    id: str = ""
    name: str = ""
    basis: str = ""
    amount: int = 0


class Rounding(M):
    unit: Literal[1, 10, 100, 1000] = 1
    mode: Literal["down", "half_up"] = "down"


class CostSettings(M):
    standard_id: str = "KOSA-FORM-2024G-241231"
    method: Literal["simple", "detailed"] = "simple"
    integration_level: int = Field(1, ge=1, le=5)
    performance_level: int = Field(1, ge=1, le=5)
    compatibility_level: int = Field(1, ge=1, le=5)
    security_level: int = Field(2, ge=1, le=5)
    profit_rate: str | None = None  # None → 기준 버전 기본값
    unit_price: int | None = None  # None → 기준 버전 값, 지정 시 '사용자 정의' 표시
    direct_expenses: list[DirectExpense] = Field(default_factory=list)
    rounding: Rounding = Field(default_factory=Rounding)
    vat_rate: str = "0.1"


class Scenario(M):
    id: str = ""
    created_at: str = ""
    target_amount: int
    target_includes_vat: bool = True
    fp_ids: list[str] = Field(default_factory=list)
    result: dict[str, Any] = Field(default_factory=dict)
    note: str = ""


class EstimateVersion(M):
    id: str = ""
    created_at: str = ""
    label: str = ""
    method: Literal["simple", "detailed"] = "simple"
    standard_snapshot: dict[str, Any] = Field(default_factory=dict)
    settings_snapshot: dict[str, Any] = Field(default_factory=dict)
    phases_snapshot: dict[str, Any] = Field(default_factory=dict)
    fp_snapshot: list[dict[str, Any]] = Field(default_factory=list)
    input_hash: str = ""
    result: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    complete: bool = True
    mode: str = ""
    scenarios: list[Scenario] = Field(default_factory=list)


# ---------------------------------------------------------------- 검토·추천
class ReviewFinding(M):
    id: str = ""
    category: str = ""
    verdict: Literal["match", "diff", "check", "insufficient"] = "check"
    location: str = ""
    original_value: str = ""
    compared_value: str = ""
    reason: str = ""
    suggestion: str = ""
    question_to_vendor: str = ""
    document_ids: list[str] = Field(default_factory=list)
    doc_check_only: bool = True  # 자료 일치 검토(실제 시스템 검증 아님)
    origin: Origin = "system"


class ReviewRun(M):
    ran_at: str = ""
    document_ids: list[str] = Field(default_factory=list)
    mode: str = ""
    summary: dict[str, int] = Field(default_factory=dict)


class TechInputs(M):
    deployment: Literal["unknown", "onprem", "cloud", "hybrid"] = "unknown"
    network: Literal["unknown", "internal", "external", "both"] = "unknown"
    existing_os: str = ""
    existing_db: str = ""
    existing_was: str = ""
    licenses: str = ""
    ops_staff: Literal["unknown", "none", "part_time", "dedicated"] = "unknown"
    total_users: int | None = None
    concurrent_users: int | None = None
    data_growth_gb_per_year: float | None = None
    file_storage: bool = False
    integrations: str = ""
    availability: Literal["normal", "high"] = "normal"
    preferred_stack: str = ""


class TechRec(M):
    id: str = ""
    area: str = ""  # 서버구성/OS/WAS/DB/프레임워크/백업/보안 등
    proposal: str = ""
    reason: str = ""
    assumptions: str = ""
    alternatives: str = ""
    compatibility: str = ""
    license: str = ""
    support_status: str = "현재 상태 미확인"
    ops_difficulty: str = ""
    official_source_ids: list[str] = Field(default_factory=list)
    paid_item: bool = False  # 별도 유료 SW·서비스(개발비 미합산)


class OfficialSource(M):
    id: str = ""
    title: str = ""
    url: str = ""
    publisher: str = ""
    checked_at: str = ""
    version_info: str = ""
    support_status: str = ""
    status: Literal["registered_unverified", "fetched", "verified_by_user"] = "registered_unverified"
    note: str = ""


class TechSection(M):
    inputs: TechInputs = Field(default_factory=TechInputs)
    recommendations: list[TechRec] = Field(default_factory=list)
    ran_at: str = ""
    mode: str = ""


# ---------------------------------------------------------------- 제안(AI 변경안)
class ProposalItem(M):
    key: str
    op: Literal["add", "update"]
    collection: str
    target_id: str = ""
    data: dict[str, Any] = Field(default_factory=dict)
    before: dict[str, Any] = Field(default_factory=dict)
    reason: str = ""
    status: Literal["pending", "applied", "rejected", "conflict"] = "pending"
    applied_id: str = ""


class Proposal(M):
    id: str = ""
    kind: str = ""
    created_at: str = ""
    mode: str = ""
    source: str = ""  # 만든 AI 연결 표시(예: 'OpenAI(ChatGPT) · 모델명')
    job_id: str = ""
    status: Literal["pending", "partial", "applied", "rejected"] = "pending"
    summary: str = ""
    warnings: list[str] = Field(default_factory=list)
    items: list[ProposalItem] = Field(default_factory=list)


class TaskSection(M):
    key: str
    title: str
    text: str = ""
    user_edited: bool = False
    regenerated_candidate: str = ""


class TaskDraft(M):
    generated_at: str = ""
    input_hash: str = ""
    sections: list[TaskSection] = Field(default_factory=list)


# ---------------------------------------------------------------- 프로젝트
class Project(M):
    schema_version: int = SCHEMA_VERSION
    id: str = ""
    name: str = ""
    created_at: str = ""
    updated_at: str = ""
    overview: Overview = Field(default_factory=Overview)
    ai_profile: str = ""  # 이 프로젝트에 쓸 AI 연결 이름(비우면 서버 기본 연결)
    counters: dict[str, int] = Field(default_factory=dict)
    requirements: list[Requirement] = Field(default_factory=list)
    workflows: list[WorkflowStep] = Field(default_factory=list)
    functions: list[FunctionDesign] = Field(default_factory=list)
    screens: list[Screen] = Field(default_factory=list)
    data_entities: list[DataEntity] = Field(default_factory=list)
    interfaces: list[Interface] = Field(default_factory=list)
    fp_items: list[FPItem] = Field(default_factory=list)
    questions: list[Question] = Field(default_factory=list)
    assumptions: list[Assumption] = Field(default_factory=list)
    documents: list[DocumentMeta] = Field(default_factory=list)
    sources: list[SourceRef] = Field(default_factory=list)
    reference_items: list[ReferenceItem] = Field(default_factory=list)
    cost_settings: CostSettings = Field(default_factory=CostSettings)
    estimates: list[EstimateVersion] = Field(default_factory=list)
    reviews: list[ReviewFinding] = Field(default_factory=list)
    review_run: ReviewRun = Field(default_factory=ReviewRun)
    tech: TechSection = Field(default_factory=TechSection)
    official_sources: list[OfficialSource] = Field(default_factory=list)
    proposals: list[Proposal] = Field(default_factory=list)
    task_draft: TaskDraft = Field(default_factory=TaskDraft)


# 편집 가능한 컬렉션: (모델, ID 접두어)
COLLECTIONS: dict[str, tuple[type[M], str]] = {
    "requirements": (Requirement, "REQ"),
    "workflows": (WorkflowStep, "WF"),
    "functions": (FunctionDesign, "FN"),
    "screens": (Screen, "SCR"),
    "data_entities": (DataEntity, "DAT"),
    "interfaces": (Interface, "IF"),
    "fp_items": (FPItem, "FP"),
    "questions": (Question, "Q"),
    "assumptions": (Assumption, "AS"),
    "reference_items": (ReferenceItem, "REF"),
    "reviews": (ReviewFinding, "RV"),
    "official_sources": (OfficialSource, "OS"),
}

# 다른 컬렉션을 참조하는 링크 필드: 필드명 → 대상 컬렉션
LINK_FIELDS: dict[str, str] = {
    "requirement_ids": "requirements",
    "function_ids": "functions",
    "screen_ids": "screens",
    "data_ids": "data_entities",
    "interface_ids": "interfaces",
}

# 변경 시 영향을 받는 종속 관계: 원천 컬렉션 → [(종속 컬렉션, 링크 필드)]
DEPENDENTS: dict[str, list[tuple[str, str]]] = {
    "requirements": [("functions", "requirement_ids"), ("fp_items", "requirement_ids"), ("workflows", "requirement_ids")],
    "functions": [("fp_items", "function_ids"), ("screens", "function_ids"), ("data_entities", "function_ids"), ("interfaces", "function_ids")],
    "data_entities": [("fp_items", "data_ids"), ("functions", "data_ids")],
    "interfaces": [("functions", "interface_ids")],
    "screens": [("functions", "screen_ids")],
}

LABELS = {
    "requirements": "요구사항",
    "workflows": "업무흐름",
    "functions": "기능설계",
    "screens": "화면",
    "data_entities": "데이터",
    "interfaces": "연계",
    "fp_items": "FP 항목",
    "questions": "질문",
    "assumptions": "가정",
    "reference_items": "참고문서 항목",
    "reviews": "검토의견",
    "official_sources": "공식 자료",
}
