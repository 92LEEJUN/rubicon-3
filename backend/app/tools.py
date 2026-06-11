"""LLM tool(함수) 정의 + 디스패치 — orchestration.md §3 tool 레이어.

tool은 함수 시그니처고, 구현은 타입 있는 Mock 어댑터(`adapters.mock`). 실 전환 시 어댑터만 교체.
tool 결과는 JSON 직렬화해 LLM에 회신한다.
"""
from .adapters import mock as _mock

# 어댑터 싱글턴(주문은 상태 보유)
_device = _mock.MockDeviceAdapter()
_cs = _mock.MockCSKnowledgeAdapter()
_catalog = _mock.MockCatalogAdapter()


def _get_device_status(device_query: str) -> dict:
    return _device.get_status(device_query).model_dump(mode="json")


def _search_solutions(query: str, error_code: str | None = None) -> dict:
    return _cs.find_solutions(query, error_code).model_dump(mode="json")


def _match_parts(device_model: str | None = None, part_ids: list[str] | None = None) -> dict:
    return _catalog.match_parts(device_model, part_ids).model_dump(mode="json")

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_device_status",
            "description": "사용자 기기의 현재 상태와 감지된 이상(오류코드·소모품)을 조회한다. 기기 문제·상태 질문이면 먼저 호출.",
            "parameters": {
                "type": "object",
                "properties": {
                    "device_query": {"type": "string", "description": "기기 종류/모델/이름 (예: '세탁기', 'washer', 'WF45T6000AW')"}
                },
                "required": ["device_query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_solutions",
            "description": "CS 지식에서 증상/오류코드에 대한 단계별 해결 가이드와 필요한 부품을 검색한다. 해결법을 안내할 때 호출.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "증상 설명 (자유 텍스트)"},
                    "error_code": {"type": "string", "description": "오류코드 (있으면, 예: '5C')"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "match_parts",
            "description": "기기 모델 또는 부품 id로 호환 부품/소모품(가격·재고)을 조회한다. 부품 주문/추천 시 호출.",
            "parameters": {
                "type": "object",
                "properties": {
                    "device_model": {"type": "string", "description": "호환 기기 모델"},
                    "part_ids": {"type": "array", "items": {"type": "string"}, "description": "조회할 부품 id 목록 (해결책의 required_parts 등)"},
                },
            },
        },
    },
]

DISPATCH = {
    "get_device_status": _get_device_status,
    "search_solutions": _search_solutions,
    "match_parts": _match_parts,
}


def call(name: str, args: dict) -> dict:
    fn = DISPATCH.get(name)
    if not fn:
        return {"error": f"unknown tool: {name}"}
    return fn(**args)
