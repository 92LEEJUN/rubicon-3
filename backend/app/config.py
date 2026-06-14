"""중앙 설정 — 환경 계층(dev/stg/prd) 단일 소스(ADR-0056, 12-Factor III·X).

목적: 환경별 동작·구성을 **한 곳**에서 결정해 "환경 parity"를 확보한다. 기존 `os.getenv`
사용처는 그대로 둔다(스트랭글러·회귀 불변) — 본 모듈은 **추가형**으로, 신규 코드와 환경별
기본값이 필요한 곳이 `get_settings()`를 통해 일관되게 읽는다.

규칙:
- `APP_ENV` ∈ {dev, stg, prd} (미지정·오타 → dev). 환경별 **기본값**을 제공한다.
- 명시 env 변수가 있으면 **항상 우선**(precedence: 명시 env > 환경 기본값). 시크릿은 코드/저장소에
  두지 않고 env로만(`OPENAI_API_KEY` 등) — 본 모듈은 시크릿 값을 보관하지 않는다.
- 결정적·테스트 가능: `get_settings()`는 캐시되며, 테스트는 `reload_settings()`로 갱신한다.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache

ENVS = ("dev", "stg", "prd")

# 환경별 기본값(명시 env 변수가 없을 때만 적용). 운영(prd/stg)은 JSON 로그·INFO, 개발은 디버그.
_DEFAULTS: dict[str, dict] = {
    "dev": {"log_level": "DEBUG", "log_json": False, "metrics": True, "debug": True},
    "stg": {"log_level": "INFO", "log_json": True, "metrics": True, "debug": False},
    "prd": {"log_level": "INFO", "log_json": True, "metrics": True, "debug": False},
}


def _flag(name: str, default: bool) -> bool:
    v = os.getenv(name)
    if v is None:
        return default
    return v.strip().lower() in ("1", "true", "yes", "on")


def resolve_env() -> str:
    """APP_ENV 정규화 — 미지정·미지값이면 dev(안전 기본)."""
    e = (os.getenv("APP_ENV") or "dev").strip().lower()
    return e if e in ENVS else "dev"


@dataclass(frozen=True)
class Settings:
    """환경별 해석된 설정(불변). 명시 env > 환경 기본값."""

    app_env: str
    log_level: str
    log_json: bool
    metrics_enabled: bool
    debug: bool

    @property
    def is_prod(self) -> bool:
        return self.app_env == "prd"

    @property
    def is_dev(self) -> bool:
        return self.app_env == "dev"


def _build() -> Settings:
    env = resolve_env()
    d = _DEFAULTS[env]
    return Settings(
        app_env=env,
        log_level=os.getenv("LOG_LEVEL", d["log_level"]).upper(),
        log_json=_flag("LOG_JSON", d["log_json"]),
        metrics_enabled=_flag("METRICS_ENABLED", d["metrics"]),
        debug=_flag("DEBUG", d["debug"]),
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """프로세스 단일 설정(캐시). 환경 변수 변경 후에는 reload_settings()로 갱신한다."""
    return _build()


def reload_settings() -> Settings:
    """캐시를 비우고 현재 env로 재해석(테스트·환경 전환용)."""
    get_settings.cache_clear()
    return get_settings()
