# 긴 질의·멀티턴 테스트셋 (정본)

> CapabilityOrchestrator(ADR-0046·0048)의 **라우팅·거동 정본 테스트셋**. 케이스ID ↔ 발화 ↔
> 기대 plan/거동 ↔ 검증 위치를 한곳에 모은다. 분석·결함 서사는 [test-findings.md](./test-findings.md),
> 결정은 [ADR-0048](../../docs/adr/0048-llm-planner-single-router.md).

## 읽는 법
- **규칙폴백 plan**: LLM 미연결(오프라인·테스트) 시 `RuleBasedClassifier` → `rule_plan`. **결정적** — pytest로 고정.
- **LLM 기대 plan**: 실 LLM(gpt-4o-mini) 단일 라우터(ADR-0048)의 기대 라우팅. **비결정적**(꼬리 변동) — 하니스로 확인, pytest는 stub 플래너로 병합만 고정.
- **검증 위치**: `harness`=수동 실행(출력), `pytest`=자동 단언.

## 검증 수단
| 수단 | 파일 | 성격 |
|---|---|---|
| harness(장문 멀티턴) | `backend/verify_multiturn_long.py` | 대화 A~D 결정적 출력 |
| harness(멀티턴 기본) | `backend/verify_multiturn.py` | Mock 시나리오 턴별 산출 |
| harness(실 LLM 라우팅) | `backend/verify_llm_planner.py` | 규칙 vs 실 LLM plan |
| harness(E2E 타이밍) | `backend/verify_e2e_timing.py` | 패리티 + 구간/총 시간 |
| pytest(라우팅·거동) | `backend/tests/test_capability.py` | 조언형/행동형·게이팅·carry·신규 capability |
| **pytest(장문 멀티턴)** | `backend/tests/test_multiturn_long.py` | **본 문서의 대화 A~D 회귀 단언** |

---

## 1. 단일턴 라벨 코퍼스 (`verify_llm_planner.py`)

| ID | 발화(요약) | 규칙폴백 plan | LLM 기대 plan | 핵심 거동 |
|---|---|---|---|---|
| clean-단일 | "세탁기에서 물이 안 빠져요" | `[diagnose]` | `[diagnose]` | guide_steps + 부품/handoff/booking CTA |
| J5-복합 | "세탁기 해결법 + 정수필터·헤파 주문" | `[diagnose, order]` | `[diagnose, order]` | guide_steps + 정수필터 product_card(handled) / 헤파 text(품절 unhandled) |
| A-T2 (F1) | "…새로 살까…배수필터 **확인해서 가격**" | `[device_status]`(빈 응답) | `[diagnose, explain]` | 규칙은 `확인해`로 device_status 트랩 → LLM이 진단+설명으로 교정 |
| B-T2 (F2) | "**보증**으로 무상 수리 + 기사 **예약**" | `[diagnose]` | `[warranty, booking]` | warranty(text) + booking(슬롯 초안). 규칙은 `수리`로 흡수 |
| C-T2 (F2) | "비스포크 큐브 **더 알려주고** + 상태 확인 + 헤파 주문" | `[device_status, order]` | `[device_status, diagnose, explain, order]` | explain 라우팅 + 명시 order 보존 |
| warranty-단독 | "이 냉장고 보증 되나요? 무상?" | `[general]` | `[warranty]` | coverage 기반 안내 |
| clarify-모호 | "이거 좀 어떻게 해줘" | `[general]` | `[clarify]` | 되묻기 + 보유 기기 빠른 선택지(select_device) |

> 과선택 억제(§9.4): 명시 요청 capability만 — 예) J5에 `recommend` 미추가. 실 LLM 5회 안정.

---

## 2. 장문 멀티턴 코퍼스 (`verify_multiturn_long.py`)

각 대화는 한 세션(session_id 고정)으로 흐른다. **규칙폴백 plan·섹션**은 결정적(pytest 단언 대상),
**LLM 기대**는 단일 라우터 기준.

### 대화 A — 세탁기 고장: 증상 서술 → 비용 고민 → 부품 주문
| 턴 | 발화(요약) | 규칙폴백 plan | LLM 기대 | 결정적 섹션/거동 |
|---|---|---|---|---|
| A-T1 | 장황한 증상 + 5C 에러 | `[diagnose]` | `[diagnose]` | `guide_steps`, required_parts=`[part_drain_filter]`, CTA order/handoff/booking |
| A-T2 | "…배수필터 확인해서 가격" | `[device_status]` | `[diagnose, explain]` | (규칙) device_status `text` **unhandled** = F1 결함 |
| A-T3 | "그 배수필터로 주문" | `[order]` | `[order]` | `product_card`, id=`part_drain_filter`, CTA order |

### 대화 B — 인덕션 안전 위험: 위험 서술 → 보증 → 기사 예약
| 턴 | 발화(요약) | 규칙폴백 plan | LLM 기대 | 결정적 섹션/거동 |
|---|---|---|---|---|
| B-T1 | "타는 냄새·탁탁 소리…무섭다" | `[diagnose]` | `[diagnose]` | `text` + **`cta_notice`(안전 경고)**, 부품 CTA **숨김**, CTA handoff/booking = F3 게이팅 |
| B-T2 | "보증 무상? 기사 예약?" | `[diagnose]` | `[warranty, booking]` | (규칙) `text` **unhandled**, CTA handoff = F2 결함 |

### 대화 C — 공기청정기: 추천 → 비교/상태/주문 복합
| 턴 | 발화(요약) | 규칙폴백 plan | LLM 기대 | 결정적 섹션/거동 |
|---|---|---|---|---|
| C-T1 | 이사·비염·예산 서술 + 추천 | `[recommend]` | `[recommend]` | `recommendation_list`(비스포크 큐브 포함), candidates 적재 |
| C-T2 | "더 알려주고 + 상태 확인 + 헤파 주문" | `[device_status, order]` | `[device_status, diagnose, explain, order]` | `device_status` + 헤파 `text`(품절 unhandled). (규칙) explain 증발 = F2 |

### 대화 D — 복합 폭탄: 진단+주문+추천+무관(날씨)
| 턴 | 발화(요약) | 규칙폴백 plan | LLM 기대 | 결정적 섹션/거동 |
|---|---|---|---|---|
| D | "세탁기 해결 + 정수필터·헤파 주문 + 거실 공청 추천 + 날씨" | `[diagnose, recommend, order]` | `[diagnose, recommend, order]` | guide_steps + recommendation_list + 정수필터 `product_card`(handled) + 헤파 `text`(unhandled). 날씨=범위 밖(F4) |

---

## 3. 결함 라벨 ↔ 케이스 (요약, 상세는 test-findings)
| 결함 | 케이스 | 상태 |
|---|---|---|
| F1 단어 오발화(문맥 무시) | A-T2 | LLM 단일 라우터로 교정(`[diagnose, explain]`) |
| F2 후속 의도 미분류 | B-T2·C-T2 | §9.3 목적지 capability(warranty/booking/explain)로 해소 |
| F3 안전 게이팅 데이터 의존 | B-T1 | `detect_danger` 메시지 표지로 보강(결정적, pytest) |
| F4 복합 누락의 침묵 | D(날씨)·C-T2 | 부분 — unhandled 명시 일부, 범위 밖 침묵은 잔존 |
| F5 carry vs 직접 해석 혼동 | A-T3 | 잔존(키워드 유무 의존) — carry 단위 테스트는 `test_capability` |

## 갱신 규칙
- 코퍼스 발화를 바꾸면 `verify_multiturn_long.py`(데이터)와 `test_multiturn_long.py`(단언)를 **함께** 갱신.
- LLM 기대 plan이 바뀌면 본 표 + test-findings "전면수정" 절을 갱신(실 LLM 재실행 근거 첨부).
