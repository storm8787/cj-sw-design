import { useState } from "react";
import { api, P } from "../api";
import { JobStatus, useJobRunner } from "../components/Jobs";
import { Proposals } from "../components/Proposals";
import { Badge, OriginBadge, Section, Warn, useProject } from "../components/ui";
import { DOC_KIND, EXTRACT_STATUS, ORG_SPECIFIC, QUALITY, REF_KIND } from "../labels";
import type { DocumentMeta, ProjectResponse, Question, ReferenceItem } from "../types";

export default function SourcesStep() {
  const { data } = useProject();
  const isReviewMode = data.project.overview.start_mode === "review";
  return (
    <>
      <QuestionsPanel />
      <DocumentsPanel defaultKind={isReviewMode ? "vendor_task" : "reference"} />
      <ReferencePanel />
    </>
  );
}

function QuestionsPanel() {
  const { data } = useProject();
  const pid = data.project.id;
  const jr = useJobRunner();
  const open = data.project.questions.filter((q) => q.status === "open");
  const done = data.project.questions.filter((q) => q.status !== "open");
  const [showDone, setShowDone] = useState(false);
  return (
    <Section
      title="질문으로 구체화하기"
      right={
        <button className="primary" disabled={jr.running} onClick={() => jr.start(`${P(pid)}/ai/questions`)}>
          {open.length ? "다음 질문 더 받기" : "질문 받기"}
        </button>
      }
    >
      <p className="muted small">중요한 질문을 몇 개씩 드립니다. 모르면 '모름'을 고르면 권장안을 가정으로 기록합니다. 답에 따라 추가할 요구사항은 '변경안'으로 제시되어 3단계에서 적용합니다.</p>
      <JobStatus job={jr.job} running={jr.running} onRetry={jr.retry} note={jr.note} />
      {open.map((q) => (
        <QuestionCard key={q.id} q={q} />
      ))}
      {!open.length && <p className="muted">열린 질문이 없습니다.</p>}
      <Proposals kinds={["answer"]} />
      {done.length > 0 && (
        <button className="link" onClick={() => setShowDone(!showDone)}>
          답한 질문 {done.length}개 {showDone ? "접기" : "보기"}
        </button>
      )}
      {showDone && (
        <table className="grid compact">
          <tbody>
            {done.map((q) => (
              <tr key={q.id}>
                <td>{q.id}</td>
                <td>{q.text}</td>
                <td>{q.status === "deferred" ? <Badge kind="st-review">나중에 결정</Badge> : q.answer_kind === "unknown" ? <Badge kind="st-review">모름 → 권장안 가정</Badge> : q.options.find((o) => o.value === q.answer)?.label || q.answer}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </Section>
  );
}

function QuestionCard({ q }: { q: Question }) {
  const { data, setData, run, busy } = useProject();
  const [text, setText] = useState("");
  const answer = async (kind: string, value = "") => {
    const r = await run(() => api.post<ProjectResponse>(`${P(data.project.id)}/questions/${q.id}/answer`, { kind, value }));
    if (r) setData(r);
  };
  const rec = q.options.find((o) => o.recommended);
  return (
    <div className="question">
      <div>
        <b>{q.text}</b> <OriginBadge o={q.origin} /> <span className="muted small">{q.topic.split(":")[1]}</span>
      </div>
      <div className="muted small">왜 묻나요? {q.why}</div>
      <div className="options">
        {q.options.map((o) => (
          <button key={o.value} disabled={busy} onClick={() => answer("choice", o.value)} className={o.recommended ? "recommended" : ""}>
            {o.label}
            {o.recommended && <span className="small"> (권장)</span>}
          </button>
        ))}
        <button disabled={busy} onClick={() => answer("unknown")} title={`권장안: ${rec?.label} — ${q.recommended_reason}`}>
          모름(권장안으로 가정)
        </button>
        <button disabled={busy} onClick={() => answer("defer")}>
          나중에 결정
        </button>
      </div>
      {q.allow_text && (
        <div className="row-actions">
          <input value={text} onChange={(e) => setText(e.target.value)} placeholder="직접 입력" aria-label={`${q.id} 직접 입력`} />
          <button disabled={busy || !text.trim()} onClick={() => answer("text", text)}>
            입력
          </button>
        </div>
      )}
      <div className="muted small">권장안: {rec?.label} — {q.recommended_reason}</div>
    </div>
  );
}

function DocumentsPanel({ defaultKind }: { defaultKind: string }) {
  const { data, setData, run, busy, system } = useProject();
  const pid = data.project.id;
  const external = data.ai.external;
  const [kind, setKind] = useState(defaultKind);
  const jr = useJobRunner();
  const upload = async (files: FileList) => {
    for (const f of Array.from(files)) {
      const fd = new FormData();
      fd.append("file", f);
      fd.append("kind", kind);
      const r = await run(() => api.form<ProjectResponse>(`${P(pid)}/documents`, fd), `${f.name} 업로드·추출 완료`);
      if (r) setData(r);
    }
  };
  const consent = async (d: DocumentMeta, v: boolean) => {
    const r = await run(() => api.post<ProjectResponse>(`${P(pid)}/documents/${d.id}/consent`, { consent: v }));
    if (r) setData(r);
  };
  const remove = async (d: DocumentMeta) => {
    if (!confirm(`${d.file_name}를 삭제할까요?`)) return;
    const r = await run(() => api.del<ProjectResponse>(`${P(pid)}/documents/${d.id}`));
    if (r) setData(r);
  };
  return (
    <Section title="자료(문서) 올리기">
      <div className="row-actions">
        <select value={kind} onChange={(e) => setKind(e.target.value)} aria-label="문서 종류">
          {Object.entries(DOC_KIND).map(([k, l]) => (
            <option key={k} value={k}>
              {l}
            </option>
          ))}
        </select>
        <label className="button primary">
          파일 선택
          <input type="file" multiple hidden accept={system.allowed_formats.map((f) => "." + f).join(",")} onChange={(e) => e.target.files && upload(e.target.files)} disabled={busy} />
        </label>
        <span className="muted small">
          {system.allowed_formats.join(", ").toUpperCase()} · 최대 {system.max_upload_mb}MB. HWP는 실험적(표·서식 미보존) — 가능하면 HWPX/PDF로 변환해 올려 주세요. 스캔 PDF는 글자를 읽지 못합니다(OCR 미지원).
        </span>
      </div>
      <p className="muted small">문서 안의 지시문은 분석 대상일 뿐 실행하지 않습니다. 업로드만으로는 외부로 전송되지 않습니다{external ? ` — '${data.ai.display}'로 보내는 AI 분석은 문서별 전송 동의 후에만 진행합니다.` : data.ai.is_real_ai ? ` — 내부 AI 연결 '${data.ai.display}'로 분석합니다(외부 전송 없음).` : "(샘플 모드: 서버 규칙으로 추출)."}</p>
      <JobStatus job={jr.job} running={jr.running} onRetry={jr.retry} note={jr.note} />
      <table className="grid">
        <thead>
          <tr>
            <th>문서</th>
            <th>종류</th>
            <th>추출 상태·품질</th>
            <th>분석</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {data.project.documents.map((d) => (
            <tr key={d.id}>
              <td>
                <code>{d.id}</code> {d.file_name}
                <div className="muted small">
                  {(d.size / 1024).toFixed(0)}KB · {d.extraction.pages ? `${d.extraction.pages}쪽 · ` : ""}
                  {d.extraction.chars.toLocaleString()}자
                </div>
              </td>
              <td>{DOC_KIND[d.kind]}</td>
              <td>
                <Badge kind={d.extraction.status === "ok" ? "st-confirmed" : d.extraction.status === "partial" ? "st-review" : "st-excluded"}>{EXTRACT_STATUS[d.extraction.status]}</Badge> 품질 {QUALITY[d.extraction.quality]}
                <Warn items={d.extraction.messages} />
              </td>
              <td>
                {d.extraction.chunks_analyzed}/{d.extraction.chunks_total} 구간
                <div>{{ not_started: "미분석", partial: "일부만 분석(완료 아님)", complete: "전체 분석 완료", failed: "실패" }[d.extraction.analysis_status]}</div>
                {external && (
                  <label className="small">
                    <input type="checkbox" checked={d.ai_consent} onChange={(e) => consent(d, e.target.checked)} /> 이 문서 원문의 외부 AI 전송 동의
                  </label>
                )}
              </td>
              <td className="actions">
                <button disabled={jr.running || !d.extraction.chunks_total || d.extraction.analysis_status === "complete"} onClick={() => jr.start(`${P(pid)}/documents/${d.id}/analyze`)}>
                  {d.extraction.analysis_status === "partial" ? "이어서 분석" : "항목 추출"}
                </button>
                <a className="button" href={`${P(pid)}/documents/${d.id}/download`}>
                  원본
                </a>
                <button className="danger" onClick={() => remove(d)}>
                  삭제
                </button>
              </td>
            </tr>
          ))}
          {!data.project.documents.length && (
            <tr>
              <td colSpan={5} className="muted center">
                올린 문서가 없습니다.
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </Section>
  );
}

function ReferencePanel() {
  const { data } = useProject();
  const items = data.project.reference_items;
  const [onlyPending, setOnlyPending] = useState(true);
  if (!items.length) return null;
  const shown = onlyPending ? items.filter((r) => r.decision === "pending") : items;
  return (
    <Section
      title="참고문서 항목 — 우리 기관 기준으로 유지·수정·제외"
      right={
        <label className="small">
          <input type="checkbox" checked={onlyPending} onChange={(e) => setOnlyPending(e.target.checked)} /> 결정 대기만 보기 ({items.filter((r) => r.decision === "pending").length}/{items.length})
        </label>
      }
    >
      <p className="muted small">기관명만 바꾸지 말고 항목마다 판단하세요. 예산·기간·개인정보·특정 제품 조건은 우리 사업 값으로 자동 확정되지 않습니다. 유지·수정한 항목은 원문 위치가 연결된 요구사항(초안)으로 들어갑니다.</p>
      <table className="grid">
        <thead>
          <tr>
            <th style={{ width: 70 }}>ID</th>
            <th>원문(위치)</th>
            <th style={{ width: 80 }}>종류</th>
            <th style={{ width: 380 }}>결정</th>
          </tr>
        </thead>
        <tbody>
          {shown.map((r) => (
            <RefRow key={r.id} r={r} />
          ))}
        </tbody>
      </table>
    </Section>
  );
}

function RefRow({ r }: { r: ReferenceItem }) {
  const { data, setData, run, busy } = useProject();
  const [mod, setMod] = useState(r.modified_text || r.text);
  const [reason, setReason] = useState(r.reason);
  const [mode, setMode] = useState<"" | "modify" | "exclude">("");
  const decide = async (decision: string) => {
    const res = await run(() => api.post<ProjectResponse>(`${P(data.project.id)}/reference-items/${r.id}/decide`, { decision, modified_text: decision === "modify" ? mod : "", reason }));
    if (res) {
      setData(res);
      setMode("");
    }
  };
  return (
    <tr className={r.org_specific.length ? "needs-review" : ""}>
      <td>
        <code>{r.id}</code>
      </td>
      <td>
        {r.text}
        <div className="muted small">{r.location}</div>
        {r.org_specific.length > 0 && <div className="error small">타 기관 고유 조건: {r.org_specific.map((o) => ORG_SPECIFIC[o]).join(", ")} — 우리 값으로 확인 필요</div>}
      </td>
      <td>{REF_KIND[r.kind]}</td>
      <td>
        {r.decision !== "pending" && (
          <div>
            <Badge kind={r.decision === "exclude" ? "st-excluded" : "st-confirmed"}>{{ keep: "유지", modify: "수정", exclude: "제외", pending: "" }[r.decision]}</Badge> {r.applied_requirement_id && <code>{r.applied_requirement_id}</code>} <span className="muted small">{r.reason}</span>
          </div>
        )}
        {r.decision === "pending" && !mode && (
          <div className="row-actions">
            <button disabled={busy} onClick={() => decide("keep")}>
              유지
            </button>
            <button onClick={() => setMode("modify")}>수정</button>
            <button onClick={() => setMode("exclude")}>제외</button>
          </div>
        )}
        {mode && (
          <div className="stack">
            {mode === "modify" && <textarea rows={2} value={mod} onChange={(e) => setMod(e.target.value)} aria-label="수정 내용" />}
            <input value={reason} onChange={(e) => setReason(e.target.value)} placeholder="이유(변경 내역에 기록)" aria-label="이유" />
            <div className="row-actions">
              <button className="primary" disabled={busy || !reason.trim()} onClick={() => decide(mode)}>
                확인
              </button>
              <button onClick={() => setMode("")}>취소</button>
            </div>
          </div>
        )}
      </td>
    </tr>
  );
}
