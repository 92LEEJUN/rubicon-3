"""보안 심화 스트림(S7, ADR-0063) — 입력 검증 유틸 + 보안 감사 헬퍼.

에지 친화 검사(레이트리밋·보안 헤더)는 BFF가 소유한다(`bff/gateway/{ratelimit,security}.py`,
ADR-0052 계층 분담). 이 패키지는 **횡단 순수 유틸**(`validation`)과 **S5 AuditLog 재사용 헬퍼**
(`audit`)만 제공한다. 모두 옵트인·추가형(회귀 불변).
"""
from .audit import AUTH_FAILURE, COMMIT_GATE, RATELIMIT_BLOCK, security_audit  # noqa: F401
from .validation import (  # noqa: F401
    DEFAULT_MAX_BYTES,
    ValidationError,
    check_payload_size,
    whitelist_fields,
)
