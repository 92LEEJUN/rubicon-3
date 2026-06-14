#!/usr/bin/env python3
"""OpenAPI 스펙 export (S4 · ADR-0060) — FastAPI 기본 schema를 JSON 파일로 떨군다.

BE 노출 인터페이스의 단일 기계 산출물. `scripts/gen_types.py`·계약 점검의 입력으로 쓴다.
새 무거운 pip 의존성 없음(stdlib + 기존 FastAPI만).

사용:
    python scripts/export_openapi.py                 # build/openapi.json 으로 출력
    python scripts/export_openapi.py --out path.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# 레포 루트 기준 backend 를 import 경로에 추가(스크립트는 어디서 실행돼도 동작).
_ROOT = Path(__file__).resolve().parents[1]
_BACKEND = _ROOT / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))


def export(out: Path) -> Path:
    """app.openapi() + x-api-version 을 out(JSON)으로 dump. 반환: 작성 경로."""
    # 테스트 컨테이너처럼 결정적 import — 실제 LLM/네트워크 불필요(schema만 생성).
    from app.api.internal import app  # noqa: E402
    from app.openapi import build_openapi  # noqa: E402

    schema = build_openapi(app)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(schema, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Export FastAPI OpenAPI schema to JSON.")
    ap.add_argument("--out", default=str(_ROOT / "build" / "openapi.json"),
                    help="출력 JSON 경로(기본 build/openapi.json)")
    args = ap.parse_args(argv)
    out = Path(args.out).resolve()
    written = export(out)
    schema = json.loads(written.read_text(encoding="utf-8"))
    version = schema.get("info", {}).get("x-api-version", "?")
    n_paths = len(schema.get("paths", {}))
    n_models = len(schema.get("components", {}).get("schemas", {}))
    print(f"OpenAPI exported → {written} (version={version}, paths={n_paths}, schemas={n_models})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
