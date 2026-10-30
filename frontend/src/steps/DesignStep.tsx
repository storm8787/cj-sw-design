import { useEffect, useState } from "react";
import { api, P } from "../api";
import { EditableTable, type Col } from "../components/EditableTable";
import { JobStatus, useJobRunner } from "../components/Jobs";
import { Proposals } from "../components/Proposals";
import { ActionButton, Badge, EditArea, Section, useProject } from "../components/ui";
import { ORIGIN } from "../labels";
import type { ProjectResponse, Row } from "../types";

const TABS = [
  ["functions", "기능설계"],
  ["workflows", "업무흐름"],
  ["screens", "화면"],
  ["data_entities", "데이터"],
  ["interfaces", "연계"],
  ["task", "과업지시서 초안"],
  ["history", "스냅샷·변경이력"],
] as const;

const COLS: Record<string, Col[]> = {
  functions: [
    { key: "name", label: "기능명", width: 140 },
    { key: "actor", label: "사용자", width: 80 },
    { key: "purpose", label: "업무 목적", type: "textarea" },
    { key: "inputs", label: "입력", type: "textarea" },
    { key: "outputs", label: "출력", type: "textarea" },
    { key: "rules", label: "처리 규칙", type: "textarea" },
    { key: "exceptions", label: "예외", type: "textarea" },
    { key: "permissions", label: "권한", width: 80 },
    { key: "acceptance", label: "검수 기준", type: "textarea" },
    { key: "requirement_ids", label: "요구사항ID", type: "ids", width: 100 },
    { key: "data_ids", label: "데이터ID", type: "ids", width: 80 },
    { key: "interface_ids", label: "연계ID", type: "ids", width: 70 },
  ],
  workflows: [
    { key: "order", label: "순서", type: "number", width: 50 },
    { key: "name", label: "단계", width: 160 },
    { key: "actor", label: "수행자", width: 90 },
    { key: "description", label: "설명", type: "textarea" },
    { key: "requirement_ids", label: "요구사항ID", type: "ids", width: 110 },
  ],
  screens: [
    { key: "name", label: "화면명", width: 180 },
    { key: "users", label: "이용자", width: 90 },
    { key: "description", label: "설명", type: "textarea" },
    { key: "function_ids", label: "기능ID", type: "ids", width: 110 },
  ],
  data_entities: [
    { key: "name", label: "데이터명", width: 150 },
    { key: "description", label: "설명", type: "textarea" },
    { key: "attributes", label: "주요 항목", type: "textarea" },
    { key: "relations", label: "관계", type: "textarea", width: 120 },
    { key: "maintained_by", label: "유지 주체", type: "select", options: [["internal", "이 시스템"], ["external", "외부 시스템"], ["unknown", "확인 필요"]], width: 90 },
    { key: "personal_info", label: "개인정보", type: "bool", width: 70 },
    { key: "retention", label: "보존기간", width: 70 },
  ],
  interfaces: [
    { key: "name", label: "연계명", width: 150 },
    { key: "counterpart", label: "상대 시스템", width: 110 },
    { key: "direction", label: "방향", type: "select", options: [["inbound", "수신"], ["outbound", "송신"], ["both", "양방향"], ["unknown", "확인 필요"]], width: 80 },
    { key: "method", label: "방식", width: 110 },
    { key: "data_items", label: "데이터 항목", type: "textarea" },
    { key: "frequency", label: "주기", width: 90 },
    { key: "verified", label: "확인 상태", type: "select", options: [["unverified", "미확인"], ["confirmed_by_org", "기관 확인"], ["confirmed_by_counterpart", "상대기관 확인"]], width: 100 },
  ],
};

export default function DesignStep() {
  const { data } = useProject();
  const [tab, setTab] = useState<string>("functions");
  const jr = useJobRunner();
  const pid = data.project.id;
  return (
    <>
      <Section
        title="설계 작업대"
        right={
          <ActionButton className="primary" disabled={jr.running} onClick={() => jr.start(`${P(pid)}/ai/design`)}>
            요구사항으로 설계 초안 만들기
          </ActionButton>
        }
      >
        <p className="muted small">발주자가 검토할 초안입니다. 확인하지 않은 DB·API·기존 시스템 구조는 '확인 필요'로 남기세요. 화면·테이블 수는 FP 수와 같지 않습니다.</p>
        <JobStatus job={jr.job} running={jr.running} onRetry={jr.retry} note={jr.note} />
      </Section>
      <Proposals kinds={["design"]} />
      <div className="tabs">
        {TABS.map(([k, l]) => (
          <button key={k} className={tab === k ? "active" : ""} onClick={() => setTab(k)}>
            {l}
            {k in COLS ? ` (${(data.project[k as keyof typeof data.project] as Row[]).length})` : ""}
          </button>
        ))}
      </div>
      {tab in COLS && (
        <Section title={TABS.find(([k]) => k === tab)![1]}>
          <EditableTable collection={tab} rows={data.project[tab as "functions"] as Row[]} cols={COLS[tab]} />
        </Section>
      )}
      {tab === "task" && <TaskDraft />}
      {tab === "history" && <History />}
    </>
  );
}

function TaskDraft() {
  const { data, setData, run, busy } = useProject();
  const pid = data.project.id;
  const [edit, setEdit] = useState<Record<string, string>>({});
  const gen = async () => {
    const r = await run(() => api.post<ProjectResponse>(`${P(pid)}/task-draft/generate`), "과업지시서 초안을 갱신했습니다(직접 고친 항목은 유지).");
    if (r) setData(r);
  };
  const save = async (key: string, body: Record<string, unknown>) => {
    const r = await run(() => api.patch<ProjectResponse>(`${P(pid)}/task-draft/${key}`, body));
    if (r) {
      setData(r);
      const e = { ...edit };
      delete e[key];
      setEdit(e);
    }
  };
  const td = data.project.task_draft;
  return (
    <Section
      title="과업지시서 초안"
      right={
        <>
          {data.status.task_draft_stale && <Badge kind="st-review">갱신 필요</Badge>}{" "}
          <ActionButton className="primary" disabled={busy} onClick={gen}>
            {td.sections.length ? "현재 내용으로 다시 구성" : "초안 만들기"}
          </ActionButton>
        </>
      }
    >
      {!td.sections.length && <p className="muted">사업 개요·목적·범위·상세 요구사항·일정·산출물·검수 기준을 현재 데이터로 구성합니다.</p>}
      {td.sections.map((s) => (
        <div key={s.key} className="task-sec">
          <div className="row-actions">
            <b>{s.title}</b> {s.user_edited && <Badge kind="or-user">직접 수정함</Badge>}
            {edit[s.key] === undefined ? <ActionButton onClick={() => setEdit({ ...edit, [s.key]: s.text })}>수정</ActionButton> : <ActionButton className="primary" onClick={() => save(s.key, { text: edit[s.key] })}>저장</ActionButton>}
          </div>
          {edit[s.key] !== undefined ? <textarea rows={8} value={edit[s.key]} onChange={(e) => setEdit({ ...edit, [s.key]: e.target.value })} aria-label={s.title} /> : <pre>{s.text}</pre>}
          {s.regenerated_candidate && (
            <div className="compare">
              <div className="muted small">현재 데이터로 다시 만든 내용(직접 고친 내용은 덮어쓰지 않음):</div>
              <pre>{s.regenerated_candidate}</pre>
              <ActionButton onClick={() => save(s.key, { accept_candidate: true })}>이 내용으로 바꾸기</ActionButton>
            </div>
          )}
        </div>
      ))}
    </Section>
  );
}

interface Change {
  seq: number;
  at: string;
  actor: string;
  collection: string;
  item_id: string | null;
  op: string;
  before: unknown;
  after: unknown;
  affected: string[];
  needs_review: boolean;
}
type Diff = Record<string, { added: string[]; removed: string[]; changed: { id: string; fields: string[]; before: Record<string, unknown>; after: Record<string, unknown> }[] }>;

function History() {
  const { data, run } = useProject();
  const pid = data.project.id;
  const [snaps, setSnaps] = useState<{ id: string; label: string; created_at: string }[]>([]);
  const [changes, setChanges] = useState<Change[]>([]);
  const [diff, setDiff] = useState<Diff | null>(null);
  const [label, setLabel] = useState("");
  useEffect(() => {
    api.get<typeof snaps>(`${P(pid)}/snapshots`).then(setSnaps);
    api.get<Change[]>(`${P(pid)}/changes?limit=200`).then(setChanges);
  }, [pid, data.version]);
  const snap = async () => {
    const r = await run(() => api.post(`${P(pid)}/snapshots`, { label }), "스냅샷을 저장했습니다.");
    if (r) setSnaps(await api.get(`${P(pid)}/snapshots`));
  };
  return (
    <>
      <Section title="설계 스냅샷(과거 버전 보존)">
        <EditArea>
          <div className="row-actions">
            <input value={label} onChange={(e) => setLabel(e.target.value)} placeholder="예: 1차 검토 전" aria-label="스냅샷 이름" />
            <button onClick={snap}>현재 상태 저장</button>
          </div>
        </EditArea>
        <ul>
          {snaps.map((s) => (
            <li key={s.id}>
              {s.label} <span className="muted small">{s.created_at}</span>{" "}
              <button className="link" onClick={async () => setDiff(await api.get<Diff>(`${P(pid)}/snapshots/${s.id}/diff`))}>
                현재와 비교
              </button>
            </li>
          ))}
        </ul>
        {diff && (
          <table className="grid compact">
            <thead>
              <tr>
                <th>대상</th>
                <th>추가</th>
                <th>삭제</th>
                <th>변경(변경 전 → 후)</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(diff)
                .filter(([k, v]) => k !== "overview" && (v.added.length || v.removed.length || v.changed.length))
                .map(([k, v]) => (
                  <tr key={k}>
                    <td>{k}</td>
                    <td>{v.added.join(", ")}</td>
                    <td>{v.removed.join(", ")}</td>
                    <td>
                      {v.changed.map((c) => (
                        <div key={c.id}>
                          <code>{c.id}</code> {c.fields.map((f) => `${f}: ${JSON.stringify(c.before[f])} → ${JSON.stringify(c.after[f])}`).join(" / ")}
                        </div>
                      ))}
                    </td>
                  </tr>
                ))}
            </tbody>
          </table>
        )}
      </Section>
      <Section title="변경 이력(최근 200건)">
        <table className="grid compact">
          <thead>
            <tr>
              <th>시각</th>
              <th>주체</th>
              <th>대상</th>
              <th>작업</th>
              <th>변경 전 → 후</th>
              <th>영향</th>
            </tr>
          </thead>
          <tbody>
            {changes.map((c) => (
              <tr key={c.seq} className={c.needs_review ? "needs-review" : ""}>
                <td className="small">{c.at.replace("T", " ").slice(0, 19)}</td>
                <td>{ORIGIN[c.actor] || c.actor}</td>
                <td>
                  {c.collection} <code>{c.item_id}</code>
                </td>
                <td>{c.op}</td>
                <td className="small">{c.op === "update" ? `${JSON.stringify(c.before).slice(0, 140)} → ${JSON.stringify(c.after).slice(0, 140)}` : JSON.stringify(c.after ?? c.before).slice(0, 160)}</td>
                <td className="small">{c.affected.join(", ")}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Section>
    </>
  );
}
