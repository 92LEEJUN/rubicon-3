"""BFF 설정 — 환경 계층(dev/stg/prd) 단일 소스(ADR-0056, 12-Factor III·X).

기존 상수(BE_BASE_URL·UPSTREAM_TIMEOUT)는 호환을 위해 유지하되, `APP_ENV`별 기본값과 명시 env
우선 규칙을 따른다(명시 env > 환경 기본값). 시크릿은 env로만.
"""
import os

ENVS = ("dev", "stg", "prd")

_DEFAULTS = {
    "dev": {"be_base_url": "http://localhost:8001", "timeout": 10.0, "log_json": False},
    "stg": {"be_base_url": "http://backend:8001", "timeout": 10.0, "log_json": True},
    "prd": {"be_base_url": "http://backend:8001", "timeout": 8.0, "log_json": True},
}


def resolve_env() -> str:
    e = (os.getenv("APP_ENV") or "dev").strip().lower()
    return e if e in ENVS else "dev"


APP_ENV = resolve_env()
_d = _DEFAULTS[APP_ENV]

# 명시 env가 있으면 항상 우선, 없으면 환경 기본값.
BE_BASE_URL = os.getenv("BE_BASE_URL", _d["be_base_url"])
UPSTREAM_TIMEOUT = float(os.getenv("BFF_UPSTREAM_TIMEOUT", str(_d["timeout"])))
LOG_JSON = (os.getenv("LOG_JSON", "").strip().lower() in ("1", "true", "yes", "on")) or _d["log_json"]
IS_PROD = APP_ENV == "prd"
