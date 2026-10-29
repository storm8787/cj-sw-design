import { useState } from "react";
import { P } from "../api";
import { EditableTable, type Col } from "../components/EditableTable";
import { JobStatus, useJobRunner } from "../components/Jobs";
import { Proposals } from "../components/Proposals";
import { Section, useProject } from "../components/ui";
import type { Row } from "../types";

export const REQ_COLS: Col[] = [
  { key: "kind", label: "구분", type: "select", options: [["functional", "기능"], ["nonfunctional", "비기능"]], width: 70 },
  { key: "category", label: "분류", width: 80 },
  { key: "title", label: "요구사항명", width: 180 },
  { key: "description", label: "설명", type: "textarea" },
  { key: "original_text", label: "사용자 요구 원문", type: "textarea", width: 160 },
  { key: "priority", label: "우선순위", type: "select", options: [["high", "상"], ["medium", "중"], ["low", "하"]], width: 60 },
  { key: "acceptance", label: "검수 기준", type: "textarea", width: 160 },
  { key: "why", label: "왜 필요한가", type: "textarea", width: 140 },
];

export default function RequirementsStep() {
  const { data } = useProject();
  const pid = data.project.id;
  const jr = useJobRunner();
  const [text, setText] = useState("");
  return (
    <>
      <Section title="생각한 기능 입력 → 요구사항 초안">
        <p className="muted small">자유문장·목록(줄마다 1개)·표(엑셀에서 복사한 '이름[탭]설명')를 붙여 넣으세요. 입력한 기능은 모두 '사용자' 요구로 보존되고, 빠진 기능·비기능 요구는 별도 '제안'으로 구분됩니다.</p>
        <textarea rows={6} value={text} onChange={(e) => setText(e.target.value)} placeholder={"예)\n교육 신청: 직원이 신청기간 내 신청\n신청 취소\n과정별 통계"} aria-label="기능 입력" />
        <div className="row-actions">
          <button className="primary" disabled={jr.running} onClick={() => jr.start(`${P(pid)}/ai/requirements`, { feature_text: text })}>
            요구사항 초안 만들기
          </button>
        </div>
        <JobStatus job={jr.job} running={jr.running} onRetry={jr.retry} note={jr.note} />
      </Section>
      <Proposals kinds={["requirements", "answer"]} />
      <Section title="요구사항 목록" right={<span className="muted small">비기능 요구사항은 FP 대상은 아니지만 과업·검수 기준에 남습니다.</span>}>
        <EditableTable collection="requirements" rows={data.project.requirements as unknown as Row[]} cols={REQ_COLS} defaults={{ kind: "functional", priority: "medium" }} addLabel="요구사항 추가" />
      </Section>
    </>
  );
}
