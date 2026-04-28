from datetime import UTC, datetime

import pytest

from golf_application.errors import SessionNotFoundError
from golf_application.use_cases.get_session_with_shots import (
    GetSessionWithShotsInput,
    GetSessionWithShotsUseCase,
)
from golf_application.use_cases.list_sessions import (
    ListSessionsInput,
    ListSessionsUseCase,
)
from golf_domain.session import Session, SessionStatus
from golf_domain.shot import Shot, ShotSource
from golf_domain.value_objects import Confidence

from ..fakes.in_memory_repos import InMemorySessionRepository, InMemoryShotRepository


def _session(id: str, user_id: str | None = None) -> Session:
    now = datetime.now(UTC)
    return Session(
        id=id,
        user_id=user_id,
        raw_video_key=f"raw/{id}/v.mp4",
        status=SessionStatus.READY,
        pre_roll_seconds=2.0,
        post_roll_seconds=5.0,
        shot_count=0,
        duration_seconds=900.0,
        error=None,
        created_at=now,
        updated_at=now,
    )


def _shot(id: str, session_id: str, index: int) -> Shot:
    now = datetime.now(UTC)
    return Shot(
        id=id,
        session_id=session_id,
        index=index,
        t_impact=10.0,
        t_start=8.0,
        t_end=15.0,
        confidence=Confidence(value=0.9),
        source=ShotSource.AUTO,
        clip_key=None,
        created_at=now,
        updated_at=now,
    )


async def test_list_sessions_filters_by_user():
    repo = InMemorySessionRepository()
    await repo.add(_session("ses_1", user_id="u_1"))
    await repo.add(_session("ses_2", user_id="u_2"))
    await repo.add(_session("ses_3", user_id=None))

    uc = ListSessionsUseCase(sessions=repo)
    out = await uc.execute(ListSessionsInput(user_id="u_1"))
    assert [s.id for s in out] == ["ses_1"]


async def test_get_session_returns_session_and_shots_in_index_order():
    sessions = InMemorySessionRepository()
    shots = InMemoryShotRepository()
    await sessions.add(_session("ses_1"))
    await shots.add(_shot("shot_2", "ses_1", index=2))
    await shots.add(_shot("shot_1", "ses_1", index=1))

    uc = GetSessionWithShotsUseCase(sessions=sessions, shots=shots)
    out = await uc.execute(GetSessionWithShotsInput(session_id="ses_1"))
    assert out.session.id == "ses_1"
    assert [s.id for s in out.shots] == ["shot_1", "shot_2"]


async def test_get_session_raises_when_missing():
    sessions = InMemorySessionRepository()
    shots = InMemoryShotRepository()
    uc = GetSessionWithShotsUseCase(sessions=sessions, shots=shots)
    with pytest.raises(SessionNotFoundError):
        await uc.execute(GetSessionWithShotsInput(session_id="missing"))
