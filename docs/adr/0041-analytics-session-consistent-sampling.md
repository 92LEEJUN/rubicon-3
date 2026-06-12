# ADR-0041: 분석 이벤트 = 세션 일관 샘플링

- **상태**: 채택
- **관련**: `docs/analytics.md` §8, `docs/data-model.md`(`AnalyticsEvent.sample_rate`)

## 배경
고빈도 저단가 이벤트(`screen_viewed`·`template_shown`·`cta_shown`·dwell)가 볼륨·비용의 대부분을 차지한다. 비용을 제어하되 **퍼널·전환 분석의 무결성**은 지켜야 한다.

## 후보안
| 안 | 내용 | 장점 | 단점 |
|---|---|---|---|
| **A (선택)** | **세션 일관 샘플링** — `hash(session_id) < rate`, 수집 세션은 전 이벤트 | **퍼널 무결성 보존**, 비용 선제 제어 | 희소 세그먼트 분산↑ |
| B | **이벤트별 랜덤 샘플링** | 단순 | `cta_clicked`는 남고 `order_confirmed` 누락 가능 → **퍼널 붕괴** |
| C | **정책만, 미적용** | 단순 | 고빈도 비용 노출 |

## 결정
**A — 지금 적용.** + 보강:
- **중요 이벤트 100%(allowlist)** — `order_confirmed`·`order_cancelled`·`error_shown`·`fallback_shown`·`flow_abandoned`·`handoff_started`·`resolution_confirmed`는 샘플링 무관 항상 전송.
- **드롭보다 클라 집계** — dwell 합산·impression 배치 카운트.
- **`sample_rate` 기록** → 분석 시 1/rate 재가중. MVP 기본 1.0(전수), 비용 문제 시 하향.

## 기각 이유
- B: 이벤트별 랜덤은 한 세션의 funnel 일부만 남겨 **전환·이탈 분석을 왜곡**한다.
- C: 메커니즘이 없으면 고빈도 급증 시 즉시 대응 불가 → 미리 심어둔다(기본 전수라 데이터 손실 없음).

## 결과/영향
중요 이벤트는 항상 100%라 전환/UX 건강(ADR-0037·0039) 분석은 영향 없음. 샘플 세션은 reweight로 모수 복원.
