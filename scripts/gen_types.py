#!/usr/bin/env python3
"""스키마 → TS 타입 생성 (S4 · ADR-0060) — OpenAPI components.schemas → TS interface.

목적: BE pydantic 모델(→ OpenAPI)에서 TS 타입을 **생성**해, 손-작성 계약(`contract.ts`)과의
드리프트를 점검한다. 정본은 `contract.ts`(permissive kind 등 BE 스키마에 없는 의미 포함)이므로,
생성물은 **별도 파일**(`contract.generated.ts`)로 떨구고 점검 보조로만 쓴다(역방향 자동 갱신 아님).

새 무거운 pip/npm 의존성 없음 — 경량 자체 매퍼(완벽한 타입은 비목표, 드리프트 점검이 목표).

사용:
    python scripts/gen_types.py                     # build/openapi.json → contract.generated.ts
    python scripts/gen_types.py --check             # 생성 + contract.ts 드리프트 보고(비차단)
    python scripts/gen_types.py --openapi x.json --out y.ts
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_DEFAULT_OPENAPI = _ROOT / "build" / "openapi.json"
_DEFAULT_OUT = _ROOT / "frontend" / "src" / "types" / "contract.generated.ts"
_CONTRACT_TS = _ROOT / "frontend" / "src" / "types" / "contract.ts"

_PRIMITIVE = {"string": "string", "integer": "number", "number": "number", "boolean": "boolean"}


def _ref_name(ref: str) -> str:
    """'#/components/schemas/Foo' → 'Foo'."""
    return ref.rsplit("/", 1)[-1]


def _ts_type(schema: dict) -> str:
    """JSON Schema(한 노드) → TS 타입 문자열(경량). 매핑 못 하면 unknown 폴백."""
    if not isinstance(schema, dict):
        return "unknown"
    if "$ref" in schema:
        return _ref_name(schema["$ref"])
    # anyOf/allOf/oneOf — 멤버 union(널 포함 nullable 흔함).
    for key in ("anyOf", "oneOf"):
        if key in schema:
            members = [_ts_type(s) for s in schema[key]]
            # OpenAPI nullable: {anyOf:[T, {type:null}]} → T | null
            members = [m if m != "null" else "null" for m in members]
            uniq = list(dict.fromkeys(members))
            return " | ".join(uniq) if uniq else "unknown"
    if "allOf" in schema:
        members = [_ts_type(s) for s in schema["allOf"]]
        return " & ".join(dict.fromkeys(members)) if members else "unknown"
    t = schema.get("type")
    if t == "null":
        return "null"
    if t == "array":
        inner = _ts_type(schema.get("items", {})) or "unknown"
        return f"{inner}[]"
    if t == "object" or "properties" in schema or "additionalProperties" in schema:
        ap = schema.get("additionalProperties")
        if isinstance(ap, dict):
            return f"Record<string, {_ts_type(ap)}>"
        if ap is True or (ap is None and "properties" not in schema):
            return "Record<string, unknown>"
        # 인라인 object — 단순화: Record(중첩 인터페이스는 비목표).
        return "Record<string, unknown>"
    if isinstance(t, list):  # ["string","null"] 류
        members = [_PRIMITIVE.get(x, "null" if x == "null" else "unknown") for x in t]
        return " | ".join(dict.fromkeys(members))
    return _PRIMITIVE.get(t, "unknown")


def _interface(name: str, schema: dict) -> str:
    """object schema → `export interface Name { ... }` (그 외엔 type alias)."""
    if schema.get("type") == "object" or "properties" in schema:
        required = set(schema.get("required", []))
        lines = [f"export interface {name} {{"]
        for prop, ps in (schema.get("properties") or {}).items():
            opt = "" if prop in required else "?"
            lines.append(f"  {prop}{opt}: {_ts_type(ps)};")
        lines.append("}")
        return "\n".join(lines)
    return f"export type {name} = {_ts_type(schema)};"


def generate(openapi: dict) -> str:
    """OpenAPI dict → TS 소스 문자열(헤더 + 인터페이스들)."""
    schemas = openapi.get("components", {}).get("schemas", {})
    version = openapi.get("info", {}).get("x-api-version", "unknown")
    out = [
        "/**",
        " * 자동 생성 (scripts/gen_types.py) — 편집 금지.",
        f" * 출처: OpenAPI(x-api-version={version}). 정본 계약은 contract.ts(손-작성).",
        " * 이 파일은 BE 스키마→TS 드리프트 점검 보조다(ADR-0060 · api-contract §7.4).",
        " */",
        "",
    ]
    for name in sorted(schemas):
        out.append(_interface(name, schemas[name]))
        out.append("")
    return "\n".join(out)


def _contract_ts_names(text: str) -> set[str]:
    """contract.ts 에서 export 된 interface/type 이름 추출(드리프트 비교용)."""
    names = set(re.findall(r"export\s+(?:interface|type)\s+([A-Za-z0-9_]+)", text))
    return names


def check_drift(openapi: dict, contract_text: str) -> list[str]:
    """생성 모델 이름 ↔ contract.ts 이름 비교. 보고 라인 리스트 반환(비차단)."""
    gen_names = set(openapi.get("components", {}).get("schemas", {}).keys())
    ts_names = _contract_ts_names(contract_text)
    report: list[str] = []
    only_be = sorted(gen_names - ts_names)
    only_ts = sorted(ts_names - gen_names)
    common = sorted(gen_names & ts_names)
    report.append(f"[drift] BE 스키마 {len(gen_names)}개 · contract.ts {len(ts_names)}개 · 공통 {len(common)}개")
    if only_be:
        report.append(f"[drift] BE에만 있음(contract.ts 미반영 후보): {', '.join(only_be)}")
    if only_ts:
        report.append(f"[drift] contract.ts에만 있음(손-작성 계약 — 정상일 수 있음): {', '.join(only_ts)}")
    if not only_be:
        report.append("[drift] BE 모델은 모두 contract.ts에 대응 이름이 있음(키 수준 정합).")
    return report


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Generate TS types from OpenAPI; optional drift check.")
    ap.add_argument("--openapi", default=str(_DEFAULT_OPENAPI), help="OpenAPI JSON 입력")
    ap.add_argument("--out", default=str(_DEFAULT_OUT), help="생성 TS 출력(별도 산출물)")
    ap.add_argument("--check", action="store_true", help="contract.ts 드리프트 보고(비차단)")
    args = ap.parse_args(argv)

    oa_path = Path(args.openapi)
    if not oa_path.exists():
        print(f"openapi 파일 없음: {oa_path}\n먼저 `python scripts/export_openapi.py` 를 실행하세요.",
              file=sys.stderr)
        return 2
    openapi = json.loads(oa_path.read_text(encoding="utf-8"))

    out_path = Path(args.out).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(generate(openapi) + "\n", encoding="utf-8")
    n = len(openapi.get("components", {}).get("schemas", {}))
    print(f"TS types generated → {out_path} ({n} schemas)")

    if args.check:
        contract_text = _CONTRACT_TS.read_text(encoding="utf-8") if _CONTRACT_TS.exists() else ""
        for line in check_drift(openapi, contract_text):
            print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
