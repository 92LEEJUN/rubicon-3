"""LLM 클라이언트 — provider-agnostic 경계(현재 OpenAI 소형 모델).

모델: 기본 gpt-4o-mini (소형·저비용, function calling + 구조화 출력 지원).
환경변수 LLM_MODEL 로 교체 가능. 키는 OPENAI_API_KEY 환경변수에서만 읽는다(코드/저장소에 두지 않음).
"""
import os
from pathlib import Path

try:  # backend/.env 자동 로드(있으면). 키는 .env(gitignore) 또는 환경변수로만.
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
except ModuleNotFoundError:
    pass

MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")

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
