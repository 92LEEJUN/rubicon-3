"""Mock 어댑터 — Port의 MVP 구현(fixtures 반환).

data-model.md §6 Port에 대응:
  get_device_status  ← DevicePort.get_status/detect_anomalies (SmartThings)
  search_solutions   ← CSKnowledgePort.find_solutions (CS, 하이브리드 검색)
  match_parts        ← CatalogPort.match_parts (제품정보, demand-driven)
실 전환 시 Real 어댑터로 교체(인터페이스 불변).
"""
from . import fixtures as fx


def get_device_status(device_query: str) -> dict:
    """기기 id/type/모델로 상태 + 이상을 조회."""
    q = (device_query or "").lower()
    dev = next(
        (d for d in fx.DEVICES
         if q in d["id"].lower() or q in d["type"].lower() or q in d["model"].lower()),
        None,
    )
    if not dev:
        # 한국어 별칭 매핑(데모용)
        alias = {"세탁기": "washer", "냉장고": "refrigerator", "공기청정기": "air_purifier"}
        for k, v in alias.items():
            if k in (device_query or ""):
                dev = next((d for d in fx.DEVICES if d["type"] == v), None)
                break
    if not dev:
        return {"found": False, "message": "해당 기기를 찾지 못했습니다(미연동 가능)."}
    anomalies = [a for a in fx.ANOMALIES if a["device_id"] == dev["id"]]
    return {"found": True, "device": dev, "anomalies": anomalies}


def search_solutions(query: str, error_code: str | None = None) -> dict:
    """오류코드 정확 매칭(키) + 자유 증상 키워드 검색(하이브리드).

    MVP는 데모용 동의어 매칭. 실 전환 시 벡터 임베딩 유사도로 교체.
    """
    # 데모용 증상 동의어(실 전환 시 벡터 검색으로 대체)
    SYN = {
        "sol_washer_5c": ["배수", "물", "빠", "안빠", "드레인", "drain", "세탁", "5c"],
        "sol_fridge_filter": ["정수", "필터", "냉장", "물맛", "교체", "filter"],
    }
    code = (error_code or "").strip().upper()
    if not code:  # 질의 문자열에서 코드 추출(예: "5C")
        import re
        m = re.search(r"\b([0-9][A-Z]|[A-Z][0-9])\b", (query or "").upper())
        code = m.group(1) if m else ""
    q = (query or "")

    results = []
    for sol in fx.SOLUTIONS:
        ano = next((a for a in fx.ANOMALIES if a["id"] == sol.get("anomaly_id")), None)
        detail = (ano["detail"] if ano else "") + " " + " ".join(
            s["instruction"] for s in sol["steps"]
        )
        keywords = SYN.get(sol["id"], [])
        if code and code in detail.upper():
            results.append(sol)
        elif q and (any(k in q for k in keywords)
                    or any(w in detail for w in q.split() if len(w) > 1)):
            results.append(sol)
    return {"count": len(results), "solutions": results}


def match_parts(device_model: str | None = None, part_ids: list[str] | None = None) -> dict:
    """기기 모델 호환 부품 또는 id로 부품 조회(전체 나열 없음 — demand-driven)."""
    if part_ids:
        parts = [p for p in fx.PARTS if p["id"] in part_ids]
    elif device_model:
        parts = [p for p in fx.PARTS if device_model.lower() in p["device_model"].lower()]
    else:
        parts = []
    return {"count": len(parts), "parts": parts}
