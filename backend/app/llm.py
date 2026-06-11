"""LLM 클라이언트 — provider-agnostic 경계(현재 OpenAI 소형 모델).

모델: 기본 gpt-4o-mini (소형·저비용, function calling + 구조화 출력 지원).
환경변수 LLM_MODEL 로 교체 가능. 키는 OPENAI_API_KEY 환경변수에서만 읽는다(코드/저장소에 두지 않음).
"""
import os
from pathlib import Path
from openai import OpenAI

try:  # backend/.env 자동 로드(있으면). 키는 .env(gitignore) 또는 환경변수로만.
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
except ModuleNotFoundError:
    pass

MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")
client = OpenAI()  # OPENAI_API_KEY 환경변수 사용
