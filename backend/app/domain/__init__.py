"""도메인 모델 — data-model.md 타입의 Pydantic 구현(공유 계약).

이 패키지는 BE 도메인의 **진실의 출처(typed)** 다. Port·서비스·내부 API가 모두 이 타입을 쓴다.
외부 표현(SmartThings/CS/제품 raw)은 어댑터(ACL)에서 이 타입으로 변환된다(architecture.md §5).
"""
from .models import *  # noqa: F401,F403
