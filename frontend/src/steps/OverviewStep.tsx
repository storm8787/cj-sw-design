import { useState } from "react";
import { api, P } from "../api";
import { Field, Help, Section, useProject } from "../components/ui";
import { SYSTEM_KINDS } from "../labels";
import type { Overview, ProjectResponse } from "../types";

const PHASES: [keyof Overview["phases"], string][] = [
  ["analysis", "분석"],
  ["design", "설계"],
  ["implementation", "구현"],
  ["test", "시험"],
];

export default function OverviewStep() {
  const { data, setData, run, busy } = useProject();
  const p = data.project;
  const [name, setName] = useState(p.name);
  const [ov, setOv] = useState<Overview>(p.overview);
  const [delName, setDelName] = useState("");
  const set = <K extends keyof Overview>(k: K, v: Overview[K]) => setOv({ ...ov, [k]: v });
  const partial = PHASES.some(([k]) => !ov.phases[k]);

  const save = async () => {
    const r = await run(() => api.patch<ProjectResponse>(P(p.id), { name, overview: ov, version: data.version }), "저장했습니다.");
    if (r) {
      setData(r);
      setOv(r.project.overview);
    }
  };
  const del = async () => {
    const r = await run(() => api.del(`${P(p.id)}?confirm_name=${encodeURIComponent(delName)}`));
    if (r) location.hash = "#/";
  };

  return (
    <>
      <Section title="사업 개요" right={<button className="primary" disabled={busy} onClick={save}>저장</button>}>
        <div className="form-grid">
          <Field label="사업 이름">
            <input value={name} onChange={(e) => setName(e.target.value)} />
          </Field>
          <Field label="사업 유형">
            <select value={ov.business_type} onChange={(e) => set("business_type", e.target.value as Overview["business_type"])}>
              <option value="system">일반 SW·정보시스템 신규개발</option>
              <option value="portal">홈페이지·포털 신규개발</option>
            </select>
          </Field>
          <Field label="시작 방식">
            <select value={ov.start_mode} onChange={(e) => set("start_mode", e.target.value as Overview["start_mode"])}>
              <option value="idea">구상 기반</option>
              <option value="document">참고문서 기반</option>
              <option value="review">기존 문서 검토</option>
            </select>
          </Field>
          <Field label="처음 구상(원문)">
            <textarea rows={2} value={ov.idea_text} onChange={(e) => set("idea_text", e.target.value)} />
          </Field>
          <Field label="목적">
            <textarea rows={2} value={ov.purpose} onChange={(e) => set("purpose", e.target.value)} />
          </Field>
          <Field label="추진 배경">
            <textarea rows={2} value={ov.background} onChange={(e) => set("background", e.target.value)} />
          </Field>
          <Field label="이용자">
            <input value={ov.users} onChange={(e) => set("users", e.target.value)} placeholder="예: 직원 1,200명, 담당자 3명" />
          </Field>
          <Field label="구축 방식">
            <input value={ov.build_method} onChange={(e) => set("build_method", e.target.value)} placeholder="예: 외주 신규개발" />
          </Field>
          <Field label="사업 기간(개월)">
            <input type="number" value={ov.period_months ?? ""} onChange={(e) => set("period_months", e.target.value ? Number(e.target.value) : null)} />
          </Field>
          <Field label="기관 환경">
            <textarea rows={2} value={ov.org_environment} onChange={(e) => set("org_environment", e.target.value)} placeholder="예: 내부망, 기존 인사시스템 운영 중" />
          </Field>
          <Field label="시스템 형태">
            <div className="checks">
              {Object.entries(SYSTEM_KINDS).map(([k, l]) => (
                <label key={k}>
                  <input type="checkbox" checked={ov.system_kinds.includes(k)} onChange={(e) => set("system_kinds", e.target.checked ? [...ov.system_kinds, k] : ov.system_kinds.filter((x) => x !== k))} /> {l}
                </label>
              ))}
            </div>
          </Field>
          <Field label={<>FP 측정 대상 애플리케이션(경계) <Help term="BOUNDARY" /></>} hint="이 이름과 다른 애플리케이션의 처리는 FP에 넣지 않습니다.">
            <input value={ov.boundary_name} onChange={(e) => set("boundary_name", e.target.value)} placeholder="예: 교육관리시스템" />
          </Field>
        </div>
      </Section>

      <Section title="금액 조건(먼저 정하기)">
        <div className="form-grid">
          <Field label="예산">
            <select value={ov.budget_mode} onChange={(e) => set("budget_mode", e.target.value as Overview["budget_mode"])}>
              <option value="none">예산 미지정(기준 산정만)</option>
              <option value="target">개발비 지정(목표예산 시나리오)</option>
            </select>
          </Field>
          {ov.budget_mode === "target" && (
            <>
              <Field label="목표 금액(원)">
                <input inputMode="numeric" value={ov.target_amount ?? ""} onChange={(e) => set("target_amount", e.target.value ? Number(e.target.value.replace(/[^0-9]/g, "")) : null)} />
              </Field>
              <Field label="부가세">
                <select value={ov.target_includes_vat ? "1" : "0"} onChange={(e) => set("target_includes_vat", e.target.value === "1")}>
                  <option value="1">포함</option>
                  <option value="0">별도</option>
                </select>
              </Field>
            </>
          )}
          <Field label="포함 단계" hint={partial ? "일부 단계만 포함하면 단계별 비율을 직접 입력해야 합니다(공식 비율 미확인)." : "4단계 모두 포함(비율 1.0)"}>
            <div className="checks">
              {PHASES.map(([k, l]) => (
                <label key={k}>
                  <input type="checkbox" checked={ov.phases[k]} onChange={(e) => set("phases", { ...ov.phases, [k]: e.target.checked })} /> {l}
                </label>
              ))}
            </div>
          </Field>
          {partial &&
            PHASES.filter(([k]) => ov.phases[k]).map(([k, l]) => (
              <Field key={k} label={`${l} 단계 비율(0~1)`}>
                <input value={ov.phase_ratios[k] ?? ""} onChange={(e) => set("phase_ratios", { ...ov.phase_ratios, [k]: e.target.value || null })} placeholder="예: 0.25" />
              </Field>
            ))}
        </div>
        <p className="muted small">장비 구매비는 개발비 합계에 넣지 않습니다. HW·SW 구성은 '검토·추천' 단계에서 참고용으로 제시합니다.</p>
      </Section>

      <Section title="프로젝트 삭제">
        <p className="muted">삭제하면 이 프로젝트의 데이터·첨부·견적이 모두 지워지고 되돌릴 수 없습니다. 다른 프로젝트에는 영향이 없습니다. 먼저 '엑셀' 단계에서 JSON 백업을 받아 두세요.</p>
        <div className="row-actions">
          <input placeholder="확인을 위해 프로젝트 이름 입력" value={delName} onChange={(e) => setDelName(e.target.value)} aria-label="삭제 확인용 이름" />
          <button className="danger" disabled={delName !== p.name || busy} onClick={del}>
            삭제
          </button>
        </div>
      </Section>
    </>
  );
}
