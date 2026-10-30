import { useCallback, useEffect, useState } from "react";
import { ApiError, api, P } from "../api";
import { ProjectContext, type Ctx } from "../components/ui";
import { Skeleton } from "../components/Frame";
import DesignStep from "../steps/DesignStep";
import ExcelStep from "../steps/ExcelStep";
import FpStep from "../steps/FpStep";
import OverviewStep from "../steps/OverviewStep";
import RequirementsStep from "../steps/RequirementsStep";
import ReviewStep from "../steps/ReviewStep";
import SourcesStep from "../steps/SourcesStep";
import type { ProjectResponse, SystemInfo } from "../types";

export const STEPS: { key: string; label: string }[] = [
  { key: "overview", label: "1 개요" },
  { key: "sources", label: "2 자료·질문" },
  { key: "requirements", label: "3 요구사항" },
  { key: "design", label: "4 설계" },
  { key: "fp", label: "5 FP·개발비" },
  { key: "review", label: "6 검토·추천" },
  { key: "excel", label: "7 엑셀" },
];

/** readOnly: 정적 시연판에서만 넘긴다(버튼을 쓸 수 없는 이유). 서버 앱은 넘기지 않는다. */
export default function Workspace({ pid, step, system, readOnly }: { pid: string; step: string; system: SystemInfo; readOnly?: string }) {
  const [data, setData] = useState<ProjectResponse | null>(null);
  const [err, setErr] = useState("");
  const [msg, setMsg] = useState("");
  const [allNext, setAllNext] = useState(false);
  const [summary, setSummary] = useState(false);
  const [busy, setBusy] = useState(false);

  const reload = useCallback(async () => {
    try {
      setErr("");
      setData(await api.get<ProjectResponse>(P(pid)));
    } catch (e) {
      setErr((e as Error).message);
    }
  }, [pid]);
  useEffect(() => {
    reload();
  }, [reload]);

  if (!data) return <div className="pad">{err ? <div role="alert" className="error">{err} <button onClick={reload}>다시 불러오기</button></div> : <Skeleton />}</div>;

  const run: Ctx["run"] = async (fn, okMsg) => {
    setBusy(true);
    setErr("");
    try {
      const r = await fn();
      if (okMsg) {
        setMsg(okMsg);
        setTimeout(() => setMsg(""), 2500);
      }
      return r;
    } catch (e) {
      const m = (e as Error).message;
      setErr(e instanceof ApiError && e.status === 409 ? `${m}` : m);
      if (e instanceof ApiError && e.status === 409) await reload();
      return undefined;
    } finally {
      setBusy(false);
    }
  };
  const goto = (s: string) => (location.hash = `#/p/${pid}/${s}`);
  const ctx: Ctx = { data, system, setData, reload, run, busy, goto, readOnly };
  const st = data.status;
  const cur = STEPS.some((s) => s.key === step) ? step : "overview";
  const currentIndex = STEPS.findIndex(s => s.key === cur);
  const stepNeeds = st.next_steps.filter(n => n.step === cur);
  const visibleNeeds = allNext ? st.next_steps : (stepNeeds.length ? stepNeeds : st.next_steps).slice(0, 1);
  const stepCount = (k: string) => st.next_steps.filter((n) => n.step === k).length;

  return (
    <ProjectContext.Provider value={ctx}>
      <div className="ws">
        <div className="ws-head">
          <h2>{data.project.name}</h2>
          <div className="workspace-state" role="status">{readOnly ? "읽기 전용 샘플" : busy ? "처리 중 · 잠시 기다려 주세요" : `서버 저장 버전 v${data.version}`}<button className="link" aria-expanded={summary} onClick={() => setSummary(!summary)}>사업 상태 {summary ? "접기" : "보기"}</button></div>
          <div className={`chips project-summary ${summary ? "expanded" : ""}`}>
            <span className={`chip ${data.ai.is_real_ai ? "" : "chip-warn"}`} title={data.ai.note || (data.ai.external ? "외부 AI 서비스로 전송(요청마다 동의)" : "외부 전송 없음")}>
              AI: {data.ai.display}
            </span>
            <span className="chip">FP 간이 {st.fp_total.simple} / 정통 {st.fp_total.detailed}{st.fp_total.detailed_complete ? "" : "(미완)"}</span>
            <span className="chip">미확정 요구 {st.counts.requirements_unconfirmed}</span>
            <span className="chip">미확정 FP {st.counts.fp_unconfirmed}</span>
            <span className="chip">미답변 질문 {st.counts.questions_open}</span>
            {st.counts.needs_review > 0 && <span className="chip chip-warn">재검토 {st.counts.needs_review}</span>}
            {st.counts.pending_proposals > 0 && <span className="chip chip-info">검토할 변경안 {st.counts.pending_proposals}</span>}
            <span className="muted small">
              {readOnly ? "샘플 데이터 생성" : `저장됨 · v${data.version}`} · {data.project.updated_at.replace("T", " ").slice(0, 16)}
            </span>
          </div>
        </div>
        <nav className="steps" aria-label="작업 단계">
          {STEPS.map((s) => (
            <a key={s.key} href={`#/p/${pid}/${s.key}`} title={stepCount(s.key) ? `추가 입력 ${stepCount(s.key)}건` : "추가 입력 안내 없음(최종 검토 필요)"} aria-current={s.key === cur ? "step" : undefined} className={s.key === cur ? "active" : ""}>
              {s.label}
              {stepCount(s.key) > 0 && <span className="dot">{stepCount(s.key)}</span>}
            </a>
          ))}
        </nav>
        {readOnly && (
          <details className="demo-note"><summary>읽기 전용 · 저장·AI 실행·업로드 불가</summary>
            시연판: 저장·AI 실행·업로드·삭제 버튼은 비활성화되어 있습니다. 화면의 질문·초안·FP 후보는 서버 <b>샘플 규칙</b>으로 미리 만든 결과이며 AI가 만든 것이 아닙니다.
          </details>
        )}
        {st.next_steps.length > 0 && (
          <div className="next">
            <b>다음에 필요한 입력</b>
            <ul>
              {visibleNeeds.map((n, i) => (
                <li key={i}>
                  <a href={`#/p/${pid}/${n.step}`}>{n.text}</a>
                </li>
              ))}
            </ul><button className="link" aria-expanded={allNext} onClick={() => setAllNext(!allNext)}>{allNext ? "핵심 항목만" : `전체 ${st.next_steps.length}건 보기`}</button>
          </div>
        )}
        {err && (
          <div className="error" role="alert">
            {err} <button className="link" onClick={() => setErr("")}>닫기</button>
          </div>
        )}
        {msg && <div className="ok toast" role="status">✓ {msg}<button className="link" onClick={() => setMsg("")}>닫기</button></div>}
        <div className="step-intro"><span className="eyebrow">STEP {currentIndex + 1} / 7</span><h2>{({overview:"사업의 기준을 정해요",sources:"자료를 모으고 질문에 답해요",requirements:"필요한 기능을 정리해요",design:"기능을 구체적인 설계로",fp:"기능 규모와 개발비를 확인해요",review:"빠진 내용과 차이를 살펴봐요",excel:"검토한 내용을 엑셀로"} as Record<string,string>)[cur]}</h2><p className="muted">{readOnly ? "준비된 결과를 확인하고 다음 단계로 이동해 보세요." : "입력 후 저장·적용 버튼을 눌러 반영하세요."}</p></div>
        {cur === "overview" && <OverviewStep />}
        {cur === "sources" && <SourcesStep />}
        {cur === "requirements" && <RequirementsStep />}
        {cur === "design" && <DesignStep />}
        {cur === "fp" && <FpStep />}
        {cur === "review" && <ReviewStep />}
        {cur === "excel" && <ExcelStep />}
        <nav className="step-footer" aria-label="이전·다음 단계"><a className="button" href={cur === "overview" ? "#/" : `#/p/${pid}/${STEPS[currentIndex-1].key}`}>{cur === "overview" ? "프로젝트 목록" : "← 이전 단계"}</a>{cur !== "excel" && <a className="button primary" href={`#/p/${pid}/${STEPS[currentIndex+1].key}`}>다음: {STEPS[currentIndex+1].label.replace(/^\d /, "")} →</a>}</nav>
      </div>
    </ProjectContext.Provider>
  );
}
