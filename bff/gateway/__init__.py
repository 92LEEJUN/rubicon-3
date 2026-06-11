"""BFF (Backend-for-Frontend) — 클라이언트 표면 서비스(architecture.md §9).

FE↔BFF 계약(api-contract §2)을 소유하고, BE 도메인 내부 API(§2.4)를 중계·정형화한다.
비즈니스 로직은 없다(aggregation·Template 변환·인증 게이트·스트리밍 중계만).
"""
