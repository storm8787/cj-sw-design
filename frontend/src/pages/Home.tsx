import { useEffect, useState } from "react";
import { api } from "../api";
import { Dialog, Skeleton } from "../components/Frame";
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

const EX = "/api/examples/"; // 저장소 examples/와 같은 원본(로그인 후 내려받기)

const STARTS = [
  { mode: "idea", title: "구상으로 시작하기", desc: "한 줄 구상을 질문에 답하며 구체화해요." },
  { mode: "document", title: "참고문서로 시작하기", desc: "과업지시서·FP 산정표를 우리 사업에 맞춰요." },
  { mode: "review", title: "기존 문서 검토하기", desc: "업체 문서의 누락과 금액 차이를 확인해요." },
];

export default function Home({ system }: { system: SystemInfo }) {
  const [list, setList] = useState<ListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [err, setErr] = useState("");
  const [form, setForm] = useState<{ mode: string; name: string; business_type: string; budget_mode: string; target: string; vat: boolean; idea: string; example?: boolean } | null>(null);

  const load = () => api.get<ListItem[]>("/api/projects").then(setList).catch((e) => setErr(e.message)).finally(() => setLoading(false));
  useEffect(() => {
    load();
  }, []);

  const create = async (sample?: string) => {
    if (creating) return;
    setCreating(true);
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
    } finally { setCreating(false); }
  };

  // 예제 A: 만들기 창에 예시 값만 채운다(누르기만으로 프로젝트·AI 호출이 생기지 않음)
  const startExampleA = () =>
    setForm({ mode: "idea", name: "[예제] 직원 교육 신청·관리 시스템 구축", business_type: "system", budget_mode: "target", target: "80,000,000", vat: true, example: true,
      idea: "직원 교육 신청·관리 프로그램이 필요하다. 신청·취소·승인과 정원 초과 시 대기자 관리, 이수 통계가 필요하다." });

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
      <div className="hero"><span className="eyebrow">사업 설계의 첫걸음</span><h1>무엇을 하시겠어요?</h1><p>지금 가진 자료에 맞춰 시작하세요. 나머지는 함께 정리해요.</p><a href="#continue">저장된 프로젝트 이어하기 ↓</a></div>
      {err && <div className="error">{err}</div>}
      <div className="starts">
        {STARTS.map((s) => (
          <button key={s.mode} className="start" onClick={() => setForm({ mode: s.mode, name: "", business_type: "system", budget_mode: "none", target: "", vat: true, idea: "" })}>
            <span className="start-icon" aria-hidden="true">{s.mode === "idea" ? "01" : s.mode === "document" ? "02" : "03"}</span><b>{s.title} <span aria-hidden="true">↗</span></b>
            <span>{s.desc}</span>
          </button>
        ))}

      </div>

      <details className="card examples" id="examples">
        <summary>
          <b>예제로 체험하기</b> <span className="muted small">가상 자료 · 누르기만으로는 AI를 호출하지 않아요</span>
        </summary>
        <ul className="example-list">
          <li>
            <b>01 구상</b> <span className="muted small">입력부터 체험:</span>{" "}
            <button className="link" onClick={startExampleA}>예제 값으로 시작</button>
            {" · "}
            <a href={`${EX}A-idea/idea_example.md`} download>입력 예시 받기</a>
            <br />
            <span className="muted small">미리 채운 완성 예시(샘플 규칙으로 만든 새 프로젝트, AI 결과 아님):</span>{" "}
            <button className="link" disabled={creating} onClick={() => create("education")}>교육 신청·관리</button>
            {" · "}
            <button className="link" disabled={creating} onClick={() => create("complaint")}>민원·배치 연계</button>
          </li>
          <li>
            <b>02 참고문서</b> <a href={`${EX}B-reference/reference_task_order.txt`} download>가상 타 기관 과업지시서 받기</a>
            <span className="muted small"> → '참고문서로 시작하기'로 만든 뒤 '2 자료·질문'에서 올리고 항목 추출</span>
          </li>
          <li>
            <b>03 검토</b> <span className="muted small">가상 업체 문서:</span>{" "}
            <a href={`${EX}C-review/vendor_task.txt`} download>과업지시서</a>
            {" · "}
            <a href={`${EX}C-review/vendor_design.txt`} download>설계서</a>
            {" · "}
            <a href={`${EX}C-review/vendor_fp.xlsx`} download>FP 산정표</a>
            {" · "}
            <a href={`${EX}C-review/vendor_cost.txt`} download>금액 산출서</a>
            {" · "}
            <a href={`${EX}C-review/expected_findings.md`} download>기대 확인 목록</a>
            <span className="muted small"> → '기존 문서 검토하기' → '2 자료·질문'에서 종류별로 올리기 → '6 검토·추천'에서 검토 실행</span>
          </li>
        </ul>
      </details>

      {form && (
        <Dialog title={STARTS.find((s) => s.mode === form.mode)!.title} onClose={() => setForm(null)}><p className="muted">이름부터 정해 주세요. 세부 내용은 나중에 바꿀 수 있어요.</p>
          {form.example && <p className="muted small">예제 값이 채워져 있어요. 만든 뒤 '2 자료·질문'에서 질문 받기, '3 요구사항'에 입력 예시 파일의 기능 일곱 줄을 붙여 넣으세요.</p>}{err && <div role="alert" className="error">{err}</div>}
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
            <button className="primary" disabled={creating || !form.name.trim()} onClick={() => create()}>
              {creating ? "만드는 중…" : "만들기"}
            </button>
            <button onClick={() => setForm(null)}>닫기</button>
          </div>
        </Dialog>
      )}

      <div className="card" id="continue">
        <div className="card-head">
          <h3>프로젝트 이어하기</h3>
          <div className="card-right">
            <label className="button">
              백업 파일로 복원
              <input type="file" accept=".json,application/json" hidden onChange={(e) => e.target.files?.[0] && restore(e.target.files[0])} />
            </label>
          </div>
        </div>
        {loading && <Skeleton />}
        <div className="table-wrap"><table className="grid">
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
            {!loading && !list.length && (
              <tr>
                <td colSpan={7} className="muted center">
                  저장된 프로젝트가 없습니다. 위에서 새로 시작하거나 '예제로 체험하기'를 열어 보세요.
                </td>
              </tr>
            )}
          </tbody>
        </table></div>
        <p className="muted small">
          {system.ai.is_real_ai ? "AI 모드: 질문·초안 생성 시 전송 범위를 확인한 뒤 외부 AI로 보냅니다." : "샘플 모드: AI 키가 없어 서버 규칙으로 질문·초안을 만듭니다(AI 분석 결과 아님). 계산·저장·엑셀은 모두 사용할 수 있습니다."}
        </p>
      </div>
    </div>
  );
}
