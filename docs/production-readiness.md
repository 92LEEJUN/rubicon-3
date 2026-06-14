# 프로덕션 준비도 (Production Readiness)

> MVP(데모)를 프로덕션으로 끌어올리는 **다중 스트림 프로그램**의 단일 추적 문서.
> 백본 표준: **15-Factor**(Beyond the Twelve-Factor) + **Well-Architected**(+ OWASP·DORA·개인정보).
> 각 셀은 ✅ 착수(채택/구현) · 🟡 부분 · ⬜ 미착수. 결정 근거는 `docs/adr/`.

## green의 정의 (DoD)
한 항목이 ✅이 되려면: **① ADR 결정 · ② (큰 건) `specs/` 3종 · ③ 토글 뒤 구현(기본 off=회귀 불변,
외부 인프라는 Mock/인터페이스 어댑터 허용) · ④ 테스트(전 스위트 green) · ⑤ 계약 3계층 동기 + 문서**.
→ green = "결정+구조적 구현(Mock 허용)+테스트+문서"이지 실 클라우드 배포가 아니다.

## 작업 스트림 & 웨이브
| 스트림 | 대상 | 소유 파일(배타) | 의존 | 웨이브 | 상태 |
|---|---|---|---|:--:|:--:|
| **S0 환경·구성** | 12F#5·#9 | `app/config.py`·`app/platform/*`·`bff/gateway/config.py`·`frontend/src/config/*` | — | **P0** | 🟡 진행 |
| S1 관측성 | 12F#14·WA운영 | `app/observability/*`·`*_middleware_obs` | S0 | W1 | ⬜ |
| S2 회복력 | WA신뢰성·12F#7 | `app/resilience.py`·lifecycle | S0 | W1 | ⬜ |
| S3 백킹서비스 | 12F#8·#12 | `app/repositories/*`·`adapters/*`·`migrations/` | S0 | W1 | ⬜ |
| S4 API 성숙 | 12F#2 | `docs/api-contract`·`scripts/gen_types`·openapi | — | W1 | ⬜ |
| S5 개인정보 | GDPR | `app/privacy/*`·consent·DSR | S0 | W1 | ⬜ |
| S6 비용·캐싱 | WA비용 | `app/llm.py`(비용)·`app/cache/*` | S1 | W2 | ⬜ |
| S7 보안 심화 | WA보안·OWASP | `bff/gateway/ratelimit`·`app/audit/*` | S0·S5 | W2 | ⬜ |
| S8 실험 A/B | ⑭ | `app/experiments/*`·`frontend/src/experiments/*` | S0·S1 | W2 | ⬜ |
| S9 딜리버리/DORA | 12F#4·DORA | `.github/workflows/*`·`docker/*`·`scripts/release` | S1 | W2 | ⬜ |

> 공유 핫스팟: `internal.py`(→ S0 wiring 시임으로 등록만)·`llm.py`(비용=S6 단독)·CI yml(=S9 소유)·
> analytics 택소노미(owner append). 계약 변경(S4·S8)은 main이 3계층 동기 검증 후 머지.

## 매트릭스 — 15-Factor
| # | 항목 | 상태 | 근거 / 갭 | 스트림 |
|---|---|:--:|---|:--:|
| 1 | Codebase/app | ✅ | monorepo 3계층(ADR-0019) | — |
| 2 | API first | 🟡 | 계약 문서·contract.ts. 버저닝·OpenAPI·Pact 없음 | S4 |
| 3 | Dependency mgmt | ✅ | 핀 고정·pyproject·pre-commit | — |
| 4 | Build/release/run | 🟡 | CI·Docker·gh-pages. release 분리·아티팩트 약함 | S9 |
| 5 | Config/credentials | 🟡→ | **APP_ENV·Settings 토대(ADR-0056)**. 시크릿 매니저 후속 | **S0** |
| 6 | Logs | 🟡 | JSON 로깅. 집계·보존 표준 미정 | S1 |
| 7 | Disposability | ⬜ | graceful shutdown 없음 | S2 |
| 8 | Backing services | 🟡 | Port/DI. 실 DB·캐시·큐 미배선 | S3 |
| 9 | Env parity | 🟡→ | **APP_ENV 동형(BE/BFF/FE)**. 환경별 테스트·시드 확장 | **S0** |
| 10 | Admin processes | ⬜ | 마이그레이션·admin 콘솔 없음 | S3(부분) |
| 11 | Port binding | ✅ | FastAPI/uvicorn 자기완결 | — |
| 12 | Stateless | 🟡 | 세션 인메모리. 외부화 부분 | S3 |
| 13 | Concurrency | 🟡 | async·세마포어·KeyedLock. 분산 보류 | — |
| 14 | Telemetry | 🟡 | /metrics·/health. 추적·SLO 없음 | S1 |
| 15 | Auth & authz | 🟡 | Principal·커밋게이트. 실 SSO·RBAC 미정 | S7 |

## 매트릭스 — Well-Architected
| 기둥 | 상태 | 갭 | 스트림 |
|---|:--:|---|:--:|
| 운영 우수성 | 🟡 | 배포 자동화·런북·온콜 | S9·S1 |
| 보안 | 🟡 | 암호화·OWASP·시크릿 | S7 |
| 신뢰성 | 🟡 | DR·백업·서킷브레이커 | S2 |
| 성능 효율 | 🟡 | 부하·용량 계획 | S6 |
| 비용 최적화 | ⬜ | LLM 비용 관측·쿼터 | S6 |
| 지속가능성 | ⬜ | (범위 외) | — |

## 보강 렌즈
| 영역 | 표준 | 상태 | 스트림 |
|---|---|:--:|:--:|
| 보안 심화 | OWASP | 🟡 | S7 |
| 딜리버리 | DORA | 🟡 | S9 |
| 개인정보 | GDPR/개인정보보호법 | 🟡 | S5 |
| 실험·롤아웃 | (런타임 A/B) | ⬜ | S8 |

## 범위 외(의도적 ⬜, deferred)
SmartThings 엔터프라이즈 실 텔레메트리 · 삼성계정 SSO · 실 결제(PG) · 모바일/릴리스(OTA·앱스토어·푸시)
· 어드민 콘솔 · 지속가능성 기둥 → 사유는 [`docs/deferred.md`](deferred.md).
