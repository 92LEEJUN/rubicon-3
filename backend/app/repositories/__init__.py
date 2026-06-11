"""Repository — 내부 데이터(외부 Port 아님). MVP=인메모리, 실 전환 시 Postgres/Redis.

Engagement(확인 정보, R29)는 앱 동작을 바꾸는 조회 가능한 내부 상태 — Analytics(fire-and-forget)와 구분.
"""
from .memory import InMemoryEngagementRepository  # noqa: F401
