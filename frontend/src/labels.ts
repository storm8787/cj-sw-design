// 화면 한국어 표기와 쉬운 용어 설명.
export const STATUS: Record<string, string> = { draft: "초안", review: "검토중", confirmed: "확정", excluded: "제외" };
export const ORIGIN: Record<string, string> = { user: "사용자", ai: "AI 제안", sample: "샘플 규칙", document: "참고문서", system: "시스템" };
export const KIND: Record<string, string> = { functional: "기능", nonfunctional: "비기능" };
export const PRIORITY: Record<string, string> = { high: "상", medium: "중", low: "하" };
export const VERDICT: Record<string, string> = { match: "확인 일치", diff: "차이 발견", check: "확인 필요", insufficient: "근거 부족" };
export const DOC_KIND: Record<string, string> = {
  reference: "참고문서(타 기관)",
  vendor_task: "업체 과업지시서·제안요청서",
  vendor_design: "업체 설계서",
  vendor_fp: "업체 FP 산정표",
  vendor_cost: "업체 금액 산출서",
  other: "기타",
};
export const EXTRACT_STATUS: Record<string, string> = {
  pending: "대기",
  ok: "정상 추출",
  partial: "일부만 추출",
  failed: "실패",
  unsupported: "지원 안 함",
  scanned: "스캔본(텍스트 없음)",
  encrypted: "암호화됨",
};
export const QUALITY: Record<string, string> = { high: "상", medium: "중", low: "하", none: "없음", "": "-" };
export const ORG_SPECIFIC: Record<string, string> = { budget: "예산", period: "기간", personal_info: "개인정보", product: "특정 제품", org_name: "기관명" };
export const REF_KIND: Record<string, string> = { requirement: "요구사항", function: "기능", data: "데이터", interface: "연계", condition: "조건", other: "기타" };
export const SYSTEM_KINDS: Record<string, string> = { web: "웹", mobile: "모바일", desktop: "데스크톱 프로그램", server: "서버 프로그램", batch: "배치 자동처리", integration: "시스템 연계" };
export const CX_SOURCE: Record<string, string> = { table: "복잡도표(입력값)", derived: "복잡도표(근거 목록 집계)", assumed: "가정", missing: "근거 부족", unclassified: "미분류", excluded: "제외" };
/** 산정 상태 — 숫자가 나왔다고 완료가 아니다(engine.estimate_basis). */
export const BASIS_BADGE: Record<string, string> = { empty: "st-excluded", partial: "st-review", estimated: "st-draft", confirmed: "st-confirmed" };
export const BASIS_HELP: Record<string, string> = {
  empty: "집계된 FP가 0건 — 금액을 만들 수 없습니다.",
  partial: "아직 집계에 넣지 못한 후보·미분류·중복 의심·FP 미연결 요구사항이 남아 있습니다.",
  estimated: "업무 확인만 한 항목(FP 기술 검토 전)이나 가정 복잡도가 포함된 추정치입니다.",
  confirmed: "집계 항목이 모두 기술 검토 확정이고 남은 후보가 없습니다.",
};
/** FP 유형을 업무 말로 묻는 선택지(기본 화면에서 EI/EO 같은 약어를 고르게 하지 않음). */
export const PLAIN_TYPE: [string, string][] = [
  ["EI", "자료를 등록·수정·삭제하는 처리"],
  ["EQ", "저장된 자료를 그대로 찾아보는 처리"],
  ["EO", "계산·집계해서 보여주거나 내보내는 처리"],
  ["ILF", "이 시스템이 직접 관리하는 자료 묶음"],
  ["EIF", "다른 시스템 자료를 읽기만 함"],
];
export const PLAIN_TYPE_LABEL: Record<string, string> = Object.fromEntries(PLAIN_TYPE);

export const GLOSSARY: Record<string, { title: string; text: string; example: string }> = {
  FP: { title: "기능점수(FP)", text: "사용자 입장에서 시스템이 제공하는 기능의 양을 점수로 잰 것입니다. 화면·메뉴·테이블 개수가 아니라 '업무 처리 단위'와 '데이터 묶음'을 셉니다.", example: "교육 신청 등록(EI) 1건, 교육과정 정보(ILF) 1건 …" },
  EI: { title: "외부입력(EI)", text: "밖에서 들어온 자료로 이 시스템이 관리하는 데이터를 등록·수정·삭제하는 처리입니다.", example: "교육 신청 등록, 신청 취소, 승인 처리" },
  EO: { title: "외부출력(EO)", text: "계산·집계 등 가공을 거쳐 밖으로 내보내는 처리입니다. 단순 조회가 아니라 계산이 있으면 EO입니다.", example: "과정별 이수율 통계, 처리결과 전송 배치" },
  EQ: { title: "외부조회(EQ)", text: "가공 없이 저장된 데이터를 꺼내 보여주는 처리입니다.", example: "신청 내역 조회, 과정 목록 조회" },
  ILF: { title: "내부논리파일(ILF)", text: "이 시스템이 직접 등록·수정하며 관리하는 데이터 묶음입니다. 테이블 여러 개가 하나의 ILF일 수 있습니다.", example: "교육과정 정보, 교육 신청 정보" },
  EIF: { title: "외부연계파일(EIF)", text: "다른 시스템이 관리하고 이 시스템은 읽기만 하는 데이터 묶음입니다.", example: "인사시스템의 직원 정보" },
  DET: { title: "DET(데이터 요소)", text: "처리나 데이터에 포함된, 사용자가 알아볼 수 있는 항목 수입니다. 정통법 복잡도 판단에 씁니다.", example: "신청 화면의 과정명·신청자·연락처·신청일 → DET 4" },
  FTR: { title: "FTR(참조 파일)", text: "처리 하나가 읽거나 고치는 데이터 묶음(ILF/EIF) 수입니다.", example: "교육 신청: 과정정보·신청정보·직원정보 → FTR 3" },
  RET: { title: "RET(하위 그룹)", text: "데이터 묶음 안의 하위 그룹 수입니다. 하위 그룹이 없으면 1입니다.", example: "교육 신청 정보 + 승인이력 → RET 2" },
  BOUNDARY: { title: "애플리케이션 경계", text: "FP를 셀 대상 시스템의 범위입니다. 경계 밖 시스템의 기능은 세지 않고, 경계 밖 데이터를 읽기만 하면 EIF로 셉니다.", example: "측정 대상: 교육관리시스템 / 경계 밖: 인사시스템" },
  SIMPLE: { title: "간이법", text: "유형별 평균 가중치(ILF 7.5, EIF 5.4, EI 4.0, EO 5.2, EQ 3.9)로 빠르게 셉니다. 기획·예산 단계에 씁니다.", example: "EI 10건 → 40점" },
  DETAILED: { title: "정통법", text: "항목마다 DET·FTR(RET)로 복잡도(L/A/H)를 정하고 가중치를 줍니다. 값이 빠지면 확정할 수 없습니다.", example: "EI, FTR 2, DET 10 → 보통(A) 4점" },
  TARGET: { title: "목표예산 시나리오", text: "기능은 그대로 두고 지정한 금액에 맞춘 참고 견적입니다. 조정률·환산값은 공식 측정값이 아니며 기준 산정과 따로 보관됩니다.", example: "기준 4,730만 원 → 목표 8,000만 원: 조정률 169%" },
};

export const won = (n: number | undefined | null) => (n === undefined || n === null ? "-" : `${Math.round(n).toLocaleString("ko-KR")}원`);
export const num = (s: string | number | undefined | null, d = 2) => {
  if (s === undefined || s === null || s === "") return "-";
  const v = typeof s === "number" ? s : Number(s);
  return Number.isFinite(v) ? v.toLocaleString("ko-KR", { maximumFractionDigits: d }) : String(s);
};
