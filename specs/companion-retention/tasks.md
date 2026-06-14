# 작업 (Tasks) — 컴패니언·리텐션

> `design.md` 구현 체크리스트. **스펙 단계 — 구현은 사용자 확인 후 시작.**

- [ ] 1. ADR-0066 + 인덱스 _(요구사항 1~4)_
- [ ] 2. `OpenLoopStore`(기록·만료·닫기) + 테스트 _(요구사항 1)_
- [ ] 3. `ReengagementProposer`(트리거) + `ReengagementGate`(ADR-0042 빈도·중요도·동의) + 테스트 _(요구사항 2)_
- [ ] 4. `SatisfactionCollector`(CSAT/NPS 인라인, 미해결→재진단) + 신호 emit _(요구사항 3)_
- [ ] 5. Engagement 기록 연계 + `COMPANION` 토글 배선(off=미등록) _(요구사항 4)_
- [ ] 6. 검증 — `test_companion_retention.py` + 전 스위트 회귀 green·ruff

## 진행 메모
- 토글 `COMPANION` 기본 off. 채널(푸시) 비범위. 신호는 ADR-0067(자기개선) 입력으로.
