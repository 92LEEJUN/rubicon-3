"""계약 테스트 하니스 (S4 · ADR-0060 · api-contract §7.4).

BE 실제 응답 shape ↔ 손-작성 계약(`frontend/src/types/contract.ts`) 키 정합을 경량 점검한다.
- LLM off · Mock 컨테이너(기존 conftest) · TestClient → 결정적, 네트워크 없음.
- 정본은 contract.ts. 여기서는 BE가 쓰는 template kind·chunk type이 contract.ts에 **존재**하고,
  대표 응답이 contract.ts가 기대하는 키를 담는지 확인한다(드리프트 조기 감지).
- 추가형 `X-API-Version` 헤더(요구사항 1)도 단언.
"""
import re
from pathlib import Path

from fastapi.testclient import TestClient

from app.api.internal import app
from app.openapi import API_VERSION, API_VERSION_HEADER, build_openapi

client = TestClient(app)

# frontend/src/types/contract.ts (레포 루트 기준).
_CONTRACT_TS = Path(__file__).resolve().parents[2] / "frontend" / "src" / "types" / "contract.ts"


def _contract_text() -> str:
    assert _CONTRACT_TS.exists(), f"contract.ts 없음: {_CONTRACT_TS}"
    return _CONTRACT_TS.read_text(encoding="utf-8")


def _string_literals(text: str, type_name: str) -> set[str]:
    """contract.ts 의 `export type X = 'a' | 'b' ...` 에서 문자열 리터럴 집합 추출."""
    m = re.search(rf"export type {type_name}\s*=([^;]+);", text, re.S)
    if not m:
        return set()
    return set(re.findall(r"'([^']+)'", m.group(1)))


# ── 버전 헤더(요구사항 1) ────────────────────────────────────────────────────
def test_api_version_header_present():
    r = client.get("/internal/devices")
    assert r.status_code == 200
    assert r.headers.get(API_VERSION_HEADER) == API_VERSION


def test_openapi_carries_version_meta():
    schema = build_openapi(app)
    assert schema["info"]["x-api-version"] == API_VERSION
    assert schema.get("paths"), "OpenAPI paths 비어 있음"


# ── 응답 shape ↔ contract.ts 정합(요구사항 4) ──────────────────────────────
def test_devices_shape_has_core_keys():
    r = client.get("/internal/devices")
    assert r.status_code == 200
    items = r.json()
    assert isinstance(items, list) and items, "devices 응답이 비어 있음"
    # Device 핵심 키(존재 점검 — data-model). 누락 시 FE 렌더가 깨진다.
    assert {"id", "type", "status"} <= set(items[0].keys())


def test_home_is_home_summary_template():
    r = client.get("/internal/home")
    assert r.status_code == 200
    body = r.json()
    # Template 봉투: {kind, data}. home_summary kind는 contract.ts TemplateKind에 있어야 한다.
    assert set(body.keys()) >= {"kind", "data"}
    assert body["kind"] == "home_summary"
    template_kinds = _string_literals(_contract_text(), "TemplateKind")
    assert "home_summary" in template_kinds, "home_summary가 contract.ts TemplateKind에 없음(드리프트)"


def test_resume_matches_resume_payload_keys():
    r = client.get("/internal/resume")
    assert r.status_code == 200
    body = r.json()
    # ResumePayload 필수 키(contract.ts) — has_context 는 항상 존재.
    assert "has_context" in body
    text = _contract_text()
    assert "has_context" in text and "open_loops" in text


def test_confirmation_required_409_envelope():
    # 미확인 주문 커밋 → 409 ConfirmationRequired + confirmation 템플릿(R17·§2.2·§4).
    r = client.post("/internal/orders", json={"user_id": "usr_01", "part_ids": ["p1"], "confirmed": False})
    assert r.status_code == 409
    body = r.json()
    assert body["code"] == "ConfirmationRequired"
    assert body["template"]["kind"] == "confirmation"
    template_kinds = _string_literals(_contract_text(), "TemplateKind")
    assert "confirmation" in template_kinds, "confirmation이 contract.ts TemplateKind에 없음(드리프트)"


# ── 양방향 존재 점검 — BE가 쓰는 kind/봉투가 contract.ts에 있는지 ────────────
def test_be_template_kinds_subset_of_contract():
    """BE가 실제로 내보내는 template kind들이 contract.ts TemplateKind에 모두 존재해야 한다."""
    text = _contract_text()
    template_kinds = _string_literals(text, "TemplateKind")
    # 결정적 경로에서 BE가 내보내는 대표 kind(코드 grep 기준): home_summary·confirmation·bridge·text.
    for kind in ("home_summary", "confirmation", "bridge", "text"):
        assert kind in template_kinds, f"BE template kind '{kind}'가 contract.ts에 없음(드리프트)"


def test_chunk_envelope_types_in_contract():
    """BE 섹션 스트림 봉투 type(delta·section·flow·done·error)이 contract.ts Chunk에 있어야 한다."""
    text = _contract_text()
    # Chunk 선언부 전체를 다음 `export` 또는 파일 끝까지 캡처(멤버 내부 `;`에 멈추지 않게).
    m = re.search(r"export type Chunk\s*=(.*?)(?:\n\s*export |\Z)", text, re.S)
    assert m, "contract.ts에 Chunk 타입 없음"
    chunk_src = m.group(1)
    for t in ("delta", "section", "flow", "done", "error"):
        assert f"'{t}'" in chunk_src, f"chunk type '{t}'가 contract.ts Chunk에 없음(드리프트)"
