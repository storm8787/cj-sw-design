import { useEffect, useId, useRef, type ReactNode } from "react";
import { createPortal } from "react-dom";
export function Header({ children }: { children: ReactNode }) {
  return <header className="top"><a href="#content" onClick={e => { e.preventDefault(); document.getElementById("content")?.focus(); }} className="skip-link">본문으로 건너뛰기</a><a href="#/" className="brand"><span className="brand-mark" aria-hidden="true">설</span>정보화 설계 도우미</a>{children}</header>;
}
/** Native dialog supplies focus containment, Escape and modal semantics. */
export function Dialog({ title, children, onClose }: { title: string; children: ReactNode; onClose: () => void }) {
  const ref = useRef<HTMLDialogElement>(null);
  const id = useId();
  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    const el = ref.current!; el.showModal();
    return () => { el.close(); previous?.focus(); };
  }, []);
  return createPortal(<dialog ref={ref} aria-labelledby={id} onKeyDown={e => {
    if (e.key !== "Tab") return;
    const nodes = Array.from(e.currentTarget.querySelectorAll<HTMLElement>('button:not(:disabled), a[href], input:not(:disabled):not([type=hidden]), select:not(:disabled), textarea:not(:disabled), summary, [tabindex="0"]')).filter(el => el.getClientRects().length);
    const first = nodes[0], last = nodes[nodes.length - 1];
    if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last?.focus(); }
    else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first?.focus(); }
  }} onCancel={onClose} onClick={e => { if(e.target === e.currentTarget) onClose(); }}><div className="dialog-head"><h2 id={id}>{title}</h2><button onClick={onClose} aria-label="닫기">닫기</button></div>{children}</dialog>, document.body);
}
export function Skeleton() { return <div className="skeleton" role="status" aria-label="불러오는 중"><span>불러오는 중…</span><i/><i/><i/></div>; }
