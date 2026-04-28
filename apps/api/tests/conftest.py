from datetime import UTC, datetime

import fakeredis.aioredis
import pytest
from fastapi.testclient import TestClient

from app.repository.auth.jwt_repository import JwtRepository
from fakes.fake_clock import FakeClock
from fakes.fake_id_generator import FakeIdGenerator
from fakes.fake_publisher import FakeEventPublisher
from fakes.fake_queue import FakeJobQueue
from fakes.fake_storage import FakeStorage
from fakes.in_memory_repos import InMemorySessionRepository, InMemoryShotRepository
from app.services.session_service import (
    SessionService,
)
from app.services.shot_service import ShotService
from app.services.export_service import ExportService


class _Container:
    """Simple test container for router tests (no dependency-injector)."""

    def __init__(self):
        self.sessions_repo = InMemorySessionRepository()
        self.shots_repo = InMemoryShotRepository()
        self.storage = FakeStorage()
        self.queue = FakeJobQueue()
        self.publisher = FakeEventPublisher()
        self.clock = FakeClock(datetime(2026, 4, 28, tzinfo=UTC))
        self.ids = FakeIdGenerator()
        self.jwt = JwtRepository(secret="x" * 32, issuer="golf-test", ttl_seconds=3600)

        self._session_service = SessionService(
            sessions_repo=self.sessions_repo,
            shots_repo=self.shots_repo,
            storage=self.storage,
            queue=self.queue,
            events=self.publisher,
            clock=self.clock,
            ids=self.ids,
        )
        self._shot_service = ShotService(
            sessions_repo=self.sessions_repo,
            shots_repo=self.shots_repo,
            events=self.publisher,
            clock=self.clock,
            ids=self.ids,
        )
        self._export_service = ExportService(
            sessions_repo=self.sessions_repo,
            storage=self.storage,
            ids=self.ids,
        )

    # --- session use-case delegation ---
    class _UcProxy:
        def __init__(self, svc, method):
            self._svc = svc
            self._method = method

        async def execute(self, inp):
            return await getattr(self._svc, self._method)(inp)

    @property
    def create_session(self):
        return self._UcProxy(self._session_service, "create")

    @property
    def request_upload_url(self):
        return self._UcProxy(self._session_service, "request_upload_url")

    @property
    def start_processing(self):
        return self._UcProxy(self._session_service, "start_processing")

    @property
    def list_sessions(self):
        return self._UcProxy(self._session_service, "list")

    @property
    def get_session(self):
        return self._UcProxy(self._session_service, "get_with_shots")

    @property
    def update_shot_boundary(self):
        return self._UcProxy(self._shot_service, "update_boundary")

    @property
    def add_manual_shot(self):
        return self._UcProxy(self._shot_service, "add_manual")

    @property
    def delete_shot(self):
        return self._UcProxy(self._shot_service, "delete")

    @property
    def export_session_zip(self):
        return self._UcProxy(self._export_service, "export")

    # redis for realtime tests
    redis = None


@pytest.fixture
def container() -> _Container:
    return _Container()


@pytest.fixture
def client(container) -> TestClient:
    from golf_api.main import create_app

    app = create_app(env="test")
    app.state.container = container
    return TestClient(app)


@pytest.fixture
def container_with_redis(container) -> _Container:
    container.redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    return container


@pytest.fixture
def client_with_redis(container_with_redis) -> TestClient:
    from golf_api.main import create_app

    app = create_app(env="test")
    app.state.container = container_with_redis
    return TestClient(app)
