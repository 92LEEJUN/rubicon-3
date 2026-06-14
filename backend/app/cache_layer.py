"""응답 캐시 래퍼 — S3 `CachePort` 재사용(ADR-0062, ADR-0059; 요구사항 4).

결정적 응답·플래너 결과를 캐시해 동일 입력의 중복 LLM 호출을 줄인다. **새 캐시 저장소를 만들지 않고**
`adapters/cache.py`의 `CachePort`(`backing.select_cache()`로 선택)를 재사용한다. `RESPONSE_CACHE` off
또는 백엔드가 `NoopCache`면 항상 `compute()`를 실행한다(캐시 미동작·회귀 불변).
"""
from __future__ import annotations

import hashlib
import json
import os
from typing import Any, Callable, Optional

from .adapters.cache import CachePort
from .repositories.backing import select_cache


def _response_cache_on() -> bool:
    return (os.environ.get("RESPONSE_CACHE") or "").strip().lower() in ("1", "true", "yes", "on")


def _normalize_messages(messages: Any) -> Any:
    """messages를 JSON 직렬화 가능한 결정적 형태로 정규화(dict는 키 정렬로 안정화)."""
    if isinstance(messages, list):
        return [_normalize_messages(m) for m in messages]
    if isinstance(messages, dict):
        return {k: _normalize_messages(messages[k]) for k in sorted(messages)}
    if isinstance(messages, str) or messages is None or isinstance(messages, (int, float, bool)):
        return messages
    # 알 수 없는 객체는 문자열화(best-effort 결정성)
    content = getattr(messages, "content", None)
    if content is not None:
        return {"content": _normalize_messages(content)}
    return str(messages)


def make_key(model: str, messages: Any, *, namespace: str = "resp") -> str:
    """모델+정규화 messages의 결정적 sha256 키. 동일 입력 → 동일 키."""
    payload = json.dumps(
        {"model": model, "messages": _normalize_messages(messages)},
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return f"{namespace}:{digest}"


class ResponseCache:
    """`CachePort` 위의 얇은 응답 캐시 래퍼 — get_or_compute + 무효화."""

    def __init__(self, cache: Optional[CachePort] = None, ttl: Optional[float] = None) -> None:
        # 미지정 시 ADR-0059 선택 팩토리(기본 NoopCache=항상 미스=회귀 불변). 새 저장소 생성 안 함.
        self._cache: CachePort = cache if cache is not None else select_cache()
        self._ttl = ttl

    def get_or_compute(
        self,
        model: str,
        messages: Any,
        compute: Callable[[], Any],
        *,
        namespace: str = "resp",
        ttl: Optional[float] = None,
    ) -> Any:
        """캐시 히트면 캐시 값, 미스면 `compute()` 결과를 저장 후 반환.

        `RESPONSE_CACHE` off면 캐시를 건드리지 않고 항상 `compute()`(회귀 불변).
        """
        if not _response_cache_on():
            return compute()
        key = make_key(model, messages, namespace=namespace)
        hit = self._cache.get(key)
        if hit is not None:
            return hit
        value = compute()
        if value is not None:
            self._cache.set(key, value, ttl=ttl if ttl is not None else self._ttl)
        return value

    def get(self, model: str, messages: Any, *, namespace: str = "resp") -> Optional[Any]:
        if not _response_cache_on():
            return None
        return self._cache.get(make_key(model, messages, namespace=namespace))

    def invalidate(self, key: str) -> None:
        """단일 키 무효화(완성된 캐시 키 문자열)."""
        self._cache.delete(key)

    def invalidate_for(self, model: str, messages: Any, *, namespace: str = "resp") -> None:
        """모델+messages로 키를 산출해 무효화."""
        self._cache.delete(make_key(model, messages, namespace=namespace))

    def clear(self) -> None:
        """전체 무효화."""
        self._cache.clear()
