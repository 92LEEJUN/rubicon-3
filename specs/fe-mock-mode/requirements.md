# 요구사항 (Requirements) — FE 단독 동작 Mock 모드

## 개요
BE/BFF 없이도 FE(GitHub Pages 정적 배포)가 **모든 화면·채팅·커밋이 동작**하도록 풍부한 mock
데이터와 결정적 mock 응답 계층을 둔다. mock 동작은 **아키텍처 문서**(`docs/backend-architecture.md`·
`docs/frontend-architecture.md`)가 기술한 라우팅·게이팅·템플릿·커밋 계약을 **미러**한다. 실연동
(apiBase/wsUrl 설정) 경로는 그대로 두고, mock은 폴백/명시 모드에서만 동작한다(회귀 불변).

> 결정(사용자): 채팅 mock = **시나리오 재생 + 자유입력 키워드 라우터 폴백**, 상태 = **localStorage 영속**,
> 신원 = **로그인 사용자 기준**(게스트/로그인 월 mock은 범위 외; 실연동 시엔 BE가 처리).

## 요구사항 목록

### 요구사항 1: BE 없이 모든 화면이 채워진다
**User Story:** 데모 사용자로서, BE 연결 없이도 홈·고객지원·채팅·갤러리·시나리오 화면이 의미 있는
데이터로 채워지길 원한다, 그래서 정적 배포만으로 제품을 체험할 수 있다.

**수용기준:**
1. WHEN apiBase가 없을 때 THEN 시스템은 홈(기기·알림·추천)·이력(주문·예약)을 **풍부한 fixtures**로 채워야 한다 (SHALL).
2. WHEN 화면 조회가 실패하거나 비어 있을 때 THEN 시스템은 빈 화면 대신 mock 데이터를 보여야 한다 (SHALL).

### 요구사항 2: Mock 모드 감지·표시
**User Story:** 사용자로서, 지금이 데모(mock) 모드인지 알고 싶다, 그래서 실제 동작과 혼동하지 않는다.

**수용기준:**
1. WHEN apiBase·wsUrl이 모두 없거나 `?mock=1`일 때 THEN 시스템은 **mock 모드**로 동작해야 한다 (SHALL).
2. WHEN mock 모드일 때 THEN 시스템은 작은 "데모 모드" 표시를 노출해야 한다 (SHALL).
3. WHEN apiBase·wsUrl이 설정됐을 때 THEN 시스템은 **실연동 경로**를 쓰고 mock은 네트워크 실패 시에만 폴백해야 한다 (SHALL, 회귀 불변).

### 요구사항 3: 인터랙티브 채팅 (시나리오 + 키워드 라우터)
**User Story:** 사용자로서, mock 모드에서도 자유롭게 입력하면 그럴듯한 응답을 받고 싶다, 그래서
대화 흐름을 끝까지 체험할 수 있다.

**수용기준:**
1. WHEN 정의된 시나리오 트리거(예: J1 5C·정수필터·HEPA·예약·복합)를 입력하면 THEN 시스템은 해당 **스크립트 저니**를 재생해야 한다 (SHALL).
2. WHEN 그 외 자유 입력이면 THEN 시스템은 **키워드 라우터**로 BE capability 출력을 미러해야 한다 — 진단(guide_steps+안전 게이팅)·추천·주문(품절 unhandled)·보증·예약(슬롯)·설명·clarify(되묻기) (SHALL).
3. WHEN 응답을 낼 때 THEN 시스템은 **§2.1 봉투**(section*→flow→done) 청크로 스트리밍해야 한다 (SHALL).
4. WHEN 위험 발화·보증 무상·품절 등일 때 THEN 시스템은 문서의 **게이팅 규칙**(부품 CTA 숨김+안내, unhandled 표기)을 따라야 한다 (SHALL).

### 요구사항 4: 커밋이 상태에 반영된다
**User Story:** 사용자로서, mock에서 주문·예약을 확정하면 이력·홈에 반영되길 원한다, 그래서 흐름이
끊기지 않는다.

**수용기준:**
1. WHEN 주문/예약 commit CTA를 확정(409→confirmed)하면 THEN 시스템은 **mock 스토어**에 기록해야 한다 (SHALL).
2. WHEN 이후 이력(주문·예약)·홈을 조회하면 THEN 방금 커밋한 항목이 나타나야 한다 (SHALL).
3. 커밋 왕복(409 ConfirmationRequired→확정)은 실연동과 동일한 표현을 보여야 한다 (SHALL).

### 요구사항 5: 상태 영속(localStorage)
**User Story:** 사용자로서, 새로고침·재방문해도 내가 만든 주문·예약·대화가 유지되길 원한다.

**수용기준:**
1. WHEN mock 상태가 바뀌면 THEN 시스템은 **localStorage**에 영속해야 한다 (SHALL).
2. WHEN 재방문하면 THEN 시스템은 영속 상태를 복원해야 한다 (SHALL).
3. 시스템은 **리셋 수단**(데모 초기화)을 제공해야 한다 (SHALL).

### 요구사항 6: 풍부한 데이터셋
**User Story:** 데모 사용자로서, 화면이 비어 보이지 않게 충분한 데이터를 원한다.

**수용기준:**
1. 시스템은 **다중 기기·제품/부품 카탈로그·해결책·주문/예약 이력·추천·재참여·open-loop·대화 기억**의 fixtures를 갖춰야 한다 (SHALL).
2. fixtures는 문서의 템플릿/스키마(`docs/response-templates.md`·`contract.ts`)와 정합해야 한다 (SHALL).

### 요구사항 7: 문서 정합·회귀 불변
**User Story:** 유지보수자로서, mock 동작이 문서와 어긋나거나 실연동을 깨지 않길 원한다.

**수용기준:**
1. mock 라우팅·게이팅·템플릿은 `docs/backend-architecture.md`·`docs/frontend-architecture.md`와 일치해야 한다 (SHALL).
2. apiBase/wsUrl 설정 시 기존 실연동·테스트(jest)가 그대로 통과해야 한다 (SHALL).
3. mock 계층은 **클라이언트 전용**이며 BE 계약(엔드포인트·봉투·CTA kind)을 바꾸지 않는다 (SHALL).
