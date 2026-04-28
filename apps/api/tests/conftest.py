from datetime import UTC, datetime

import fakeredis.aioredis
import pytest
from fastapi.testclient import TestClient

from app.core.container import Container
from app.main import create_app
from app.repository.auth.jwt_repository import JwtRepository
from fakes.fake_clock import FakeClock
from fakes.fake_id_generator import FakeIdGenerator
from fakes.fake_publisher import FakeEventPublisher
from fakes.fake_queue import FakeJobQueue
from fakes.fake_storage import FakeStorage
from fakes.in_memory_repos import (
    InMemorySessionRepository,
    InMemoryShotRepository,
)


_WIRING_MODULES = [
    "app.api.v1.endpoints.health",
    "app.api.v1.endpoints.auth",
    "app.api.v1.endpoints.sessions",
    "app.api.v1.endpoints.shots",
    "app.api.v1.endpoints.upload",
    "app.api.v1.endpoints.export",
    "app.api.v1.endpoints.realtime",
    "app.deps.auth",
]


@pytest.fixture
def container():
    c = Container()
    c.sessions_repo.override(InMemorySessionRepository())
    c.shots_repo.override(InMemoryShotRepository())
    c.storage_repo.override(FakeStorage())
    c.queue_repo.override(FakeJobQueue())
    c.publisher_repo.override(FakeEventPublisher())
    c.clock.override(FakeClock(datetime(2026, 4, 28, tzinfo=UTC)))
    c.ids.override(FakeIdGenerator())
    c.jwt_repo.override(JwtRepository(secret="x" * 32, issuer="golf-test", ttl_seconds=3600))
    c.wire(modules=_WIRING_MODULES)
    yield c
    c.unwire()


@pytest.fixture
def client(container):
    app = create_app(env="test")
    app.state.container = container
    return TestClient(app)


@pytest.fixture
def container_with_redis(container):
    container.redis.override(fakeredis.aioredis.FakeRedis(decode_responses=True))
    return container


@pytest.fixture
def client_with_redis(container_with_redis):
    app = create_app(env="test")
    app.state.container = container_with_redis
    return TestClient(app)
