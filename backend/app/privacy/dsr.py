"""DSR(데이터 주체 요청) 서비스 — 접근/내보내기·삭제·정정(ADR-0061).

상태 저장소는 이미 `user_id`로 키잉돼 있으므로(ADR-0049), DSR은 그 키로 데이터를
**모으고(export)·지우고(delete)·바로잡는다(rectify)**. 기존 Repository 시그니처는 바꾸지
않고 재사용한다(추가형). 삭제 메서드가 없는 저장소는 건너뛴다(best-effort, 비차단).
"""
from __future__ import annotations

from ..domain import User

# 정정 허용 프로필 필드(요구사항 4). 그 외 필드는 거부(ValueError → 400).
_RECTIFIABLE: tuple[str, ...] = ("display_name", "addresses", "preferences")


class DSRService:
    """컨테이너·UserDirectory를 받아 user_id로 DSR 워크플로를 수행.

    `directory`(UserDirectory)는 프로필 export/rectify·삭제에 쓰인다.
    """

    def __init__(self, container, directory) -> None:
        self._c = container
        self._dir = directory

    # ── 접근/내보내기(요구사항 2) ──────────────────────────────────────────
    def export(self, user_id: str) -> dict:
        """user_id로 키잉된 데이터를 JSON 직렬화 가능한 단일 구조로 모은다.

        없으면 빈 컬렉션(형태 보존). 프로필·동의·주문·대화 메모리·미해결 스레드·engagement.
        """
        profile = self._profile(user_id)
        memory = self._c.conversation_memory.get(user_id)
        return {
            "user_id": user_id,
            "profile": profile.model_dump(mode="json"),
            "consent": profile.consent.model_dump(mode="json"),
            "orders": [o.model_dump(mode="json") for o in self._c.order.history(user_id)],
            "conversation_memory": memory.model_dump(mode="json"),
            "open_loops": [
                loop.model_dump(mode="json")
                for loop in self._c.companion.open_loops_repo.list_open(user_id)
            ],
            "engagement": [
                rec.model_dump(mode="json") for rec in self._c.engagement.list(user_id)
            ],
        }

    # ── 삭제/잊힐 권리(요구사항 3) ─────────────────────────────────────────
    def delete(self, user_id: str) -> dict:
        """user_id 데이터를 best-effort 삭제, 저장소별 결과 요약 반환.

        삭제 메서드가 없는 저장소(인메모리 engagement·order 등)는 `skipped`로 표기하고
        흐름을 막지 않는다(요구사항 3.2).
        """
        summary: dict[str, str] = {}

        # 대화 메모리 — delete(user_id)
        conv = self._c.conversation_memory
        if hasattr(conv, "delete"):
            conv.delete(user_id)
            summary["conversation_memory"] = "deleted"
        else:
            summary["conversation_memory"] = "skipped"

        # 미해결 스레드 — clear(user_id)
        loops = self._c.companion.open_loops_repo
        if hasattr(loops, "clear"):
            loops.clear(user_id)
            summary["open_loops"] = "deleted"
        else:
            summary["open_loops"] = "skipped"

        # engagement — delete_user(user_id)(sqlite만; 인메모리는 미제공 → skip)
        eng = self._c.engagement
        if hasattr(eng, "delete_user"):
            eng.delete_user(user_id)
            summary["engagement"] = "deleted"
        else:
            summary["engagement"] = "skipped"

        # 주문 — OrderPort는 삭제 미제공(이력 보존 의무와 충돌 소지). skip(후속 retention).
        summary["orders"] = "skipped"

        # 프로필 — UserDirectory에서 제거(있으면)
        users = getattr(self._dir, "_users", None)
        if isinstance(users, dict) and user_id in users:
            del users[user_id]
            summary["profile"] = "deleted"
        else:
            summary["profile"] = "skipped"

        return summary

    # ── 정정(요구사항 4) ──────────────────────────────────────────────────
    def rectify(self, user_id: str, fields: dict) -> User:
        """허용 필드(display_name·addresses·preferences)만 갱신. 그 외는 ValueError."""
        unknown = [k for k in fields if k not in _RECTIFIABLE]
        if unknown:
            raise ValueError(f"non-rectifiable fields: {unknown}")
        profile = self._profile(user_id)
        # model_validate로 재구성 — addresses·preferences가 dict로 와도 도메인 타입으로 강제.
        updated = User.model_validate({**profile.model_dump(mode="python"), **fields})
        self._dir.upsert(updated)
        return updated

    # ── 내부 ──────────────────────────────────────────────────────────────
    def _profile(self, user_id: str) -> User:
        from ..principal import Principal
        return self._dir.get(Principal("user", user_id))
