import { useState } from "react";
import { api, P } from "../api";
import { EditableTable, type Col } from "../components/EditableTable";
import { ActionButton, Badge, EditArea, Field, Section, useProject } from "../components/ui";
import { DOC_KIND, VERDICT } from "../labels";
import type { ProjectResponse, Row } from "../types";

export default function ReviewStep() {
  return (
    <>
      <ReviewPanel />
      <TechPanel />
      <SourcesPanel />
    </>
  );
}

function ReviewPanel() {
  const { data, setData, run, busy, goto } = useProject();
  const p = data.project;
  const [sel, setSel] = useState<string[]>(p.documents.map((d) => d.id));
  const [verdict, setVerdict] = useState("");
  const runReview = async () => {
    const r = await run(() => api.post<ProjectResponse>(`${P(p.id)}/review/run`, { document_ids: sel }), "검토를 실행했습니다.");
    if (r) setData(r);
  };
  const shown = verdict ? p.reviews.filter((f) => f.verdict === verdict) : p.reviews;
  return (
    <Section title="기존 문서 검토(대조)" right={<ActionButton className="primary" disabled={busy} onClick={runReview}>검토 실행</ActionButton>}>
      <p className="muted small">
        업체 과업·설계·FP·금액 문서를 '자료·질문' 단계에서 종류를 지정해 올린 뒤 실행하세요. 결과는 자료끼리의 일치 검토이며, 실제 성능·연계 가능성·보안 충족은 문서만으로 확정할 수 없습니다.{" "}
        <button className="link" onClick={() => goto("sources")}>
          문서 올리러 가기
        </button>
      </p>
      <EditArea>
      <div className="checks">
        {p.documents.map((d) => (
          <label key={d.id}>
            <input type="checkbox" checked={sel.includes(d.id)} onChange={(e) => setSel(e.target.checked ? [...sel, d.id] : sel.filter((x) => x !== d.id))} /> {d.file_name} <span className="muted small">({DOC_KIND[d.kind]})</span>
          </label>
        ))}
      </div>
      </EditArea>
      {p.review_run.ran_at && (
        <div className="row-actions">
          <span className="muted small">
            실행 {p.review_run.ran_at} · {p.review_run.mode}
          </span>
          {Object.entries(VERDICT).map(([k, l]) => (
            <button key={k} className={verdict === k ? "active" : ""} onClick={() => setVerdict(verdict === k ? "" : k)}>
              {l} {p.review_run.summary[k] || 0}
            </button>
          ))}
        </div>
      )}
      {p.review_run.ran_at && (
        <table className="grid">
          <thead>
            <tr>
              <th style={{ width: 60 }}>ID</th>
              <th style={{ width: 110 }}>분야·판정</th>
              <th>근거 위치 / 원문 값 / 비교 값</th>
              <th>이유</th>
              <th>수정안</th>
              <th>업체에 물어볼 질문</th>
            </tr>
          </thead>
          <tbody>
            {shown.map((f) => (
              <tr key={f.id}>
                <td>
                  <code>{f.id}</code>
                </td>
                <td>
                  {f.category}
                  <div>
                    <Badge kind={`v-${f.verdict}`}>{VERDICT[f.verdict]}</Badge>
                  </div>
                  {!f.doc_check_only && <div className="small error">문서로 확정 불가</div>}
                </td>
                <td className="small">
                  <div>{f.location}</div>
                  {f.original_value && <div>원문: {f.original_value}</div>}
                  {f.compared_value && <div>비교: {f.compared_value}</div>}
                </td>
                <td className="small">{f.reason}</td>
                <td className="small">{f.suggestion}</td>
                <td className="small">{f.question_to_vendor}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </Section>
  );
}

function TechPanel() {
  const { data, setData, run, busy } = useProject();
  const p = data.project;
  const [inp, setInp] = useState<Record<string, unknown>>(p.tech.inputs);
  const set = (k: string, v: unknown) => setInp({ ...inp, [k]: v });
  const save = async (recommend: boolean) => {
    let r = await run(() => api.put<ProjectResponse>(`${P(p.id)}/tech/inputs`, inp));
    if (r && recommend) r = await run(() => api.post<ProjectResponse>(`${P(p.id)}/tech/recommend`), "구성 추천을 만들었습니다.");
    if (r) setData(r);
  };
  const sel = (k: string, opts: [string, string][]) => (
    <select value={String(inp[k] ?? "")} onChange={(e) => set(k, e.target.value)}>
      {opts.map(([v, l]) => (
        <option key={v} value={v}>
          {l}
        </option>
      ))}
    </select>
  );
  const numIn = (k: string) => <input type="number" value={inp[k] === null || inp[k] === undefined ? "" : String(inp[k])} onChange={(e) => set(k, e.target.value === "" ? null : Number(e.target.value))} />;
  return (
    <Section title="HW·SW 구성 추천(설계 보조)" right={<ActionButton className="primary" disabled={busy} onClick={() => save(true)}>입력 저장 후 추천</ActionButton>}>
      <EditArea>
      <div className="form-grid">
        <Field label="구축 방식">{sel("deployment", [["unknown", "미정"], ["onprem", "자체 서버"], ["cloud", "클라우드"], ["hybrid", "혼합"]])}</Field>
        <Field label="망 구분">{sel("network", [["unknown", "미정"], ["internal", "내부망"], ["external", "인터넷"], ["both", "둘 다"]])}</Field>
        <Field label="운영 담당 인력">{sel("ops_staff", [["unknown", "미정"], ["none", "없음"], ["part_time", "겸임"], ["dedicated", "전담"]])}</Field>
        <Field label="가용성 요구">{sel("availability", [["normal", "일반"], ["high", "높음(이중화)"]])}</Field>
        <Field label="전체 이용자 수">{numIn("total_users")}</Field>
        <Field label="동시 접속(최대)">{numIn("concurrent_users")}</Field>
        <Field label="연간 데이터 증가(GB)">{numIn("data_growth_gb_per_year")}</Field>
        <Field label="첨부파일 저장">{sel("file_storage", [["false", "없음"], ["true", "있음"]])}</Field>
        <Field label="기존 OS">
          <input value={String(inp.existing_os ?? "")} onChange={(e) => set("existing_os", e.target.value)} />
        </Field>
        <Field label="기존 DB·라이선스">
          <input value={String(inp.existing_db ?? "")} onChange={(e) => set("existing_db", e.target.value)} placeholder="예: Oracle 19c(코어 4)" />
        </Field>
        <Field label="기존 WAS">
          <input value={String(inp.existing_was ?? "")} onChange={(e) => set("existing_was", e.target.value)} />
        </Field>
        <Field label="연계 대상">
          <input value={String(inp.integrations ?? "")} onChange={(e) => set("integrations", e.target.value)} />
        </Field>
      </div>
      </EditArea>
      <p className="muted small">자체 서버 사양은 입력 가정에 따른 초기 추정이며 성능을 보장하지 않습니다(부하시험 후 조정). 클라우드는 인스턴스 사양을 제시하지 않습니다. 장비·유료 SW·클라우드 비용은 개발비에 포함하지 않습니다.</p>
      {p.tech.ran_at && (
        <>
          <div className="muted small">
            실행 {p.tech.ran_at} · {p.tech.mode}
          </div>
          <table className="grid">
            <thead>
              <tr>
                <th>분야</th>
                <th>구성안</th>
                <th>선정 이유·가정</th>
                <th>대안·호환성</th>
                <th>라이선스</th>
                <th>지원 상태(출처·확인일)</th>
                <th>운영 난도</th>
              </tr>
            </thead>
            <tbody>
              {p.tech.recommendations.map((r) => (
                <tr key={r.id}>
                  <td>
                    {r.area} {r.paid_item && <Badge kind="st-review">별도 비용</Badge>}
                  </td>
                  <td className="pre">{r.proposal}</td>
                  <td className="small">
                    {r.reason}
                    <div className="muted">가정: {r.assumptions || "-"}</div>
                  </td>
                  <td className="small">
                    {r.alternatives}
                    <div className="muted">{r.compatibility}</div>
                  </td>
                  <td className="small">{r.license}</td>
                  <td className="small">{r.support_status}</td>
                  <td className="small">{r.ops_difficulty}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}
    </Section>
  );
}

function SourcesPanel() {
  const { data, setData, run, busy } = useProject();
  const pid = data.project.id;
  const cols: Col[] = [
    { key: "title", label: "자료명", width: 160 },
    { key: "url", label: "공식 URL", width: 200 },
    { key: "publisher", label: "발행처", width: 100 },
    { key: "note", label: "분야(추천 연결 키워드)", width: 90 },
    { key: "checked_at", label: "확인일", width: 90 },
    { key: "version_info", label: "확인한 버전", width: 90 },
    { key: "support_status", label: "지원 상태", width: 120 },
    { key: "status", label: "확인 상태", type: "select", options: [["registered_unverified", "등록만(미확인)"], ["fetched", "서버 조회됨(내용 확인 필요)"], ["verified_by_user", "사용자 확인"]], width: 110 },
    {
      key: "_fetch",
      label: "",
      readOnly: true,
      width: 80,
      render: (r) => (
        <ActionButton
          disabled={busy}
          onClick={async () => {
            const res = await run(() => api.post<ProjectResponse & { fetched: { title: string } }>(`${P(pid)}/official-sources/${r.id}/fetch`));
            if (res) {
              setData(res);
              alert(`조회 성공: ${res.fetched.title}\n버전·지원 상태는 페이지를 확인해 직접 입력하세요.`);
            }
          }}
        >
          서버 조회
        </ActionButton>
      ),
    },
  ];
  const addSuggested = async () => {
    const r = await run(() => api.post<ProjectResponse>(`${P(pid)}/official-sources/suggested`));
    if (r) setData(r);
  };
  return (
    <Section title="공식 자료(최신 추천 근거)" right={<ActionButton onClick={addSuggested}>후보 공식 URL 등록</ActionButton>}>
      <p className="muted small">최신 버전·지원 상태는 공식 자료를 확인한 날짜와 함께 기록해야 '확인됨'으로 표시됩니다. 서버 조회는 허용된 공식 도메인만 가능하며(내부 주소 차단), 페이지 제목만 확인합니다.</p>
      <EditableTable collection="official_sources" rows={data.project.official_sources as unknown as Row[]} cols={cols} statusCol={false} addLabel="공식 자료 등록" />
    </Section>
  );
}
