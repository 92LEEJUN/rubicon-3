"""동시성 안전 유틸 — 키별 잠금(KeyedLock).

멀티테넌트 read-modify-write 임계구역(주문 커밋·픽업 전이)에서, **같은 키**
(예: user_id·order_id)에 대한 동시 요청을 직렬화해 상태 오염/oversell을 막는다.
**다른 키**는 서로 막지 않고 독립적으로 진행한다.

설계 메모(정직하게):
- CPython의 GIL 하에서, 중간에 양보(I/O·sleep·await)하지 않는 순수 동기 메서드는
  사실상 원자적이다. 따라서 현재 Mock(인메모리) 경로에서는 이 잠금이 없어도
  대부분 안전하다.
- 그럼에도 이 잠금을 두는 이유: (1) read와 write 사이에 양보 지점이 생기는
  순간(비동기/DB I/O — slice 3의 실 어댑터) 경쟁이 실재한다. (2) "한 키의 임계구역은
  직렬화된다"는 불변식을 코드로 **명시적·미래보장**한다.
- 그래서 이 모듈은 GIL에 기대지 않고, 실제 `threading.Lock` 으로 직렬화를 강제한다.
"""
from __future__ import annotations

import threading
from typing import Hashable


class KeyedLock:
    """키별로 별도의 `threading.Lock` 을 제공하는 스레드 안전 레지스트리.

    같은 키로 `acquire(key)` 한 컨텍스트들은 직렬화되고, 다른 키끼리는 독립적으로
    동시에 진행한다. 락 레지스트리 자체의 갱신은 내부 가드락으로 보호한다.

    사용:
        _locks = KeyedLock()
        with _locks.acquire(user_id):
            ...  # user_id 임계구역(read-modify-write)

    주의: 단순함을 위해 락은 생성 후 제거하지 않는다(키 도메인이 유계 — user/order id).
    수명 동안 유한·재사용되는 키에 적합하며, 무한히 늘어나는 키에는 부적합하다.
    """

    def __init__(self) -> None:
        self._guard = threading.Lock()
        self._locks: dict[Hashable, threading.Lock] = {}

    def get(self, key: Hashable) -> threading.Lock:
        """키에 대응하는 락을 반환(없으면 생성). 같은 키는 항상 같은 락을 돌려준다."""
        # 빠른 경로: 가드 없이 조회 시도(dict 읽기는 GIL 하 원자적).
        lock = self._locks.get(key)
        if lock is not None:
            return lock
        # 느린 경로: 생성은 가드락으로 직렬화해 중복 생성을 막는다.
        with self._guard:
            lock = self._locks.get(key)
            if lock is None:
                lock = threading.Lock()
                self._locks[key] = lock
            return lock

    def acquire(self, key: Hashable) -> threading.Lock:
        """`with` 문에서 바로 쓰도록 키의 락을 반환한다(컨텍스트 매니저).

        `threading.Lock` 자체가 컨텍스트 매니저이므로 `with kl.acquire(k):` 로 쓴다.
        """
        return self.get(key)
