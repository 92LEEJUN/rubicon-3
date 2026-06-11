"""pytest 픽스처 — Mock 어댑터로 조립한 컨테이너를 매 테스트 새로 만든다."""
import os

# 테스트는 결정적 경로(룰베이스+Mock)로 고정 — backend/.env 의 LLM_BACKED=1 이
# load_dotenv 로 새어들어와 실제 OpenAI를 타지 않도록 import 전에 미리 끈다.
# (load_dotenv 는 기본 override=False 라 이미 설정된 값을 덮지 않는다.)
os.environ.setdefault("LLM_BACKED", "")
os.environ["LLM_BACKED"] = ""

import pytest

from app.container import Container, build_container


@pytest.fixture
def container() -> Container:
    return build_container()
