"""더미데이터(fixtures) 로더 — Mock 어댑터가 반환할 데이터.

실 전환 시 이 모듈을 SmartThings/CS/제품 Real 어댑터로 교체한다(인터페이스 불변).
경로: specs/mvp-concierge/fixtures/  (data-model.md 타입 정합)
"""
import json
from pathlib import Path

FIX = Path(__file__).resolve().parents[2] / "specs" / "mvp-concierge" / "fixtures"


def _load(name: str):
    return json.loads((FIX / name).read_text(encoding="utf-8"))


USER = _load("user.json")
DEVICES = _load("devices.json")
ANOMALIES = _load("anomalies.json")
SOLUTIONS = _load("solutions.json")
CATALOG = _load("catalog.json")
PARTS = CATALOG["parts"]
PRODUCTS = CATALOG["products"]
