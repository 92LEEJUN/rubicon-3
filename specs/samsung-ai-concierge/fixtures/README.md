# 더미데이터 (Fixtures)

`docs/data-model.md` 타입에 맞춘 **카테고리별 일부** 더미데이터. full journey 검증용이며
`Mock*` 어댑터(`data-model.md` §8)와 계약 Stub 서버(`api-contract.md` §5)가 그대로 반환·재생한다.

| 파일 | 내용 | 매핑 타입 |
|------|------|-----------|
| `user.json` | 사용자·동의·선호·주소 | `User`·`Consent`·`UserPreferences`·`Address` |
| `devices.json` | 연동 기기·소모품·지표 (SmartThings) | `Device`·`Consumable` |
| `anomalies.json` | 이상(오류코드·소모품) | `Anomaly` |
| `solutions.json` | 해결 가이드·근거·필요부품 (CS) | `Solution`·`SolutionStep`·`Source` |
| `catalog.json` | 부품·완제품 (제품정보) | `Part`·`Product` |

**카테고리**: 세탁기(`dev_washer_01`)·냉장고(`dev_fridge_01`)·공기청정기(`dev_purifier_01`).
**시나리오**: 이 데이터를 쓰는 풀 저니 4종은 [`../journeys.md`](../journeys.md).

> 더미는 "전수"가 아니라 **각 카테고리 일부**다(실데이터 일부 티어, `architecture.md` §5).
> 실 전환 시 Real 어댑터가 SmartThings/CS/제품 소스로 교체한다(인터페이스 불변).
