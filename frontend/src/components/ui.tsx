import { createContext, useContext, useState, type ButtonHTMLAttributes, type ReactNode } from "react";
import { GLOSSARY, ORIGIN, STATUS } from "../labels";
import type { ProjectResponse, SystemInfo } from "../types";

export function Badge({ kind, children, title }: { kind?: string; children: ReactNode; title?: string }) {
  return (
    <span className={`badge badge-${kind || "plain"}`} title={title}>
      {children}
    </span>
  );
}

export function StatusBadge({ s }: { s: string }) {
  return <Badge kind={`st-${s}`}>{STATUS[s] || s}</Badge>;
}

export function OriginBadge({ o }: { o: string }) {
  return (
    <Badge kind={`or-${o}`} title={o === "sample" ? "샘플 모드 규칙으로 만든 제안(AI 아님)" : o === "ai" ? "AI가 만든 제안 — 확인 필요" : undefined}>
      {ORIGIN[o] || o}
    </Badge>
  );
}

export function Help({ term }: { term: keyof typeof GLOSSARY }) {
  const [open, setOpen] = useState(false);
  const g = GLOSSARY[term];
  return (
    <span className="help">
      <button type="button" className="help-btn" aria-label={`${g.title} 설명`} onClick={() => setOpen(!open)}>
        ?
      </button>
      {open && (
        <span className="help-pop" role="dialog">
          <b>{g.title}</b>
          <br />
          {g.text}
          <br />
          <i>예: {g.example}</i>
        </span>
      )}
    </span>
  );
}

export function Section({ title, children, right, help }: { title: string; children: ReactNode; right?: ReactNode; help?: ReactNode }) {
  return (
    <section className="card">
      <div className="card-head">
        <h3>
          {title} {help}
        </h3>
        <div className="card-right">{right}</div>
      </div>
      {children}
    </section>
  );
}

export function Warn({ items }: { items: string[] | undefined }) {
  if (!items || !items.length) return null;
  return (
    <ul className="warn">
      {items.map((w, i) => (
        <li key={i}>{w}</li>
      ))}
    </ul>
  );
}

export function Field({ label, children, hint }: { label: ReactNode; children: ReactNode; hint?: string }) {
  return (
    <label className="field">
      <span className="field-label">{label}</span>
      {children}
      {hint && <span className="hint">{hint}</span>}
    </label>
  );
}

export interface Ctx {
  data: ProjectResponse;
  system: SystemInfo;
  setData: (d: ProjectResponse) => void;
  reload: () => Promise<void>;
  run: <T>(fn: () => Promise<T>, okMsg?: string) => Promise<T | undefined>;
  busy: boolean;
  goto: (step: string) => void;
  /** 비어 있지 않으면 읽기 전용(정적 시연판 빌드에서만 설정). 값은 버튼을 쓸 수 없는 이유. */
  readOnly?: string;
}

export const ProjectContext = createContext<Ctx | null>(null);
export function useProject(): Ctx {
  const c = useContext(ProjectContext);
  if (!c) throw new Error("ProjectContext 없음");
  return c;
}

export function useReadOnly(): string {
  return useContext(ProjectContext)?.readOnly || "";
}

/** 저장·실행 버튼. 읽기 전용(시연판)이면 비활성화하고 이유를 툴팁으로 보여 준다. */
export function ActionButton({ disabled, title, ...rest }: ButtonHTMLAttributes<HTMLButtonElement>) {
  const ro = useReadOnly();
  return <button {...rest} disabled={disabled || !!ro} title={ro || title} />;
}

/** 입력 묶음. 읽기 전용(시연판)이면 안의 입력·버튼을 모두 비활성화한다. */
export function EditArea({ children }: { children: ReactNode }) {
  const ro = useReadOnly();
  return (
    <fieldset className="edit-area" disabled={!!ro} title={ro || undefined}>
      {children}
    </fieldset>
  );
}
