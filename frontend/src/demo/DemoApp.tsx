// 정적 시연판(GitHub Pages) 루트. `npm run build:demo`에서만 src/App.tsx 대신 쓰인다(vite.config.ts).
// 로그인·서버 없이 미리 만든 가상 샘플을 기존 작업 화면(Workspace·단계 화면)으로 읽기 전용 표시한다.
import { useEffect, useState } from "react";
import Workspace, { STEPS } from "../pages/Workspace";
import { won } from "../labels";
import type { ProjectResponse, SystemInfo } from "../types";
import { api, DATA_BASE, loadManifest, READ_ONLY_REASON, type DemoManifest, type DemoSample } from "./api";

export const BANNER = "샘플 시연판 — 가상 데이터로 기능 흐름과 결과를 보여줍니다. 실제 AI 호출·문서 분석·서버 저장은 수행하지 않습니다.";

const INTRO: Record<string, { title: string; kind: string; desc: string; shows: string[] }> = {
  sampleA: {
    title: "A. 구상 기반 — 직원 교육 신청·관리 시스템",
    kind: "정상 완료 사례",
    desc: "한 줄 구상에서 시작해 질문·요구사항·설계·FP·개발비·검토·엑셀까지 끝까지 진행한 사례입니다.",
    shows: [
      "질문과 답변 예시(선택·모름→권장안 가정·나중에 결정)",
      "사용자 요구(원문 보존)와 규칙 제안의 구분, 적용·거절 이력",
      "기능·화면·데이터·연계 설계와 요구사항 ID 연결",
      "FP 분류 근거·점수, 기준 산정과 목표예산 시나리오",
      "가상 업체 문서 대조 검토(일치·차이·문서로 확정 불가)와 HW·SW 구성 추천",
    ],
  },
  sampleB: {
    title: "B. 참고문서 기반 — 공공시설 예약 관리 시스템(가상 과업지시서)",
    kind: "검토가 필요한 사례",
    desc: "타 기관 가상 과업지시서에서 항목을 추출해 우리 사업에 맞게 유지·수정·제외하고, 아직 확인할 것이 남은 상태를 보여 줍니다.",
    shows: [
      "원문 문장과 추출 위치(문단), 타 기관 고유 조건(예산·제품·개인정보) 표시",
      "수정·제외 예시와 이유, 결정 대기 항목",
      "미확정·미분류 FP, 중복 의심, 확인이 필요한 결제 연계 조건",
      "미답변 질문과 검토 대기 변경안(사용자 요구 vs 규칙 제안)",
      "확정 항목만으로 만든 기준 산정(미확정 제외 경고 포함)",
    ],
  },
};

function parseHash(): { pid: string | null; step: string } {
  const m = location.hash.match(/^#\/p\/([A-Za-z0-9]+)(?:\/(\w+))?/);
  return m ? { pid: m[1], step: m[2] || "overview" } : { pid: null, step: "" };
}

export default function DemoApp() {
  const [system, setSystem] = useState<SystemInfo | null>(null);
  const [man, setMan] = useState<DemoManifest | null>(null);
  const [err, setErr] = useState("");
  const [route, setRoute] = useState(parseHash());
  const [reset, setReset] = useState(0);

  useEffect(() => {
    Promise.all([loadManifest(), api.get<SystemInfo>("/api/system")])
      .then(([m, s]) => {
        setMan(m);
        setSystem(s);
      })
      .catch((e) => setErr((e as Error).message));
    const h = () => setRoute(parseHash());
    window.addEventListener("hashchange", h);
    return () => window.removeEventListener("hashchange", h);
  }, []);

  const known = !!(route.pid && man?.samples.some((s) => s.pid === route.pid));
  const resetSample = () => {
    setReset((n) => n + 1);
    location.hash = `#/p/${route.pid}/overview`;
  };

  return (
    <div className="app">
      <div className="sticky-head">
        <header className="top">
          <a href="#/" className="brand">
            정보화 설계 도우미
          </a>
          <span className="mode mode-demo" title="서버·AI 없이 미리 만든 가상 샘플을 보여 주는 정적 시연판입니다. 실제 앱의 '샘플 모드'(서버 규칙 실행)와 다릅니다.">
            정적 시연판 · 서버·AI 없음
          </span>
          <span className="spacer" />
          {known && (
            <button className="link light" onClick={resetSample} title="화면에서 바꾼 탭·필터·선택을 지우고 샘플을 다시 불러옵니다(서버 저장 없음).">
              샘플 초기화
            </button>
          )}
          {route.pid && (
            <a className="link-light" href="#/">
              처음으로
            </a>
          )}
        </header>
        <div className="demo-banner" role="note">
          {BANNER}
        </div>
      </div>
      <main>
        {err && <div className="error">{err}</div>}
        {!err && (!system || !man) && <div className="center pad">샘플 데이터를 불러오는 중…</div>}
        {system && man && known && <Workspace key={`${route.pid}-${reset}`} pid={route.pid!} step={route.step} system={system} readOnly={READ_ONLY_REASON} />}
        {system && man && !known && <DemoHome man={man} unknown={route.pid} />}
      </main>
    </div>
  );
}

function DemoHome({ man, unknown }: { man: DemoManifest; unknown: string | null }) {
  return (
    <>
      {unknown && <div className="error">샘플 '{unknown}'이 없습니다. 아래에서 샘플을 고르세요.</div>}
      <h2>샘플을 골라 둘러보세요</h2>
      <p className="muted">
        지방자치단체 신규 정보화사업(홈페이지·포털, 일반 SW·정보시스템 신규개발)을 구상하거나 참고문서를 제시하면, 질문으로 요구사항·설계를 구체화하고 FP·개발비·검토의견·엑셀 산출물을 만드는 도구입니다. 이 시연판은 미리 만든 가상 샘플로 화면과 결과물을 보여 줍니다.
      </p>
      <div className="demo-cards">
        {man.samples.map((s) => (
          <SampleCard key={s.pid} s={s} />
        ))}
      </div>
      <section className="card">
        <h3>시연판과 실제 앱의 차이</h3>
        <div className="table-wrap">
          <table className="grid compact">
            <thead>
              <tr>
                <th style={{ width: 110 }}>구분</th>
                <th>이 시연판(GitHub Pages)</th>
                <th>실제 앱(서버 배포)</th>
              </tr>
            </thead>
            <tbody>
              <tr><td>로그인</td><td>없음(누구나 둘러보기)</td><td>관리자 비밀번호 로그인</td></tr>
              <tr><td>데이터</td><td>미리 만든 가상 샘플만. 바꿔도 저장되지 않음</td><td>프로젝트를 만들고 서버에 저장·이어하기</td></tr>
              <tr><td>질문·초안</td><td>미리 만든 결과를 보여 줌(AI 호출 없음)</td><td>AI 연결 시 AI가 생성, 키가 없으면 서버 '샘플 모드' 규칙으로 생성</td></tr>
              <tr><td>문서</td><td>업로드·분석 없음(미리 분석한 가상 문서 표시)</td><td>PDF·HWPX·DOCX·XLSX 등 업로드·추출·분석</td></tr>
              <tr><td>FP·개발비</td><td>서버 계산 엔진으로 미리 계산한 값</td><td>입력을 바꿀 때마다 서버가 다시 계산</td></tr>
              <tr><td>엑셀</td><td>서버 엑셀 생성기로 미리 만든 샘플 파일</td><td>현재 데이터로 즉시 생성</td></tr>
            </tbody>
          </table>
        </div>
        <p className="muted small">
          실제 앱의 '샘플 모드'는 AI 키가 없을 때 서버가 규칙으로 질문·초안을 만드는 기능입니다. 이 시연판은 그 결과를 미리 저장해 둔 정적 화면이며, 브라우저에서 아무것도 새로 계산하거나 생성하지 않습니다.
        </p>
      </section>
    </>
  );
}

function SampleCard({ s }: { s: DemoSample }) {
  const info = INTRO[s.pid];
  const [p, setP] = useState<ProjectResponse | null>(null);
  useEffect(() => {
    api.get<ProjectResponse>(`/api/projects/${s.pid}`).then(setP).catch(() => setP(null));
  }, [s.pid]);
  const est = p?.project.estimates.at(-1);
  const xlsx = est ? s.xlsx[est.id] : s.xlsx.none;
  return (
    <section className="card demo-card">
      <div className="row-actions">
        <b className="demo-card-title">{info?.title || s.name}</b>
        {info && <span className={`badge ${s.pid === "sampleA" ? "badge-st-confirmed" : "badge-st-review"}`}>{info.kind}</span>}
      </div>
      {info && <p>{info.desc}</p>}
      {info && (
        <ul className="small">
          {info.shows.map((t) => (
            <li key={t}>{t}</li>
          ))}
        </ul>
      )}
      {p && (
        <div className="chips">
          <span className="chip">요구사항 {p.project.requirements.length}</span>
          <span className="chip">FP 간이 {p.status.fp_total.simple}</span>
          {est && <span className="chip">기준 산정 총액 {won(est.result.money.total)}</span>}
          {p.status.counts.fp_unconfirmed > 0 && <span className="chip chip-warn">미확정 FP {p.status.counts.fp_unconfirmed}</span>}
        </div>
      )}
      <div className="row-actions">
        <a className="button primary" href={`#/p/${s.pid}/overview`}>
          둘러보기
        </a>
        {xlsx && (
          <a className="button" href={`${DATA_BASE}${s.pid}/${xlsx}`} download={xlsx}>
            샘플 엑셀 다운로드(미리 만든 가상 파일)
          </a>
        )}
      </div>
      <nav className="demo-steps" aria-label={`${s.name} 단계 바로가기`}>
        {STEPS.map((st, i) => (
          <a key={st.key} href={`#/p/${s.pid}/${st.key}`}>
            {"①②③④⑤⑥⑦"[i]} {st.label.replace(/^\d\s/, "")}
          </a>
        ))}
      </nav>
    </section>
  );
}
