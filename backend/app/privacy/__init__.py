"""개인정보·DSR 스트림(S5, ADR-0061) — 동의 확장·DSR·보존·감사.

`router` 모듈이 import되면 `wiring.register_router`로 DSR 라우터가 등록된다(ADR-0056).
로드 진입점은 `platform/registry.py`의 import 한 줄(append).
"""
from .audit import AuditEvent, AuditLog  # noqa: F401
from .consent import KNOWN_SCOPES, ConsentStore  # noqa: F401
from .dsr import DSRService  # noqa: F401
from .retention import RETENTION_DAYS, RetentionPolicy  # noqa: F401
