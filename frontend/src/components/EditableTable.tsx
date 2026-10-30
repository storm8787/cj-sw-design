import { useState } from "react";
import { Dialog } from "./Frame";
import { api, P } from "../api";
import type { ProjectResponse, Row } from "../types";
import { OriginBadge, StatusBadge, useProject, useReadOnly } from "./ui";

export interface Col {
  key: string;
  label: string;
  type?: "text" | "textarea" | "select" | "number" | "ids" | "bool";
  options?: [string, string][];
  width?: number;
  render?: (row: Row) => React.ReactNode;
  readOnly?: boolean;
}

function show(v: unknown, col: Col): React.ReactNode {
  if (col.type === "select") return col.options?.find(([k]) => k === v)?.[1] ?? (v === null || v === "" ? "미분류" : String(v));
  if (col.type === "ids") return Array.isArray(v) && v.length ? (v as string[]).join(", ") : "-";
  if (col.type === "bool") return v ? "예" : "아니오";
  if (v === null || v === undefined || v === "") return <span className="muted">-</span>;
  return String(v);
}

function toValue(raw: string, col: Col): unknown {
  if (col.type === "number") return raw === "" ? null : Number(raw);
  if (col.type === "ids") return raw.split(/[,\s]+/).map((s) => s.trim()).filter(Boolean);
  if (col.type === "bool") return raw === "true";
  if (col.type === "select" && raw === "__null") return null;
  return raw;
}

function toRaw(v: unknown, col: Col): string {
  if (col.type === "ids") return Array.isArray(v) ? (v as string[]).join(", ") : "";
  if (col.type === "bool") return v ? "true" : "false";
  if (col.type === "select" && (v === null || v === undefined)) return "__null";
  return v === null || v === undefined ? "" : String(v);
}

export function Editor({ col, value, onChange }: { col: Col; value: string; onChange: (s: string) => void }) {
  if (col.type === "select")
    return (
      <select value={value} onChange={(e) => onChange(e.target.value)} aria-label={col.label}>
        {col.options?.map(([k, l]) => (
          <option key={k} value={k}>
            {l}
          </option>
        ))}
      </select>
    );
  if (col.type === "bool")
    return (
      <select value={value} onChange={(e) => onChange(e.target.value)} aria-label={col.label}>
        <option value="false">아니오</option>
        <option value="true">예</option>
      </select>
    );
  if (col.type === "textarea") return <textarea value={value} rows={3} onChange={(e) => onChange(e.target.value)} aria-label={col.label} />;
  return <input type={col.type === "number" ? "number" : "text"} value={value} onChange={(e) => onChange(e.target.value)} aria-label={col.label} placeholder={col.type === "ids" ? "예: REQ-001, REQ-002" : ""} />;
}

/** 프로젝트 컬렉션 표: 직접 수정, 추가, 삭제, 상태·출처·재검토 표시. */
export function EditableTable({ collection, rows, cols, defaults = {}, addLabel = "행 추가", canDelete = true, statusCol = true }: { collection: string; rows: Row[]; cols: Col[]; defaults?: Record<string, unknown>; addLabel?: string; canDelete?: boolean; statusCol?: boolean }) {
  const { data, setData, run, busy } = useProject();
  const ro = useReadOnly(); // 시연판: 추가·수정·삭제 숨김
  const pid = data.project.id;
  const [editing, setEditing] = useState<string | null>(null);
  const [draft, setDraft] = useState<Record<string, string>>({});
  const [adding, setAdding] = useState(false);
  const [detail, setDetail] = useState<Row | null>(null);
  const [status, setStatus] = useState("");
  const [filter, setFilter] = useState("");

  const begin = (row: Row) => {
    setEditing(row.id);
    const d: Record<string, string> = {};
    cols.forEach((c) => (d[c.key] = toRaw(row[c.key], c)));
    if (statusCol) d.status = String(row.status ?? "draft");
    setDraft(d);
  };
  const save = async (row: Row | null) => {
    const patch: Record<string, unknown> = {};
    cols.filter((c) => !c.readOnly).forEach((c) => {
      const v = toValue(draft[c.key] ?? "", c);
      if (!row || JSON.stringify(v) !== JSON.stringify(row[c.key] ?? (c.type === "ids" ? [] : c.type === "select" ? null : ""))) patch[c.key] = v;
    });
    if (statusCol && draft.status && (!row || draft.status !== row.status)) patch.status = draft.status;
    const r = await run(() =>
      row
        ? api.patch<ProjectResponse>(`${P(pid)}/items/${collection}/${row.id}`, { data: patch, version: data.version })
        : api.post<ProjectResponse>(`${P(pid)}/items/${collection}`, { data: { ...defaults, ...patch }, version: data.version }),
    );
    if (r) {
      setData(r);
      setEditing(null);
      setAdding(false);
    }
  };
  const remove = async (row: Row) => {
    if (!confirm(`${row.id}를 삭제할까요? 연결된 항목은 '재검토 필요'로 표시됩니다.`)) return;
    const r = await run(() => api.del<ProjectResponse>(`${P(pid)}/items/${collection}/${row.id}?version=${data.version}`));
    if (r) setData(r);
  };
  const reviewed = async (row: Row) => {
    const r = await run(() => api.patch<ProjectResponse>(`${P(pid)}/items/${collection}/${row.id}`, { data: { needs_review: false, review_reason: "" } }));
    if (r) setData(r);
  };
  const shown = rows.filter(r => (!filter || JSON.stringify(r).toLowerCase().includes(filter.toLowerCase())) && (!status || (status === "needs_review" ? r.needs_review : r.status === status)));

  const editRow = (row: Row | null) => (
    <tr className="editing" key={row?.id || "new"}>
      <td>{row?.id || "새 항목"}</td>
      {cols.map((c) => (
        <td key={c.key}>{c.readOnly ? show(row?.[c.key], c) : <Editor col={c} value={draft[c.key] ?? ""} onChange={(v) => setDraft({ ...draft, [c.key]: v })} />}</td>
      ))}
      {statusCol && (
        <td>
          <select value={draft.status || "draft"} onChange={(e) => setDraft({ ...draft, status: e.target.value })} aria-label="상태">
            <option value="draft">초안</option>
            <option value="review">검토중</option>
            <option value="confirmed">확정</option>
            <option value="excluded">제외</option>
          </select>
        </td>
      )}
      <td className="actions">
        <button className="primary" disabled={busy} onClick={() => save(row)}>
          저장
        </button>
        <button onClick={() => (row ? setEditing(null) : setAdding(false))}>취소</button>
      </td>
    </tr>
  );

  return (
    <div className="table-wrap">
      <div className="table-tools">
        <input className="filter" placeholder="표 안에서 찾기" value={filter} onChange={(e) => setFilter(e.target.value)} aria-label="표 검색" />
        {!ro && (
        <button
          onClick={() => {
            setAdding(true);
            setEditing(null);
            const d: Record<string, string> = {};
            cols.forEach((c) => (d[c.key] = toRaw(defaults[c.key], c)));
            d.status = "draft";
            setDraft(d);
          }}
        >
          + {addLabel}
        </button>
        )}
        <span className="muted" role="status">{shown.length} / {rows.length}건</span>
        {statusCol && <div className="filter-chips" aria-label="상태 필터">{[["", "전체"], ["draft", "초안"], ["confirmed", "확정"], ["needs_review", "재검토 필요"]].map(([key, label]) => <button key={key} className={status === key ? "active" : ""} aria-pressed={status === key} onClick={() => setStatus(key)}>{label}</button>)}</div>}
      </div>
      <table className="grid">
        <thead>
          <tr>
            <th style={{ width: 80 }}>ID</th>
            {cols.map((c) => (
              <th key={c.key} style={c.width ? { width: c.width } : undefined}>
                {c.label}
              </th>
            ))}
            {statusCol && <th style={{ width: 90 }}>상태</th>}
            {!ro && <th style={{ width: 120 }}></th>}
          </tr>
        </thead>
        <tbody>
          {adding && editRow(null)}
          {shown.map((row) =>
            editing === row.id ? (
              editRow(row)
            ) : (
              <tr key={row.id} className={row.needs_review ? "needs-review" : row.status === "excluded" ? "excluded" : ""}>
                <td>
                  <button className="link detail-link" onClick={() => setDetail(row)} aria-label={`${row.id} 상세 보기`}><code>{row.id}</code></button>
                  {row.origin ? (
                    <div>
                      <OriginBadge o={String(row.origin)} />
                    </div>
                  ) : null}
                </td>
                {cols.map((c) => (
                  <td key={c.key} className={c.type === "textarea" ? "pre" : ""}>
                    {c.render ? c.render(row) : show(row[c.key], c)}
                  </td>
                ))}
                {statusCol && (
                  <td>
                    <StatusBadge s={String(row.status)} />
                    {row.needs_review ? (
                      <div className="review-flag" title={String(row.review_reason || "")}>
                        재검토 필요
                        {!ro && (
                          <button className="link" onClick={() => reviewed(row)}>
                            검토 완료
                          </button>
                        )}
                      </div>
                    ) : null}
                  </td>
                )}
                {!ro && (
                  <td className="actions">
                    <button onClick={() => begin(row)}>수정</button>
                    {canDelete && (
                      <button className="danger" onClick={() => remove(row)}>
                        삭제
                      </button>
                    )}
                  </td>
                )}
              </tr>
            ),
          )}
          {!shown.length && !adding && (
            <tr>
              <td colSpan={cols.length + (ro ? 2 : 3)} className="muted center">
                {rows.length ? "검색 조건에 맞는 항목이 없습니다. 검색어나 상태 필터를 바꿔 보세요." : ro ? "이 샘플에는 항목이 없습니다. 다른 단계에서 결과를 확인해 보세요." : "아직 항목이 없습니다. 위에서 초안을 만들거나 ‘+ 행 추가’ 버튼으로 직접 입력하세요."}
              </td>
            </tr>
          )}
        </tbody>
      </table>
      {detail && <Dialog title={`${detail.id} · 상세 근거`} onClose={() => setDetail(null)}><dl className="detail-list">{cols.map(c => <div key={c.key}><dt>{c.label}</dt><dd>{c.render ? c.render(detail) : show(detail[c.key], c)}</dd></div>)}<div><dt>상태</dt><dd><StatusBadge s={String(detail.status || "draft")} /></dd></div>{detail.review_reason ? <div><dt>재검토 이유</dt><dd>{String(detail.review_reason)}</dd></div> : null}</dl></Dialog>}
    </div>
  );
}
