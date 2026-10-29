import { useCallback, useEffect, useState } from "react";
import { ApiError, api, P } from "../api";
import { ProjectContext, type Ctx } from "../components/ui";
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

export default function Workspace({ pid, step, system }: { pid: string; step: string; system: SystemInfo }) {
  const [data, setData] = useState<ProjectResponse | null>(null);
  const [err, setErr] = useState("");
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);

  const reload = useCallback(async () => {
    try {
      setData(await api.get<ProjectResponse>(P(pid)));
    } catch (e) {
      setErr((e as Error).message);
    }
  }, [pid]);
  useEffect(() => {
    reload();
  }, [reload]);

  if (!data) return <div className="pad">{err ? <div className="error">{err}</div> : "불러오는 중…"}</div>;

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
  const ctx: Ctx = { data, system, setData, reload, run, busy, goto };
  const st = data.status;
  const cur = STEPS.some((s) => s.key === step) ? step : "overview";
  const stepCount = (k: string) => st.next_steps.filter((n) => n.step === k).length;

  return (
    <ProjectContext.Provider value={ctx}>
      <div className="ws">
        <div className="ws-head">
          <h2>{data.project.name}</h2>
          <div className="chips">
            <span className="chip">FP 간이 {st.fp_total.simple} / 정통 {st.fp_total.detailed}{st.fp_total.detailed_complete ? "" : "(미완)"}</span>
            <span className="chip">미확정 요구 {st.counts.requirements_unconfirmed}</span>
            <span className="chip">미확정 FP {st.counts.fp_unconfirmed}</span>
            <span className="chip">미답변 질문 {st.counts.questions_open}</span>
            {st.counts.needs_review > 0 && <span className="chip chip-warn">재검토 {st.counts.needs_review}</span>}
            {st.counts.pending_proposals > 0 && <span className="chip chip-info">검토할 변경안 {st.counts.pending_proposals}</span>}
            <span className="muted small">저장됨 · v{data.version} · {data.project.updated_at.replace("T", " ").slice(0, 16)}</span>
          </div>
        </div>
        <nav className="steps" aria-label="작업 단계">
          {STEPS.map((s) => (
            <a key={s.key} href={`#/p/${pid}/${s.key}`} className={s.key === cur ? "active" : ""}>
              {s.label}
              {stepCount(s.key) > 0 && <span className="dot">{stepCount(s.key)}</span>}
            </a>
          ))}
        </nav>
        {st.next_steps.length > 0 && (
          <div className="next">
            <b>다음에 필요한 입력</b>
            <ul>
              {st.next_steps.slice(0, 6).map((n, i) => (
                <li key={i}>
                  <a href={`#/p/${pid}/${n.step}`}>{n.text}</a>
                </li>
              ))}
            </ul>
          </div>
        )}
        {err && (
          <div className="error" role="alert">
            {err} <button className="link" onClick={() => setErr("")}>닫기</button>
          </div>
        )}
        {msg && <div className="ok">{msg}</div>}
        {cur === "overview" && <OverviewStep />}
        {cur === "sources" && <SourcesStep />}
        {cur === "requirements" && <RequirementsStep />}
        {cur === "design" && <DesignStep />}
        {cur === "fp" && <FpStep />}
        {cur === "review" && <ReviewStep />}
        {cur === "excel" && <ExcelStep />}
      </div>
    </ProjectContext.Provider>
  );
}
