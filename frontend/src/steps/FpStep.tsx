import { useEffect, useState } from "react";
import { api, P } from "../api";
import { EditableTable, type Col } from "../components/EditableTable";
import { JobStatus, useJobRunner } from "../components/Jobs";
import { Proposals } from "../components/Proposals";
import { ActionButton, Badge, EditArea, Field, Help, Section, Warn, useProject } from "../components/ui";
import { CX_SOURCE, num, won } from "../labels";
import type { CostSettings, Estimate, FPSummary, ProjectResponse, Row } from "../types";

const TYPE_OPTS: [string, string][] = [["__null", "미분류"], ["EI", "EI 외부입력"], ["EO", "EO 외부출력"], ["EQ", "EQ 외부조회"], ["ILF", "ILF 내부논리파일"], ["EIF", "EIF 외부연계파일"]];

export default function FpStep() {
  const { data } = useProject();
  const pid = data.project.id;
  const [sum, setSum] = useState<FPSummary | null>(null);
  const jr = useJobRunner();
  useEffect(() => {
    api.get<FPSummary>(`${P(pid)}/fp`).then(setSum);
  }, [pid, data.version]);
  const byId = Object.fromEntries((sum?.items || []).map((i) => [i.id, i]));
  const cols: Col[] = [
    { key: "name", label: "단위프로세스·데이터명", width: 160 },
    { key: "application", label: "애플리케이션", width: 100 },
    { key: "fp_type", label: "유형", type: "select", options: TYPE_OPTS, width: 110 },
    { key: "rationale", label: "분류 근거", type: "textarea" },
    { key: "ftr_ret", label: "FTR/RET", type: "number", width: 60 },
    { key: "det", label: "DET", type: "number", width: 55 },
    { key: "assumed_complexity", label: "가정 복잡도", type: "select", options: [["__null", "없음"], ["L", "L 낮음"], ["A", "A 보통"], ["H", "H 높음"]], width: 80 },
    { key: "assumption_note", label: "가정 사유", width: 90 },
    { key: "requirement_ids", label: "요구사항ID", type: "ids", width: 90 },
    { key: "duplicate_of", label: "중복 대상ID", width: 70 },
    {
      key: "_score",
      label: "점수(코드 계산)",
      readOnly: true,
      width: 130,
      render: (r) => {
        const s = byId[r.id];
        if (!s) return "-";
        return (
          <div className="small">
            간이 {s.simple_weight ?? "-"} / 정통 {s.detailed_weight ?? "-"} {s.complexity ? `(${s.complexity})` : ""}
            <div className="muted">{CX_SOURCE[s.complexity_source]}{s.counted ? " · 집계" : " · 미집계"}</div>
            {s.issues.filter((i) => !i.startsWith("미확정 항목")).map((i, k) => (
              <div key={k} className="issue">{i}</div>
            ))}
          </div>
        );
      },
    },
  ];
  return (
    <>
      <Section
        title="FP 항목"
        help={<Help term="FP" />}
        right={
          <ActionButton className="primary" disabled={jr.running} onClick={() => jr.start(`${P(pid)}/ai/fp_candidates`)}>
            기능·데이터로 FP 후보 만들기
          </ActionButton>
        }
      >
        <p className="muted small">
          유형 설명: EI <Help term="EI" /> EO <Help term="EO" /> EQ <Help term="EQ" /> ILF <Help term="ILF" /> EIF <Help term="EIF" /> · DET <Help term="DET" /> FTR <Help term="FTR" /> RET <Help term="RET" />. 점수는 직접 입력하지 않고 유형·DET·FTR/RET·상태를 고치면 코드가 다시 계산합니다. '확정' 항목만 기준 산정에 들어갑니다.
        </p>
        <JobStatus job={jr.job} running={jr.running} onRetry={jr.retry} note={jr.note} />
      </Section>
      <Proposals kinds={["fp_candidates"]} />
      {sum && <FpSummaryBox sum={sum} />}
      <Section title="FP 항목 표">
        <EditableTable collection="fp_items" rows={data.project.fp_items as unknown as Row[]} cols={cols} defaults={{ application: data.project.overview.boundary_name }} addLabel="FP 항목 추가" />
      </Section>
      {sum && <Coverage sum={sum} />}
      <CostPanel />
      <Estimates />
    </>
  );
}

function FpSummaryBox({ sum }: { sum: FPSummary }) {
  return (
    <Section title="FP 집계(확정 항목)" help={<><Help term="SIMPLE" /> <Help term="DETAILED" /></>}>
      <div className="kpis">
        <div className="kpi">
          <span>간이법</span>
          <b>{num(sum.simple.total_fp, 1)} FP</b>
        </div>
        <div className="kpi">
          <span>정통법</span>
          <b>{sum.detailed.total_fp} FP</b>
          {!sum.detailed.complete && <Badge kind="st-review">미확정(입력 누락 {sum.detailed.missing_ids.length})</Badge>}
        </div>
        <div className="kpi">
          <span>미확정 포함 추정(간이, 참고)</span>
          <b>{num(sum.tentative_simple_fp_including_unconfirmed, 1)} FP</b>
        </div>
        <div className="kpi">
          <span>미확정·미분류·중복의심·경계</span>
          <b>
            {sum.counts.unconfirmed} · {sum.counts.unclassified} · {sum.counts.duplicate_suspects} · {sum.counts.boundary_issues}
          </b>
        </div>
      </div>
      <table className="grid compact">
        <thead>
          <tr>
            <th>유형</th>
            {["ILF", "EIF", "EI", "EO", "EQ"].map((t) => (
              <th key={t}>{t}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          <tr>
            <td>간이법 건수/점수</td>
            {["ILF", "EIF", "EI", "EO", "EQ"].map((t) => (
              <td key={t}>
                {sum.simple.by_type[t].count} / {num(sum.simple.by_type[t].fp, 1)}
              </td>
            ))}
          </tr>
          <tr>
            <td>정통법 건수/점수</td>
            {["ILF", "EIF", "EI", "EO", "EQ"].map((t) => (
              <td key={t}>
                {sum.detailed.by_type[t].count} / {sum.detailed.by_type[t].fp}
              </td>
            ))}
          </tr>
        </tbody>
      </table>
      <p className="muted small">기준: {sum.standard.title} {sum.standard.official_guide_checked ? "" : "· 가이드 원문 미확인(양식 수식 기준)"}</p>
    </Section>
  );
}

function Coverage({ sum }: { sum: FPSummary }) {
  const rows = sum.coverage.rows;
  if (!rows.length) return null;
  return (
    <Section title="요구사항별 FP 연결">
      <table className="grid compact">
        <tbody>
          {rows.map((r) => (
            <tr key={r.requirement_id} className={r.state === "FP 미연결" ? "needs-review" : ""}>
              <td>
                <code>{r.requirement_id}</code>
              </td>
              <td>{r.title}</td>
              <td>{r.state}</td>
              <td className="small">{r.fp_ids.join(", ")}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </Section>
  );
}

const FACTORS: [keyof CostSettings, string, string[]][] = [
  ["integration_level", "연계복잡성", ["1 타 기관 연계 없음 (0.88)", "2 1~2개 (0.94)", "3 3~5개 (1.00)", "4 6~10개 (1.06)", "5 10개 초과 (1.12)"]],
  ["performance_level", "성능 요구수준", ["1 특별한 요구 없음 (0.91)", "2 요구 있으나 특별 조치 불필요 (0.95)", "3 피크타임 중요·처리시한 명시 (1.00)", "4 모든 업무시간 중요 (1.05)", "5 엄격·성능분석도구 필요 (1.09)"]],
  ["compatibility_level", "운영환경 호환성", ["1 요구 없음 (0.94)", "2 동일 HW·SW 환경 (1.00)", "3 유사 환경 (1.06)", "4 이질적 환경 (1.13)", "5 4+운영절차 문서화·모의훈련 (1.19)"]],
  ["security_level", "보안성 요구수준", ["1 1가지 (0.97)", "2 2가지 (1.00)", "3 3가지 (1.03)", "4 4가지 (1.06)", "5 5가지 이상 (1.08)"]],
];

function CostPanel() {
  const { data, setData, run, busy, system } = useProject();
  const pid = data.project.id;
  const [cs, setCs] = useState<CostSettings>(data.project.cost_settings);
  const [preview, setPreview] = useState<{ complete: boolean; warnings: string[]; money: { total?: number; supply?: number; basis?: string[] }; fp: { total_fp: string } } | null>(null);
  useEffect(() => setCs(data.project.cost_settings), [data.project.cost_settings]);
  useEffect(() => {
    api.get<typeof preview>(`${P(pid)}/estimate-preview`).then(setPreview).catch(() => setPreview(null));
  }, [pid, data.version]);
  const save = async () => {
    const r = await run(() => api.put<ProjectResponse>(`${P(pid)}/cost-settings`, { ...cs, version: data.version }), "산정 설정을 저장했습니다.");
    if (r) setData(r);
  };
  const exp = cs.direct_expenses;
  return (
    <Section title="개발비 산정 설정" right={<ActionButton className="primary" disabled={busy} onClick={save}>설정 저장</ActionButton>}>
      <EditArea>
      <div className="form-grid">
        <Field label="산정 기준 버전">
          <select value={cs.standard_id} onChange={(e) => setCs({ ...cs, standard_id: e.target.value })}>
            {system.standards.map((s) => (
              <option key={s.id} value={s.id}>
                {s.id}
                {s.builtin ? "" : " (사용자 정의)"}
              </option>
            ))}
          </select>
        </Field>
        <Field label="산정 방법">
          <select value={cs.method} onChange={(e) => setCs({ ...cs, method: e.target.value as CostSettings["method"] })}>
            <option value="simple">간이법</option>
            <option value="detailed">정통법</option>
          </select>
        </Field>
        {FACTORS.map(([k, label, opts]) => (
          <Field key={k} label={`${label} 보정`}>
            <select value={cs[k] as number} onChange={(e) => setCs({ ...cs, [k]: Number(e.target.value) })}>
              {opts.map((o, i) => (
                <option key={i} value={i + 1}>
                  {o}
                </option>
              ))}
            </select>
          </Field>
        ))}
        <Field label="이윤율" hint="비우면 기준값(양식 예시 0.20, 공식 기준 미확인)을 씁니다.">
          <input value={cs.profit_rate ?? ""} onChange={(e) => setCs({ ...cs, profit_rate: e.target.value || null })} placeholder="0.20" />
        </Field>
        <Field label="FP당 단가(원)" hint="비우면 기준 버전 값(605,784원, 2024 가이드 표기 양식값)">
          <input value={cs.unit_price ?? ""} onChange={(e) => setCs({ ...cs, unit_price: e.target.value ? Number(e.target.value.replace(/[^0-9]/g, "")) : null })} placeholder="605784" />
        </Field>
        <Field label="끝수 처리" hint="공식 규정 미확인 — 기관 기준에 맞게 선택">
          <div className="row-actions">
            <select value={cs.rounding.unit} onChange={(e) => setCs({ ...cs, rounding: { ...cs.rounding, unit: Number(e.target.value) as 1 } })} aria-label="끝수 단위">
              <option value={1}>원 미만</option>
              <option value={10}>10원 미만</option>
              <option value={100}>100원 미만</option>
              <option value={1000}>1,000원 미만</option>
            </select>
            <select value={cs.rounding.mode} onChange={(e) => setCs({ ...cs, rounding: { ...cs.rounding, mode: e.target.value as "down" } })} aria-label="끝수 방식">
              <option value="down">절사</option>
              <option value="half_up">반올림</option>
            </select>
          </div>
        </Field>
      </div>
      <h4>직접경비(장비 구매비 제외)</h4>
      <table className="grid compact">
        <tbody>
          {exp.map((d, i) => (
            <tr key={i}>
              <td>
                <input value={d.name} onChange={(e) => setCs({ ...cs, direct_expenses: exp.map((x, j) => (j === i ? { ...x, name: e.target.value } : x)) })} placeholder="항목" aria-label="직접경비 항목" />
              </td>
              <td>
                <input value={d.basis} onChange={(e) => setCs({ ...cs, direct_expenses: exp.map((x, j) => (j === i ? { ...x, basis: e.target.value } : x)) })} placeholder="산출 내역" aria-label="산출 내역" />
              </td>
              <td>
                <input inputMode="numeric" value={d.amount} onChange={(e) => setCs({ ...cs, direct_expenses: exp.map((x, j) => (j === i ? { ...x, amount: Number(e.target.value.replace(/[^0-9]/g, "")) || 0 } : x)) })} aria-label="금액" />
              </td>
              <td>
                <button className="danger" onClick={() => setCs({ ...cs, direct_expenses: exp.filter((_, j) => j !== i) })}>
                  삭제
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <button onClick={() => setCs({ ...cs, direct_expenses: [...exp, { id: `DE-${Date.now()}`, name: "", basis: "", amount: 0 }] })}>+ 직접경비</button>
      </EditArea>
      {preview && (
        <div className="preview-box">
          <b>저장된 설정 기준 미리보기:</b> FP {preview.fp.total_fp} → 공급가액 {won(preview.money.supply)} / 총액(부가세 포함) {won(preview.money.total)} {!preview.complete && <Badge kind="st-review">미완료</Badge>}
          <Warn items={preview.warnings} />
        </div>
      )}
    </Section>
  );
}

function Estimates() {
  const { data, setData, run, busy } = useProject();
  const pid = data.project.id;
  const ov = data.project.overview;
  const [label, setLabel] = useState("");
  const [target, setTarget] = useState(ov.target_amount ? String(ov.target_amount) : "");
  const [vat, setVat] = useState(ov.target_includes_vat);
  const ests = [...data.project.estimates].reverse();
  const create = async () => {
    const r = await run(() => api.post<ProjectResponse>(`${P(pid)}/estimates`, { label }), "기준 산정 버전을 저장했습니다.");
    if (r) setData(r);
  };
  const scenario = async (e: Estimate) => {
    const r = await run(() => api.post<ProjectResponse>(`${P(pid)}/estimates/${e.id}/scenarios`, { target_amount: Number(target.replace(/[^0-9]/g, "")), includes_vat: vat }));
    if (r) setData(r);
  };
  return (
    <Section
      title="기준 산정(견적 버전)"
      right={
        <EditArea>
          <div className="row-actions">
            <input value={label} onChange={(e) => setLabel(e.target.value)} placeholder="버전 이름(선택)" aria-label="견적 버전 이름" />
            <ActionButton className="primary" disabled={busy} onClick={create}>
              기준 산정 실행·저장
            </ActionButton>
          </div>
        </EditArea>
      }
    >
      <p className="muted small">견적 버전은 당시 FP 내역·기준값·설정을 그대로 보관합니다. 이후 값을 바꾸면 '갱신 필요'로 표시되고 과거 버전은 남습니다.</p>
      {ests.map((e) => {
        const m = e.result.money;
        const state = data.status.estimate_states[e.id];
        return (
          <div key={e.id} className="estimate">
            <div className="row-actions">
              <b>
                {e.id} {e.label}
              </b>
              <Badge kind="st-confirmed">기준 산정</Badge>
              <span className="muted small">
                {e.created_at} · {e.method === "simple" ? "간이법" : "정통법"} · {e.standard_snapshot.id}
              </span>
              {state === "stale" ? <Badge kind="st-review">갱신 필요(이후 변경 있음)</Badge> : <Badge kind="st-confirmed">현재 데이터와 일치</Badge>}
              {!e.complete && <Badge kind="st-excluded">미완료</Badge>}
            </div>
            {m.complete ? (
              <table className="grid compact money">
                <tbody>
                  <tr><td>총 기능점수</td><td>{e.result.fp.total_fp} FP</td></tr>
                  <tr><td>개발원가(보정 후)</td><td>{won(m.dev_cost)}</td></tr>
                  <tr><td>이윤({num(Number(m.profit_rate) * 100, 2)}%)</td><td>{won(m.profit)}</td></tr>
                  <tr><td>직접경비</td><td>{won(m.direct_total)}</td></tr>
                  <tr><td>SW개발비(부가세 별도)</td><td>{won(m.supply)}</td></tr>
                  <tr><td>부가세</td><td>{won(m.vat)}</td></tr>
                  <tr className="total"><td>총액(부가세 포함)</td><td>{won(m.total)}</td></tr>
                </tbody>
              </table>
            ) : null}
            <details>
              <summary>계산 근거 보기</summary>
              <ol className="small">{m.basis?.map((b, i) => <li key={i}>{b}</li>)}</ol>
            </details>
            <Warn items={e.warnings} />
            {e.complete && (
              <div className="scenario-box">
                <b>목표예산 시나리오</b> <Help term="TARGET" />
                <EditArea>
                <div className="row-actions">
                  <input inputMode="numeric" value={target} onChange={(x) => setTarget(x.target.value)} placeholder="목표 금액(원)" aria-label="목표 금액" />
                  <select value={vat ? "1" : "0"} onChange={(x) => setVat(x.target.value === "1")} aria-label="부가세 포함 여부">
                    <option value="1">부가세 포함</option>
                    <option value="0">부가세 별도</option>
                  </select>
                  <ActionButton disabled={busy || !target} onClick={() => scenario(e)}>
                    시나리오 만들기
                  </ActionButton>
                </div>
                </EditArea>
                {e.scenarios.map((s) => {
                  const r = s.result;
                  return (
                    <div key={s.id} className="scenario">
                      <div>
                        <b>{s.id}</b> <Badge kind="st-review">예산 조정 결과(참고, 공식 측정값 아님)</Badge> <span className="muted small">{s.created_at}</span>
                      </div>
                      <table className="grid compact money">
                        <tbody>
                          <tr><td>목표 금액</td><td>{won(r.target_amount)} ({r.target_includes_vat ? "부가세 포함" : "부가세 별도"})</td></tr>
                          <tr><td>기준 산정 총액</td><td>{won(r.base_total)}</td></tr>
                          <tr><td>차이</td><td>{won(r.difference_total)}</td></tr>
                          <tr><td>조정 방식</td><td>단일 조정률 {r.adjustment_ratio_display}</td></tr>
                          <tr><td>기준 FP(보존)</td><td>{r.base_total_fp} FP</td></tr>
                          <tr><td>예산 대응 환산 FP(참고)</td><td>{num(r.equivalent_fp, 2)} FP</td></tr>
                          <tr><td>예산 대응 환산 단가(참고)</td><td>{won(Number(r.equivalent_unit_price))}</td></tr>
                          <tr><td>조정 개발원가 / 이윤 / 직접경비</td><td>{won(r.dev_cost)} / {won(r.profit)} / {won(r.direct_total)}</td></tr>
                          <tr><td>끝수조정(원 단위 일치용)</td><td>{won(r.rounding_adjustment)}</td></tr>
                          <tr><td>공급가액 / 부가세</td><td>{won(r.supply)} / {won(r.vat)} ({r.vat_method_text})</td></tr>
                          <tr className="total"><td>최종 참고 금액</td><td>{won(r.total)} {r.matches_target ? "· 목표액 일치" : "· 목표액과 차이 있음"}</td></tr>
                          <tr><td>기능 유지</td><td>FP 항목 {s.fp_ids.length}건 그대로 유지(삭제·추가 없음)</td></tr>
                        </tbody>
                      </table>
                      <p className="muted small">{r.method_text}</p>
                      <Warn items={r.warnings} />
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        );
      })}
      {!ests.length && <p className="muted">아직 기준 산정이 없습니다. FP 항목을 확정한 뒤 실행하세요.</p>}
    </Section>
  );
}
