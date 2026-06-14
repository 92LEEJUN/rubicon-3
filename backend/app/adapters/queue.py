"""큐/배치 인터페이스 + Mock 구현 + 재시도 훅 — S3 백킹서비스(ADR-0059, 12F#8·#12).

`QueuePort`(Protocol)는 enqueue/dequeue/size 시그니처를 고정한다(ADR-0020 경계). 실 전환 시 동일
Protocol을 만족하는 메시지 브로커(Redis Streams·SQS 등) 어댑터로 교체한다. 이번 범위는 Mock —
인프로세스 FIFO + 재시도/데드레터 훅으로 배치·선제 파이프라인을 구조적으로 검증한다.
"""
from __future__ import annotations

from typing import Any, Callable, Optional, Protocol, runtime_checkable

Job = dict[str, Any]


@runtime_checkable
class QueuePort(Protocol):
    """큐 백킹서비스 계약."""

    def enqueue(self, job: Job) -> None: ...

    def dequeue(self) -> Optional[Job]:
        """비었으면 None(FIFO)."""
        ...

    def size(self) -> int: ...


class MockQueue:
    """`QueuePort` Mock(인프로세스 FIFO) + 재시도/데드레터.

    `process(handler, max_attempts)`는 큐를 비우며 각 작업에 handler를 적용한다. handler가 예외를
    던지면 attempts를 늘려 재시도하고, `max_attempts`를 초과하면 dead_letter로 옮긴다(소실 없음).
    """

    def __init__(self) -> None:
        self._items: list[Job] = []
        self.dead_letter: list[Job] = []

    def enqueue(self, job: Job) -> None:
        self._items.append(job)

    def dequeue(self) -> Optional[Job]:
        if not self._items:
            return None
        return self._items.pop(0)

    def size(self) -> int:
        return len(self._items)

    def process(self, handler: Callable[[Job], Any], max_attempts: int = 3) -> dict[str, int]:
        """큐를 소비하며 handler를 적용. 성공 제거·실패 재시도·초과 데드레터.

        반환: {"succeeded": n, "dead_lettered": n}. 작업은 `_attempts` 키로 시도횟수를 추적한다.
        """
        succeeded, dead_lettered = 0, 0
        while True:
            job = self.dequeue()
            if job is None:
                break
            attempts = job.get("_attempts", 0) + 1
            try:
                handler(job)
                succeeded += 1
            except Exception:
                if attempts >= max_attempts:
                    job["_attempts"] = attempts
                    self.dead_letter.append(job)
                    dead_lettered += 1
                else:
                    job["_attempts"] = attempts
                    self.enqueue(job)  # 재시도 — 큐 끝으로 되돌림
        return {"succeeded": succeeded, "dead_lettered": dead_lettered}
