"""LLM 클라이언트 — provider-agnostic 경계(현재 OpenAI 소형 모델).

모델: 기본 gpt-4o-mini (소형·저비용, function calling + 구조화 출력 지원).
환경변수 LLM_MODEL 로 교체 가능. 키는 OPENAI_API_KEY 환경변수에서만 읽는다(코드/저장소에 두지 않음).
"""
import os
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


def get_client():
    """OpenAI 클라이언트 지연 생성 — 키 없이도 모듈 import는 가능(테스트·오프라인).

    실제 LLM 호출(legacy CLI·OpenAIClassifier) 시점에만 OPENAI_API_KEY가 필요하다.
    """
    global _client
    if _client is None:
        from openai import OpenAI
        _client = OpenAI()  # OPENAI_API_KEY 환경변수 사용
    return _client


def chat_completion(**kwargs):
    """Phase A LLM 호출 래퍼 — 동시성 세마포어 + 일시적 오류(429/5xx/타임아웃) 지수 백오프+지터.

    멀티에이전트/툴루프의 모든 LLM 호출을 이 래퍼로 통일해 동시성·레이트리밋을 한 곳에서 제어한다.
    """
    try:
        from openai import APIConnectionError, APITimeoutError, InternalServerError, RateLimitError
        transient = (RateLimitError, APITimeoutError, APIConnectionError, InternalServerError)
    except Exception:  # SDK 버전 차이 대비
        transient = (Exception,)

    last = None
    with _SEM:  # 동시 호출 상한
        for attempt in range(len(_RETRY_DELAYS) + 1):
            try:
                return get_client().chat.completions.create(**kwargs)
            except transient as exc:  # 일시적 → 백오프 재시도
                last = exc
                if attempt == len(_RETRY_DELAYS):
                    raise
                time.sleep(_RETRY_DELAYS[attempt] * (1 + random.random() * 0.3))
    raise last  # pragma: no cover
