import { useEffect, useState } from "react";
import { api } from "../api";
import { Field } from "../components/ui";
import type { ProjectResponse, SystemInfo } from "../types";

interface ListItem {
  id: string;
  name: string;
  updated_at: string;
  business_type: string;
  start_mode: string;
  budget_mode: string;
  requirements: number;
  fp_items: number;
  estimates: number;
}

const STARTS = [
  { mode: "idea", title: "새 설계", desc: "\"교육 신청·관리 프로그램이 필요하다\"처럼 한 줄로 시작해 질문에 답하며 구체화합니다." },
  { mode: "document", title: "참고문서로 설계", desc: "타 기관 과업지시서·제안요청서·FP 산정표를 올려 우리 기관에 맞게 고칩니다." },
  { mode: "review", title: "기존 문서 검토", desc: "업체가 낸 과업·설계·FP·금액 문서를 서로 대조해 누락·오류를 찾습니다." },
];

export default function Home({ system }: { system: SystemInfo }) {
  const [list, setList] = useState<ListItem[]>([]);
  const [err, setErr] = useState("");
  const [form, setForm] = useState<{ mode: string; name: string; business_type: string; budget_mode: string; target: string; vat: boolean; idea: string } | null>(null);

  const load = () => api.get<ListItem[]>("/api/projects").then(setList).catch((e) => setErr(e.message));
  useEffect(() => {
    load();
  }, []);

  const create = async (sample?: string) => {
    setErr("");
    try {
      const body = sample
        ? { name: sample === "education" ? "[샘플] 직원 교육 신청·관리 시스템" : "[샘플] 민원 접수·처리 및 야간 배치 연계 시스템", sample }
        : {
            name: form!.name,
            overview: {
              start_mode: form!.mode,
              business_type: form!.business_type,
              budget_mode: form!.budget_mode,
              target_amount: form!.budget_mode === "target" && form!.target ? Number(form!.target.replace(/[^0-9]/g, "")) : null,
              target_includes_vat: form!.vat,
              idea_text: form!.idea,
            },
          };
      const r = await api.post<ProjectResponse>("/api/projects", body);
      location.hash = `#/p/${r.project.id}/${sample ? "overview" : form!.mode === "review" ? "review" : "sources"}`;
    } catch (e) {
      setErr((e as Error).message);
    }
  };

  const restore = async (f: File) => {
    const fd = new FormData();
    fd.append("file", f);
    try {
      const r = await api.form<ProjectResponse>("/api/projects/restore", fd);
      location.hash = `#/p/${r.project.id}/overview`;
    } catch (e) {
      setErr((e as Error).message);
    }
  };

  return (
    <div className="home">
      <h2>무엇을 하시겠어요?</h2>
      {err && <div className="error">{err}</div>}
      <div className="starts">
        {STARTS.map((s) => (
          <button key={s.mode} className="start" onClick={() => setForm({ mode: s.mode, name: "", business_type: "system", budget_mode: "none", target: "", vat: true, idea: "" })}>
            <b>{s.title}</b>
            <span>{s.desc}</span>
          </button>
        ))}
        <a className="start" href="#continue">
          <b>프로젝트 이어하기</b>
          <span>저장된 프로젝트를 열어 이어서 작업합니다.</span>
        </a>
      </div>

      {form && (
        <div className="card">
          <h3>새 프로젝트 — {STARTS.find((s) => s.mode === form.mode)?.title}</h3>
          <div className="form-grid">
            <Field label="사업(프로젝트) 이름">
              <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="예: 직원 교육 신청·관리 시스템 구축" />
            </Field>
            <Field label="사업 유형" hint="설계 흐름은 같고 질문·과업 초안이 조금 달라집니다.">
              <select value={form.business_type} onChange={(e) => setForm({ ...form, business_type: e.target.value })}>
                <option value="system">일반 SW·정보시스템 신규개발</option>
                <option value="portal">홈페이지·포털 신규개발</option>
              </select>
            </Field>
            <Field label="금액 조건" hint="시작 방식과 별개입니다. 목표예산은 기능을 줄이지 않고 참고 견적만 따로 만듭니다.">
              <select value={form.budget_mode} onChange={(e) => setForm({ ...form, budget_mode: e.target.value })}>
                <option value="none">예산 미지정(기준 산정만)</option>
                <option value="target">개발비 지정(목표예산 시나리오도 작성)</option>
              </select>
            </Field>
            {form.budget_mode === "target" && (
              <>
                <Field label="목표 금액(원)">
                  <input inputMode="numeric" value={form.target} onChange={(e) => setForm({ ...form, target: e.target.value })} placeholder="80,000,000" />
                </Field>
                <Field label="부가세">
                  <select value={form.vat ? "1" : "0"} onChange={(e) => setForm({ ...form, vat: e.target.value === "1" })}>
                    <option value="1">목표 금액에 부가세 포함</option>
                    <option value="0">부가세 별도</option>
                  </select>
                </Field>
              </>
            )}
            {form.mode === "idea" && (
              <Field label="처음 구상(한 줄이면 충분)">
                <textarea value={form.idea} onChange={(e) => setForm({ ...form, idea: e.target.value })} placeholder="예: 교육 신청·관리 프로그램이 필요하다" rows={2} />
              </Field>
            )}
          </div>
          <div className="row-actions">
            <button className="primary" disabled={!form.name.trim()} onClick={() => create()}>
              만들기
            </button>
            <button onClick={() => setForm(null)}>닫기</button>
          </div>
        </div>
      )}

      <div className="card" id="continue">
        <div className="card-head">
          <h3>프로젝트 이어하기</h3>
          <div className="card-right">
            <button onClick={() => create("education")}>샘플: 교육 신청·관리</button>
            <button onClick={() => create("complaint")}>샘플: 민원·배치 연계</button>
            <label className="button">
              백업 파일로 복원
              <input type="file" accept=".json,application/json" hidden onChange={(e) => e.target.files?.[0] && restore(e.target.files[0])} />
            </label>
          </div>
        </div>
        <table className="grid">
          <thead>
            <tr>
              <th>이름</th>
              <th>유형</th>
              <th>시작</th>
              <th>요구사항</th>
              <th>FP 항목</th>
              <th>견적</th>
              <th>최종 수정</th>
            </tr>
          </thead>
          <tbody>
            {list.map((p) => (
              <tr key={p.id}>
                <td>
                  <a href={`#/p/${p.id}/overview`}>{p.name}</a>
                </td>
                <td>{p.business_type === "portal" ? "홈페이지·포털" : "정보시스템"}</td>
                <td>{{ idea: "구상", document: "참고문서", review: "검토" }[p.start_mode] || p.start_mode}</td>
                <td>{p.requirements}</td>
                <td>{p.fp_items}</td>
                <td>{p.estimates}</td>
                <td className="muted">{p.updated_at.replace("T", " ").slice(0, 16)}</td>
              </tr>
            ))}
            {!list.length && (
              <tr>
                <td colSpan={7} className="muted center">
                  저장된 프로젝트가 없습니다. 위에서 새로 시작하거나 샘플을 열어 보세요.
                </td>
              </tr>
            )}
          </tbody>
        </table>
        <p className="muted small">
          {system.ai.is_real_ai ? "AI 모드: 질문·초안 생성 시 전송 범위를 확인한 뒤 외부 AI로 보냅니다." : "샘플 모드: AI 키가 없어 서버 규칙으로 질문·초안을 만듭니다(AI 분석 결과 아님). 계산·저장·엑셀은 모두 사용할 수 있습니다."}
        </p>
      </div>
    </div>
  );
}
