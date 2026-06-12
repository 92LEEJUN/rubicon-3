# 작업 (Tasks) — product-recommendation (선제적 제품 추천)

> `design.md`를 구현 단위로 나눈 체크리스트. 각 항목 끝에 관련 요구사항 번호를 표기한다.
> 완료한 항목은 `[x]`로 체크한다. 토대(컴패니언 메모리/게이트·Engagement·CatalogPort)는 선행 의존이다.

## 작업 목록

### 0. 선행 확인 (토대 점검 — 신규 구현 아님)
- [ ] 0.1 `CatalogService.recommend`·`EngagementRepository`(has_seen·dismissed·interests) 현황 점검 _(요구 3·8)_
  - `backend/app/services/services.py` 기준선 확인. 추천 코어가 확장할 지점 식별.
- [ ] 0.2 컴패니언 `ReEngagementService` 게이트(ADR-0042) 재사용 가능 형태 확인 _(요구 2·7-4)_
  - `specs/always-present-companion/` 게이트 인터페이스에 추천 후보를 트리거로 넣을 접점 확인.
- [ ] 0.3 `operations.md` §4 개인화 컨텍스트 조립 규칙 확인(동의·토큰 예산·최소화) _(요구 3·4)_

### 1. 추천 코어 (RecommendationService) _(요구 3·4·5·8)_
- [ ] 1.1 `RecommendationService.recommend(ctx)` 골격 — 후보→랭킹→제외→근거 파이프라인 _(요구 3)_
- [ ] 1.2 보유 기기/제품 **중복 제외** + 보완·대안 우선 _(요구 3-1)_
- [ ] 1.3 Engagement `viewed/dismissed` **중복 제외**, `interests` 관심 반영 랭킹 _(요구 3-2·3-3)_
- [ ] 1.4 `PersonalizationContext` 어셈블러 — operations §4 컨텍스트를 동의 범위 안에서 조립 _(요구 3·4)_
- [ ] 1.5 후보 조회는 `CatalogPort`만 경유(랭킹·제외는 서비스에 유지) _(요구 8-1·8-3)_

### 2. 동의 게이트 · 폴백 _(요구 4)_
- [ ] 2.1 `personalization` 없으면 **일반 추천 폴백** _(요구 4-1)_
- [ ] 2.2 폴백 시 "개인화 제한" **고지** 표기 _(요구 4-2)_
- [ ] 2.3 `device_data`만 있으면 보유 제외까지만, 이력 개인화 제외(scope별 차등) _(요구 4-3)_
- [ ] 2.4 동의 철회 시 개인화·선제 **즉시 중단** _(요구 4-4, R19)_

### 3. 선제 트리거 + 게이트 정합 _(요구 1·2)_
- [ ] 3.1 `RecommendationTrigger.evaluate(user)` — 소모품 수명(`consumable_alerts` 재사용) _(요구 1-1)_
- [ ] 3.2 구매/교체 주기 추정(주문 이력) + 관심 이력 트리거 _(요구 1-2)_
- [ ] 3.3 트리거 근거(`TriggerKind`·reason_seed) 기록, 무신호면 미생성 _(요구 1-3·1-4)_
- [ ] 3.4 선제 후보를 **컴패니언 게이트(ADR-0042)** 에 통과 — `Consent/opted_in → R26 빈도 → 가치/중복 → R27 묶음` _(요구 2-1·2-2·2-3)_
- [ ] 3.5 다수 후보 묶음/상위 제한(R27) — 알림 피로 방지 _(요구 2-4)_
- [ ] 3.6 통과분만 `AlertPort`(§10) 전달 — 별도 선제 인프라 신설 금지 _(요구 2·7-4)_

### 4. 추천 근거 + 표현/CTA _(요구 5)_
- [ ] 4.1 항목별 **근거 reason** 생성(트리거·개인화 신호 기반, 무근거 금지) _(요구 5-1, llm-policy §4)_
- [ ] 4.2 `recommendation_list`(reason 포함)·`product_comparison`(비교) 매핑 _(요구 5)_
- [ ] 4.3 항목별 CTA(`add_to_cart`·`reorder`) + 대화형 CTA("왜 추천?"·"비교/대안") _(요구 5-2)_
- [ ] 4.4 대화형 CTA → `/chat` 재진입 + 추천 맥락 주입(FlowState 이어가기) _(요구 5-2, proactive→reactive)_
- [ ] 4.5 선제 카드 탭 — `bridge`(`card_type: recommendation`) / 패널 동적 분기 _(요구 5-3, response-templates §9)_

### 5. 컴패니언 메모리 / open-loop 연계 _(요구 7)_
- [ ] 5.1 추천 보류(나중에·관심) → `OpenLoop`(kind: flow) 추적 _(요구 7-1)_
- [ ] 5.2 resume 우선순위 요약에 보류 추천 포함 _(요구 7-2)_
- [ ] 5.3 추천 해소(주문·dismiss·만료) 시 open-loop 닫기 _(요구 7-3)_
- [ ] 5.4 `ConversationMemory`(facts·summary) 관심/미해결 신호를 추천 컨텍스트로 활용 _(요구 7-4)_

### 6. 전환 기여 / 분석 _(요구 6)_
- [ ] 6.1 추천 노출~주문 `correlation_id` 전파(`template_shown`→`cta_clicked`→`cart_item_added`→`order_confirmed`) _(요구 6-1)_
- [ ] 6.2 선제 전달 이벤트(`notification_delivered`·`notification_opened`·`notification_dismissed`) _(요구 6)_
- [ ] 6.3 `analytics` 동의 게이트 + 가명화 _(요구 6-2)_
- [ ] 6.4 신규 추천 이벤트 필요 시 `docs/analytics.md` 갱신 후 추가(추가-only) _(요구 6-3)_

### 7. 카탈로그 Mock↔실 경계 _(요구 8)_
- [ ] 7.1 `CatalogPort` 추천/조회 계약 테스트(Mock↔실 교체 시 추천 로직 불변) _(요구 8-1)_
- [ ] 7.2 빈/부분/실패(`PortError`) → 일반 추천·안내 폴백 _(요구 8-2)_
- [ ] 7.3 demand-driven 경계 준수(카드·대화로만 노출, 브라우즈 없음) _(요구 8-3)_

### 8. 캐시 / 정합
- [ ] 8.1 추천 캐시 키(`user·interest`·consent) + **Engagement 변경 시 무효화** _(요구 3-3, operations §2)_
- [ ] 8.2 개인화 응답 사용자 경계 밖 캐시 금지 검증 _(operations §2)_

### 9. 검증 / 통합 시나리오
- [ ] 9.1 동의 차등 결정적 테스트(personalization 유/무, device_data만, 철회) _(요구 4)_
- [ ] 9.2 선제 게이트 차단 테스트(opt-out·빈도·저가치·중복) _(요구 2)_
- [ ] 9.3 통합 시나리오 — 소모품 수명 임박 → 선제 추천(게이트 통과) → 탭 → /chat 비교 → 장바구니 → 주문(기여 추적) _(요구 1·2·5·6)_
- [ ] 9.4 통합 시나리오 — 추천 보류 → open-loop → 재방문 resume → 주문 후 닫힘 _(요구 7)_

## 진행 메모 (구현)
**구현됨** — `backend/app/recommendation.py`(`RecommendationService` 추천 코어: 보유/seen 제외·동의 차등·근거 / `triggers` 소모품·관심 / `enqueue_preemptive`→컴패니언 open-loop) + `companion.track_loop`(공개 생성) + container 배선 + `GET /internal/recommendations`·`POST /internal/recommendations/preemptive` + BFF `/recommendations` + `tests/test_recommendation.py`(7종). **백엔드 142·BFF 37 통과.**

핵심: **새 영속 엔티티 0**(Product·Engagement·OpenLoop 조합), 선제는 **컴패니언 ReEngagement 게이트 재사용**(ADR-0042, 신규 선제 인프라 없음). 동의 차등(personalization/device_data scope별)·보유 제외·중복 억제 결정적 테스트.

**남은(부분/후속)**:
- 5 반응형 표현(recommendation_list/product_comparison 템플릿 직렬화)·대화형 CTA 재진입·bridge 분기는 표현 레이어(FE/오케스트레이터) 연결 후속
- 6 전환 기여(correlation_id 추적)·analytics 이벤트 배선 후속
- 9.3·9.4 통합 시나리오, 선제 전달 스케줄/이벤트 합류(이벤트 vs 스케줄)는 신규 ADR 후보

<!-- 변경 시 docs/도 함께 갱신(CLAUDE.md 규칙). -->
- 데이터 모델·공개 인터페이스·아키텍처가 실제로 바뀌면 스펙이 아니라 `docs/`(data-model·operations·analytics 등)를 갱신하고 여기서 참조한다(CLAUDE.md 규칙).
- 선제 추천 트리거를 컴패니언 `ReEngagementService`에 합류시키는 방식(이벤트 vs 스케줄) 확정 시 신규 ADR 후보.
