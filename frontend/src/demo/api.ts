// 정적 시연판(GitHub Pages) 전용 API 어댑터. `npm run build:demo`에서만 src/api.ts 대신 쓰인다(vite.config.ts).
// - 서버 없이 미리 만든 정적 JSON(demo-data/)을 읽는다. /api 로 요청을 보내지 않는다.
// - 저장·실행(POST/PUT/PATCH/DELETE)은 하지 않는다. 화면 버튼은 읽기 전용으로 비활성화되고, 혹시 호출돼도 거절한다.
// - 타입은 실제 api.ts와 같게 맞춰 화면 코드를 그대로 재사용한다.
import type * as Real from "../api";
import type { Job } from "../types";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

export const READ_ONLY_REASON = "샘플 시연판에서는 저장·AI 실행·업로드를 하지 않습니다(실제 앱에서 사용).";
export const DATA_BASE = `${import.meta.env.BASE_URL}demo-data/`;

export interface DemoSample {
  key: string;
  pid: string;
  name: string;
  file_prefix: string;
  xlsx: Record<string, string>;
  originals: Record<string, string>;
}
export interface DemoManifest {
  schema: number;
  label: string;
  samples: DemoSample[];
}

let manifest: DemoManifest | null = null;
export async function loadManifest(): Promise<DemoManifest> {
  if (!manifest) manifest = await fetchJson<DemoManifest>("manifest.json");
  return manifest;
}
const sample = (pid: string) => manifest?.samples.find((s) => s.pid === pid) || null;

async function fetchJson<T>(file: string): Promise<T> {
  const res = await fetch(DATA_BASE + file);
  if (!res.ok) throw new ApiError(res.status, `샘플 데이터를 읽지 못했습니다(${file}).`);
  return res.json() as Promise<T>;
}

/** 화면이 쓰는 서버 GET 주소 → 정적 파일 이름. 준비되지 않은 주소는 null. */
export function staticFile(url: string): string | null {
  const u = new URL(url, "http://demo.invalid");
  if (u.pathname === "/api/system") return "system.json";
  const m = u.pathname.match(/^\/api\/projects\/([A-Za-z0-9]+)(\/.*)?$/);
  if (!m || !sample(m[1])) return null;
  const dir = `${m[1]}/`;
  const rest = m[2] || "";
  if (rest === "") return dir + "project.json";
  if (rest === "/fp") return dir + "fp.json";
  if (rest === "/estimate-preview") return dir + "estimate-preview.json";
  if (rest === "/changes") return dir + "changes.json";
  if (rest === "/snapshots") return dir + "snapshots.json";
  if (rest === "/export/preview") return `${dir}preview-${u.searchParams.get("estimate_id") || "none"}.json`;
  const d = rest.match(/^\/snapshots\/([A-Za-z0-9-]+)\/diff$/);
  if (d) return `${dir}diff-${d[1]}.json`;
  return null;
}

function get<T>(url: string): Promise<T> {
  const f = staticFile(url);
  if (!f) return Promise.reject(new ApiError(404, "샘플 시연판에 준비되지 않은 데이터입니다."));
  return fetchJson<T>(f);
}
const refuse = <T>(): Promise<T> => Promise.reject(new ApiError(403, READ_ONLY_REASON));

export const api: typeof Real.api = {
  get,
  post: refuse,
  put: refuse,
  patch: refuse,
  del: refuse,
  form: refuse,
};

export const setUnauthorizedHandler: typeof Real.setUnauthorizedHandler = () => {};
export const P: typeof Real.P = (pid) => `/api/projects/${pid}`;

export const waitJob: typeof Real.waitJob = async (job: Job) => job;

/** 미리 만든 정적 파일 주소(원본 가상 문서·샘플 엑셀·백업). 없으면 null. */
function staticDownload(url: string): { href: string; name: string } | null {
  const u = new URL(url, "http://demo.invalid");
  const m = u.pathname.match(/^\/api\/projects\/([A-Za-z0-9]+)\/(.+)$/);
  const s = m && sample(m[1]);
  if (!m || !s) return null;
  if (m[2] === "export.xlsx") {
    const f = s.xlsx[u.searchParams.get("estimate_id") || "none"];
    return f ? { href: `${DATA_BASE}${s.pid}/${f}`, name: f } : null;
  }
  if (m[2] === "backup.json") return { href: `${DATA_BASE}${s.pid}/backup.json`, name: `${s.file_prefix}_backup.json` };
  const doc = m[2].match(/^documents\/([A-Za-z0-9-]+)\/download$/);
  if (doc && s.originals[doc[1]]) return { href: `${DATA_BASE}${s.pid}/${s.originals[doc[1]]}`, name: s.originals[doc[1]] };
  return null;
}

export const fileUrl: typeof Real.fileUrl = (url) => staticDownload(url)?.href ?? null;

export const download: typeof Real.download = (url) => {
  const f = staticDownload(url);
  if (!f) {
    alert("샘플 시연판에는 이 파일이 준비되어 있지 않습니다.");
    return;
  }
  const a = document.createElement("a");
  a.href = f.href;
  a.download = f.name;
  a.rel = "noopener";
  document.body.appendChild(a);
  a.click();
  a.remove();
};
