# 외부 구성요소·라이선스

2026-10-30에 실제 잠금 파일(`backend/uv.lock`, `frontend/package-lock.json`)로 설치된 직접 의존성의 패키지 메타데이터에서 확인했습니다.
간접(하위) 의존성은 개별 확인하지 않았습니다. 재배포·제출 전에 잠금 파일 기준으로 다시 확인하세요. 아래 표는 법률 검토가 아니며 "제약 없음"을 뜻하지 않습니다.

## 이 저장소 자체
- 저장소에 LICENSE 파일이 **없습니다.** 라이선스 지정 여부는 저장소 소유자가 결정할 사항이며, 이 문서는 지정하지 않습니다.

## 서버(Python, 실행 시 포함)
| 패키지 | 확인 버전 | 라이선스 | 용도 |
|---|---|---|---|
| fastapi | 0.162.0 | MIT | 웹 API |
| uvicorn | 0.54.0 | BSD-3-Clause | 웹 서버 |
| pydantic | 2.14.1 | MIT | 데이터 검증 |
| python-multipart | 0.0.32 | Apache-2.0 | 파일 업로드 |
| itsdangerous | 2.2.0 | BSD-3-Clause | 로그인 쿠키 서명 |
| openpyxl | 3.1.5 | MIT | 엑셀 생성·읽기 |
| pypdf | 6.21.4 | BSD-3-Clause | PDF 텍스트 추출 |
| python-docx | 1.2.0 | MIT | DOCX 추출 |
| olefile | 0.47 | BSD-2-Clause 계열(BSD) | HWP(실험적) 읽기 |
| httpx | 0.28.1 | BSD-3-Clause | HTTP 클라이언트(OpenAI 호환 연결) |
| anthropic | 2.3.0 | Apache-2.0 | Anthropic 공급자 연결 |
| openai | 3.41.0 | Apache-2.0 | OpenAI 공급자 연결 |

개발 전용: pytest(MIT, 테스트).

## 화면(npm)
| 패키지 | 확인 버전 | 라이선스 | 포함 여부 |
|---|---|---|---|
| react, react-dom | 18.3.1 | MIT | 빌드 결과에 포함 |
| typescript | 5.6.3 | Apache-2.0 | 빌드 도구(결과물에 미포함) |
| vite | 5.4.11 | MIT | 빌드 도구 |
| @vitejs/plugin-react | 4.3.4 | MIT | 빌드 도구 |
| @types/react, @types/react-dom | — | MIT | 타입 정의(빌드 도구) |
| playwright(`e2e/`) | 1.63.0 | Apache-2.0 | E2E 테스트 전용, 앱에 미포함 |

## 실행 환경(Docker 기반 이미지)
| 이미지 | 비고 |
|---|---|
| `node:22-slim` | 화면 빌드 단계에서만 사용, 최종 이미지에 미포함 |
| `python:3.13-slim` | 최종 이미지. Debian 패키지·Python 각각의 라이선스를 따름(개별 확인 안 함) |

## 외부 서비스(선택)
- OpenAI·Anthropic·OpenAI 호환 LLM: 각 공급자의 이용약관·데이터 정책을 따릅니다. 키가 없으면 호출하지 않습니다(샘플 모드).
- Render(운영 배포)·GitHub Pages(읽기 전용 시연판): 각 서비스 약관을 따릅니다.

## 기준값 자료
- `backend/app/standards/KOSA-FORM-2024G-241231.json`의 FP 단가·보정계수 등은 산정양식(엑셀) 수식에서 **값을 추출**해 근거와 확인 상태를 함께 기록한 것입니다. 산정양식 파일 자체는 저장소에 넣지 않았습니다.
- KOSA 가이드 원문은 확인하지 못했습니다(`docs/FP_RULES.md`). 자료 이용 조건도 원문으로 확인하지 않았습니다.
