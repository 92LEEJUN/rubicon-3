# 작업 (Tasks) — 컴패니언·리텐션

> `design.md` 구현 체크리스트. **스펙 단계 — 구현은 사용자 확인 후 시작.**

- [x] 1. ADR-0066 + 인덱스 _(요구사항 1~4)_
- [x] 2. open-loop 기록·해소·닫기 — **기존 `always-present-companion`에 이미 구현**(`app/companion.py`·`open_loop.py`). 재사용 _(요구사항 1)_
- [x] 3. 재관여 제안 + 엄격 게이트 — **기존 `app/reengagement.py`**(동의·cooldown·중복·묶음, ADR-0042). 재사용 _(요구사항 2)_
- [x] 4. `SatisfactionService`(CSAT/NPS 인라인, 미해결→`next_action=rediagnose`) + 신호 emit (`app/satisfaction.py`) _(요구사항 3)_
- [x] 5. Engagement 기록(`sat:<topic>`) 연계 + `POST /internal/satisfaction` + 컨테이너 배선 _(요구사항 4)_
- [x] 6. 검증 — `tests/test_satisfaction.py`(7) + 전 스위트 회귀 green·ruff

## 진행 메모
- open-loop·재관여는 **이미 구현(재사용)** — 본 라운드 신규는 **만족도 수집**과 **자기개선 신호 연결**.
- 채널(푸시) 비범위. **추가형** — 만족도는 신규 엔드포인트·스토어로 기존 경로 불변(별도 글로벌 토글 불필요).
- 신호 emit은 ADR-0067 입력 — `SELF_IMPROVE` off면 sink no-op(회귀 불변). 동의 scope 없으면 신호 드롭(R28).
