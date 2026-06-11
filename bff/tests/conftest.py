"""BFF 테스트 — BackendClient를 httpx ASGITransport로 **BE 앱에 인프로세스 연결**.

FE↔BFF↔BE를 실제 HTTP 계약으로 묶어 검증한다(api-contract §5 계약 테스트).
별도 네트워크/서버 없이 같은 fixtures로 합치를 확인.
"""
import httpx
import pytest
from fastapi.testclient import TestClient

from app.api.internal import app as be_app  # BE (../backend)
from gateway.backend_client import BackendClient
from gateway.main import create_app

AUTH = {"Authorization": "Bearer test-token"}


@pytest.fixture
def be_backend() -> BackendClient:
    transport = httpx.ASGITransport(app=be_app)
    return BackendClient(base_url="http://be", transport=transport)


@pytest.fixture
def client(be_backend) -> TestClient:
    return TestClient(create_app(be_backend))


@pytest.fixture
def broken_client() -> TestClient:
    """업스트림 장애 시뮬레이션 — 모든 BE 호출이 ConnectError."""
    def _boom(request):
        raise httpx.ConnectError("backend down")
    transport = httpx.MockTransport(_boom)
    return TestClient(create_app(BackendClient(base_url="http://be", transport=transport)))
