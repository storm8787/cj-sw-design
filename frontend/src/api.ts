// 서버 API 호출. 쿠키 세션 + 변경 요청에는 X-Requested-With 헤더(서버 CSRF 검사).
import type { Job, ProjectResponse } from "./types";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

let onUnauthorized: () => void = () => {};
export function setUnauthorizedHandler(fn: () => void) {
  onUnauthorized = fn;
}

async function request<T>(method: string, url: string, body?: unknown, isForm = false): Promise<T> {
  const headers: Record<string, string> = { "X-Requested-With": "swd" };
  let payload: BodyInit | undefined;
  if (body !== undefined) {
    if (isForm) payload = body as FormData;
    else {
      headers["Content-Type"] = "application/json";
      payload = JSON.stringify(body);
    }
  }
  const res = await fetch(url, { method, headers, body: payload, credentials: "same-origin" });
  if (res.status === 401 && !url.endsWith("/auth/login")) onUnauthorized();
  if (!res.ok) {
    let msg = `요청 실패(${res.status})`;
    try {
      const j = await res.json();
      if (typeof j.detail === "string") msg = j.detail;
      else if (Array.isArray(j.detail)) msg = j.detail.map((d: { msg: string; loc: unknown[] }) => `${d.loc.join(".")}: ${d.msg}`).join("; ");
    } catch {
      /* 본문 없음 */
    }
    throw new ApiError(res.status, msg);
  }
  const ct = res.headers.get("content-type") || "";
  return (ct.includes("application/json") ? res.json() : (res.text() as unknown)) as Promise<T>;
}

export const api = {
  get: <T>(url: string) => request<T>("GET", url),
  post: <T>(url: string, body: unknown = {}) => request<T>("POST", url, body),
  put: <T>(url: string, body: unknown) => request<T>("PUT", url, body),
  patch: <T>(url: string, body: unknown) => request<T>("PATCH", url, body),
  del: <T>(url: string) => request<T>("DELETE", url),
  form: <T>(url: string, fd: FormData) => request<T>("POST", url, fd, true),
};

export const P = (pid: string) => `/api/projects/${pid}`;

/** 내려받기 링크 주소(서버 앱은 그대로). 정적 시연판 빌드에서는 같은 이름의 함수가 정적 파일 주소로 바꾼다. */
export const fileUrl = (url: string): string | null => url;

export async function waitJob(job: Job, onProgress?: (j: Job) => void): Promise<Job> {
  let j = job;
  while (j.status === "queued" || j.status === "running") {
    onProgress?.(j);
    await new Promise((r) => setTimeout(r, 800));
    j = await api.get<Job>(`/api/jobs/${j.id}`);
  }
  onProgress?.(j);
  return j;
}

export function download(url: string) {
  const a = document.createElement("a");
  a.href = url;
  a.rel = "noopener";
  document.body.appendChild(a);
  a.click();
  a.remove();
}

export type { ProjectResponse };
