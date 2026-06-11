"""pytest 픽스처 — Mock 어댑터로 조립한 컨테이너를 매 테스트 새로 만든다."""
import pytest

from app.container import Container, build_container


@pytest.fixture
def container() -> Container:
    return build_container()
