import { useState } from "react";
import { api, P, waitJob } from "../api";
import type { Job } from "../types";
import { useProject } from "./ui";

/** 긴 작업 실행: 진행 표시·실패 이유·재시도. 같은 입력이면 서버가 기존 작업을 재사용(중복 비용 방지). */
export function useJobRunner() {
  const { data, reload } = useProject();
  const [job, setJob] = useState<Job | null>(null);
  const [running, setRunning] = useState(false);
  const [note, setNote] = useState("");

  const start = async (url: string, body: Record<string, unknown> = {}) => {
    if (running) return null;
    if (data.ai.external) {
      const preview = await api.get<{ explanation: string }>(`${P(data.project.id)}/ai/transmission-preview`);
      if (!confirm(`${preview.explanation}\n\n전송에 동의하고 진행할까요?`)) return null;
      body = { ...body, consent: true };
    }
    setRunning(true);
    setNote("");
    try {
      const r = await api.post<{ job: Job; reused: boolean }>(url, body);
      if (r.reused) setNote("같은 입력의 작업이 이미 있어 그 결과를 사용합니다(중복 실행 안 함).");
      const done = await waitJob(r.job, setJob);
      await reload();
      return done;
    } catch (e) {
      setJob({ id: "-", kind: "-", status: "failed", progress: 0, message: "실패", error: (e as Error).message, result: null, created_at: "" });
      return null;
    } finally {
      setRunning(false);
    }
  };

  const retry = async () => {
    if (!job || job.id === "-") return;
    setRunning(true);
    try {
      const j = await api.post<Job>(`/api/jobs/${job.id}/retry`);
      const done = await waitJob(j, setJob);
      await reload();
      return done;
    } catch (e) {
      setNote((e as Error).message);
    } finally {
      setRunning(false);
    }
  };
  return { job, running, start, retry, note };
}

export function JobStatus({ job, running, onRetry, note }: { job: Job | null; running: boolean; onRetry: () => void; note?: string }) {
  if (!job && !note) return null;
  const warnings = (job?.result?.warnings as string[] | undefined) || [];
  return (
    <div className={`job job-${job?.status}`} role="status">
      {job && (
        <>
          <b>{{ queued: "대기", running: "진행 중", succeeded: "완료", failed: "실패", interrupted: "중단됨" }[job.status]}</b>{" "}
          {running && <progress value={job.progress} max={1} />} {job.message}
          {job.result?.mode ? <span className="muted"> · {job.result.mode === "ai" ? `AI 결과(${String(job.result.source || "")})` : "샘플 규칙 결과(AI 아님)"}</span> : null}
          {job.error && <div className="error">이유: {job.error} — 기존 데이터는 바뀌지 않았습니다.</div>}
          {(job.status === "failed" || job.status === "interrupted") && job.id !== "-" && (
            <button onClick={onRetry} disabled={running}>
              다시 시도
            </button>
          )}
          {warnings.length > 0 && (
            <ul className="warn">
              {warnings.slice(0, 10).map((w, i) => (
                <li key={i}>{w}</li>
              ))}
            </ul>
          )}
        </>
      )}
      {note && <div className="muted">{note}</div>}
    </div>
  );
}
