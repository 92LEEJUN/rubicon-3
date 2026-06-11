"""CLI 데모 — 풀 저니를 소형 모델로 실행.

사용:  python -m app.cli "세탁기에서 물이 안 빠져요. 어떻게 해결하나요?"
환경:  OPENAI_API_KEY 필요 (LLM_MODEL 로 모델 교체, 기본 gpt-4o-mini)
"""
import sys
from .orchestrator import run

DEFAULT = "세탁기에서 물이 안 빠져요. 어떻게 해결하고, 필요한 부품도 주문하고 싶어요."


def main():
    query = " ".join(sys.argv[1:]).strip() or DEFAULT
    print(f"🧑 {query}\n" + "-" * 60)
    answer = run(query)
    print("-" * 60 + f"\n🤖 {answer}")


if __name__ == "__main__":
    main()
