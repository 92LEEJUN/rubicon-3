# 작업 (Tasks) — always-present companion

> `design.md`를 구현 단위로 나눈 체크리스트. 끝에 요구사항 번호 표기. 완료는 `[x]`.
> 토대(메모리 ADR-0040)는 선행 의존 — 컴팩션 구현이 먼저거나 병행.

## 0. 선행 (토대)
- [ ] 0.1 `ConversationMemory`(summary·facts·summarized_through) 영속화 + 컴팩션 트리거 _(ADR-0040)_
  - 요약 프롬프트·사실 추출 스키마·토큰 임계(~70%)/N턴 트리거
  - 손실 위험 항목(주문ID·기기모델·동의)은 facts로 보존

## 1. Resume (이어가기) _(요구 1·4·5)_
- [ ] 1.1 `ResumeService.resume(user_id)` — user 메모리 rehydrate + open-loop 조회 → `ResumePayload`
- [ ] 1.2 TTL 만료 후 영속 메모리 복원 경로(working 없음 → durable에서) _(요구 1.2)_
- [ ] 1.3 `elapsed` 상대 시간 산출·인사 반영 _(요구 5)_
- [ ] 1.4 '새로 시작' 분기(메모리 비주입) _(요구 1.3)_
- [ ] 1.5 패널 open(R9) 시 resume 템플릿 노출(FE)

## 2. OpenLoop (미해결 스레드) _(요구 2)_
- [ ] 2.1 `OpenLoop` 모델 + Repository(상태·우선순위·해소 시점)
- [ ] 2.2 생성 훅 — 진단 미해결·주문 진행·`suspended_flow` → open-loop
- [ ] 2.3 해소 훅 — R25 해결확인·주문 배송완료·사용자 dismiss → close _(요구 2.3)_
- [ ] 2.4 resume 시 열린 loop 우선순위 요약 제시 _(요구 2.2)_

## 3. ReEngagement (선제, 엄격 게이트) _(요구 3·6)_
- [ ] 3.1 트리거 — open-loop 후속(입고·R25 시점·리마인드) 이벤트/스케줄
- [ ] 3.2 **엄격 게이트** — Consent/opted_in → R26 빈도/중요도 → 가치/중복 억제 → R27 묶음 _(요구 3.2·3.3·6.1)_
- [ ] 3.3 통과분 AlertPort 전달(§10) + 탭 시 proactive→reactive 맥락 이어가기 _(요구 3.4)_
- [ ] 3.4 게이트 차단 결정적 테스트(동의 없음·빈도 초과·저가치·중복)

## 4. 교차기기 / 프라이버시 _(요구 4·6)_
- [ ] 4.1 메모리·open-loop **user 단위 키** + Consent 접근 가드 _(요구 4.2·6.1)_
- [ ] 4.2 삭제 요청 시 메모리·open-loop cascade _(요구 6.2, R19)_

## 5. 계측 / 검증
- [ ] 5.1 분석 이벤트 — resume·open-loop 제시/해소·선제 전달·탭(analytics.md 택소노미 정합)
- [ ] 5.2 통합 시나리오 — 진단 미완료 → 재방문 resume → 부품 입고 선제 → 탭 이어가기

## 진행 메모
- 구현 중 설계와 달라지면 `design.md`/관련 ADR 갱신. 선제 자세는 ADR-0042 준수(엄격 게이트).
