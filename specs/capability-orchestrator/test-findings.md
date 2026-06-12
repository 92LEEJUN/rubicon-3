# 장문 멀티턴 검증 결과 (Test Findings)

> `backend/verify_multiturn_long.py` — 3~4줄 장문 발화로 `CapabilityOrchestrator`(결정적 경로)를
> 구동한 실측. 한 문장 검증(`verify_multiturn.py`)이 놓친 **규칙 분류기의 한계**를 드러낸다.
> 결론: 장문은 LLM 플래너(tasks §9)가 필요하다 — 키워드 규칙은 문맥을 못 읽는다.

## 버틴 것 (장문에서도 정상)
- **A-T1 진단**: 장황한 증상 서술에서 `troubleshoot` 단일 분류 → guide_steps + 게이팅 CTA. ✅
- **C-T1 추천**: 이사·비염·예산 등 잡소리 많아도 `recommend` 단일 분류 → recommendation_list. ✅
- **D 복합 폭탄**: "진단+주문+추천"이 한 발화에 → `[diagnose, recommend, order]` fan-out, 정수필터(product_card)·헤파(품절 unhandled) 구분. ✅
- **크로스턴 carry / 세션 격리**: 단위 테스트로 보장(`test_capability.py`).

## 깨진 것 (장문이 드러낸 결함)

### F1. 단어 오발화 — 문맥 무시 (높음)
- **A-T2**: "비용 많이 들면 새로 살까… 배수 필터 가격이랑 같이 **확인해서** 알려주세요" →
  `확인해` 한 단어 때문에 `device_status`로 분류 → 기기 못 찾아 text/unhandled. **사용자는 부품 가격을 물었는데 아무것도 못 받음.**
- 원인: `_STATUS=("상태","어때","확인해"…)`, `_RECOMMEND=("바꿀"…)` 등 키워드가 문맥과 무관히 의도를 깨움.
- 처방: LLM 플래너(§9). 규칙으로는 whack-a-mole.

### F2. 후속 의도 미분류 — explain·warranty·booking 부재 (높음)
- **C-T2**: "비스포크 큐브 **더 알려주고**(explain) + 상태 확인 + 헤파 주문" → explain/비교 의도가 사라지고 device_status+order로만. 추천 후속 질문이 증발.
- **B-T2**: "**보증**으로 무상 수리 되나요 + 기사님 **예약** 가능?" → `수리` 키워드로 troubleshoot에 흡수, 보증조회·예약 의도 누락.
- 처방: `explain`/`warranty`/`booking` 의도 + capability 추가, 또는 LLM 플래너.

### F3. 안전 게이팅이 해결책 데이터에 의존 (높음) — **이번에 보강함**
- **B-T1**(수정 전): 인덕션 "타는 냄새·탁탁 소리"는 fixtures에 해결책이 없어 `risk_level` 판정 자체가 안 됨 → 위험 발화에 **경고 0**, handoff CTA만.
- **보강**: 메시지 레벨 위험 표지 감지(`detect_danger`: 타는 냄새·가스·감전·스파크·연기…)를 추가. 해결책이 없어도 위험 발화면 **안전 경고 + 부품 CTA 숨김 + 상담원/기사 CTA**로 응답.
- **B-T1**(수정 후): ✅ `cta_notice`(안전 경고) + handoff·booking. 단위 테스트 `test_diagnose_message_danger_without_solution`.
- 남은 한계: 키워드 기반이라 표지 없는 위험(예: 우회 표현)은 못 잡음 → LLM 플래너 보완 필요.

### F4. 복합 누락의 침묵 — unhandled 미표기 (중간)
- **D**: "주말 **날씨**" 같은 범위 밖/미처리 의도가 unhandled 섹션 없이 그냥 사라짐 → R7(handled/unhandled 명시) 위반.
- **C-T2**: 못 잡은 explain 의도도 흔적 없음.
- 처방: 분류된 의도 vs 처리된 섹션 차집합을 unhandled 섹션으로 명시.

### F5. carry vs 직접 해석 혼동 (낮음)
- **A-T3**: "배수필터 주문" — 문구에 `배수`가 있어 직접 해석으로 동작(carry 아님). 우연히 맞음.
  문구가 "아까 그거"였다면 carry 경로. 둘의 경계가 키워드 유무에 달려 불안정.

## 결론 / 우선순위
- **즉시 처방(데이터·규칙 독립, 안전 직결)**: F3 → **완료**(detect_danger).
- **LLM 플래너로 해소(tasks §9)**: F1·F2 — 장문 문맥·후속 의도. 규칙 분류기의 구조적 한계.
- **결정적으로 보강 가능(후속)**: F4(unhandled 차집합 명시), F5(carry 우선순위 명확화).
- 이 결과가 **LLM 플래너가 "있으면 좋은" 게 아니라 장문 UX에 필수**임을 실측으로 입증한다.
