from datetime import UTC, datetime

import fakeredis.aioredis
import pytest
from fastapi.testclient import TestClient

from golf_api.deps.container import Container
from golf_api.main import create_app
from fakes.fake_clock import FakeClock
from fakes.fake_id_generator import FakeIdGenerator
from fakes.fake_publisher import FakeEventPublisher
from fakes.fake_queue import FakeJobQueue
from fakes.fake_storage import FakeStorage
from fakes.in_memory_repos import (
    InMemorySessionRepository,
    InMemoryShotRepository,
)
from golf_application.use_cases.add_manual_shot import AddManualShotUseCase
from golf_application.use_cases.create_session import CreateSessionUseCase
from golf_application.use_cases.delete_shot import DeleteShotUseCase
from golf_application.use_cases.export_session_zip import ExportSessionZipUseCase
from golf_application.use_cases.get_session_with_shots import (
    GetSessionWithShotsUseCase,
)
from golf_application.use_cases.list_sessions import ListSessionsUseCase
from golf_application.use_cases.process_video import ProcessVideoUseCase
from golf_application.use_cases.request_signed_upload_url import (
    RequestSignedUploadUrlUseCase,
)
from golf_application.use_cases.start_processing import StartProcessingUseCase
from golf_application.use_cases.update_shot_boundary import UpdateShotBoundaryUseCase
from golf_infrastructure.auth.jwt_service import JwtService


@pytest.fixture
def container() -> Container:
    sessions = InMemorySessionRepository()
    shots = InMemoryShotRepository()
    storage = FakeStorage()
    queue = FakeJobQueue()
    publisher = FakeEventPublisher()
    clock = FakeClock(datetime(2026, 4, 28, tzinfo=UTC))
    ids = FakeIdGenerator()
    jwt = JwtService(secret="x" * 32, issuer="golf-test", ttl_seconds=3600)

    return Container(
        settings=None,
        mongo_client=None,
        redis=None,
        celery=None,
        jwt=jwt,
        sessions_repo=sessions,
        shots_repo=shots,
        storage=storage,
        queue=queue,
        publisher=publisher,
        clock=clock,
        ids=ids,
        create_session=CreateSessionUseCase(
            sessions=sessions, storage=storage, clock=clock, ids=ids
        ),
        request_upload_url=RequestSignedUploadUrlUseCase(sessions=sessions, storage=storage),
        start_processing=StartProcessingUseCase(
            sessions=sessions, queue=queue, events=publisher, clock=clock
        ),
        list_sessions=ListSessionsUseCase(sessions=sessions),
        get_session=GetSessionWithShotsUseCase(sessions=sessions, shots=shots),
        update_shot_boundary=UpdateShotBoundaryUseCase(
            sessions=sessions, shots=shots, events=publisher, clock=clock
        ),
        add_manual_shot=AddManualShotUseCase(
            sessions=sessions, shots=shots, events=publisher, clock=clock, ids=ids
        ),
        delete_shot=DeleteShotUseCase(
            sessions=sessions, shots=shots, events=publisher, clock=clock
        ),
        process_video=ProcessVideoUseCase(
            sessions=sessions, shots=shots, events=publisher, clock=clock, ids=ids
        ),
        export_session_zip=ExportSessionZipUseCase(sessions=sessions, storage=storage, ids=ids),
    )


@pytest.fixture
def client(container) -> TestClient:
    app = create_app(env="test")
    app.state.container = container
    return TestClient(app)


@pytest.fixture
def container_with_redis(container) -> Container:
    container.redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    return container


@pytest.fixture
def client_with_redis(container_with_redis) -> TestClient:
    app = create_app(env="test")
    app.state.container = container_with_redis
    return TestClient(app)
