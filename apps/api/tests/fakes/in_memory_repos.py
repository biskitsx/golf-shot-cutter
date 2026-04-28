from app.services.errors import SessionNotFoundError, ShotNotFoundError
from app.core.models.ids import SessionId, ShotId, UserId
from app.core.models.session import Session
from app.core.models.shot import Shot


class InMemorySessionRepository:
    def __init__(self) -> None:
        self._items: dict[SessionId, Session] = {}

    async def add(self, session: Session) -> None:
        self._items[session.id] = session

    async def get(self, session_id: SessionId) -> Session:
        if session_id not in self._items:
            raise SessionNotFoundError(session_id)
        return self._items[session_id]

    async def list_for_user(self, user_id: UserId | None) -> list[Session]:
        return [s for s in self._items.values() if s.user_id == user_id]

    async def update(self, session: Session) -> None:
        if session.id not in self._items:
            raise SessionNotFoundError(session.id)
        self._items[session.id] = session


class InMemoryShotRepository:
    def __init__(self) -> None:
        self._items: dict[ShotId, Shot] = {}

    async def add(self, shot: Shot) -> None:
        self._items[shot.id] = shot

    async def add_many(self, shots: list[Shot]) -> None:
        for s in shots:
            self._items[s.id] = s

    async def get(self, shot_id: ShotId) -> Shot:
        if shot_id not in self._items:
            raise ShotNotFoundError(shot_id)
        return self._items[shot_id]

    async def list_by_session(self, session_id: SessionId) -> list[Shot]:
        return sorted(
            (s for s in self._items.values() if s.session_id == session_id),
            key=lambda s: s.index,
        )

    async def update(self, shot: Shot) -> None:
        if shot.id not in self._items:
            raise ShotNotFoundError(shot.id)
        self._items[shot.id] = shot

    async def delete(self, shot_id: ShotId) -> None:
        if shot_id not in self._items:
            raise ShotNotFoundError(shot_id)
        del self._items[shot_id]
