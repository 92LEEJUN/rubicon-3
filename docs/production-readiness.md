# 프로덕션 준비도 (Production Readiness)

> MVP(데모)를 프로덕션으로 끌어올리는 **다중 스트림 프로그램**의 단일 추적 문서.
> 백본 표준: **15-Factor**(Beyond the Twelve-Factor) + **Well-Architected**(+ OWASP·DORA·개인정보).
> 각 셀은 ✅ 착수(채택/구현) · 🟡 부분 · ⬜ 미착수. 결정 근거는 `docs/adr/`.

## green의 정의 (DoD)
한 항목이 ✅이 되려면: **① ADR 결정 · ② (큰 건) `specs/` 3종 · ③ 토글 뒤 구현(기본 off=회귀 불변,
외부 인프라는 Mock/인터페이스 어댑터 허용) · ④ 테스트(전 스위트 green) · ⑤ 계약 3계층 동기 + 문서**.
→ green = "결정+구조적 구현(Mock 허용)+테스트+문서"이지 실 클라우드 배포가 아니다.

## 진행 현황 (요약)
- **Phase 0 + Wave 1 + Wave 2 = 10개 스트림(S0~S9) 전부 ✅** main 통합 완료(ADR-0056~0065).
- 검증(통합 시점): backend **439** · bff **65** · frontend jest **108** · ruff·eslint 0 errors.
- 매트릭스: 15-Factor **13/15 ✅**(잔여 #10 Admin 🟡·#13 Concurrency 🟡 분산보류·#15 Auth 🟡 실 SSO 후속),
  Well-Architected **5/6 ✅**(성능 효율 🟡=부하/용량 후속, 지속가능성 ⬜=범위 외), 보강 렌즈 **전부 ✅**.
- 모두 토글 기본 off=회귀 불변(스트랭글러), 외부 인프라는 Mock/Port 어댑터(실 연동은 후속).

## 작업 스트림 & 웨이브
| 스트림 | 대상 | 소유 파일(배타) | 의존 | 웨이브 | 상태 |
|---|---|---|---|:--:|:--:|
| **S0 환경·구성** | 12F#5·#9 | `app/config.py`·`app/platform/*`·`bff/gateway/config.py`·`frontend/src/config/*` | — | **P0** | ✅ (ADR-0056) |
| S1 관측성 | 12F#14·WA운영 | `app/observability/*`·`middleware_obs` | S0 | W1 | ✅ (ADR-0057) |
| S2 회복력 | WA신뢰성·12F#7 | `app/resilience.py`·lifecycle | S0 | W1 | ✅ (ADR-0058) |
| S3 백킹서비스 | 12F#8·#12 | `app/repositories/*`·`adapters/*`·`migrations/` | S0 | W1 | ✅ (ADR-0059) |
| S4 API 성숙 | 12F#2 | `docs/api-contract`·`scripts/gen_types`·openapi | — | W1 | ✅ (ADR-0060) |
| S5 개인정보 | GDPR | `app/privacy/*`·consent·DSR | S0 | W1 | ✅ (ADR-0061) |
| S6 비용·캐싱 | WA비용 | `app/cost/*`·`app/cache_layer.py`·`llm.py` | S1 | W2 | ✅ (ADR-0062) |
| S7 보안 심화 | WA보안·OWASP | `bff/gateway/ratelimit·security`·`app/security/*` | S0·S5 | W2 | ✅ (ADR-0063) |
| S8 실험 A/B | ⑭ | `app/experiments/*`·`frontend/src/experiments/*` | S0·S1 | W2 | ✅ (ADR-0064) |
| S9 딜리버리/DORA | 12F#4·DORA | `.github/workflows/*`·`docker/*`·`scripts/release` | S1 | W2 | ✅ (ADR-0065) |

> 공유 핫스팟: `internal.py`(→ S0 wiring 시임으로 등록만)·`llm.py`(비용=S6 단독)·CI yml(=S9 소유)·
> analytics 택소노미(owner append). 계약 변경(S4·S8)은 main이 3계층 동기 검증 후 머지.

## 매트릭스 — 15-Factor
| # | 항목 | 상태 | 근거 / 갭 | 스트림 |
|---|---|:--:|---|:--:|
| 1 | Codebase/app | ✅ | monorepo 3계층(ADR-0019) | — |
| 2 | API first | ✅ | 버저닝·`X-API-Version`·OpenAPI export·타입생성·계약테스트(ADR-0060) | S4 |
| 3 | Dependency mgmt | ✅ | 핀 고정·pyproject·pre-commit | — |
| 4 | Build/release/run | ✅ | release 분리·버전 스탬프·DORA·컨테이너(ADR-0065) | S9 |
| 5 | Config/credentials | ✅ | APP_ENV·Settings·명시 우선(ADR-0056). 실 시크릿 매니저는 후속 | S0 |
| 6 | Logs | ✅ | settings 기반 구조화 로깅(JSON/평문, ADR-0057) | S1 |
| 7 | Disposability | ✅ | graceful shutdown 훅(ADR-0058) | S2 |
| 8 | Backing services | ✅ | DB·캐시·큐·세션 Port + Mock(ADR-0059). 실 어댑터는 후속 | S3 |
| 9 | Env parity | ✅ | APP_ENV 동형(BE/BFF/FE, ADR-0056) | S0 |
| 10 | Admin processes | 🟡 | 마이그레이션 러너(ADR-0059). admin 콘솔은 범위 외 | S3 |
| 11 | Port binding | ✅ | FastAPI/uvicorn 자기완결 | — |
| 12 | Stateless | ✅ | 세션 외부화 Port + Mock(ADR-0059). 실 Redis는 후속 | S3 |
| 13 | Concurrency | 🟡 | async·세마포어·KeyedLock. 분산 보류 | — |
| 14 | Telemetry | ✅ | request_id·지연 히스토그램·추적(ADR-0057) | S1 |
| 15 | Auth & authz | 🟡 | Principal·커밋게이트·DSR(0061). 실 SSO·RBAC 미정 | S7 |

## 매트릭스 — Well-Architected
| 기둥 | 상태 | 갭 | 스트림 |
|---|:--:|---|:--:|
| 운영 우수성 | ✅ | 관측성(0057)·릴리스/DORA(0065). 런북·온콜은 후속 | S9·S1 |
| 보안 | ✅ | 가드레일(0052·54)·레이트리밋·헤더·감사·스캔(0063). 실 암호화·시크릿 매니저 후속 | S7 |
| 신뢰성 | ✅ | 서킷브레이커·단계 타임아웃·graceful shutdown(ADR-0058). DR·백업은 후속 | S2 |
| 성능 효율 | 🟡 | async·스트리밍·응답 캐싱(0062). **부하·용량 계획**은 후속 | S6 |
| 비용 최적화 | ✅ | LLM 비용 회계·모델 라우팅·예산 가드(ADR-0062) | S6 |
| 지속가능성 | ⬜ | (범위 외) | — |

## 보강 렌즈
| 영역 | 표준 | 상태 | 스트림 |
|---|---|:--:|:--:|
| 보안 심화 | OWASP | ✅ (ASVS 전수 후속) | S7 |
| 딜리버리 | DORA | ✅ | S9 |
| 개인정보 | GDPR/개인정보보호법 | ✅ | S5 |
| 실험·롤아웃 | (런타임 A/B) | ✅ | S8 |

## 범위 외(의도적 ⬜, deferred)
SmartThings 엔터프라이즈 실 텔레메트리 · 삼성계정 SSO · 실 결제(PG) · 모바일/릴리스(OTA·앱스토어·푸시)
· 어드민 콘솔 · 지속가능성 기둥 → 사유는 [`docs/deferred.md`](deferred.md).
