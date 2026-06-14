"""LLM 클라이언트 — provider-agnostic 경계(현재 OpenAI 소형 모델).

모델: 기본 gpt-4o-mini (소형·저비용, function calling + 구조화 출력 지원).
환경변수 LLM_MODEL 로 교체 가능. 키는 OPENAI_API_KEY 환경변수에서만 읽는다(코드/저장소에 두지 않음).
"""
import os
import asyncio
import random
import threading
import time
from pathlib import Path

try:  # backend/.env 자동 로드(있으면). 키는 .env(gitignore) 또는 환경변수로만.
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
except ModuleNotFoundError:
    pass

MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")

# Phase A — LLM 호출 동시성 상한(세마포어). 멀티에이전트는 턴당 호출이 누적되므로 워커당 상한을 둔다.
_MAX_CONCURRENCY = int(os.getenv("LLM_MAX_CONCURRENCY", "4"))
_SEM = threading.BoundedSemaphore(_MAX_CONCURRENCY)
_RETRY_DELAYS = (0.5, 1.0, 2.0, 4.0)  # 지수 백오프(+지터)

_client = None
_async_client = None
_async_sem = None


def get_client():
    """OpenAI 클라이언트 지연 생성 — 키 없이도 모듈 import는 가능(테스트·오프라인).

    실제 LLM 호출(legacy CLI·OpenAIClassifier) 시점에만 OPENAI_API_KEY가 필요하다.
    """
    global _client
    if _client is None:
        from openai import OpenAI
        _client = OpenAI()  # OPENAI_API_KEY 환경변수 사용
    return _client


def get_async_client():
    """AsyncOpenAI 클라이언트 지연 생성 — 비동기 서빙 경로(이벤트 루프 비차단)용."""
    global _async_client
    if _async_client is None:
        from openai import AsyncOpenAI
        _async_client = AsyncOpenAI()
    return _async_client


def _transient_errors():
    """일시적(재시도 대상) 오류 튜플 — 429/타임아웃/연결/5xx."""
    try:
        from openai import APIConnectionError, APITimeoutError, InternalServerError, RateLimitError
        return (RateLimitError, APITimeoutError, APIConnectionError, InternalServerError)
    except Exception:  # SDK 버전 차이 대비
        return (Exception,)


def _maybe_cost(kwargs, response):
    """S6 비용 계측(ADR-0062) — `COST_TRACKING` on일 때만 비용 기록. 예외는 본 경로로 전파하지 않는다.

    off면 `cost.maybe_record`가 즉시 None(무동작). 시그니처·반환·재시도 로직은 불변(회귀 불변).
    """
    try:
        from .cost import maybe_record

        maybe_record(kwargs.get("model", MODEL), kwargs.get("messages"), response)
    except Exception:
        pass


def chat_completion(**kwargs):
    """Phase A 동기 LLM 래퍼 — 동시성 세마포어 + 일시적 오류 지수 백오프+지터(스레드 컨텍스트용)."""
    transient = _transient_errors()
    last = None
    with _SEM:  # 동시 호출 상한
        for attempt in range(len(_RETRY_DELAYS) + 1):
            try:
                resp = get_client().chat.completions.create(**kwargs)
                _maybe_cost(kwargs, resp)  # S6 비용 계측(토글 off면 무동작)
                return resp
            except transient as exc:  # 일시적 → 백오프 재시도
                last = exc
                if attempt == len(_RETRY_DELAYS):
                    raise
                time.sleep(_RETRY_DELAYS[attempt] * (1 + random.random() * 0.3))
    raise last  # pragma: no cover


def _get_async_sem() -> asyncio.Semaphore:
    """async 동시성 세마포어 — 실행 중 이벤트 루프에 지연 바인딩(서빙 단일 루프)."""
    global _async_sem
    if _async_sem is None:
        _async_sem = asyncio.Semaphore(_MAX_CONCURRENCY)
    return _async_sem


async def achat_completion(**kwargs):
    """Phase A 비동기 LLM 래퍼 — 동시성 세마포어 + 일시적 오류 지수 백오프+지터.

    비동기 서빙 경로(`/internal/turn`)가 LLM I/O 대기 동안 이벤트 루프를 비우도록 한다
    (스레드-당-턴 점유 제거 → 동시 처리량↑). 실행은 순차 유지(출력 동일).
    """
    transient = _transient_errors()
    last = None
    async with _get_async_sem():  # 동시 호출 상한
        for attempt in range(len(_RETRY_DELAYS) + 1):
            try:
                resp = await get_async_client().chat.completions.create(**kwargs)
                _maybe_cost(kwargs, resp)  # S6 비용 계측(토글 off면 무동작)
                return resp
            except transient as exc:  # 일시적 → 백오프 재시도
                last = exc
                if attempt == len(_RETRY_DELAYS):
                    raise
                await asyncio.sleep(_RETRY_DELAYS[attempt] * (1 + random.random() * 0.3))
    raise last  # pragma: no cover
