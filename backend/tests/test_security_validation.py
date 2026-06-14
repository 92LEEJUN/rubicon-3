"""입력 검증 유틸(S7, ADR-0063, 요구사항 3) — 크기 상한·화이트리스트·순수성."""
import pytest

from app.security.validation import (
    DEFAULT_MAX_BYTES,
    ValidationError,
    check_payload_size,
    whitelist_fields,
)


# ── 페이로드 크기 ─────────────────────────────────────────────────────────────
def test_check_payload_size_ok_returns_size():
    assert check_payload_size("hello", max_bytes=10) == 5


def test_check_payload_size_counts_utf8_bytes():
    # 한글 1자 = UTF-8 3바이트.
    assert check_payload_size("가", max_bytes=10) == 3


def test_check_payload_size_too_large_raises():
    with pytest.raises(ValidationError) as ei:
        check_payload_size(b"x" * 20, max_bytes=10)
    assert ei.value.code == "PayloadTooLarge"


def test_check_payload_size_default_limit():
    assert check_payload_size(b"x" * 10) == 10  # 기본 상한 안
    assert DEFAULT_MAX_BYTES == 64 * 1024


# ── 화이트리스트 ──────────────────────────────────────────────────────────────
def test_whitelist_strip_removes_unknown():
    out = whitelist_fields({"a": 1, "b": 2, "evil": 3}, allowed=["a", "b"])
    assert out == {"a": 1, "b": 2}


def test_whitelist_strict_raises_on_unknown():
    with pytest.raises(ValidationError) as ei:
        whitelist_fields({"a": 1, "evil": 3}, allowed=["a"], mode="strict")
    assert ei.value.code == "UnknownField"


def test_whitelist_strict_ok_passes_through():
    out = whitelist_fields({"a": 1}, allowed=["a", "b"], mode="strict")
    assert out == {"a": 1}


def test_whitelist_does_not_mutate_input():
    src = {"a": 1, "evil": 2}
    whitelist_fields(src, allowed=["a"])
    assert src == {"a": 1, "evil": 2}  # 순수(요구사항 3.4)


def test_whitelist_unknown_mode_raises():
    with pytest.raises(ValueError):
        whitelist_fields({"a": 1}, allowed=["a"], mode="bogus")
