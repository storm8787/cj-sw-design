"""AI(및 샘플 규칙) 응답 스키마. 모든 필드는 필수로 두어 구조화 출력 스키마와 맞춘다."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class B(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SuggestedReq(B):
    title: str
    kind: Literal["functional", "nonfunctional"]
    description: str


class OptionOut(B):
    value: str
    label: str
    recommended: bool
    adds: list[SuggestedReq]


class QuestionOut(B):
    key: str
    topic: str
    text: str
    why: str
    options: list[OptionOut]
    recommended_value: str
    recommended_reason: str


class QuestionsOut(B):
    questions: list[QuestionOut] = Field(max_length=8)


class ReqDraft(B):
    title: str
    kind: Literal["functional", "nonfunctional"]
    category: str
    description: str
    original_text: str
    priority: Literal["high", "medium", "low"]
    acceptance: str
    why: str
    from_user: bool


class RequirementsOut(B):
    requirements: list[ReqDraft] = Field(max_length=200)


class FuncDraft(B):
    key: str
    name: str
    actor: str
    purpose: str
    inputs: str
    outputs: str
    rules: str
    exceptions: str
    permissions: str
    acceptance: str
    requirement_ids: list[str]
    data_keys: list[str]
    existing_data_ids: list[str]
    interface_keys: list[str]
    reason: str


class DataDraft(B):
    key: str
    name: str
    description: str
    maintained_by: Literal["internal", "external", "unknown"]
    personal_info: bool
    requirement_ids: list[str]
    reason: str


class IfDraft(B):
    key: str
    name: str
    counterpart: str
    direction: Literal["inbound", "outbound", "both", "unknown"]
    method: str
    data_items: str
    requirement_ids: list[str]
    reason: str


class ScreenDraft(B):
    key: str
    name: str
    users: str
    description: str
    function_keys: list[str]
    reason: str


class FlowDraft(B):
    key: str
    order: int
    name: str
    actor: str
    description: str
    requirement_ids: list[str]


class DesignOut(B):
    functions: list[FuncDraft] = Field(max_length=300)
    data_entities: list[DataDraft] = Field(max_length=200)
    interfaces: list[IfDraft] = Field(max_length=100)
    screens: list[ScreenDraft] = Field(max_length=300)
    workflows: list[FlowDraft] = Field(max_length=200)


class FPDraft(B):
    name: str
    fp_type: Literal["EI", "EO", "EQ", "ILF", "EIF"] | None
    rationale: str
    uncertainty: str
    det: int | None
    ftr_ret: int | None
    requirement_ids: list[str]
    function_ids: list[str]
    data_ids: list[str]


class FPOut(B):
    items: list[FPDraft] = Field(max_length=500)


class RefDraft(B):
    kind: Literal["requirement", "function", "data", "interface", "condition", "other"]
    text: str
    location: str
    org_specific: list[Literal["budget", "period", "personal_info", "product", "org_name"]]


class RefOut(B):
    items: list[RefDraft] = Field(max_length=200)
