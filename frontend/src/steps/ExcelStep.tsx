import { useEffect, useState } from "react";
import { api, download, P } from "../api";
import { Section, useProject, useReadOnly } from "../components/ui";

interface Sheet {
  name: string;
  rows: unknown[][];
  truncated: boolean;
  total_rows: number;
}

// 시트 → 편집할 단계
const EDIT_STEP: Record<string, string> = {
  사업개요: "overview",
  과업내용: "design",
  요구사항: "requirements",
  기능설계: "design",
  화면_데이터_연계: "design",
  FP_간이법: "fp",
  FP_정통법: "fp",
  개발비_기준: "fp",
  목표예산_시나리오: "fp",
  검토의견: "review",
  HW_SW추천: "review",
  근거_변경이력: "sources",
};

function cell(v: unknown) {
  if (v && typeof v === "object" && "formula" in (v as object)) return <span className="formula" title={(v as { formula: string }).formula}>ƒ 수식</span>;
  if (typeof v === "number") return v.toLocaleString("ko-KR", { maximumFractionDigits: 6 });
  return v === null || v === undefined ? "" : String(v);
}

export default function ExcelStep() {
  const { data, goto } = useProject();
  const ro = useReadOnly();
  const pid = data.project.id;
  const [est, setEst] = useState(data.project.estimates.at(-1)?.id || "");
  const [sheets, setSheets] = useState<Sheet[]>([]);
  const [active, setActive] = useState(0);
  const [err, setErr] = useState("");
  useEffect(() => {
    api
      .get<{ sheets: Sheet[] }>(`${P(pid)}/export/preview${est ? `?estimate_id=${est}` : ""}`)
      .then((r) => setSheets(r.sheets))
      .catch((e) => setErr(e.message));
  }, [pid, est, data.version]);
  const sh = sheets[active];
  return (
    <>
      <Section
        title="엑셀 산출물"
        right={
          <div className="row-actions">
            <select value={est} onChange={(e) => setEst(e.target.value)} aria-label="적용 견적 버전">
              <option value="">견적 없음</option>
              {data.project.estimates.map((e) => (
                <option key={e.id} value={e.id}>
                  {e.id} {e.label}
                </option>
              ))}
            </select>
            <button className="primary" onClick={() => download(`${P(pid)}/export.xlsx${est ? `?estimate_id=${est}` : ""}`)}>
              {ro ? "샘플 엑셀 내려받기(.xlsx, 미리 만든 파일)" : "엑셀 내려받기(.xlsx)"}
            </button>
          </div>
        }
      >
        {ro && <p className="muted small">시연판: 미리보기와 내려받는 파일은 서버 엑셀 생성기로 미리 만든 가상 샘플이며, 파일 첫 시트에 '샘플 시연판(가상 데이터)'으로 표시되어 있습니다.</p>}
        <p className="muted small">
          금액·FP 칸은 Excel 수식과 Python 계산 확인값을 함께 넣습니다. 수식은 Excel에서 열 때 계산되며, '검산' 시트에서 두 값이 일치하는지 확인하세요. 아래 미리보기의 'ƒ 수식'은 파일을 열면 계산됩니다. 내용을 고치려면 각 시트의 편집 단계로 이동하세요.
        </p>
        {err && <div className="error">{err}</div>}
        <div className="tabs">
          {sheets.map((s, i) => (
            <button key={s.name} className={i === active ? "active" : ""} onClick={() => setActive(i)}>
              {s.name}
            </button>
          ))}
        </div>
        {sh && (
          <>
            <div className="row-actions">
              {EDIT_STEP[sh.name] && <button onClick={() => goto(EDIT_STEP[sh.name])}>{ro ? "이 시트 내용 단계로 가기" : "이 시트 내용 편집하러 가기"}</button>}
              <span className="muted small">
                {sh.total_rows}행{sh.truncated ? " (미리보기는 200행까지)" : ""}
              </span>
            </div>
            <div className="sheet-preview">
              <table className="grid compact">
                <tbody>
                  {sh.rows.map((r, i) => (
                    <tr key={i}>
                      {r.map((c, j) => (
                        <td key={j}>{cell(c)}</td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </Section>
      <Section title="백업">
        <p className="muted small">프로젝트 전체(요구사항·설계·FP·견적·변경이력·추출 텍스트)를 JSON으로 내려받습니다. 첨부 원본 파일은 포함되지 않습니다. 첫 화면의 '백업 파일로 복원'으로 새 프로젝트로 복원할 수 있습니다.</p>
        <button onClick={() => download(`${P(pid)}/backup.json`)}>{ro ? "샘플 JSON 백업 내려받기(미리 만든 파일)" : "JSON 백업 내려받기"}</button>
      </Section>
    </>
  );
}
