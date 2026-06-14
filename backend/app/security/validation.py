"""입력 검증 하드닝 — 순수 유틸(S7, ADR-0063, 요구사항 3).

페이로드 크기 상한·필드 화이트리스트를 경계에서 검사한다. **옵트인**(호출하지 않으면 동작 불변)이며
전역 상태를 변경하지 않는 순수 함수다(결정적·테스트 가능). 새 의존성 없음(stdlib only).

OWASP: 과대 입력(DoS)·미상 필드 주입(mass assignment) 방어면.
"""
from __future__ import annotations

from typing import Iterable, Mapping

# 기본 페이로드 상한(바이트). 명시적으로 넘기지 않으면 이 값 사용.
DEFAULT_MAX_BYTES = 64 * 1024  # 64 KiB


class ValidationError(ValueError):
    """입력 검증 실패. `code`로 사유를 구분한다(PayloadTooLarge·UnknownField)."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def check_payload_size(raw: bytes | str, max_bytes: int = DEFAULT_MAX_BYTES) -> int:
    """페이로드 바이트 크기를 검사한다(요구사항 3.1).

    초과 시 `ValidationError("PayloadTooLarge")`. 통과하면 실제 바이트 수를 반환한다.
    str은 UTF-8로 인코딩해 측정한다.
    """
    size = len(raw.encode("utf-8")) if isinstance(raw, str) else len(raw)
    if size > max_bytes:
        raise ValidationError(
            "PayloadTooLarge",
            f"페이로드가 너무 큽니다: {size} bytes > 상한 {max_bytes} bytes",
        )
    return size


def whitelist_fields(
    data: Mapping,
    allowed: Iterable[str],
    mode: str = "strip",
) -> dict:
    """dict 입력을 화이트리스트로 정제한다(요구사항 3.2·3.3).

    - mode="strip"  : 화이트리스트 밖 키를 **제거**하고 허용 키만 남긴 새 dict 반환.
    - mode="strict" : 화이트리스트 밖 키가 하나라도 있으면 `ValidationError("UnknownField")`.

    입력 dict는 변형하지 않는다(순수, 요구사항 3.4).
    """
    allowed_set = set(allowed)
    if mode == "strict":
        unknown = [k for k in data.keys() if k not in allowed_set]
        if unknown:
            raise ValidationError(
                "UnknownField",
                f"허용되지 않은 필드: {', '.join(map(str, sorted(unknown)))}",
            )
        return dict(data)
    if mode == "strip":
        return {k: v for k, v in data.items() if k in allowed_set}
    raise ValueError(f"알 수 없는 mode: {mode!r} (strip|strict)")
