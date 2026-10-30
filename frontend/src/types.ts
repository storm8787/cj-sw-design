// 서버 모델(backend/app/models.py)의 화면용 타입. 서버가 기준이며 여기서는 화면에 쓰는 필드만 정의한다.
export type Status = "draft" | "review" | "confirmed" | "excluded";
export type Origin = "user" | "ai" | "sample" | "document" | "system";

export interface Tracked {
  id: string;
  origin: Origin;
  status: Status;
  needs_review: boolean;
  review_reason: string;
  source_ids: string[];
  note: string;
}

export interface Requirement extends Tracked {
  kind: "functional" | "nonfunctional";
  category: string;
  title: string;
  original_text: string;
  description: string;
  priority: "high" | "medium" | "low";
  acceptance: string;
  why: string;
}

export interface FPItem extends Tracked {
  name: string;
  application: string;
  business: string;
  description: string;
  fp_type: "EI" | "EO" | "EQ" | "ILF" | "EIF" | null;
  rationale: string;
  uncertainty: string;
  det: number | null;
  ftr_ret: number | null;
  assumed_complexity: "L" | "A" | "H" | null;
  assumption_note: string;
  requirement_ids: string[];
  function_ids: string[];
  data_ids: string[];
  duplicate_of: string;
  /** 업무 확인(우리 사업에 있는 처리·자료) — FP 기술 검토 확정과 별개 */
  scope_confirmed: boolean;
  /** 정통법 근거 목록(코드가 개수를 셈) */
  det_items: string[];
  ret_groups: string[];
}

export interface QuestionOption {
  value: string;
  label: string;
  recommended: boolean;
  adds_requirements: string[];
}

export interface Question {
  id: string;
  topic: string;
  text: string;
  why: string;
  options: QuestionOption[];
  allow_text: boolean;
  recommended_value: string;
  recommended_reason: string;
  answer: string;
  answer_kind: "" | "choice" | "text" | "unknown";
  status: "open" | "answered" | "deferred";
  origin: Origin;
  batch: number;
}

export interface Extraction {
  status: string;
  quality: string;
  messages: string[];
  pages: number | null;
  chars: number;
  chunks_total: number;
  chunks_analyzed: number;
  analysis_status: "not_started" | "partial" | "complete" | "failed";
}

export interface DocumentMeta {
  id: string;
  file_name: string;
  kind: string;
  format: string;
  size: number;
  uploaded_at: string;
  extraction: Extraction;
  ai_consent: boolean;
}

export interface ReferenceItem {
  id: string;
  document_id: string;
  source_id: string;
  kind: string;
  text: string;
  location: string;
  decision: "pending" | "keep" | "modify" | "exclude";
  modified_text: string;
  reason: string;
  org_specific: string[];
  applied_requirement_id: string;
  origin: Origin;
}

export interface ProposalItem {
  key: string;
  op: "add" | "update";
  collection: string;
  target_id: string;
  data: Record<string, unknown>;
  before: Record<string, unknown>;
  reason: string;
  status: "pending" | "applied" | "rejected" | "conflict" | "merged";
  applied_id: string;
}

export interface Proposal {
  id: string;
  kind: string;
  created_at: string;
  mode: string;
  source: string;
  status: "pending" | "partial" | "applied" | "rejected";
  summary: string;
  warnings: string[];
  items: ProposalItem[];
}

export interface Money {
  complete: boolean;
  warnings: string[];
  total_fp: string;
  unit_price: number;
  size_factor: string;
  factors: { key: string; label: string; level: number; level_text: string; value: string }[];
  phase_text: string;
  dev_cost_raw?: string;
  dev_cost?: number;
  profit_rate?: string;
  profit?: number;
  direct_total?: number;
  supply?: number;
  vat?: number;
  total?: number;
  rounding?: { unit: number; mode: string; label: string };
  basis?: string[];
}

export interface ScenarioResult {
  target_amount: number;
  target_includes_vat: boolean;
  base_total: number;
  difference_total: number;
  adjustment_ratio: string;
  adjustment_ratio_display: string;
  base_total_fp: string;
  equivalent_fp: string;
  equivalent_unit_price: string;
  dev_cost: number;
  profit: number;
  direct_total: number;
  rounding_adjustment: number;
  supply: number;
  vat: number;
  total: number;
  vat_method_text: string;
  matches_target: boolean;
  method_text: string;
  warnings: string[];
}

export interface Scenario {
  id: string;
  created_at: string;
  target_amount: number;
  target_includes_vat: boolean;
  fp_ids: string[];
  result: ScenarioResult;
}

export interface Estimate {
  id: string;
  created_at: string;
  label: string;
  method: "simple" | "detailed";
  standard_snapshot: { id: string; title: string };
  fp_snapshot: { id: string; name: string; fp_type: string; simple_weight: string | null; detailed_weight: number | null; complexity: string | null }[];
  result: { fp: { total_fp: string }; money: Money; basis?: EstimateBasis };
  warnings: string[];
  complete: boolean;
  mode: string;
  scenarios: Scenario[];
}

export interface ReviewFinding {
  id: string;
  category: string;
  verdict: "match" | "diff" | "check" | "insufficient";
  location: string;
  original_value: string;
  compared_value: string;
  reason: string;
  suggestion: string;
  question_to_vendor: string;
  doc_check_only: boolean;
}

export interface TechRec {
  id: string;
  area: string;
  proposal: string;
  reason: string;
  assumptions: string;
  alternatives: string;
  compatibility: string;
  license: string;
  support_status: string;
  ops_difficulty: string;
  official_source_ids: string[];
  paid_item: boolean;
}

export interface OfficialSource {
  id: string;
  title: string;
  url: string;
  publisher: string;
  checked_at: string;
  version_info: string;
  support_status: string;
  status: "registered_unverified" | "fetched" | "verified_by_user";
  note: string;
}

export interface CostSettings {
  standard_id: string;
  method: "simple" | "detailed";
  integration_level: number;
  performance_level: number;
  compatibility_level: number;
  security_level: number;
  profit_rate: string | null;
  unit_price: number | null;
  direct_expenses: { id: string; name: string; basis: string; amount: number }[];
  rounding: { unit: 1 | 10 | 100 | 1000; mode: "down" | "half_up" };
  vat_rate: string;
}

export interface Overview {
  business_type: "portal" | "system";
  start_mode: "idea" | "document" | "review";
  budget_mode: "none" | "target";
  target_amount: number | null;
  target_includes_vat: boolean;
  phases: { analysis: boolean; design: boolean; implementation: boolean; test: boolean };
  phase_ratios: { analysis: string | null; design: string | null; implementation: string | null; test: string | null };
  idea_text: string;
  purpose: string;
  background: string;
  users: string;
  build_method: string;
  period_months: number | null;
  org_environment: string;
  system_kinds: string[];
  boundary_name: string;
  boundary_note: string;
}

export type Row = Record<string, unknown> & { id: string };

export interface Project {
  id: string;
  name: string;
  updated_at: string;
  overview: Overview;
  ai_profile: string;
  requirements: Requirement[];
  workflows: Row[];
  functions: Row[];
  screens: Row[];
  data_entities: Row[];
  interfaces: Row[];
  fp_items: FPItem[];
  questions: Question[];
  assumptions: Row[];
  documents: DocumentMeta[];
  sources: Row[];
  reference_items: ReferenceItem[];
  cost_settings: CostSettings;
  estimates: Estimate[];
  reviews: ReviewFinding[];
  review_run: { ran_at: string; document_ids: string[]; mode: string; summary: Record<string, number> };
  tech: { inputs: Record<string, unknown>; recommendations: TechRec[]; ran_at: string; mode: string };
  official_sources: OfficialSource[];
  proposals: Proposal[];
  task_draft: { generated_at: string; sections: { key: string; title: string; text: string; user_edited: boolean; regenerated_candidate: string }[] };
}

export type BasisKind = "empty" | "partial" | "estimated" | "confirmed";

export interface EstimateBasis {
  basis: BasisKind;
  label: string;
  counted: number;
  scope_only_ids: string[];
  assumed_ids: string[];
  pending: Record<string, string[]>;
  reasons: string[];
}

export interface ChecklistItem {
  category: string;
  ref: string;
  text: string;
  step: string;
}

export interface ProjectStatus {
  counts: Record<string, number>;
  fp_total: { simple: string; detailed: string; detailed_complete: boolean; simple_basis?: BasisKind; detailed_basis?: BasisKind };
  fp_basis?: { simple: EstimateBasis; detailed: EstimateBasis; method: string };
  checklist?: ChecklistItem[];
  checklist_summary?: Record<string, number>;
  estimate_states: Record<string, "current" | "stale">;
  task_draft_stale: boolean;
  needs_review_ids: string[];
  next_steps: { step: string; text: string }[];
}

export interface ProjectResponse {
  project: Project;
  version: number;
  status: ProjectStatus;
  ai: AIConnection;
}

export interface Job {
  id: string;
  kind: string;
  status: "queued" | "running" | "succeeded" | "failed" | "interrupted";
  progress: number;
  message: string;
  error: string | null;
  result: Record<string, unknown> | null;
  created_at: string;
  /** 실제 AI 호출 사용량(토큰 수만). 공급자가 주지 않은 값은 null(미측정) */
  usage?: { calls: number; models: string[]; input_tokens: number | null; cached_tokens: number | null; output_tokens: number | null; reasoning_tokens: number | null; latency_ms: number; failed_calls: number } | null;
}

export interface AIConnection {
  name: string;
  kind: string;
  label: string;
  model: string;
  external: boolean;
  is_real_ai: boolean;
  display: string;
  usable: boolean;
  missing: string[];
  default?: boolean;
  note?: string;
}

export interface SystemInfo {
  ai: AIConnection;
  ai_profiles: AIConnection[];
  default_profile: string;
  mode_label: string;
  app_env: string;
  auth_disabled: boolean;
  max_upload_mb: number;
  allowed_formats: string[];
  standards: { id: string; title: string; builtin: boolean; official_guide_checked: boolean }[];
}

export interface FPSummaryItem {
  id: string;
  name: string;
  fp_type: string | null;
  status: string;
  counted: boolean;
  count_basis?: "confirmed" | "scope" | "";
  simple_weight: string | null;
  complexity: string | null;
  complexity_source: string;
  detailed_weight: number | null;
  det_used?: number | null;
  ftr_ret_used?: number | null;
  detailed_note?: string;
  issues: string[];
}

export interface FPSummary {
  items: FPSummaryItem[];
  simple: { total_fp: string; by_type: Record<string, { count: number; fp: string }> };
  detailed: { total_fp: string; complete: boolean; missing_ids: string[]; assumed_ids: string[]; by_type: Record<string, { count: number; fp: number }> };
  tentative_simple_fp_including_unconfirmed: string;
  basis: { simple: EstimateBasis; detailed: EstimateBasis };
  foreign_text_ids?: string[];
  duplicate_ids?: string[];
  counts: Record<string, number>;
  coverage: { rows: { requirement_id: string; title: string; kind: string; state: string; fp_ids: string[] }[] };
  standard: { id: string; title: string; official_guide_checked: boolean };
}
