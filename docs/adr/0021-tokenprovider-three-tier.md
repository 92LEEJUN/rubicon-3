# ADR-0021: SmartThings 인증 = TokenProvider 3계층 (PAT→OAuth→Enterprise)

- **상태**: 채택
- **관련**: `docs/architecture.md` §5, `docs/data-model.md` §6

## 배경
SmartThings 인증은 단계별로 다르다 — 검증 스파이크(PAT), MVP 실연동(OAuth), 조직(Enterprise). 인증 방식이 바뀔 때 `DevicePort` 어댑터까지 재작성하면 비용이 크다.

## 후보안
| 안 | 내용 | 장점 | 단점 |
|---|---|---|---|
| A | 인증을 어댑터에 **직접 하드코드**(PAT) | 빠름 | OAuth/Enterprise 전환 시 어댑터 재작성 |
| **B (선택)** | **`TokenProvider` 추상화** 뒤에 PAT/OAuth/Enterprise 구현 | 교체 지점이 "토큰 획득"으로 격리, 어댑터·ACL 불변 | 추상화 1겹 |

## 결정
**B.** 데이터·이벤트 스키마는 3계층 공통(기기/capability/attribute/command 동일) — **다른 건 인증·엔드포인트·이벤트 전달뿐.** 따라서 `TokenProvider`만 교체하고 `DevicePort`·ACL 매핑은 그대로. PAT(24h, 스파이크) → OAuth(MVP) → Enterprise(조직, 최대 1년).

## 기각 이유
- A: 인증이 바뀔 때마다 어댑터를 고쳐야 한다(스키마는 같은데 인증만 다른데도).

## 결과/영향
선제 이벤트(폴링→webhook, ADR-0036)도 같은 격리 원칙으로 도메인 매핑 불변. ADR-0020(Port 전략)의 구체 사례.
