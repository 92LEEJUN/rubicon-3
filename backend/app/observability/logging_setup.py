"""구조화 로깅 — `config.get_settings()`의 log_level/log_json을 따른다(S1 관측성, ADR-0056).

- stdlib `logging`만 사용(새 의존성 없음).
- `log_json=True`면 JSON 한 줄 포맷, False면 사람이 읽는 평문 포맷.
- 레벨은 `settings.log_level`(DEBUG/INFO/...)을 따른다.
- 모든 로그 레코드에 현재 컨텍스트의 `request_id`(있으면)를 자동 부착(상관관계).
- `extra={"ctx_<key>": ...}`로 넘긴 키는 `<key>`로 평탄화되어 출력된다(기존 컨벤션 유지).

기존 동작 호환: 환경 기본(dev)은 log_json=False라 이전(JSON 강제)과 표현은 달라지지만
같은 `rubicon` 로거·`ctx_` 평탄화 규칙·propagate=False를 유지한다. 토글로 JSON 복원 가능.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from ..config import Settings, get_settings
from .request_context import get_request_id

_LOGGER_NAME = "rubicon"


def _base_payload(record: logging.LogRecord) -> dict[str, Any]:
    """레코드 → 공통 필드 dict(포맷터 공유). request_id·ctx_* 평탄화 포함."""
    payload: dict[str, Any] = {
        "level": record.levelname,
        "logger": record.name,
        "msg": record.getMessage(),
    }
    rid = get_request_id()
    if rid is not None:
        payload["request_id"] = rid
    for key, val in getattr(record, "__dict__", {}).items():
        if key.startswith("ctx_"):
            payload[key[4:]] = val
    return payload


class JsonLineFormatter(logging.Formatter):
    """로그 레코드를 JSON 한 줄로 직렬화(stdlib only)."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {"ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z")}
        payload.update(_base_payload(record))
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


class PlainFormatter(logging.Formatter):
    """사람이 읽는 평문 한 줄(dev 기본). request_id가 있으면 함께 출력."""

    def format(self, record: logging.LogRecord) -> str:
        p = _base_payload(record)
        ts = self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z")
        rid = p.get("request_id")
        prefix = f"{ts} {p['level']} {p['logger']}"
        if rid:
            prefix += f" [{rid}]"
        line = f"{prefix} {p['msg']}"
        extras = {k: v for k, v in p.items()
                  if k not in ("level", "logger", "msg", "request_id")}
        if extras:
            line += " " + " ".join(f"{k}={v}" for k, v in extras.items())
        if record.exc_info:
            line += "\n" + self.formatException(record.exc_info)
        return line


# 모든 핸들러에서 우리 포맷터인지 식별하기 위한 공통 베이스(설치 멱등성 판별).
_OUR_FORMATTERS = (JsonLineFormatter, PlainFormatter)


def configure_logging(settings: Settings | None = None) -> logging.Logger:
    """`rubicon` 로거를 settings에 맞게 (재)구성. 멱등 — 우리 핸들러는 1개만 유지.

    - log_json에 따라 JSON/평문 포맷터 선택.
    - log_level을 적용.
    - propagate=False(루트 중복 전파/print·uvicorn 로그 혼입 방지) 유지.
    """
    s = settings or get_settings()
    logger = logging.getLogger(_LOGGER_NAME)

    # 기존에 우리가 붙인 핸들러는 제거하고 재부착(설정 전환 시 중복/이전 포맷 잔존 방지).
    for h in list(logger.handlers):
        if isinstance(h.formatter, _OUR_FORMATTERS):
            logger.removeHandler(h)

    handler = logging.StreamHandler()
    handler.setFormatter(JsonLineFormatter() if s.log_json else PlainFormatter())
    logger.addHandler(handler)
    logger.setLevel(getattr(logging, s.log_level, logging.INFO))
    logger.propagate = False
    return logger


# 모듈 로드 시 1회 구성(기존 `log` 심볼 호환 — install/__init__이 재노출).
log = configure_logging()
