"""LLM 비용 회계 — stdlib 근사 토큰·모델별 단가·메트릭 기록(ADR-0062, 요구사항 1·5).

`COST_TRACKING` off면 `maybe_record`가 즉시 None(무동작·회귀 불변). tiktoken 등 무거운 의존성 없이
공백/구두점 분할 + 문자수 보정으로 토큰을 **근사**한다(절대 청구가 아니라 비용 *추세* 관측·가드 목적).
메트릭은 ADR-0057 `metrics.Metrics` 공유 인스턴스에 누적한다(기존 시리즈 불변·추가형).
"""
from __future__ import annotations

import os
import re
import threading
from dataclasses import dataclass
from typing import Any, Optional

# 단어/숫자/구두점 단위 분할(근사 토크나이저). tiktoken 미사용(stdlib only).
_TOKEN_RE = re.compile(r"\w+|[^\w\s]", re.UNICODE)


@dataclass(frozen=True)
class ModelPrice:
    """per-1K 토큰 단가(USD) — 입력/출력 분리."""

    in_per_1k: float
    out_per_1k: float


@dataclass(frozen=True)
class CostRecord:
    """턴당 비용 회계 결과."""

    model: str
    prompt_tokens: int
    completion_tokens: int
    cost_usd: float


# 기본 단가표(per-1K USD, 근사). env override로 갱신 가능. 미지 모델은 경량 단가로 폴백.
PRICES: dict[str, ModelPrice] = {
    "gpt-4o-mini": ModelPrice(0.00015, 0.0006),
    "gpt-4o": ModelPrice(0.0025, 0.01),
    "gpt-4.1-mini": ModelPrice(0.0004, 0.0016),
    "gpt-4.1": ModelPrice(0.002, 0.008),
}
_DEFAULT_PRICE = PRICES["gpt-4o-mini"]


def _cost_tracking_on() -> bool:
    return (os.environ.get("COST_TRACKING") or "").strip().lower() in ("1", "true", "yes", "on")


def estimate_tokens(text: Optional[str]) -> int:
    """텍스트 토큰 수 근사 — 토큰 분할 카운트와 문자수/4 추정의 최대값(보수적). 빈 입력=0."""
    if not text:
        return 0
    by_split = len(_TOKEN_RE.findall(text))
    by_chars = (len(text) + 3) // 4  # 영문 대략 4자/토큰
    return max(by_split, by_chars)


def estimate_messages_tokens(messages: Any) -> int:
    """OpenAI chat 포맷 messages 토큰 합산 — content 토큰 + 메시지당 role 오버헤드(근사)."""
    if not messages:
        return 0
    total = 0
    try:
        for m in messages:
            content = m.get("content") if isinstance(m, dict) else getattr(m, "content", None)
            if isinstance(content, str):
                total += estimate_tokens(content)
            elif isinstance(content, list):  # 멀티모달 파트
                for part in content:
                    if isinstance(part, dict):
                        total += estimate_tokens(part.get("text"))
            total += 4  # role/구분 오버헤드 근사
    except Exception:
        return total
    return total


def _env_key(model: str, suffix: str) -> str:
    norm = re.sub(r"[^A-Z0-9]", "_", model.upper())
    return f"LLM_PRICE_{norm}_{suffix}"


def _price_for(model: str) -> ModelPrice:
    """모델 단가 — env override(`LLM_PRICE_<MODEL>_IN/_OUT`) 우선, 없으면 기본표, 미지 모델은 폴백."""
    base = PRICES.get(model, _DEFAULT_PRICE)
    in_env = os.environ.get(_env_key(model, "IN"))
    out_env = os.environ.get(_env_key(model, "OUT"))
    if in_env is None and out_env is None:
        return base
    try:
        in_p = float(in_env) if in_env is not None else base.in_per_1k
        out_p = float(out_env) if out_env is not None else base.out_per_1k
        return ModelPrice(in_p, out_p)
    except ValueError:
        return base


def estimate_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    """턴당 비용(USD) — (in*pt + out*ct)/1000."""
    p = _price_for(model)
    return (p.in_per_1k * prompt_tokens + p.out_per_1k * completion_tokens) / 1000.0


def _usage_tokens(response: Any) -> Optional[tuple[int, int]]:
    """response.usage가 있으면 (prompt, completion) 정확 토큰 반환, 없으면 None."""
    usage = getattr(response, "usage", None)
    if usage is None and isinstance(response, dict):
        usage = response.get("usage")
    if usage is None:
        return None
    pt = getattr(usage, "prompt_tokens", None)
    ct = getattr(usage, "completion_tokens", None)
    if pt is None and isinstance(usage, dict):
        pt = usage.get("prompt_tokens")
        ct = usage.get("completion_tokens")
    if pt is None or ct is None:
        return None
    return int(pt), int(ct)


def _completion_text(response: Any) -> str:
    """response에서 첫 choice의 텍스트를 best-effort 추출(추정용)."""
    try:
        choices = getattr(response, "choices", None)
        if choices is None and isinstance(response, dict):
            choices = response.get("choices")
        if not choices:
            return ""
        first = choices[0]
        msg = getattr(first, "message", None) or (first.get("message") if isinstance(first, dict) else None)
        if msg is None:
            return ""
        content = getattr(msg, "content", None)
        if content is None and isinstance(msg, dict):
            content = msg.get("content")
        return content if isinstance(content, str) else ""
    except Exception:
        return ""


class CostMetrics:
    """LLM 비용/토큰 누적 — 프로세스 단위(인메모리·Lock).

    ADR-0057 메트릭(`observability/metrics.py`)은 S1 소유라 직접 편집하지 않는다. 대신 본 모듈이
    비용/토큰 시리즈를 자체 보관하고, 관측성 규약(Prometheus 텍스트)에 맞춰 노출한다(라우터로 배선).
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.cost_usd = 0.0
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.calls = 0

    def record(self, record: "CostRecord") -> None:
        with self._lock:
            self.cost_usd += record.cost_usd
            self.prompt_tokens += record.prompt_tokens
            self.completion_tokens += record.completion_tokens
            self.calls += 1

    def snapshot(self) -> tuple[float, int, int, int]:
        with self._lock:
            return (self.cost_usd, self.prompt_tokens, self.completion_tokens, self.calls)

    def reset(self) -> None:
        with self._lock:
            self.cost_usd = 0.0
            self.prompt_tokens = 0
            self.completion_tokens = 0
            self.calls = 0

    def prometheus(self, service: str = "backend") -> str:
        """비용/토큰 시리즈의 Prometheus 텍스트(version 0.0.4). 기존 시리즈와 충돌 없는 신규 이름."""
        cost, pt, ct, calls = self.snapshot()
        svc = f'service="{service}"'
        return "\n".join(
            [
                "# HELP rubicon_llm_cost_usd_total Estimated LLM cost in USD.",
                "# TYPE rubicon_llm_cost_usd_total counter",
                f"rubicon_llm_cost_usd_total{{{svc}}} {cost:.6f}",
                "# HELP rubicon_llm_tokens_total Estimated LLM tokens by kind.",
                "# TYPE rubicon_llm_tokens_total counter",
                f'rubicon_llm_tokens_total{{{svc},kind="prompt"}} {pt}',
                f'rubicon_llm_tokens_total{{{svc},kind="completion"}} {ct}',
                "# HELP rubicon_llm_calls_total Total accounted LLM calls.",
                "# TYPE rubicon_llm_calls_total counter",
                f"rubicon_llm_calls_total{{{svc}}} {calls}",
            ]
        ) + "\n"


_metrics_singleton = CostMetrics()


def get_cost_metrics() -> CostMetrics:
    """프로세스 단일 비용 메트릭 인스턴스(라우터·테스트가 공유)."""
    return _metrics_singleton


def record_to_metrics(record: CostRecord) -> None:
    """비용/토큰을 프로세스 비용 메트릭에 누적."""
    try:
        _metrics_singleton.record(record)
    except Exception:
        return


def maybe_record(
    model: str,
    messages: Any,
    response: Any,
    *,
    session_id: Optional[str] = None,
) -> Optional[CostRecord]:
    """`COST_TRACKING` on일 때만 턴 비용을 회계·메트릭·예산에 반영. off/실패면 None(무동작).

    usage(정확)가 있으면 그것을, 없으면 근사 추정을 쓴다. 어떤 예외도 본 LLM 경로로 전파하지 않는다
    (요구사항 5.2 — 계측이 본 로직을 깨지 않음).
    """
    if not _cost_tracking_on():
        return None
    try:
        usage = _usage_tokens(response)
        if usage is not None:
            pt, ct = usage
        else:
            pt = estimate_messages_tokens(messages)
            ct = estimate_tokens(_completion_text(response))
        cost = estimate_cost(model, pt, ct)
        record = CostRecord(model=model, prompt_tokens=pt, completion_tokens=ct, cost_usd=cost)
        record_to_metrics(record)
        try:
            from .budget import default_guard

            default_guard().add(session_id, cost)
        except Exception:
            pass
        return record
    except Exception:
        return None
