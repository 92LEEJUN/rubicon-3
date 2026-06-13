"""SQLite 백엔드 Repository — user 단위 영속(stdlib `sqlite3`, 무의존성).

`PERSISTENCE=db` 토글 시 인메모리 Repository를 대체한다(인터페이스 불변).
인메모리 구현(`conversation_memory.py`·`open_loop.py`·`memory.py`)과 **동일한
메서드 시그니처**를 가지며, 도메인 객체는 pydantic JSON으로 직렬화해 컬럼에 보관한다.

영속성 주의: `:memory:` DB는 커넥션 간 공유되지 않으므로(토글/재시작 복원 불가),
실 영속은 파일 경로를 쓴다(container는 `SQLITE_PATH` 또는 기본 파일 경로 주입).
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

from typing import Optional

from ..domain import (
    ConversationMemory,
    EngagementRecord,
    EngagementState,
    OpenLoop,
    Order,
)


def _connect(db_path: str) -> sqlite3.Connection:
    # check_same_thread=False: 서비스가 단일 커넥션을 여러 코루틴/스레드에서 재사용해도
    # 안전하도록(스크립트성 단일 프로세스 MVP). autocommit 동작은 매 write 후 commit으로 보장.
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


class SqliteConversationMemoryRepository:
    """대화 메모리 — user 단위. JSON 1컬럼에 `ConversationMemory` 저장."""

    def __init__(self, db_path: str = "rubicon.db") -> None:
        self._conn = _connect(db_path)
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS conversation_memory ("
            "  user_id TEXT PRIMARY KEY,"
            "  data    TEXT NOT NULL"
            ")"
        )
        self._conn.commit()

    def get(self, user_id: str) -> ConversationMemory:
        """없으면 빈 메모리(첫 방문 = 깨끗한 시작)."""
        row = self._conn.execute(
            "SELECT data FROM conversation_memory WHERE user_id = ?", (user_id,)
        ).fetchone()
        if row is None:
            return ConversationMemory()
        return ConversationMemory.model_validate_json(row["data"])

    def save(self, user_id: str, memory: ConversationMemory) -> None:
        self._conn.execute(
            "INSERT INTO conversation_memory (user_id, data) VALUES (?, ?) "
            "ON CONFLICT(user_id) DO UPDATE SET data = excluded.data",
            (user_id, memory.model_dump_json()),
        )
        self._conn.commit()

    def delete(self, user_id: str) -> None:
        """삭제 요청 cascade(R19)."""
        self._conn.execute(
            "DELETE FROM conversation_memory WHERE user_id = ?", (user_id,)
        )
        self._conn.commit()


class SqliteOpenLoopRepository:
    """미해결 스레드(OpenLoop) — (user_id, ref) 단위 upsert(멱등). JSON으로 저장."""

    def __init__(self, db_path: str = "rubicon.db") -> None:
        self._conn = _connect(db_path)
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS open_loops ("
            "  user_id TEXT NOT NULL,"
            "  ref     TEXT NOT NULL,"
            "  data    TEXT NOT NULL,"
            "  PRIMARY KEY (user_id, ref)"
            ")"
        )
        self._conn.commit()

    def upsert(self, user_id: str, loop: OpenLoop) -> None:
        self._conn.execute(
            "INSERT INTO open_loops (user_id, ref, data) VALUES (?, ?, ?) "
            "ON CONFLICT(user_id, ref) DO UPDATE SET data = excluded.data",
            (user_id, loop.ref, loop.model_dump_json()),
        )
        self._conn.commit()

    def get(self, user_id: str, ref: str) -> OpenLoop | None:
        row = self._conn.execute(
            "SELECT data FROM open_loops WHERE user_id = ? AND ref = ?",
            (user_id, ref),
        ).fetchone()
        if row is None:
            return None
        return OpenLoop.model_validate_json(row["data"])

    def list_open(self, user_id: str) -> list[OpenLoop]:
        rows = self._conn.execute(
            "SELECT data FROM open_loops WHERE user_id = ?", (user_id,)
        ).fetchall()
        loops = [OpenLoop.model_validate_json(r["data"]) for r in rows]
        loops = [loop for loop in loops if loop.status == "open"]
        # 우선순위·최근순(인메모리 구현과 동일 정렬).
        return sorted(loops, key=lambda loop: (loop.priority, loop.last_touch), reverse=True)

    def set_status(self, user_id: str, ref: str, status: str) -> OpenLoop | None:
        loop = self.get(user_id, ref)
        if loop is None:
            return None
        updated = loop.model_copy(update={"status": status})
        self._conn.execute(
            "UPDATE open_loops SET data = ? WHERE user_id = ? AND ref = ?",
            (updated.model_dump_json(), user_id, ref),
        )
        self._conn.commit()
        return updated

    def clear(self, user_id: str) -> None:
        self._conn.execute("DELETE FROM open_loops WHERE user_id = ?", (user_id,))
        self._conn.commit()


class SqliteEngagementRepository:
    """Engagement(R29) — (user_id, ref) 단위 열람/무시/관심 상태. JSON으로 저장."""

    _SEEN_STATES = ("viewed", "acknowledged", "dismissed")

    def __init__(self, db_path: str = "rubicon.db") -> None:
        self._conn = _connect(db_path)
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS engagement ("
            "  user_id TEXT NOT NULL,"
            "  ref     TEXT NOT NULL,"
            "  data    TEXT NOT NULL,"
            "  PRIMARY KEY (user_id, ref)"
            ")"
        )
        self._conn.commit()

    def record(self, user_id: str, ref: str, state: EngagementState) -> EngagementRecord:
        rec = EngagementRecord(
            user_id=user_id, ref=ref, state=state,
            updated_at=datetime.now(timezone.utc),
        )
        self._conn.execute(
            "INSERT INTO engagement (user_id, ref, data) VALUES (?, ?, ?) "
            "ON CONFLICT(user_id, ref) DO UPDATE SET data = excluded.data",
            (user_id, ref, rec.model_dump_json()),
        )
        self._conn.commit()
        return rec

    def get(self, user_id: str, ref: str) -> EngagementRecord | None:
        row = self._conn.execute(
            "SELECT data FROM engagement WHERE user_id = ? AND ref = ?",
            (user_id, ref),
        ).fetchone()
        if row is None:
            return None
        return EngagementRecord.model_validate_json(row["data"])

    def list(self, user_id: str) -> list[EngagementRecord]:
        rows = self._conn.execute(
            "SELECT data FROM engagement WHERE user_id = ?", (user_id,)
        ).fetchall()
        return [EngagementRecord.model_validate_json(r["data"]) for r in rows]

    def has_seen(self, user_id: str, ref: str) -> bool:
        """이미 열람/확인/무시했는지 — 중복 노출 억제용."""
        rec = self.get(user_id, ref)
        return rec is not None and rec.state in self._SEEN_STATES

    def list_all_user(self, user_id: str) -> list[EngagementRecord]:
        """머지(게스트→로그인)용 — 상태 무관 전체 행. `list`와 동일하지만 의미 명시."""
        return self.list(user_id)

    def delete_user(self, user_id: str) -> None:
        """머지 후 게스트 비우기(R re-key). user_id 키 행 전부 삭제."""
        self._conn.execute("DELETE FROM engagement WHERE user_id = ?", (user_id,))
        self._conn.commit()


class SqliteOrderRepository:
    """OrderPort(sqlite) — `MockOrderAdapter`와 **동일 시그니처**, 저장만 sqlite.

    주문 도메인 객체(Order)를 JSON 1컬럼에 보관(user_id·created_at은 정렬/필터용 보조 컬럼).
    주문 생성/금액/재고 판정 로직은 Mock과 동일하게 재사용(adapters.mock 헬퍼) — 저장소만 교체.

    ID 충돌 주의: ID는 `ord_NNNN` 시퀀스. 새 인스턴스는 기존 최대 시퀀스+1부터 발급해
    재시작·복원 후에도 충돌하지 않는다(인메모리 itertools.count의 영속 대체).
    """

    def __init__(self, db_path: str = "rubicon.db") -> None:
        self._conn = _connect(db_path)
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS orders ("
            "  id         TEXT PRIMARY KEY,"
            "  user_id    TEXT NOT NULL,"
            "  created_at TEXT,"
            "  data       TEXT NOT NULL"
            ")"
        )
        self._conn.commit()

    def _next_id(self) -> str:
        # 기존 최대 시퀀스를 읽어 +1 — 재시작 후에도 단조 증가(충돌 회피).
        rows = self._conn.execute("SELECT id FROM orders").fetchall()
        max_seq = 0
        for r in rows:
            try:
                max_seq = max(max_seq, int(str(r["id"]).split("_")[-1]))
            except (ValueError, IndexError):
                continue
        return f"ord_{max_seq + 1:04d}"

    def _save(self, order: Order) -> None:
        created = order.created_at.isoformat() if order.created_at else None
        self._conn.execute(
            "INSERT INTO orders (id, user_id, created_at, data) VALUES (?, ?, ?, ?) "
            "ON CONFLICT(id) DO UPDATE SET user_id = excluded.user_id, "
            "  created_at = excluded.created_at, data = excluded.data",
            (order.id, order.user_id, created, order.model_dump_json()),
        )
        self._conn.commit()

    def place_order(self, user_id: str, part_ids: list[str], confirmed: bool = False) -> Order:
        from ..adapters.mock import _parts, _summarize  # 재고/금액 로직 재사용(저장만 교체)
        from ..domain import OrderItem

        catalog = {p.id: p for p in _parts()}
        items, out_of_stock = [], []
        for pid in part_ids:
            part = catalog.get(pid)
            if part is None:
                continue
            if not part.in_stock:
                out_of_stock.append(pid)
                continue
            items.append(OrderItem(part_id=part.id, name=part.name, unit_price=part.price, qty=1))
        status = "DRAFT"
        if out_of_stock and not items:
            status = "FAILED"
        elif confirmed and items:
            status = "CONFIRMED"
        order = Order(id=self._next_id(), user_id=user_id, items=items, status=status,
                      summary=_summarize(items), created_at=datetime.now(timezone.utc))
        self._save(order)
        return order

    def place_pickup_order(
        self, user_id: str, part_ids: list[str], store_id: str, confirmed: bool = False
    ) -> Order:
        from ..adapters.mock import _parts
        from ..domain import OrderItem, OrderSummary

        catalog = {p.id: p for p in _parts()}
        items = [
            OrderItem(part_id=p.id, name=p.name, unit_price=p.price, qty=1)
            for pid in part_ids
            if (p := catalog.get(pid)) is not None and p.in_stock
        ]
        total = sum(i.line_total for i in items)
        order = Order(
            id=self._next_id(), user_id=user_id, items=items,
            status="CONFIRMED" if confirmed and items else "DRAFT",
            summary=OrderSummary(subtotal=total, shipping_fee=0, tax=0, discount=0, total=total),
            created_at=datetime.now(timezone.utc),
            fulfillment="pickup", store_id=store_id,
            pickup_status="RESERVED" if confirmed and items else None,
        )
        self._save(order)
        return order

    def get_order(self, order_id: str) -> Optional[Order]:
        row = self._conn.execute(
            "SELECT data FROM orders WHERE id = ?", (order_id,)
        ).fetchone()
        if row is None:
            return None
        return Order.model_validate_json(row["data"])

    def update_pickup_status(self, order_id: str, pickup_status: str) -> Order:
        order = self.get_order(order_id)
        if order is None:
            raise KeyError(order_id)
        order.pickup_status = pickup_status  # type: ignore[assignment]
        self._save(order)
        return order

    def cancel_order(self, order_id: str) -> Order:
        order = self.get_order(order_id)
        if order is None:
            raise KeyError(order_id)
        order.status = "CANCELLED"
        self._save(order)
        return order

    def refund_order(self, order_id: str) -> Order:
        order = self.get_order(order_id)
        if order is None:
            raise KeyError(order_id)
        order.status = "REFUNDED"
        self._save(order)
        return order

    def list_orders(self, user_id: Optional[str] = None) -> list[Order]:
        if user_id:
            rows = self._conn.execute(
                "SELECT data FROM orders WHERE user_id = ?", (user_id,)
            ).fetchall()
        else:
            rows = self._conn.execute("SELECT data FROM orders").fetchall()
        orders = [Order.model_validate_json(r["data"]) for r in rows]
        return sorted(
            orders,
            key=lambda o: o.created_at or datetime.min.replace(tzinfo=timezone.utc),
            reverse=True,
        )

    def reassign_user(self, from_user_id: str, to_user_id: str) -> int:
        """머지(게스트→로그인) — from_user_id 주문을 to_user_id로 re-key. 옮긴 건수 반환.

        각 행의 user_id 보조 컬럼과 JSON 내부 Order.user_id 둘 다 갱신한다(일관성)."""
        rows = self._conn.execute(
            "SELECT id, data FROM orders WHERE user_id = ?", (from_user_id,)
        ).fetchall()
        for r in rows:
            order = Order.model_validate_json(r["data"])
            order.user_id = to_user_id
            self._conn.execute(
                "UPDATE orders SET user_id = ?, data = ? WHERE id = ?",
                (to_user_id, order.model_dump_json(), r["id"]),
            )
        self._conn.commit()
        return len(rows)
