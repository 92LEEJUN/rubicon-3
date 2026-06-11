"""BFF 설정 — BE 도메인 주소(실 전환 시 환경변수로 주입)."""
import os

BE_BASE_URL = os.getenv("BE_BASE_URL", "http://localhost:8001")
UPSTREAM_TIMEOUT = float(os.getenv("BFF_UPSTREAM_TIMEOUT", "10.0"))
