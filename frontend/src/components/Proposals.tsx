import { useState } from "react";
import { api, P } from "../api";
import { ORIGIN } from "../labels";
import type { Proposal, ProjectResponse } from "../types";
import { Badge, Warn, useProject } from "./ui";

const COLL: Record<string, string> = { requirements: "요구사항", functions: "기능", data_entities: "데이터", interfaces: "연계", screens: "화면", workflows: "업무흐름", fp_items: "FP 항목" };
const KIND: Record<string, string> = { requirements: "요구사항 초안", answer: "답변에 따른 제안", design: "설계 초안", fp_candidates: "FP 후보" };

function summarize(d: Record<string, unknown>): string {
  const keys = ["title", "name", "fp_type", "description", "purpose", "counterpart", "rationale", "uncertainty"];
  return keys
    .filter((k) => d[k] !== undefined && d[k] !== "" && d[k] !== null)
    .map((k) => `${k === "fp_type" ? "유형" : ""}${String(d[k]).slice(0, 120)}`)
    .join(" · ");
}

/** 변경안 비교·적용. 사용자가 고른 항목만 반영되며 확정된 항목은 덮어쓰지 않는다. */
export function Proposals({ kinds }: { kinds: string[] }) {
  const { data, setData, run, busy } = useProject();
  const list = data.project.proposals.filter((p) => kinds.includes(p.kind) && (p.status === "pending" || p.status === "partial"));
  if (!list.length) return null;
  return (
    <div className="proposals">
      {list.map((pr) => (
        <ProposalCard key={pr.id} pr={pr} pid={data.project.id} onDone={(r) => setData(r)} run={run} busy={busy} />
      ))}
    </div>
  );
}

function ProposalCard({ pr, pid, onDone, run, busy }: { pr: Proposal; pid: string; onDone: (r: ProjectResponse) => void; run: <T>(fn: () => Promise<T>) => Promise<T | undefined>; busy: boolean }) {
  const pending = pr.items.filter((i) => i.status === "pending" || i.status === "conflict");
  const [sel, setSel] = useState<Set<string>>(new Set(pending.map((i) => i.key)));
  const toggle = (k: string) => {
    const s = new Set(sel);
    if (s.has(k)) s.delete(k);
    else s.add(k);
    setSel(s);
  };
  const apply = async () => {
    const r = await run(() => api.post<ProjectResponse & { result: { notes: string[]; conflicts: string[] } }>(`${P(pid)}/proposals/${pr.id}/apply`, { keys: [...sel] }));
    if (r) {
      onDone(r);
      if (r.result.notes.length || r.result.conflicts.length) alert([...r.result.notes, ...r.result.conflicts.map((c) => `${c}: 확정 항목이라 적용하지 않음(비교 후 직접 수정)`)].join("\n"));
    }
  };
  const reject = async () => {
    const r = await run(() => api.post<ProjectResponse>(`${P(pid)}/proposals/${pr.id}/reject`, { keys: [...sel] }));
    if (r) onDone(r);
  };
  return (
    <div className="proposal">
      <div className="proposal-head">
        <b>
          {pr.id} {KIND[pr.kind] || pr.kind}
        </b>{" "}
        <Badge kind={`or-${pr.mode}`}>{ORIGIN[pr.mode] || pr.mode}</Badge> <span className="muted">{pr.summary}</span>
      </div>
      <Warn items={pr.warnings} />
      <table className="grid compact">
        <thead>
          <tr>
            <th style={{ width: 36 }}>
              <input type="checkbox" aria-label="전체 선택" checked={sel.size === pending.length} onChange={(e) => setSel(new Set(e.target.checked ? pending.map((i) => i.key) : []))} />
            </th>
            <th style={{ width: 90 }}>대상</th>
            <th>변경 내용(추가될 값)</th>
            <th style={{ width: 90 }}>제안 주체</th>
            <th>이유</th>
          </tr>
        </thead>
        <tbody>
          {pending.map((i) => (
            <tr key={i.key} className={i.status === "conflict" ? "needs-review" : ""}>
              <td>
                <input type="checkbox" aria-label={`${i.key} 선택`} checked={sel.has(i.key)} onChange={() => toggle(i.key)} />
              </td>
              <td>
                {COLL[i.collection] || i.collection} {i.op === "add" ? "추가" : "수정"}
              </td>
              <td>
                {summarize(i.data)}
                {i.status === "conflict" && <div className="error">확정된 항목과 충돌 — 변경 전: {JSON.stringify(i.before)}</div>}
              </td>
              <td>
                <Badge kind={`or-${String(i.data.origin)}`}>{ORIGIN[String(i.data.origin)] || String(i.data.origin)}</Badge>
              </td>
              <td className="muted">{i.reason}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="row-actions">
        <button className="primary" disabled={busy || !sel.size} onClick={apply}>
          선택 {sel.size}건 적용
        </button>
        <button disabled={busy || !sel.size} onClick={reject}>
          선택 거절
        </button>
        <span className="muted">적용된 항목은 '초안' 상태로 들어가며 확인 후 확정하세요.</span>
      </div>
    </div>
  );
}
