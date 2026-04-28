# Plan 2 — Backend MVP (Infrastructure + apps/api)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the production backend: real MongoDB / Cloudflare R2 / Redis adapters in `libs/infrastructure`, then wire them through FastAPI routers in `apps/api` with JWT cookie auth and SSE. After this plan, you can `curl` a running API and create/list/edit sessions and shots end-to-end. The video-processing worker is still a stub — that's Plan 3.

**Architecture:** Plan 1's pure use cases stay untouched. Plan 2 supplies the adapters they depend on. `apps/api` is a thin FastAPI host: routers translate HTTP ↔ use case input/output, DI container wires use cases with infra adapters. Authoritative business logic remains in `libs/application` and `libs/domain`.

**Tech Stack:** Python 3.11+, Motor (async MongoDB), boto3 + R2, Redis (queue + pub/sub), Celery (producer only), python-jose (JWT), sse-starlette, FastAPI, Pydantic v2, datamodel-code-generator (contracts → Pydantic), python-ulid, mongomock-motor + moto + fakeredis (tests), Docker Compose (local dev).

**Spec reference:** `docs/superpowers/specs/2026-04-27-golf-shot-cutter-design.md` sections 4 (Architecture), 5.2 (apps/api), 5.5 (libs/infrastructure), 5.6 (contracts), 5.8 (Mongo data model), 7 (Errors), 8 (Testing).

**Prerequisite:** Plan 1 complete. HEAD ≥ tag `v0.1.0-foundation`. All 41 pytest + 3 vitest tests passing.

---

## File Structure

```
golf-shot-cutter/
  pyproject.toml                # add datamodel-code-generator to dev-deps
  .importlinter                 # restore golf_infrastructure + golf_api
  docker-compose.dev.yml        # NEW — local mongo / redis / minio
  .env.example                  # NEW — template env file

  libs/
    contracts/
      package.json              # add codegen script + datamodel-code-generator
      scripts/
        sync-python.mjs         # NEW — zod → JSON Schema → Pydantic
      generated/
        python/golf_contracts/  # NEW (output) — Pydantic v2 DTOs
          __init__.py           # re-exports
          sessions.py
          shots.py
          events.py
        ts/                     # (unused in Plan 2; placeholder for Plan 4)

    infrastructure/             # NEW — uv member golf-infrastructure
      pyproject.toml
      src/golf_infrastructure/
        __init__.py
        settings.py             # Pydantic BaseSettings
        clock.py                # SystemClock
        ids.py                  # UlidIdGenerator
        mongo/
          __init__.py
          client.py             # Motor client factory
          documents.py          # to_doc / from_doc mappers
          indexes.py            # ensure_indexes()
          session_repository.py
          shot_repository.py
        r2/
          __init__.py
          storage_gateway.py    # R2StorageGateway (boto3)
        queue/
          __init__.py
          celery_app.py         # Celery() instance, routes
          job_queue.py          # CeleryJobQueue (producer)
          event_publisher.py    # RedisEventPublisher (pub/sub)
        auth/
          __init__.py
          jwt_service.py        # encode/decode + cookie helpers
        logging/
          __init__.py
          structured.py         # structlog config
      tests/
        __init__.py
        test_settings.py
        test_clock_and_ids.py
        mongo/
          __init__.py
          test_session_repository.py
          test_shot_repository.py
        r2/
          test_storage_gateway.py
        queue/
          test_job_queue.py
          test_event_publisher.py
        auth/
          test_jwt_service.py

  apps/
    api/                        # NEW — uv member golf-api
      pyproject.toml
      Dockerfile
      src/golf_api/
        __init__.py
        main.py                 # FastAPI app + lifespan + middleware
        settings.py             # re-exports infra Settings
        deps/
          __init__.py
          container.py          # build_container() — wires use cases + adapters
          auth.py               # CurrentUser dependency (JWT cookie)
        middleware/
          __init__.py
          request_id.py
          error_handler.py
        routers/
          __init__.py
          health.py
          auth.py
          sessions.py
          shots.py
          upload.py
          export.py
          realtime.py
      tests/
        __init__.py
        conftest.py             # TestClient + DI overrides + fakes from Plan 1
        test_health.py
        test_auth.py
        test_sessions.py
        test_shots.py
        test_upload.py
        test_export.py
        test_realtime.py
```

---

## Task 1: Restore `.importlinter` for Plan 2 packages + add infra workspace member

**Files:**
- Modify: `.importlinter`
- Modify: `pyproject.toml` (root) — add `datamodel-code-generator` to dev deps

- [ ] **Step 1: Update `.importlinter` to include golf_infrastructure + golf_api**

Write `.importlinter`:
```ini
# Plan 2 scope: golf_domain + golf_application + golf_infrastructure + golf_api.
# apps/worker arrives in Plan 3; restore that row of the layered contract then.

[importlinter]
root_packages =
    golf_domain
    golf_application
    golf_infrastructure
    golf_api

[importlinter:contract:layered]
name = Clean Architecture layered dependency
type = layers
layers =
    golf_api
    golf_infrastructure
    golf_application
    golf_domain
```

- [ ] **Step 2: Add codegen tool to root dev-deps**

Edit `pyproject.toml`:
```toml
[tool.uv]
dev-dependencies = [
    "pytest>=8.3",
    "pytest-asyncio>=0.24",
    "import-linter>=2.1",
    "ruff>=0.7",
    "pre-commit>=3.8",
    "datamodel-code-generator>=0.26",
    "mongomock-motor>=0.0.34",
    "moto[s3]>=5.0",
    "fakeredis>=2.26",
    "httpx>=0.27"
]
```

Run: `uv sync`. Expected: deps resolved, no errors.

- [ ] **Step 3: Verify import-linter still passes**

Run: `uv run lint-imports`
Expected:
```
Could not find package 'golf_infrastructure' in your Python path.
```
This is expected — golf_infrastructure doesn't exist yet (Task 2 creates it). Don't commit yet.

- [ ] **Step 4: Commit**

```bash
git add .importlinter pyproject.toml uv.lock
git commit -m "chore: prep importlinter + dev deps for Plan 2"
```

---

## Task 2: Scaffold `libs/infrastructure` package + Settings module

**Files:**
- Create: `libs/infrastructure/pyproject.toml`
- Create: `libs/infrastructure/src/golf_infrastructure/__init__.py`
- Create: `libs/infrastructure/src/golf_infrastructure/settings.py`
- Create: `libs/infrastructure/tests/__init__.py`
- Create: `libs/infrastructure/tests/test_settings.py`

- [ ] **Step 1: Create `libs/infrastructure/pyproject.toml`**

```toml
[project]
name = "golf-infrastructure"
version = "0.0.0"
requires-python = ">=3.11"
dependencies = [
    "pydantic>=2.9",
    "pydantic-settings>=2.5",
    "motor>=3.6",
    "boto3>=1.35",
    "celery>=5.4",
    "redis>=5.1",
    "python-jose[cryptography]>=3.3",
    "python-ulid>=2.7",
    "structlog>=24.4",
    "golf-domain",
    "golf-application"
]

[tool.uv.sources]
golf-domain = { workspace = true }
golf-application = { workspace = true }

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/golf_infrastructure"]
```

- [ ] **Step 2: Add to root workspace**

Confirm `pyproject.toml` (root) `[tool.uv.workspace].members` already lists `libs/infrastructure`. (It does — set in Plan 1 Task 2.)

- [ ] **Step 3: Sync workspace**

Run: `uv sync --all-packages`
Expected: `golf-infrastructure==0.0.0` resolved + installed; new transitive deps installed (motor, boto3, etc.).

- [ ] **Step 4: Write failing test FIRST: `libs/infrastructure/tests/test_settings.py`**

```python
import os

import pytest

from golf_infrastructure.settings import Settings


def test_settings_load_from_env(monkeypatch):
    monkeypatch.setenv("MONGODB_URI", "mongodb://test:27017")
    monkeypatch.setenv("MONGODB_DATABASE", "golf_test")
    monkeypatch.setenv("REDIS_URL", "redis://test:6379/0")
    monkeypatch.setenv("R2_ENDPOINT", "https://r2.test")
    monkeypatch.setenv("R2_ACCESS_KEY", "ak")
    monkeypatch.setenv("R2_SECRET_KEY", "sk")
    monkeypatch.setenv("R2_BUCKET", "golf-test")
    monkeypatch.setenv("JWT_SECRET", "x" * 32)
    monkeypatch.setenv("JWT_ISSUER", "golf-shot-cutter")
    s = Settings()
    assert s.mongodb_database == "golf_test"
    assert s.r2_bucket == "golf-test"
    assert s.jwt_issuer == "golf-shot-cutter"
    assert s.signed_url_ttl_seconds == 900  # default


def test_settings_missing_required_raises(monkeypatch):
    for var in [
        "MONGODB_URI", "MONGODB_DATABASE", "REDIS_URL",
        "R2_ENDPOINT", "R2_ACCESS_KEY", "R2_SECRET_KEY", "R2_BUCKET",
        "JWT_SECRET", "JWT_ISSUER",
    ]:
        monkeypatch.delenv(var, raising=False)
    with pytest.raises(Exception):
        Settings()
```

- [ ] **Step 5: Run failing test**

Run: `uv run pytest libs/infrastructure/tests/test_settings.py -v`
Expected: FAIL — module `golf_infrastructure.settings` not found.

- [ ] **Step 6: Implement `libs/infrastructure/src/golf_infrastructure/__init__.py`**

```python
"""Infrastructure adapters: real ports for golf_application."""
```

- [ ] **Step 7: Implement `libs/infrastructure/src/golf_infrastructure/settings.py`**

```python
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    mongodb_uri: str = Field(alias="MONGODB_URI")
    mongodb_database: str = Field(alias="MONGODB_DATABASE")

    redis_url: str = Field(alias="REDIS_URL")

    r2_endpoint: str = Field(alias="R2_ENDPOINT")
    r2_access_key: str = Field(alias="R2_ACCESS_KEY")
    r2_secret_key: str = Field(alias="R2_SECRET_KEY")
    r2_bucket: str = Field(alias="R2_BUCKET")
    r2_region: str = Field(default="auto", alias="R2_REGION")

    jwt_secret: str = Field(min_length=32, alias="JWT_SECRET")
    jwt_issuer: str = Field(alias="JWT_ISSUER")
    jwt_ttl_seconds: int = Field(default=3600, alias="JWT_TTL_SECONDS")

    signed_url_ttl_seconds: int = Field(default=900, alias="SIGNED_URL_TTL_SECONDS")

    cors_origins: list[str] = Field(default_factory=list, alias="CORS_ORIGINS")
```

- [ ] **Step 8: Run passing test**

Run: `uv run pytest libs/infrastructure/tests/test_settings.py -v`
Expected: PASS — both tests green.

- [ ] **Step 9: Commit**

```bash
git add libs/infrastructure pyproject.toml uv.lock
git commit -m "feat(infrastructure): scaffold golf-infrastructure + Settings"
```

---

## Task 3: Implement `SystemClock` + `UlidIdGenerator` (TDD)

**Files:**
- Create: `libs/infrastructure/src/golf_infrastructure/clock.py`
- Create: `libs/infrastructure/src/golf_infrastructure/ids.py`
- Create: `libs/infrastructure/tests/test_clock_and_ids.py`

- [ ] **Step 1: Write failing test**

```python
from datetime import UTC, datetime

from golf_infrastructure.clock import SystemClock
from golf_infrastructure.ids import UlidIdGenerator


def test_system_clock_returns_aware_utc_now():
    c = SystemClock()
    n = c.now()
    assert n.tzinfo is not None
    assert n.tzinfo.utcoffset(n) == UTC.utcoffset(n)


def test_ulid_id_generator_emits_prefixed_ids():
    ids = UlidIdGenerator()
    s = ids.session_id()
    sh = ids.shot_id()
    e = ids.export_id()
    assert s.startswith("ses_") and len(s) == 4 + 26
    assert sh.startswith("shot_") and len(sh) == 5 + 26
    assert e.startswith("exp_") and len(e) == 4 + 26


def test_ulid_id_generator_emits_unique_ids():
    ids = UlidIdGenerator()
    seen = {ids.session_id() for _ in range(100)}
    assert len(seen) == 100
```

- [ ] **Step 2: Run failing test**

Run: `uv run pytest libs/infrastructure/tests/test_clock_and_ids.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement `clock.py`**

```python
from datetime import UTC, datetime


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(UTC)
```

- [ ] **Step 4: Implement `ids.py`**

```python
from ulid import ULID


class UlidIdGenerator:
    def _ulid(self) -> str:
        return str(ULID())

    def session_id(self) -> str:
        return f"ses_{self._ulid()}"

    def shot_id(self) -> str:
        return f"shot_{self._ulid()}"

    def export_id(self) -> str:
        return f"exp_{self._ulid()}"
```

- [ ] **Step 5: Run passing test**

Run: `uv run pytest libs/infrastructure/tests/test_clock_and_ids.py -v`
Expected: PASS — 3 tests green.

- [ ] **Step 6: Commit**

```bash
git add libs/infrastructure
git commit -m "feat(infrastructure): add SystemClock + UlidIdGenerator"
```

---

## Task 4: Mongo client factory + document mappers (TDD)

**Files:**
- Create: `libs/infrastructure/src/golf_infrastructure/mongo/__init__.py`
- Create: `libs/infrastructure/src/golf_infrastructure/mongo/client.py`
- Create: `libs/infrastructure/src/golf_infrastructure/mongo/documents.py`
- Create: `libs/infrastructure/tests/mongo/__init__.py`
- Create: `libs/infrastructure/tests/mongo/test_documents.py`

- [ ] **Step 1: Write failing test for mappers: `libs/infrastructure/tests/mongo/test_documents.py`**

```python
from datetime import UTC, datetime

from golf_domain.session import Session, SessionError, SessionStatus
from golf_domain.shot import Shot, ShotSource
from golf_domain.value_objects import Confidence
from golf_infrastructure.mongo.documents import (
    session_from_doc,
    session_to_doc,
    shot_from_doc,
    shot_to_doc,
)


def _ts() -> datetime:
    return datetime(2026, 4, 28, 10, 0, tzinfo=UTC)


def test_session_round_trip():
    s = Session(
        id="ses_abc",
        user_id=None,
        raw_video_key="raw/ses_abc/v.mp4",
        status=SessionStatus.READY,
        pre_roll_seconds=2.0,
        post_roll_seconds=5.0,
        shot_count=2,
        duration_seconds=900.0,
        error=None,
        created_at=_ts(),
        updated_at=_ts(),
    )
    doc = session_to_doc(s)
    assert doc["_id"] == "ses_abc"
    assert doc["status"] == "ready"
    back = session_from_doc(doc)
    assert back == s


def test_session_round_trip_with_error():
    s = Session(
        id="ses_x",
        user_id="u_1",
        raw_video_key="raw/ses_x/v.mp4",
        status=SessionStatus.FAILED,
        pre_roll_seconds=2.0,
        post_roll_seconds=5.0,
        shot_count=0,
        duration_seconds=0.0,
        error=SessionError(stage="audio_onset", message="bad codec"),
        created_at=_ts(),
        updated_at=_ts(),
    )
    back = session_from_doc(session_to_doc(s))
    assert back.error is not None
    assert back.error.stage == "audio_onset"


def test_shot_round_trip():
    sh = Shot(
        id="shot_1",
        session_id="ses_abc",
        index=1,
        t_impact=10.0,
        t_start=8.0,
        t_end=15.0,
        confidence=Confidence(value=0.91),
        source=ShotSource.AUTO,
        clip_key="clips/ses_abc/shot_001.mp4",
        created_at=_ts(),
        updated_at=_ts(),
    )
    back = shot_from_doc(shot_to_doc(sh))
    assert back == sh
    assert back.confidence.value == 0.91
```

- [ ] **Step 2: Run failing test**

Run: `uv run pytest libs/infrastructure/tests/mongo/test_documents.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement `mongo/__init__.py`**

```python
```
(empty)

- [ ] **Step 4: Implement `mongo/client.py`**

```python
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase


def make_client(uri: str) -> AsyncIOMotorClient:
    return AsyncIOMotorClient(uri, tz_aware=True)


def get_database(client: AsyncIOMotorClient, name: str) -> AsyncIOMotorDatabase:
    return client[name]
```

- [ ] **Step 5: Implement `mongo/documents.py`**

```python
from typing import Any

from golf_domain.session import Session, SessionError, SessionStatus
from golf_domain.shot import Shot, ShotSource
from golf_domain.value_objects import Confidence


def session_to_doc(s: Session) -> dict[str, Any]:
    return {
        "_id": s.id,
        "userId": s.user_id,
        "rawVideoKey": s.raw_video_key,
        "status": s.status.value,
        "preRollSeconds": s.pre_roll_seconds,
        "postRollSeconds": s.post_roll_seconds,
        "shotCount": s.shot_count,
        "durationSeconds": s.duration_seconds,
        "error": (
            {"stage": s.error.stage, "message": s.error.message}
            if s.error is not None
            else None
        ),
        "createdAt": s.created_at,
        "updatedAt": s.updated_at,
    }


def session_from_doc(d: dict[str, Any]) -> Session:
    err_doc = d.get("error")
    return Session(
        id=d["_id"],
        user_id=d.get("userId"),
        raw_video_key=d["rawVideoKey"],
        status=SessionStatus(d["status"]),
        pre_roll_seconds=d["preRollSeconds"],
        post_roll_seconds=d["postRollSeconds"],
        shot_count=d.get("shotCount", 0),
        duration_seconds=d["durationSeconds"],
        error=(
            SessionError(stage=err_doc["stage"], message=err_doc["message"])
            if err_doc
            else None
        ),
        created_at=d["createdAt"],
        updated_at=d["updatedAt"],
    )


def shot_to_doc(sh: Shot) -> dict[str, Any]:
    return {
        "_id": sh.id,
        "sessionId": sh.session_id,
        "index": sh.index,
        "tImpact": sh.t_impact,
        "tStart": sh.t_start,
        "tEnd": sh.t_end,
        "confidence": sh.confidence.value,
        "source": sh.source.value,
        "clipKey": sh.clip_key,
        "createdAt": sh.created_at,
        "updatedAt": sh.updated_at,
    }


def shot_from_doc(d: dict[str, Any]) -> Shot:
    return Shot(
        id=d["_id"],
        session_id=d["sessionId"],
        index=d["index"],
        t_impact=d["tImpact"],
        t_start=d["tStart"],
        t_end=d["tEnd"],
        confidence=Confidence(value=d["confidence"]),
        source=ShotSource(d["source"]),
        clip_key=d.get("clipKey"),
        created_at=d["createdAt"],
        updated_at=d["updatedAt"],
    )
```

- [ ] **Step 6: Run passing test**

Run: `uv run pytest libs/infrastructure/tests/mongo/test_documents.py -v`
Expected: PASS — 3/3.

- [ ] **Step 7: Commit**

```bash
git add libs/infrastructure
git commit -m "feat(infrastructure): mongo client + Session/Shot document mappers"
```

---

## Task 5: `MongoSessionRepository` (TDD with mongomock-motor)

**Files:**
- Create: `libs/infrastructure/src/golf_infrastructure/mongo/session_repository.py`
- Create: `libs/infrastructure/tests/mongo/test_session_repository.py`

- [ ] **Step 1: Write failing test**

```python
from datetime import UTC, datetime

import pytest
from mongomock_motor import AsyncMongoMockClient

from golf_application.errors import SessionNotFoundError
from golf_domain.session import Session, SessionStatus
from golf_infrastructure.mongo.session_repository import MongoSessionRepository


def _make(id: str = "ses_1", user_id: str | None = None) -> Session:
    now = datetime.now(UTC)
    return Session(
        id=id,
        user_id=user_id,
        raw_video_key=f"raw/{id}/v.mp4",
        status=SessionStatus.QUEUED,
        pre_roll_seconds=2.0,
        post_roll_seconds=5.0,
        shot_count=0,
        duration_seconds=900.0,
        error=None,
        created_at=now,
        updated_at=now,
    )


@pytest.fixture
def repo():
    db = AsyncMongoMockClient()["test"]
    return MongoSessionRepository(db)


async def test_add_then_get(repo):
    s = _make()
    await repo.add(s)
    fetched = await repo.get("ses_1")
    assert fetched.id == "ses_1"
    assert fetched.status is SessionStatus.QUEUED


async def test_get_missing_raises(repo):
    with pytest.raises(SessionNotFoundError):
        await repo.get("missing")


async def test_update_persists_status_change(repo):
    s = _make()
    await repo.add(s)
    moved = s.mark_processing(now=datetime.now(UTC))
    await repo.update(moved)
    fetched = await repo.get("ses_1")
    assert fetched.status is SessionStatus.PROCESSING


async def test_update_missing_raises(repo):
    with pytest.raises(SessionNotFoundError):
        await repo.update(_make("ses_missing"))


async def test_list_for_user_filters_correctly(repo):
    await repo.add(_make("ses_a", user_id="u_1"))
    await repo.add(_make("ses_b", user_id="u_2"))
    await repo.add(_make("ses_c", user_id=None))
    rows = await repo.list_for_user("u_1")
    assert {s.id for s in rows} == {"ses_a"}
    rows_anon = await repo.list_for_user(None)
    assert {s.id for s in rows_anon} == {"ses_c"}
```

- [ ] **Step 2: Run failing test**

Run: `uv run pytest libs/infrastructure/tests/mongo/test_session_repository.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement `mongo/session_repository.py`**

```python
from motor.motor_asyncio import AsyncIOMotorDatabase

from golf_application.errors import SessionNotFoundError
from golf_domain.ids import SessionId, UserId
from golf_domain.session import Session

from .documents import session_from_doc, session_to_doc


class MongoSessionRepository:
    def __init__(self, db: AsyncIOMotorDatabase) -> None:
        self._col = db["sessions"]

    async def add(self, session: Session) -> None:
        await self._col.insert_one(session_to_doc(session))

    async def get(self, session_id: SessionId) -> Session:
        doc = await self._col.find_one({"_id": session_id})
        if doc is None:
            raise SessionNotFoundError(session_id)
        return session_from_doc(doc)

    async def list_for_user(self, user_id: UserId | None) -> list[Session]:
        cursor = self._col.find({"userId": user_id}).sort("createdAt", -1)
        return [session_from_doc(d) async for d in cursor]

    async def update(self, session: Session) -> None:
        result = await self._col.replace_one(
            {"_id": session.id}, session_to_doc(session)
        )
        if result.matched_count == 0:
            raise SessionNotFoundError(session.id)
```

- [ ] **Step 4: Run passing test**

Run: `uv run pytest libs/infrastructure/tests/mongo/test_session_repository.py -v`
Expected: PASS — 5/5.

- [ ] **Step 5: Commit**

```bash
git add libs/infrastructure
git commit -m "feat(infrastructure): MongoSessionRepository"
```

---

## Task 6: `MongoShotRepository` (TDD with mongomock-motor)

**Files:**
- Create: `libs/infrastructure/src/golf_infrastructure/mongo/shot_repository.py`
- Create: `libs/infrastructure/tests/mongo/test_shot_repository.py`

- [ ] **Step 1: Write failing test**

```python
from datetime import UTC, datetime

import pytest
from mongomock_motor import AsyncMongoMockClient

from golf_application.errors import ShotNotFoundError
from golf_domain.shot import Shot, ShotSource
from golf_domain.value_objects import Confidence
from golf_infrastructure.mongo.shot_repository import MongoShotRepository


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


@pytest.fixture
def repo():
    db = AsyncMongoMockClient()["test"]
    return MongoShotRepository(db)


async def test_add_get_round_trip(repo):
    await repo.add(_shot("shot_1", "ses_1", 1))
    fetched = await repo.get("shot_1")
    assert fetched.index == 1


async def test_get_missing_raises(repo):
    with pytest.raises(ShotNotFoundError):
        await repo.get("nope")


async def test_add_many_inserts_all(repo):
    await repo.add_many(
        [
            _shot("shot_a", "ses_1", 1),
            _shot("shot_b", "ses_1", 2),
        ]
    )
    rows = await repo.list_by_session("ses_1")
    assert [s.id for s in rows] == ["shot_a", "shot_b"]


async def test_list_by_session_sorts_by_index(repo):
    await repo.add(_shot("shot_b", "ses_1", 2))
    await repo.add(_shot("shot_a", "ses_1", 1))
    await repo.add(_shot("shot_other", "ses_2", 1))
    rows = await repo.list_by_session("ses_1")
    assert [s.index for s in rows] == [1, 2]


async def test_update_persists_changes(repo):
    s = _shot("shot_1", "ses_1", 1)
    await repo.add(s)
    moved = s.adjust_boundary(t_start=7.0, t_end=16.0, now=datetime.now(UTC))
    await repo.update(moved)
    back = await repo.get("shot_1")
    assert back.t_start == 7.0


async def test_update_missing_raises(repo):
    with pytest.raises(ShotNotFoundError):
        await repo.update(_shot("missing", "ses_1", 1))


async def test_delete_removes(repo):
    await repo.add(_shot("shot_1", "ses_1", 1))
    await repo.delete("shot_1")
    with pytest.raises(ShotNotFoundError):
        await repo.get("shot_1")


async def test_delete_missing_raises(repo):
    with pytest.raises(ShotNotFoundError):
        await repo.delete("nope")
```

- [ ] **Step 2: Run failing test**

Run: `uv run pytest libs/infrastructure/tests/mongo/test_shot_repository.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement `mongo/shot_repository.py`**

```python
from motor.motor_asyncio import AsyncIOMotorDatabase

from golf_application.errors import ShotNotFoundError
from golf_domain.ids import SessionId, ShotId
from golf_domain.shot import Shot

from .documents import shot_from_doc, shot_to_doc


class MongoShotRepository:
    def __init__(self, db: AsyncIOMotorDatabase) -> None:
        self._col = db["shots"]

    async def add(self, shot: Shot) -> None:
        await self._col.insert_one(shot_to_doc(shot))

    async def add_many(self, shots: list[Shot]) -> None:
        if not shots:
            return
        await self._col.insert_many([shot_to_doc(s) for s in shots])

    async def get(self, shot_id: ShotId) -> Shot:
        doc = await self._col.find_one({"_id": shot_id})
        if doc is None:
            raise ShotNotFoundError(shot_id)
        return shot_from_doc(doc)

    async def list_by_session(self, session_id: SessionId) -> list[Shot]:
        cursor = self._col.find({"sessionId": session_id}).sort("index", 1)
        return [shot_from_doc(d) async for d in cursor]

    async def update(self, shot: Shot) -> None:
        result = await self._col.replace_one({"_id": shot.id}, shot_to_doc(shot))
        if result.matched_count == 0:
            raise ShotNotFoundError(shot.id)

    async def delete(self, shot_id: ShotId) -> None:
        result = await self._col.delete_one({"_id": shot_id})
        if result.deleted_count == 0:
            raise ShotNotFoundError(shot_id)
```

- [ ] **Step 4: Run passing test**

Run: `uv run pytest libs/infrastructure/tests/mongo/test_shot_repository.py -v`
Expected: PASS — 8/8.

- [ ] **Step 5: Commit**

```bash
git add libs/infrastructure
git commit -m "feat(infrastructure): MongoShotRepository"
```

---

## Task 7: Mongo indexes setup

**Files:**
- Create: `libs/infrastructure/src/golf_infrastructure/mongo/indexes.py`
- Create: `libs/infrastructure/tests/mongo/test_indexes.py`

- [ ] **Step 1: Write failing test**

```python
import pytest
from mongomock_motor import AsyncMongoMockClient

from golf_infrastructure.mongo.indexes import ensure_indexes


@pytest.fixture
def db():
    return AsyncMongoMockClient()["test"]


async def test_ensure_indexes_creates_expected_keys(db):
    await ensure_indexes(db)
    sess_indexes = await db["sessions"].index_information()
    shot_indexes = await db["shots"].index_information()
    # session index on (userId, createdAt desc) — name varies; check at least one exists for userId
    assert any("userId" in info["key"][0] for info in sess_indexes.values() if info.get("key"))
    # shot index on (sessionId, index)
    assert any(
        "sessionId" in [pair[0] for pair in info["key"]]
        for info in shot_indexes.values()
        if info.get("key")
    )


async def test_ensure_indexes_is_idempotent(db):
    await ensure_indexes(db)
    await ensure_indexes(db)  # no error on second run
```

- [ ] **Step 2: Run failing test**

Run: `uv run pytest libs/infrastructure/tests/mongo/test_indexes.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement `mongo/indexes.py`**

```python
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import ASCENDING, DESCENDING


async def ensure_indexes(db: AsyncIOMotorDatabase) -> None:
    await db["sessions"].create_index(
        [("userId", ASCENDING), ("createdAt", DESCENDING)],
        name="userId_createdAt",
    )
    await db["sessions"].create_index(
        [("status", ASCENDING)], name="status"
    )
    await db["shots"].create_index(
        [("sessionId", ASCENDING), ("index", ASCENDING)],
        name="sessionId_index",
        unique=True,
    )
```

- [ ] **Step 4: Run passing test**

Run: `uv run pytest libs/infrastructure/tests/mongo/test_indexes.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add libs/infrastructure
git commit -m "feat(infrastructure): mongo index setup"
```

---

## Task 8: `R2StorageGateway` (TDD with moto)

**Files:**
- Create: `libs/infrastructure/src/golf_infrastructure/r2/__init__.py`
- Create: `libs/infrastructure/src/golf_infrastructure/r2/storage_gateway.py`
- Create: `libs/infrastructure/tests/r2/__init__.py`
- Create: `libs/infrastructure/tests/r2/test_storage_gateway.py`

- [ ] **Step 1: Write failing test**

```python
import boto3
import pytest
from moto import mock_aws

from golf_infrastructure.r2.storage_gateway import R2StorageGateway


@pytest.fixture
def s3_setup():
    with mock_aws():
        client = boto3.client(
            "s3",
            aws_access_key_id="ak",
            aws_secret_access_key="sk",
            region_name="us-east-1",
        )
        client.create_bucket(Bucket="golf-test")
        yield client


async def test_signed_put_url_contains_key_and_expiry(s3_setup):
    gw = R2StorageGateway(
        endpoint=None,  # use default for moto
        access_key="ak",
        secret_key="sk",
        bucket="golf-test",
        region="us-east-1",
        ttl_seconds=900,
    )
    out = await gw.signed_put_url("raw/ses_1/v.mp4", content_type="video/mp4")
    assert "raw/ses_1/v.mp4" in out.url
    assert out.expires_at is not None


async def test_signed_get_url_returns_signed(s3_setup):
    gw = R2StorageGateway(
        endpoint=None,
        access_key="ak",
        secret_key="sk",
        bucket="golf-test",
        region="us-east-1",
        ttl_seconds=900,
    )
    out = await gw.signed_get_url("clips/ses_1/shot_001.mp4")
    assert "clips/ses_1/shot_001.mp4" in out.url


async def test_delete_object_removes_from_bucket(s3_setup):
    s3_setup.put_object(Bucket="golf-test", Key="clips/x.mp4", Body=b"hello")
    gw = R2StorageGateway(
        endpoint=None,
        access_key="ak",
        secret_key="sk",
        bucket="golf-test",
        region="us-east-1",
        ttl_seconds=900,
    )
    await gw.delete_object("clips/x.mp4")
    resp = s3_setup.list_objects_v2(Bucket="golf-test")
    assert resp.get("KeyCount", 0) == 0
```

- [ ] **Step 2: Run failing test**

Run: `uv run pytest libs/infrastructure/tests/r2/test_storage_gateway.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement `r2/__init__.py`** (empty).

- [ ] **Step 4: Implement `r2/storage_gateway.py`**

```python
import asyncio
from datetime import UTC, datetime, timedelta

import boto3
from botocore.config import Config

from golf_application.ports import SignedUrl


class R2StorageGateway:
    def __init__(
        self,
        *,
        endpoint: str | None,
        access_key: str,
        secret_key: str,
        bucket: str,
        region: str,
        ttl_seconds: int,
    ) -> None:
        self._client = boto3.client(
            "s3",
            endpoint_url=endpoint,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region,
            config=Config(signature_version="s3v4"),
        )
        self._bucket = bucket
        self._ttl = ttl_seconds

    async def signed_put_url(self, key: str, *, content_type: str) -> SignedUrl:
        url = await asyncio.to_thread(
            self._client.generate_presigned_url,
            "put_object",
            Params={
                "Bucket": self._bucket,
                "Key": key,
                "ContentType": content_type,
            },
            ExpiresIn=self._ttl,
        )
        return SignedUrl(
            url=url,
            expires_at=datetime.now(UTC) + timedelta(seconds=self._ttl),
        )

    async def signed_get_url(self, key: str) -> SignedUrl:
        url = await asyncio.to_thread(
            self._client.generate_presigned_url,
            "get_object",
            Params={"Bucket": self._bucket, "Key": key},
            ExpiresIn=self._ttl,
        )
        return SignedUrl(
            url=url,
            expires_at=datetime.now(UTC) + timedelta(seconds=self._ttl),
        )

    async def delete_object(self, key: str) -> None:
        await asyncio.to_thread(
            self._client.delete_object, Bucket=self._bucket, Key=key
        )
```

- [ ] **Step 5: Run passing test**

Run: `uv run pytest libs/infrastructure/tests/r2/test_storage_gateway.py -v`
Expected: PASS — 3/3.

- [ ] **Step 6: Commit**

```bash
git add libs/infrastructure
git commit -m "feat(infrastructure): R2StorageGateway with boto3"
```

---

## Task 9: Celery app + `CeleryJobQueue` (producer side, TDD)

**Files:**
- Create: `libs/infrastructure/src/golf_infrastructure/queue/__init__.py`
- Create: `libs/infrastructure/src/golf_infrastructure/queue/celery_app.py`
- Create: `libs/infrastructure/src/golf_infrastructure/queue/job_queue.py`
- Create: `libs/infrastructure/tests/queue/__init__.py`
- Create: `libs/infrastructure/tests/queue/test_job_queue.py`

- [ ] **Step 1: Write failing test**

```python
from golf_application.ports import ProcessVideoJob
from golf_infrastructure.queue.celery_app import make_celery_app
from golf_infrastructure.queue.job_queue import CeleryJobQueue


async def test_enqueue_records_send_call():
    app = make_celery_app(broker_url="memory://", result_backend="cache+memory://")
    app.conf.task_always_eager = True  # don't actually transmit; just verify shape
    captured: list[dict] = []

    @app.task(name="golf_worker.tasks.process_video")
    def _capture(payload: dict) -> None:
        captured.append(payload)

    queue = CeleryJobQueue(app)
    await queue.enqueue_process_video(ProcessVideoJob(session_id="ses_1"))
    assert captured == [{"sessionId": "ses_1"}]
```

- [ ] **Step 2: Run failing test**

Run: `uv run pytest libs/infrastructure/tests/queue/test_job_queue.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement `queue/__init__.py`** (empty).

- [ ] **Step 4: Implement `queue/celery_app.py`**

```python
from celery import Celery


def make_celery_app(*, broker_url: str, result_backend: str) -> Celery:
    app = Celery("golf", broker=broker_url, backend=result_backend)
    app.conf.update(
        task_serializer="json",
        accept_content=["json"],
        result_serializer="json",
        timezone="UTC",
        enable_utc=True,
        task_routes={
            "golf_worker.tasks.process_video": {"queue": "video"},
            "golf_worker.tasks.generate_export_zip": {"queue": "export"},
        },
    )
    return app


PROCESS_VIDEO_TASK = "golf_worker.tasks.process_video"
GENERATE_EXPORT_ZIP_TASK = "golf_worker.tasks.generate_export_zip"
```

- [ ] **Step 5: Implement `queue/job_queue.py`**

```python
import asyncio

from celery import Celery

from golf_application.ports import ProcessVideoJob

from .celery_app import PROCESS_VIDEO_TASK


class CeleryJobQueue:
    def __init__(self, app: Celery) -> None:
        self._app = app

    async def enqueue_process_video(self, job: ProcessVideoJob) -> None:
        payload = {"sessionId": job.session_id}
        await asyncio.to_thread(
            self._app.send_task, PROCESS_VIDEO_TASK, args=[payload]
        )
```

- [ ] **Step 6: Run passing test**

Run: `uv run pytest libs/infrastructure/tests/queue/test_job_queue.py -v`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add libs/infrastructure
git commit -m "feat(infrastructure): Celery app + CeleryJobQueue producer"
```

---

## Task 10: `RedisEventPublisher` (TDD with fakeredis)

**Files:**
- Create: `libs/infrastructure/src/golf_infrastructure/queue/event_publisher.py`
- Create: `libs/infrastructure/tests/queue/test_event_publisher.py`

- [ ] **Step 1: Write failing test**

```python
import json
from datetime import UTC, datetime

import fakeredis.aioredis

from golf_domain.events import SessionReady, ShotDetected
from golf_infrastructure.queue.event_publisher import RedisEventPublisher


async def test_publishes_shot_detected_to_session_channel():
    r = fakeredis.aioredis.FakeRedis(decode_responses=True)
    pub = RedisEventPublisher(r)
    pubsub = r.pubsub()
    await pubsub.subscribe("session:ses_1")

    await pub.publish(
        ShotDetected(
            session_id="ses_1",
            shot_id="shot_1",
            confidence=0.9,
            occurred_at=datetime(2026, 4, 28, tzinfo=UTC),
        )
    )

    # consume one (subscribe ack first, then our payload)
    msg = None
    while True:
        m = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1)
        if m is not None:
            msg = m
            break
    payload = json.loads(msg["data"])
    assert payload["type"] == "session.shot.detected"
    assert payload["sessionId"] == "ses_1"
    assert payload["payload"]["shotId"] == "shot_1"


async def test_publishes_session_ready():
    r = fakeredis.aioredis.FakeRedis(decode_responses=True)
    pub = RedisEventPublisher(r)
    pubsub = r.pubsub()
    await pubsub.subscribe("session:ses_1")
    await pub.publish(
        SessionReady(
            session_id="ses_1",
            shot_count=3,
            occurred_at=datetime(2026, 4, 28, tzinfo=UTC),
        )
    )
    while True:
        m = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1)
        if m is not None:
            break
    payload = json.loads(m["data"])
    assert payload["type"] == "session.ready"
    assert payload["payload"]["shotCount"] == 3
```

- [ ] **Step 2: Run failing test**

Run: `uv run pytest libs/infrastructure/tests/queue/test_event_publisher.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement `queue/event_publisher.py`**

```python
import json

import redis.asyncio as redis_async

from golf_domain.events import (
    DomainEvent,
    SessionFailed,
    SessionProcessingStarted,
    SessionReady,
    ShotBoundaryUpdated,
    ShotDeleted,
    ShotDetected,
)


_TYPE_MAP: dict[type[DomainEvent], str] = {
    SessionProcessingStarted: "session.processing.started",
    ShotDetected: "session.shot.detected",
    SessionReady: "session.ready",
    SessionFailed: "session.failed",
    ShotBoundaryUpdated: "session.shot.boundary.updated",
    ShotDeleted: "session.shot.deleted",
}


def _payload_for(e: DomainEvent) -> dict:
    if isinstance(e, ShotDetected):
        return {"shotId": e.shot_id, "confidence": e.confidence}
    if isinstance(e, SessionReady):
        return {"shotCount": e.shot_count}
    if isinstance(e, SessionFailed):
        return {"stage": e.stage, "message": e.message}
    if isinstance(e, ShotBoundaryUpdated):
        return {"shotId": e.shot_id, "tStart": e.t_start, "tEnd": e.t_end}
    if isinstance(e, ShotDeleted):
        return {"shotId": e.shot_id}
    return {}


class RedisEventPublisher:
    def __init__(self, client: redis_async.Redis) -> None:
        self._client = client

    async def publish(self, event: DomainEvent) -> None:
        envelope = {
            "type": _TYPE_MAP[type(event)],
            "sessionId": event.session_id,
            "payload": _payload_for(event),
            "occurredAt": event.occurred_at.isoformat(),
        }
        channel = f"session:{event.session_id}"
        await self._client.publish(channel, json.dumps(envelope))
```

- [ ] **Step 4: Run passing test**

Run: `uv run pytest libs/infrastructure/tests/queue/test_event_publisher.py -v`
Expected: PASS — 2/2.

- [ ] **Step 5: Commit**

```bash
git add libs/infrastructure
git commit -m "feat(infrastructure): RedisEventPublisher"
```

---

## Task 11: `JwtService` (TDD)

**Files:**
- Create: `libs/infrastructure/src/golf_infrastructure/auth/__init__.py`
- Create: `libs/infrastructure/src/golf_infrastructure/auth/jwt_service.py`
- Create: `libs/infrastructure/tests/auth/__init__.py`
- Create: `libs/infrastructure/tests/auth/test_jwt_service.py`

- [ ] **Step 1: Write failing test**

```python
import pytest

from golf_infrastructure.auth.jwt_service import JwtService, JwtVerifyError


def _service() -> JwtService:
    return JwtService(secret="x" * 32, issuer="golf-test", ttl_seconds=60)


def test_round_trip_token_returns_subject():
    s = _service()
    token = s.issue(subject="u_1")
    payload = s.verify(token)
    assert payload.subject == "u_1"


def test_verify_rejects_tampered_token():
    s = _service()
    token = s.issue(subject="u_1")
    bad = token[:-2] + ("aa" if not token.endswith("aa") else "bb")
    with pytest.raises(JwtVerifyError):
        s.verify(bad)


def test_verify_rejects_wrong_issuer():
    issued = _service().issue(subject="u_1")
    other = JwtService(secret="x" * 32, issuer="other", ttl_seconds=60)
    with pytest.raises(JwtVerifyError):
        other.verify(issued)
```

- [ ] **Step 2: Run failing test**

Run: `uv run pytest libs/infrastructure/tests/auth/test_jwt_service.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement `auth/__init__.py`** (empty).

- [ ] **Step 4: Implement `auth/jwt_service.py`**

```python
from datetime import UTC, datetime, timedelta

from jose import JWTError, jwt
from pydantic import BaseModel


class JwtVerifyError(Exception):
    pass


class JwtPayload(BaseModel):
    subject: str
    issued_at: datetime
    expires_at: datetime


class JwtService:
    ALGORITHM = "HS256"

    def __init__(self, *, secret: str, issuer: str, ttl_seconds: int) -> None:
        if len(secret) < 32:
            raise ValueError("JWT secret must be ≥ 32 chars")
        self._secret = secret
        self._issuer = issuer
        self._ttl = ttl_seconds

    def issue(self, *, subject: str) -> str:
        now = datetime.now(UTC)
        claims = {
            "sub": subject,
            "iss": self._issuer,
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(seconds=self._ttl)).timestamp()),
        }
        return jwt.encode(claims, self._secret, algorithm=self.ALGORITHM)

    def verify(self, token: str) -> JwtPayload:
        try:
            claims = jwt.decode(
                token,
                self._secret,
                algorithms=[self.ALGORITHM],
                issuer=self._issuer,
            )
        except JWTError as e:
            raise JwtVerifyError(str(e)) from e
        return JwtPayload(
            subject=claims["sub"],
            issued_at=datetime.fromtimestamp(claims["iat"], tz=UTC),
            expires_at=datetime.fromtimestamp(claims["exp"], tz=UTC),
        )
```

- [ ] **Step 5: Run passing test**

Run: `uv run pytest libs/infrastructure/tests/auth/test_jwt_service.py -v`
Expected: PASS — 3/3.

- [ ] **Step 6: Commit**

```bash
git add libs/infrastructure
git commit -m "feat(infrastructure): JwtService (issue + verify)"
```

---

## Task 12: Run import-linter — verify infrastructure layered correctly

**Files:** none new.

- [ ] **Step 1: Run import-linter**

Run: `uv run lint-imports`
Expected: `Contracts: 1 kept, 0 broken.`
(Now `golf_infrastructure` is on disk and depends only on `golf_application` + `golf_domain` + stdlib + pydantic + boto3/motor/celery/redis/python-jose/python-ulid/structlog. No upward imports.)

If lint-imports reports broken: investigate which module imports a forbidden layer and fix before proceeding. Don't proceed with broken architecture.

- [ ] **Step 2: Commit (only if changes were needed)**

If no changes — skip. Otherwise:
```bash
git add libs/infrastructure
git commit -m "fix(infrastructure): respect layered architecture"
```

---

## Task 13: Add Pydantic codegen for `libs/contracts`

**Files:**
- Modify: `libs/contracts/package.json` (add scripts, devDeps)
- Create: `libs/contracts/scripts/sync-python.mjs`
- Create: `libs/contracts/generated/python/__init__.py` (empty)
- Create: `libs/contracts/generated/python/golf_contracts/__init__.py` (auto-generated re-exports)
- Update: `.gitignore` to NOT ignore `generated/python/` (we want it committed for reproducibility)

- [ ] **Step 1: Update `libs/contracts/package.json`**

```json
{
  "name": "@golf/contracts",
  "version": "0.0.0",
  "private": true,
  "type": "module",
  "main": "src/index.ts",
  "types": "src/index.ts",
  "scripts": {
    "sync:python": "node scripts/sync-python.mjs"
  },
  "dependencies": {
    "zod": "3.23.8"
  },
  "devDependencies": {
    "vitest": "2.1.4",
    "zod-to-json-schema": "3.23.5"
  }
}
```

Run: `pnpm install`. Expected: zod-to-json-schema installed.

- [ ] **Step 2: Create `libs/contracts/scripts/sync-python.mjs`**

```js
import { mkdirSync, writeFileSync } from "node:fs";
import { dirname } from "node:path";
import { execFileSync } from "node:child_process";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { zodToJsonSchema } from "zod-to-json-schema";

import * as Sessions from "../src/sessions.ts";
import * as Shots from "../src/shots.ts";
import * as Events from "../src/events.ts";

const schemas = {
  SessionStatus: Sessions.SessionStatus,
  SessionDto: Sessions.SessionDto,
  CreateSessionRequest: Sessions.CreateSessionRequest,
  CreateSessionResponse: Sessions.CreateSessionResponse,
  ShotSource: Shots.ShotSource,
  ShotDto: Shots.ShotDto,
  UpdateShotBoundaryRequest: Shots.UpdateShotBoundaryRequest,
  AddManualShotRequest: Shots.AddManualShotRequest,
  SseEventEnvelope: Events.SseEventEnvelope,
};

const root = {
  $schema: "http://json-schema.org/draft-07/schema#",
  title: "GolfContracts",
  type: "object",
  definitions: {},
};

for (const [name, schema] of Object.entries(schemas)) {
  const j = zodToJsonSchema(schema, { name, target: "jsonSchema7" });
  Object.assign(root.definitions, j.definitions);
}

const tmp = join(tmpdir(), `golf-contracts-${Date.now()}.json`);
writeFileSync(tmp, JSON.stringify(root, null, 2));

const outDir = "libs/contracts/generated/python/golf_contracts";
mkdirSync(outDir, { recursive: true });

execFileSync(
  "uv",
  [
    "run",
    "datamodel-codegen",
    "--input",
    tmp,
    "--input-file-type",
    "jsonschema",
    "--output",
    `${outDir}/_models.py`,
    "--output-model-type",
    "pydantic_v2.BaseModel",
    "--target-python-version",
    "3.11",
    "--use-standard-collections",
    "--use-union-operator",
  ],
  { stdio: "inherit" }
);

writeFileSync(`${outDir}/__init__.py`, "from ._models import *  # noqa: F401,F403\n");

console.log("✓ Synced Pydantic contracts to", outDir);
```

NOTE: This script uses `import * as Sessions from "../src/sessions.ts"` — Node 22+ with `--experimental-strip-types` or via `tsx`. To keep the toolchain simple, run via `pnpm tsx` instead. Adjust the script invocation:

Actually run with: `pnpm exec tsx libs/contracts/scripts/sync-python.mjs` and add `tsx` to devDeps:

```json
"devDependencies": {
  "vitest": "2.1.4",
  "zod-to-json-schema": "3.23.5",
  "tsx": "4.19.2"
}
```

Update the npm script: `"sync:python": "tsx scripts/sync-python.mjs"` (rename to `.ts` if that helps tsx pick it up — easier: keep `.mjs` but invoke through `tsx`).

Actually simplest: rename to `sync-python.ts` and run with `tsx`:
- `libs/contracts/scripts/sync-python.ts` (same content)
- `"sync:python": "tsx scripts/sync-python.ts"`

- [ ] **Step 3: Run sync**

Run: `pnpm --filter @golf/contracts run sync:python`
Expected:
- Creates `libs/contracts/generated/python/golf_contracts/_models.py` with Pydantic v2 models for SessionDto, ShotDto, etc. (camelCase fields from the zod schemas).
- Prints `✓ Synced Pydantic contracts to ...`.

If it fails because `tsx` can't import `.ts` files transitively, fall back to a simpler approach: hand-write `libs/contracts/generated/python/golf_contracts/_models.py` for Plan 2 with the same DTOs the API will use. (Codegen wiring is not on the critical path; Plan 4 can revisit.)

If you fall back to hand-written models, document the deviation in your status report. Either way, the result must be a Python module exporting `SessionDto`, `ShotDto`, `CreateSessionRequest`, `CreateSessionResponse`, `UpdateShotBoundaryRequest`, `AddManualShotRequest`, `SseEventEnvelope` as Pydantic v2 models with camelCase field aliases (so they serialize to wire format directly).

If hand-writing, here is a minimal version to use:

```python
# libs/contracts/generated/python/golf_contracts/_models.py
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class _Camel(BaseModel):
    model_config = ConfigDict(populate_by_name=True)


SessionStatus = Literal["uploading", "queued", "processing", "ready", "failed"]
ShotSource = Literal["auto", "manual"]


class SessionError(_Camel):
    stage: str
    message: str


class SessionDto(_Camel):
    id: str
    user_id: str | None = Field(alias="userId")
    raw_video_key: str = Field(alias="rawVideoKey")
    status: SessionStatus
    pre_roll_seconds: float = Field(ge=0, alias="preRollSeconds")
    post_roll_seconds: float = Field(ge=0, alias="postRollSeconds")
    shot_count: int = Field(ge=0, alias="shotCount")
    duration_seconds: float = Field(ge=0, alias="durationSeconds")
    error: SessionError | None
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")


class CreateSessionRequest(_Camel):
    original_filename: str = Field(min_length=1, alias="originalFilename")
    pre_roll_seconds: float = Field(default=2.0, ge=0, alias="preRollSeconds")
    post_roll_seconds: float = Field(default=5.0, ge=0, alias="postRollSeconds")


class CreateSessionResponse(_Camel):
    session_id: str = Field(alias="sessionId")
    signed_upload_url: str = Field(alias="signedUploadUrl")
    expires_at: datetime = Field(alias="expiresAt")


class ShotDto(_Camel):
    id: str
    session_id: str = Field(alias="sessionId")
    index: int = Field(gt=0)
    t_impact: float = Field(ge=0, alias="tImpact")
    t_start: float = Field(ge=0, alias="tStart")
    t_end: float = Field(ge=0, alias="tEnd")
    confidence: float = Field(ge=0, le=1)
    source: ShotSource
    clip_key: str | None = Field(alias="clipKey")
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")


class UpdateShotBoundaryRequest(_Camel):
    t_start: float = Field(ge=0, alias="tStart")
    t_end: float = Field(ge=0, alias="tEnd")


class AddManualShotRequest(_Camel):
    t_impact: float = Field(ge=0, alias="tImpact")
    t_start: float = Field(ge=0, alias="tStart")
    t_end: float = Field(ge=0, alias="tEnd")


class SseEventEnvelope(_Camel):
    type: str
    session_id: str = Field(alias="sessionId")
    payload: dict[str, Any]
    occurred_at: datetime = Field(alias="occurredAt")
```

And `libs/contracts/generated/python/golf_contracts/__init__.py`:

```python
from ._models import (
    AddManualShotRequest,
    CreateSessionRequest,
    CreateSessionResponse,
    SessionDto,
    SessionError,
    SessionStatus,
    ShotDto,
    ShotSource,
    SseEventEnvelope,
    UpdateShotBoundaryRequest,
)

__all__ = [
    "AddManualShotRequest",
    "CreateSessionRequest",
    "CreateSessionResponse",
    "SessionDto",
    "SessionError",
    "SessionStatus",
    "ShotDto",
    "ShotSource",
    "SseEventEnvelope",
    "UpdateShotBoundaryRequest",
]
```

- [ ] **Step 4: Make `golf_contracts` importable from Python**

The package is at `libs/contracts/generated/python/golf_contracts/` but it's not a uv workspace member. Plan 4 can promote it; for Plan 2 we just need `apps/api` to import it. Add a path-style dependency in `apps/api/pyproject.toml` (Task 14). For now, add to root workspace as a "tool" via uv:

Actually simplest: create a tiny `pyproject.toml` at `libs/contracts/generated/python/` so it becomes a uv workspace member.

Create `libs/contracts/generated/python/pyproject.toml`:
```toml
[project]
name = "golf-contracts"
version = "0.0.0"
requires-python = ">=3.11"
dependencies = ["pydantic>=2.9"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["golf_contracts"]
```

Update root `pyproject.toml` `[tool.uv.workspace].members` to add `"libs/contracts/generated/python"`. Run `uv sync --all-packages`.

- [ ] **Step 5: Verify import**

Run: `uv run python -c "from golf_contracts import SessionDto, ShotDto; print(SessionDto.model_json_schema()['title'])"`
Expected: `SessionDto`.

- [ ] **Step 6: Commit**

```bash
git add libs/contracts pyproject.toml uv.lock
git commit -m "feat(contracts): add Python codegen / hand-written Pydantic DTOs"
```

---

## Task 14: Scaffold `apps/api` package

**Files:**
- Create: `apps/api/pyproject.toml`
- Create: `apps/api/Dockerfile` (skeleton; we tune in Plan 5)
- Create: `apps/api/src/golf_api/__init__.py`
- Create: `apps/api/src/golf_api/main.py` (minimal FastAPI app with health route)
- Create: `apps/api/src/golf_api/settings.py`
- Create: `apps/api/tests/__init__.py`
- Create: `apps/api/tests/conftest.py`
- Create: `apps/api/tests/test_health.py`

- [ ] **Step 1: Create `apps/api/pyproject.toml`**

```toml
[project]
name = "golf-api"
version = "0.0.0"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.115",
    "uvicorn[standard]>=0.32",
    "sse-starlette>=2.1",
    "python-multipart>=0.0.12",
    "golf-domain",
    "golf-application",
    "golf-infrastructure",
    "golf-contracts"
]

[tool.uv.sources]
golf-domain = { workspace = true }
golf-application = { workspace = true }
golf-infrastructure = { workspace = true }
golf-contracts = { workspace = true }

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/golf_api"]
```

- [ ] **Step 2: Sync workspace**

Run: `uv sync --all-packages`
Expected: `golf-api==0.0.0` registered in `uv.lock`.

- [ ] **Step 3: Implement `apps/api/src/golf_api/__init__.py`**

```python
"""FastAPI host for golf-shot-cutter."""
```

- [ ] **Step 4: Implement `apps/api/src/golf_api/settings.py`**

```python
from golf_infrastructure.settings import Settings

__all__ = ["Settings"]
```

- [ ] **Step 5: Write failing health test FIRST: `apps/api/tests/test_health.py`**

```python
from fastapi.testclient import TestClient


def test_health(client: TestClient):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}
```

- [ ] **Step 6: Implement `apps/api/tests/conftest.py`**

```python
import pytest
from fastapi.testclient import TestClient

from golf_api.main import create_app


@pytest.fixture
def client() -> TestClient:
    app = create_app(env="test")
    return TestClient(app)
```

- [ ] **Step 7: Run failing test**

Run: `uv run pytest apps/api/tests/test_health.py -v`
Expected: FAIL — `golf_api.main` not defined.

- [ ] **Step 8: Implement `apps/api/src/golf_api/main.py`**

```python
from fastapi import FastAPI


def create_app(env: str = "production") -> FastAPI:
    app = FastAPI(title="golf-shot-cutter API", version="0.2.0")

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()  # uvicorn entry point
```

- [ ] **Step 9: Run passing test**

Run: `uv run pytest apps/api/tests/test_health.py -v`
Expected: PASS.

- [ ] **Step 10: Commit**

```bash
git add apps/api pyproject.toml uv.lock
git commit -m "feat(api): scaffold FastAPI app with /health"
```

---

## Task 15: DI container + middleware (request_id + error_handler)

**Files:**
- Create: `apps/api/src/golf_api/deps/__init__.py`
- Create: `apps/api/src/golf_api/deps/container.py`
- Create: `apps/api/src/golf_api/middleware/__init__.py`
- Create: `apps/api/src/golf_api/middleware/request_id.py`
- Create: `apps/api/src/golf_api/middleware/error_handler.py`
- Modify: `apps/api/src/golf_api/main.py` (wire middleware + container into app state + lifespan)
- Create: `apps/api/tests/test_middleware.py`

- [ ] **Step 1: Implement `deps/__init__.py`** (empty).

- [ ] **Step 2: Implement `deps/container.py`**

```python
from dataclasses import dataclass

from celery import Celery
from motor.motor_asyncio import AsyncIOMotorClient
from redis.asyncio import Redis

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
from golf_infrastructure.clock import SystemClock
from golf_infrastructure.ids import UlidIdGenerator
from golf_infrastructure.mongo.client import get_database, make_client
from golf_infrastructure.mongo.indexes import ensure_indexes
from golf_infrastructure.mongo.session_repository import MongoSessionRepository
from golf_infrastructure.mongo.shot_repository import MongoShotRepository
from golf_infrastructure.queue.celery_app import make_celery_app
from golf_infrastructure.queue.event_publisher import RedisEventPublisher
from golf_infrastructure.queue.job_queue import CeleryJobQueue
from golf_infrastructure.r2.storage_gateway import R2StorageGateway
from golf_infrastructure.settings import Settings


@dataclass
class Container:
    settings: Settings
    mongo_client: AsyncIOMotorClient
    redis: Redis
    celery: Celery
    jwt: JwtService
    sessions_repo: MongoSessionRepository
    shots_repo: MongoShotRepository
    storage: R2StorageGateway
    queue: CeleryJobQueue
    publisher: RedisEventPublisher
    clock: SystemClock
    ids: UlidIdGenerator

    create_session: CreateSessionUseCase
    request_upload_url: RequestSignedUploadUrlUseCase
    start_processing: StartProcessingUseCase
    list_sessions: ListSessionsUseCase
    get_session: GetSessionWithShotsUseCase
    update_shot_boundary: UpdateShotBoundaryUseCase
    add_manual_shot: AddManualShotUseCase
    delete_shot: DeleteShotUseCase
    process_video: ProcessVideoUseCase
    export_session_zip: ExportSessionZipUseCase


async def build_container(settings: Settings) -> Container:
    mongo_client = make_client(settings.mongodb_uri)
    db = get_database(mongo_client, settings.mongodb_database)
    await ensure_indexes(db)

    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    celery = make_celery_app(
        broker_url=settings.redis_url, result_backend=settings.redis_url
    )

    jwt = JwtService(
        secret=settings.jwt_secret,
        issuer=settings.jwt_issuer,
        ttl_seconds=settings.jwt_ttl_seconds,
    )

    sessions_repo = MongoSessionRepository(db)
    shots_repo = MongoShotRepository(db)
    storage = R2StorageGateway(
        endpoint=settings.r2_endpoint,
        access_key=settings.r2_access_key,
        secret_key=settings.r2_secret_key,
        bucket=settings.r2_bucket,
        region=settings.r2_region,
        ttl_seconds=settings.signed_url_ttl_seconds,
    )
    queue = CeleryJobQueue(celery)
    publisher = RedisEventPublisher(redis)
    clock = SystemClock()
    ids = UlidIdGenerator()

    return Container(
        settings=settings,
        mongo_client=mongo_client,
        redis=redis,
        celery=celery,
        jwt=jwt,
        sessions_repo=sessions_repo,
        shots_repo=shots_repo,
        storage=storage,
        queue=queue,
        publisher=publisher,
        clock=clock,
        ids=ids,
        create_session=CreateSessionUseCase(
            sessions=sessions_repo, storage=storage, clock=clock, ids=ids
        ),
        request_upload_url=RequestSignedUploadUrlUseCase(
            sessions=sessions_repo, storage=storage
        ),
        start_processing=StartProcessingUseCase(
            sessions=sessions_repo, queue=queue, events=publisher, clock=clock
        ),
        list_sessions=ListSessionsUseCase(sessions=sessions_repo),
        get_session=GetSessionWithShotsUseCase(
            sessions=sessions_repo, shots=shots_repo
        ),
        update_shot_boundary=UpdateShotBoundaryUseCase(
            sessions=sessions_repo,
            shots=shots_repo,
            events=publisher,
            clock=clock,
        ),
        add_manual_shot=AddManualShotUseCase(
            sessions=sessions_repo,
            shots=shots_repo,
            events=publisher,
            clock=clock,
            ids=ids,
        ),
        delete_shot=DeleteShotUseCase(
            sessions=sessions_repo,
            shots=shots_repo,
            events=publisher,
            clock=clock,
        ),
        process_video=ProcessVideoUseCase(
            sessions=sessions_repo,
            shots=shots_repo,
            events=publisher,
            clock=clock,
            ids=ids,
        ),
        export_session_zip=ExportSessionZipUseCase(
            sessions=sessions_repo, storage=storage, ids=ids
        ),
    )


async def shutdown_container(c: Container) -> None:
    c.mongo_client.close()
    await c.redis.aclose()
```

- [ ] **Step 3: Implement `middleware/__init__.py`** (empty).

- [ ] **Step 4: Implement `middleware/request_id.py`**

```python
import uuid
from collections.abc import Awaitable, Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        rid = request.headers.get("X-Request-Id") or uuid.uuid4().hex
        request.state.request_id = rid
        response = await call_next(request)
        response.headers["X-Request-Id"] = rid
        return response
```

- [ ] **Step 5: Implement `middleware/error_handler.py`**

```python
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from golf_application.errors import (
    ApplicationError,
    SessionNotFoundError,
    ShotNotFoundError,
)
from golf_domain.errors import (
    DomainError,
    InvalidStateTransitionError,
    InvalidValueError,
)


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(SessionNotFoundError)
    async def _session_nf(_: Request, exc: SessionNotFoundError) -> JSONResponse:
        return JSONResponse(
            status_code=404, content={"error": "session_not_found", "message": str(exc)}
        )

    @app.exception_handler(ShotNotFoundError)
    async def _shot_nf(_: Request, exc: ShotNotFoundError) -> JSONResponse:
        return JSONResponse(
            status_code=404, content={"error": "shot_not_found", "message": str(exc)}
        )

    @app.exception_handler(InvalidStateTransitionError)
    async def _ist(_: Request, exc: InvalidStateTransitionError) -> JSONResponse:
        return JSONResponse(
            status_code=409, content={"error": "invalid_state", "message": str(exc)}
        )

    @app.exception_handler(InvalidValueError)
    async def _iv(_: Request, exc: InvalidValueError) -> JSONResponse:
        return JSONResponse(
            status_code=422, content={"error": "invalid_value", "message": str(exc)}
        )

    @app.exception_handler(DomainError)
    async def _de(_: Request, exc: DomainError) -> JSONResponse:
        return JSONResponse(
            status_code=400, content={"error": "domain_error", "message": str(exc)}
        )

    @app.exception_handler(ApplicationError)
    async def _ae(_: Request, exc: ApplicationError) -> JSONResponse:
        return JSONResponse(
            status_code=400,
            content={"error": "application_error", "message": str(exc)},
        )
```

- [ ] **Step 6: Update `main.py` to wire middleware + container lifecycle**

```python
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI

from .deps.container import build_container, shutdown_container
from .middleware.error_handler import install_error_handlers
from .middleware.request_id import RequestIdMiddleware
from .settings import Settings


def create_app(env: str = "production") -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if env != "test":
            settings = Settings()
            container = await build_container(settings)
            app.state.container = container
            try:
                yield
            finally:
                await shutdown_container(container)
        else:
            # Test mode: container set by conftest.py via dependency override.
            yield

    app = FastAPI(title="golf-shot-cutter API", version="0.2.0", lifespan=lifespan)
    app.add_middleware(RequestIdMiddleware)
    install_error_handlers(app)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app(env=os.environ.get("APP_ENV", "production"))
```

- [ ] **Step 7: Add request-id integration test: `apps/api/tests/test_middleware.py`**

```python
from fastapi.testclient import TestClient


def test_request_id_round_trip(client: TestClient):
    r = client.get("/health", headers={"X-Request-Id": "rid-abc"})
    assert r.headers["X-Request-Id"] == "rid-abc"


def test_request_id_generated_when_missing(client: TestClient):
    r = client.get("/health")
    assert "X-Request-Id" in r.headers
    assert len(r.headers["X-Request-Id"]) >= 16
```

- [ ] **Step 8: Run all api tests**

Run: `uv run pytest apps/api -v`
Expected: PASS — health + 2 middleware tests.

- [ ] **Step 9: Commit**

```bash
git add apps/api
git commit -m "feat(api): DI container + request_id + error_handler middleware"
```

---

## Task 16: Auth router + `CurrentUser` dependency

**Files:**
- Create: `apps/api/src/golf_api/deps/auth.py`
- Create: `apps/api/src/golf_api/routers/__init__.py`
- Create: `apps/api/src/golf_api/routers/auth.py`
- Modify: `apps/api/src/golf_api/main.py` (mount router)
- Create: `apps/api/tests/test_auth.py`

For Phase 1 the auth model is dev-friendly: a `POST /auth/login` accepts an email + password from a hard-coded dev allowlist (or any string with a recognized password), issues a JWT cookie. Plan 5 swaps in real users + DB.

- [ ] **Step 1: Failing test FIRST: `apps/api/tests/test_auth.py`**

```python
from fastapi.testclient import TestClient


def test_login_sets_cookie(client: TestClient):
    r = client.post(
        "/auth/login", json={"email": "dev@local", "password": "dev"}
    )
    assert r.status_code == 204
    assert r.cookies.get("auth")  # cookie was set


def test_logout_clears_cookie(client: TestClient):
    client.post("/auth/login", json={"email": "dev@local", "password": "dev"})
    r = client.post("/auth/logout")
    assert r.status_code == 204
    # post-logout cookie should be cleared (set to empty in Set-Cookie)
    set_cookie = r.headers.get("set-cookie", "")
    assert "auth=" in set_cookie and "Max-Age=0" in set_cookie


def test_me_requires_auth(client: TestClient):
    r = client.get("/auth/me")
    assert r.status_code == 401


def test_me_returns_subject_when_authenticated(client: TestClient):
    client.post("/auth/login", json={"email": "dev@local", "password": "dev"})
    r = client.get("/auth/me")
    assert r.status_code == 200
    assert r.json()["userId"] == "dev@local"
```

- [ ] **Step 2: Run failing test**

Run: `uv run pytest apps/api/tests/test_auth.py -v`
Expected: FAIL.

- [ ] **Step 3: Update `conftest.py` to wire a test container**

Update `apps/api/tests/conftest.py`:

```python
import pytest
from fastapi.testclient import TestClient

from golf_api.deps.container import Container
from golf_api.main import create_app
from golf_application.tests.fakes.fake_clock import FakeClock
from golf_application.tests.fakes.fake_id_generator import FakeIdGenerator
from golf_application.tests.fakes.fake_publisher import FakeEventPublisher
from golf_application.tests.fakes.fake_queue import FakeJobQueue
from golf_application.tests.fakes.fake_storage import FakeStorage
from golf_application.tests.fakes.in_memory_repos import (
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
from datetime import UTC, datetime


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
        settings=None,  # not used in tests
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
        request_upload_url=RequestSignedUploadUrlUseCase(
            sessions=sessions, storage=storage
        ),
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
        export_session_zip=ExportSessionZipUseCase(
            sessions=sessions, storage=storage, ids=ids
        ),
    )


@pytest.fixture
def client(container) -> TestClient:
    app = create_app(env="test")
    app.state.container = container
    return TestClient(app)
```

- [ ] **Step 4: Implement `routers/__init__.py`** (empty).

- [ ] **Step 5: Implement `deps/auth.py`**

```python
from fastapi import Cookie, HTTPException, Request

from golf_api.deps.container import Container
from golf_infrastructure.auth.jwt_service import JwtVerifyError


_DEV_USERS = {"dev@local": "dev"}  # Plan 5 replaces with real user store


def get_container(request: Request) -> Container:
    return request.app.state.container


def authenticate(email: str, password: str) -> str | None:
    if _DEV_USERS.get(email) == password:
        return email
    return None


def current_user_id(
    request: Request, auth: str | None = Cookie(default=None)
) -> str:
    if not auth:
        raise HTTPException(status_code=401, detail="not_authenticated")
    container: Container = get_container(request)
    try:
        payload = container.jwt.verify(auth)
    except JwtVerifyError as e:
        raise HTTPException(status_code=401, detail="invalid_token") from e
    return payload.subject
```

- [ ] **Step 6: Implement `routers/auth.py`**

```python
from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field

from golf_api.deps.auth import authenticate, current_user_id, get_container


router = APIRouter(prefix="/auth", tags=["auth"])

_COOKIE_NAME = "auth"


class LoginRequest(BaseModel):
    email: str = Field(min_length=1)
    password: str = Field(min_length=1)


@router.post("/login", status_code=204)
async def login(req: LoginRequest, response: Response, container=Depends(get_container)) -> None:
    user_id = authenticate(req.email, req.password)
    if user_id is None:
        raise HTTPException(status_code=401, detail="invalid_credentials")
    token = container.jwt.issue(subject=user_id)
    response.set_cookie(
        _COOKIE_NAME,
        token,
        httponly=True,
        samesite="lax",
        max_age=container.jwt._ttl,  # noqa: SLF001
    )


@router.post("/logout", status_code=204)
async def logout(response: Response) -> None:
    response.delete_cookie(_COOKIE_NAME)


class MeResponse(BaseModel):
    user_id: str

    model_config = {"populate_by_name": True}


@router.get("/me")
async def me(user_id: str = Depends(current_user_id)) -> dict[str, str]:
    return {"userId": user_id}
```

(Plan 2 keeps the dev login intentionally permissive — plain `str` fields, no email-validator dep, no DB. Plan 5 swaps in a real user store and stricter validation.)

- [ ] **Step 7: Mount router in `main.py`**

In `create_app`, after `install_error_handlers(app)`, before `@app.get("/health")`:

```python
from .routers.auth import router as auth_router
app.include_router(auth_router)
```

- [ ] **Step 8: Run tests**

Run: `uv run pytest apps/api/tests/test_auth.py -v`
Expected: PASS — 4/4.

- [ ] **Step 9: Commit**

```bash
git add apps/api uv.lock
git commit -m "feat(api): auth router (login/logout/me) + JWT cookie dep"
```

---

## Task 17: Sessions router

**Files:**
- Create: `apps/api/src/golf_api/routers/sessions.py`
- Modify: `main.py` (mount)
- Create: `apps/api/tests/test_sessions.py`

- [ ] **Step 1: Failing test FIRST**

```python
from fastapi.testclient import TestClient


def _login(client: TestClient) -> None:
    client.post("/auth/login", json={"email": "dev@local", "password": "dev"})


def test_create_session_returns_signed_url(client: TestClient):
    _login(client)
    r = client.post(
        "/sessions",
        json={
            "originalFilename": "range.mp4",
            "preRollSeconds": 2.0,
            "postRollSeconds": 5.0,
        },
    )
    assert r.status_code == 201
    body = r.json()
    assert body["sessionId"].startswith("ses_")
    assert "PUT" in body["signedUploadUrl"]
    assert "expiresAt" in body


def test_list_sessions_returns_only_caller_sessions(client: TestClient):
    _login(client)
    client.post("/sessions", json={"originalFilename": "a.mp4"})
    client.post("/sessions", json={"originalFilename": "b.mp4"})
    r = client.get("/sessions")
    assert r.status_code == 200
    assert len(r.json()) == 2


def test_get_session_returns_session_and_shots(client: TestClient):
    _login(client)
    create = client.post("/sessions", json={"originalFilename": "a.mp4"})
    sid = create.json()["sessionId"]
    r = client.get(f"/sessions/{sid}")
    assert r.status_code == 200
    body = r.json()
    assert body["session"]["id"] == sid
    assert body["shots"] == []


def test_get_session_404_when_missing(client: TestClient):
    _login(client)
    r = client.get("/sessions/does_not_exist")
    assert r.status_code == 404


def test_create_session_unauthenticated_401(client: TestClient):
    r = client.post("/sessions", json={"originalFilename": "a.mp4"})
    assert r.status_code == 401


def test_start_processing_transitions_status(client: TestClient):
    _login(client)
    create = client.post("/sessions", json={"originalFilename": "a.mp4"})
    sid = create.json()["sessionId"]
    r = client.post(f"/sessions/{sid}/process")
    assert r.status_code == 202
    detail = client.get(f"/sessions/{sid}").json()
    assert detail["session"]["status"] == "processing"
```

- [ ] **Step 2: Run failing test**

Run: `uv run pytest apps/api/tests/test_sessions.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement `routers/sessions.py`**

```python
from fastapi import APIRouter, Depends, status

from golf_api.deps.auth import current_user_id, get_container
from golf_application.use_cases.create_session import CreateSessionInput
from golf_application.use_cases.get_session_with_shots import (
    GetSessionWithShotsInput,
)
from golf_application.use_cases.list_sessions import ListSessionsInput
from golf_application.use_cases.start_processing import StartProcessingInput
from golf_contracts import (
    CreateSessionRequest,
    CreateSessionResponse,
    SessionDto,
    ShotDto,
)
from pydantic import BaseModel


router = APIRouter(prefix="/sessions", tags=["sessions"])


class SessionWithShotsResponse(BaseModel):
    session: SessionDto
    shots: list[ShotDto]
    model_config = {"populate_by_name": True}


def _session_dto(s) -> SessionDto:
    return SessionDto.model_validate(
        {
            "id": s.id,
            "userId": s.user_id,
            "rawVideoKey": s.raw_video_key,
            "status": s.status.value,
            "preRollSeconds": s.pre_roll_seconds,
            "postRollSeconds": s.post_roll_seconds,
            "shotCount": s.shot_count,
            "durationSeconds": s.duration_seconds,
            "error": (
                {"stage": s.error.stage, "message": s.error.message}
                if s.error
                else None
            ),
            "createdAt": s.created_at,
            "updatedAt": s.updated_at,
        }
    )


def _shot_dto(sh) -> ShotDto:
    return ShotDto.model_validate(
        {
            "id": sh.id,
            "sessionId": sh.session_id,
            "index": sh.index,
            "tImpact": sh.t_impact,
            "tStart": sh.t_start,
            "tEnd": sh.t_end,
            "confidence": sh.confidence.value,
            "source": sh.source.value,
            "clipKey": sh.clip_key,
            "createdAt": sh.created_at,
            "updatedAt": sh.updated_at,
        }
    )


@router.post("", status_code=status.HTTP_201_CREATED, response_model=CreateSessionResponse)
async def create_session(
    req: CreateSessionRequest,
    user_id: str = Depends(current_user_id),
    container=Depends(get_container),
) -> CreateSessionResponse:
    out = await container.create_session.execute(
        CreateSessionInput(
            user_id=user_id,
            original_filename=req.original_filename,
            pre_roll_seconds=req.pre_roll_seconds,
            post_roll_seconds=req.post_roll_seconds,
        )
    )
    return CreateSessionResponse.model_validate(
        {
            "sessionId": out.session_id,
            "signedUploadUrl": out.signed_upload_url,
            "expiresAt": out.expires_at,
        }
    )


@router.get("", response_model=list[SessionDto])
async def list_sessions(
    user_id: str = Depends(current_user_id),
    container=Depends(get_container),
) -> list[SessionDto]:
    sessions = await container.list_sessions.execute(
        ListSessionsInput(user_id=user_id)
    )
    return [_session_dto(s) for s in sessions]


@router.get("/{session_id}", response_model=SessionWithShotsResponse)
async def get_session(
    session_id: str,
    _user_id: str = Depends(current_user_id),
    container=Depends(get_container),
) -> SessionWithShotsResponse:
    out = await container.get_session.execute(
        GetSessionWithShotsInput(session_id=session_id)
    )
    return SessionWithShotsResponse(
        session=_session_dto(out.session),
        shots=[_shot_dto(s) for s in out.shots],
    )


@router.post("/{session_id}/process", status_code=status.HTTP_202_ACCEPTED)
async def start_processing(
    session_id: str,
    _user_id: str = Depends(current_user_id),
    container=Depends(get_container),
) -> dict[str, str]:
    await container.start_processing.execute(
        StartProcessingInput(session_id=session_id)
    )
    return {"status": "queued"}
```

- [ ] **Step 4: Mount router in `main.py`** — add `from .routers.sessions import router as sessions_router` and `app.include_router(sessions_router)`.

- [ ] **Step 5: Run passing test**

Run: `uv run pytest apps/api/tests/test_sessions.py -v`
Expected: PASS — 6/6.

- [ ] **Step 6: Commit**

```bash
git add apps/api
git commit -m "feat(api): sessions router (create, list, get, /process)"
```

---

## Task 18: Shots router

**Files:**
- Create: `apps/api/src/golf_api/routers/shots.py`
- Modify: `main.py` (mount)
- Create: `apps/api/tests/test_shots.py`

- [ ] **Step 1: Failing test FIRST**

```python
from fastapi.testclient import TestClient


def _login(client: TestClient) -> None:
    client.post("/auth/login", json={"email": "dev@local", "password": "dev"})


def _ready_session_with_two_auto_shots(client: TestClient) -> str:
    """Helper: create session, mark session ready by directly seeding container."""
    create = client.post("/sessions", json={"originalFilename": "a.mp4"})
    sid = create.json()["sessionId"]

    # Bypass: poke the in-memory repo via app.state.container to mark READY + add 2 shots
    from datetime import UTC, datetime
    from golf_domain.session import SessionStatus
    from golf_domain.shot import Shot, ShotSource
    from golf_domain.value_objects import Confidence

    container = client.app.state.container
    sessions = container.sessions_repo
    shots = container.shots_repo
    s = sessions._items[sid]  # noqa: SLF001
    sessions._items[sid] = s.model_copy(  # noqa: SLF001
        update={"status": SessionStatus.READY, "shot_count": 2}
    )
    now = datetime(2026, 4, 28, tzinfo=UTC)
    for i in (1, 2):
        shots._items[f"shot_{i}"] = Shot(  # noqa: SLF001
            id=f"shot_{i}",
            session_id=sid,
            index=i,
            t_impact=10.0 * i,
            t_start=8.0 * i,
            t_end=15.0 * i,
            confidence=Confidence(value=0.9),
            source=ShotSource.AUTO,
            clip_key=None,
            created_at=now,
            updated_at=now,
        )
    return sid


def test_update_shot_boundary(client: TestClient):
    _login(client)
    sid = _ready_session_with_two_auto_shots(client)
    r = client.patch(
        f"/sessions/{sid}/shots/shot_1",
        json={"tStart": 7.0, "tEnd": 16.0},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["tStart"] == 7.0
    assert body["tEnd"] == 16.0


def test_update_shot_boundary_invalid_window_returns_422(client: TestClient):
    _login(client)
    sid = _ready_session_with_two_auto_shots(client)
    r = client.patch(
        f"/sessions/{sid}/shots/shot_1",
        json={"tStart": 11.0, "tEnd": 12.0},  # impact 10 outside [11,12]
    )
    assert r.status_code == 422


def test_add_manual_shot(client: TestClient):
    _login(client)
    sid = _ready_session_with_two_auto_shots(client)
    r = client.post(
        f"/sessions/{sid}/shots",
        json={"tImpact": 100.0, "tStart": 98.0, "tEnd": 105.0},
    )
    assert r.status_code == 201
    body = r.json()
    assert body["index"] == 3
    assert body["source"] == "manual"


def test_delete_shot(client: TestClient):
    _login(client)
    sid = _ready_session_with_two_auto_shots(client)
    r = client.delete(f"/sessions/{sid}/shots/shot_1")
    assert r.status_code == 204
    detail = client.get(f"/sessions/{sid}").json()
    assert {s["id"] for s in detail["shots"]} == {"shot_2"}


def test_update_unauthenticated(client: TestClient):
    r = client.patch(
        "/sessions/x/shots/y", json={"tStart": 1.0, "tEnd": 2.0}
    )
    assert r.status_code == 401
```

- [ ] **Step 2: Run failing test**

Run: `uv run pytest apps/api/tests/test_shots.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement `routers/shots.py`**

```python
from fastapi import APIRouter, Depends, status

from golf_api.deps.auth import current_user_id, get_container
from golf_api.routers.sessions import _shot_dto
from golf_application.use_cases.add_manual_shot import AddManualShotInput
from golf_application.use_cases.delete_shot import DeleteShotInput
from golf_application.use_cases.update_shot_boundary import (
    UpdateShotBoundaryInput,
)
from golf_contracts import (
    AddManualShotRequest,
    ShotDto,
    UpdateShotBoundaryRequest,
)


router = APIRouter(prefix="/sessions/{session_id}/shots", tags=["shots"])


@router.patch("/{shot_id}", response_model=ShotDto)
async def update_boundary(
    session_id: str,
    shot_id: str,
    req: UpdateShotBoundaryRequest,
    _user_id: str = Depends(current_user_id),
    container=Depends(get_container),
) -> ShotDto:
    shot = await container.update_shot_boundary.execute(
        UpdateShotBoundaryInput(
            session_id=session_id,
            shot_id=shot_id,
            t_start=req.t_start,
            t_end=req.t_end,
        )
    )
    return _shot_dto(shot)


@router.post(
    "", status_code=status.HTTP_201_CREATED, response_model=ShotDto
)
async def add_manual(
    session_id: str,
    req: AddManualShotRequest,
    _user_id: str = Depends(current_user_id),
    container=Depends(get_container),
) -> ShotDto:
    shot = await container.add_manual_shot.execute(
        AddManualShotInput(
            session_id=session_id,
            t_impact=req.t_impact,
            t_start=req.t_start,
            t_end=req.t_end,
        )
    )
    return _shot_dto(shot)


@router.delete("/{shot_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_shot(
    session_id: str,
    shot_id: str,
    _user_id: str = Depends(current_user_id),
    container=Depends(get_container),
) -> None:
    await container.delete_shot.execute(
        DeleteShotInput(session_id=session_id, shot_id=shot_id)
    )
```

- [ ] **Step 4: Mount router in `main.py`**.

- [ ] **Step 5: Run tests**

Run: `uv run pytest apps/api/tests/test_shots.py -v`
Expected: PASS — 5/5.

- [ ] **Step 6: Commit**

```bash
git add apps/api
git commit -m "feat(api): shots router (PATCH/POST/DELETE)"
```

---

## Task 19: Upload + Export routers

**Files:**
- Create: `apps/api/src/golf_api/routers/upload.py`
- Create: `apps/api/src/golf_api/routers/export.py`
- Modify: `main.py` (mount)
- Create: `apps/api/tests/test_upload.py`
- Create: `apps/api/tests/test_export.py`

- [ ] **Step 1: Failing tests FIRST**

`apps/api/tests/test_upload.py`:
```python
from fastapi.testclient import TestClient


def _login(client: TestClient) -> None:
    client.post("/auth/login", json={"email": "dev@local", "password": "dev"})


def test_upload_url_for_existing_session(client: TestClient):
    _login(client)
    create = client.post("/sessions", json={"originalFilename": "x.mp4"})
    sid = create.json()["sessionId"]
    r = client.post(f"/sessions/{sid}/upload-url")
    assert r.status_code == 200
    body = r.json()
    assert "url" in body
    assert "expiresAt" in body


def test_upload_url_404_when_missing(client: TestClient):
    _login(client)
    r = client.post("/sessions/missing/upload-url")
    assert r.status_code == 404
```

`apps/api/tests/test_export.py`:
```python
from fastapi.testclient import TestClient


def _login(client: TestClient) -> None:
    client.post("/auth/login", json={"email": "dev@local", "password": "dev"})


def test_export_requires_ready_session(client: TestClient):
    _login(client)
    create = client.post("/sessions", json={"originalFilename": "x.mp4"})
    sid = create.json()["sessionId"]
    # session is in UPLOADING, not READY → assert_editable fails → 409
    r = client.post(f"/sessions/{sid}/export")
    assert r.status_code == 409


def test_export_when_ready_returns_signed_get_url(client: TestClient):
    from datetime import UTC, datetime
    from golf_domain.session import SessionStatus

    _login(client)
    create = client.post("/sessions", json={"originalFilename": "x.mp4"})
    sid = create.json()["sessionId"]
    container = client.app.state.container
    s = container.sessions_repo._items[sid]  # noqa: SLF001
    container.sessions_repo._items[sid] = s.model_copy(  # noqa: SLF001
        update={"status": SessionStatus.READY, "updated_at": datetime(2026, 4, 28, tzinfo=UTC)}
    )
    r = client.post(f"/sessions/{sid}/export")
    assert r.status_code == 200
    body = r.json()
    assert body["exportId"].startswith("exp_")
    assert "signedDownloadUrl" in body
```

- [ ] **Step 2: Run failing tests**

Run: `uv run pytest apps/api/tests/test_upload.py apps/api/tests/test_export.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement `routers/upload.py`**

```python
from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from golf_api.deps.auth import current_user_id, get_container
from golf_application.use_cases.request_signed_upload_url import (
    RequestSignedUploadUrlInput,
)


router = APIRouter(prefix="/sessions", tags=["upload"])


class UploadUrlResponse(BaseModel):
    url: str
    expires_at: datetime
    model_config = {"populate_by_name": True}


@router.post("/{session_id}/upload-url", response_model=UploadUrlResponse)
async def upload_url(
    session_id: str,
    _user_id: str = Depends(current_user_id),
    container=Depends(get_container),
) -> UploadUrlResponse:
    signed = await container.request_upload_url.execute(
        RequestSignedUploadUrlInput(session_id=session_id)
    )
    return UploadUrlResponse(url=signed.url, expires_at=signed.expires_at)
```

- [ ] **Step 4: Implement `routers/export.py`**

```python
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from golf_api.deps.auth import current_user_id, get_container
from golf_application.use_cases.export_session_zip import (
    ExportSessionZipInput,
)


router = APIRouter(prefix="/sessions", tags=["export"])


class ExportResponse(BaseModel):
    export_id: str
    signed_download_url: str
    model_config = {"populate_by_name": True}


@router.post("/{session_id}/export", response_model=ExportResponse)
async def export(
    session_id: str,
    _user_id: str = Depends(current_user_id),
    container=Depends(get_container),
) -> ExportResponse:
    out = await container.export_session_zip.execute(
        ExportSessionZipInput(session_id=session_id)
    )
    return ExportResponse(
        export_id=out.export_id, signed_download_url=out.signed_download_url
    )
```

- [ ] **Step 5: Mount routers in `main.py`** — add upload + export router includes.

- [ ] **Step 6: Run tests**

Run: `uv run pytest apps/api/tests/test_upload.py apps/api/tests/test_export.py -v`
Expected: PASS — 4/4.

- [ ] **Step 7: Commit**

```bash
git add apps/api
git commit -m "feat(api): upload-url + export routers"
```

---

## Task 20: SSE realtime router

**Files:**
- Create: `apps/api/src/golf_api/routers/realtime.py`
- Modify: `main.py` (mount)
- Create: `apps/api/tests/test_realtime.py`

This streams Redis pub/sub messages over Server-Sent Events. In tests we use `fakeredis` and inject it directly via `container.redis`.

- [ ] **Step 1: Update test conftest to support real Redis (fake) for realtime tests**

Add to `apps/api/tests/conftest.py` after the existing fixtures:

```python
import fakeredis.aioredis

@pytest.fixture
def container_with_redis(container) -> Container:
    container.redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    return container


@pytest.fixture
def client_with_redis(container_with_redis) -> TestClient:
    app = create_app(env="test")
    app.state.container = container_with_redis
    return TestClient(app)
```

- [ ] **Step 2: Failing tests FIRST**

`apps/api/tests/test_realtime.py`:
```python
import asyncio
import json

import pytest
from httpx import ASGITransport, AsyncClient

from golf_api.main import create_app


def _login(c) -> None:
    c.post("/auth/login", json={"email": "dev@local", "password": "dev"})


def test_sse_unauthenticated_401(client_with_redis):
    r = client_with_redis.get("/sessions/ses_1/events")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_sse_delivers_published_event(container_with_redis):
    """End-to-end: subscribe, publish into fakeredis, receive over SSE."""
    app = create_app(env="test")
    app.state.container = container_with_redis

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # login
        await ac.post(
            "/auth/login", json={"email": "dev@local", "password": "dev"}
        )

        async with ac.stream("GET", "/sessions/ses_1/events") as resp:
            assert resp.status_code == 200

            # Give the route a tick to subscribe before publishing
            async def _publish_after_delay():
                await asyncio.sleep(0.1)
                await container_with_redis.redis.publish(
                    "session:ses_1",
                    json.dumps(
                        {
                            "type": "session.shot.detected",
                            "sessionId": "ses_1",
                            "payload": {"shotId": "shot_1", "confidence": 0.9},
                            "occurredAt": "2026-04-28T10:00:00Z",
                        }
                    ),
                )

            publisher = asyncio.create_task(_publish_after_delay())
            try:
                async for line in resp.aiter_lines():
                    if line.startswith("data:"):
                        payload = json.loads(line[5:].strip())
                        assert payload["type"] == "session.shot.detected"
                        return
            finally:
                publisher.cancel()
            pytest.fail("never received SSE event")
```

NOTE: if the second test proves flaky in CI (timing-sensitive on fakeredis pubsub), it's acceptable to mark it `@pytest.mark.skip(reason="flaky e2e — manual verification required for SSE delivery")` for Plan 2 and rely on the unit test in `libs/infrastructure/tests/queue/test_event_publisher.py` (Task 10) for publisher correctness. The 401 test must remain.

- [ ] **Step 3: Run failing test**

Run: `uv run pytest apps/api/tests/test_realtime.py -v`
Expected: FAIL.

- [ ] **Step 4: Implement `routers/realtime.py`**

```python
import asyncio
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, Request
from sse_starlette.sse import EventSourceResponse

from golf_api.deps.auth import current_user_id, get_container


router = APIRouter(prefix="/sessions", tags=["realtime"])


@router.get("/{session_id}/events")
async def stream_events(
    session_id: str,
    request: Request,
    _user_id: str = Depends(current_user_id),
    container=Depends(get_container),
) -> EventSourceResponse:
    pubsub = container.redis.pubsub()
    await pubsub.subscribe(f"session:{session_id}")

    async def _events() -> AsyncIterator[dict]:
        try:
            while True:
                if await request.is_disconnected():
                    break
                msg = await pubsub.get_message(
                    ignore_subscribe_messages=True, timeout=1.0
                )
                if msg is None:
                    await asyncio.sleep(0)
                    continue
                yield {"data": msg["data"]}
        finally:
            await pubsub.unsubscribe(f"session:{session_id}")
            await pubsub.aclose()

    return EventSourceResponse(_events())
```

- [ ] **Step 5: Mount router in `main.py`**.

- [ ] **Step 6: Run test**

Run: `uv run pytest apps/api/tests/test_realtime.py -v`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add apps/api
git commit -m "feat(api): SSE realtime router via Redis pub/sub"
```

---

## Task 21: docker-compose.dev.yml + .env.example

**Files:**
- Create: `docker-compose.dev.yml`
- Create: `.env.example`

- [ ] **Step 1: Create `docker-compose.dev.yml`**

```yaml
services:
  mongo:
    image: mongo:7
    ports:
      - "27017:27017"
    volumes:
      - mongo-data:/data/db

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

  minio:
    image: minio/minio:latest
    command: server /data --console-address ":9001"
    ports:
      - "9000:9000"
      - "9001:9001"
    environment:
      MINIO_ROOT_USER: dev
      MINIO_ROOT_PASSWORD: devsecret
    volumes:
      - minio-data:/data

volumes:
  mongo-data:
  minio-data:
```

- [ ] **Step 2: Create `.env.example`**

```
MONGODB_URI=mongodb://localhost:27017
MONGODB_DATABASE=golf_dev

REDIS_URL=redis://localhost:6379/0

R2_ENDPOINT=http://localhost:9000
R2_ACCESS_KEY=dev
R2_SECRET_KEY=devsecret
R2_BUCKET=golf-dev
R2_REGION=us-east-1

JWT_SECRET=dev_dev_dev_dev_dev_dev_dev_dev_dev_dev
JWT_ISSUER=golf-shot-cutter
JWT_TTL_SECONDS=3600

SIGNED_URL_TTL_SECONDS=900
CORS_ORIGINS=http://localhost:3000

APP_ENV=dev
```

- [ ] **Step 3: Manually verify dev stack boots**

Run (separate terminal): `docker compose -f docker-compose.dev.yml up -d`. Wait ~10s.

Then: `cp .env.example .env`. Then `uv run uvicorn golf_api.main:app --port 8000 --reload`. Hit `http://localhost:8000/health` → expect `{"status":"ok"}`.

If everything boots, kill server + `docker compose down`. (No automated test for this; manual smoke.)

- [ ] **Step 4: Commit**

```bash
git add docker-compose.dev.yml .env.example
git commit -m "chore(dev): docker-compose for mongo/redis/minio + .env.example"
```

---

## Task 22: Bare-bones `apps/api/Dockerfile`

**Files:**
- Create: `apps/api/Dockerfile`
- Create: `apps/api/.dockerignore`

We'll tune for production in Plan 5; here we just want a runnable image.

- [ ] **Step 1: Create `apps/api/Dockerfile`**

```dockerfile
# syntax=docker/dockerfile:1.7

FROM python:3.11-slim AS base
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
RUN apt-get update -y && apt-get install -y --no-install-recommends curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:$PATH"

WORKDIR /app

# Copy workspace metadata first for better layer caching
COPY pyproject.toml uv.lock ./
COPY libs/domain/pyproject.toml libs/domain/pyproject.toml
COPY libs/application/pyproject.toml libs/application/pyproject.toml
COPY libs/infrastructure/pyproject.toml libs/infrastructure/pyproject.toml
COPY libs/contracts/generated/python/pyproject.toml libs/contracts/generated/python/pyproject.toml
COPY apps/api/pyproject.toml apps/api/pyproject.toml

# Lock-respecting install of full workspace
RUN uv sync --frozen --no-dev --all-packages || uv sync --no-dev --all-packages

# Copy source
COPY libs ./libs
COPY apps/api ./apps/api

EXPOSE 8000
CMD ["uv", "run", "--package", "golf-api", "uvicorn", "golf_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 2: Create `apps/api/.dockerignore`**

```
**/__pycache__
**/*.pyc
**/.pytest_cache
**/.ruff_cache
**/.venv
**/.nx
**/.import_linter_cache
**/node_modules
**/dist
**/coverage
.git
docs
docker-compose.dev.yml
.env
.env.local
```

- [ ] **Step 3: Manual smoke (optional — skip if Docker not available locally)**

Run: `docker build -t golf-api:dev -f apps/api/Dockerfile .`. Optionally `docker run --rm -p 8000:8000 --env-file .env golf-api:dev` and hit `/health`.

If Docker isn't accessible from your environment, just confirm the Dockerfile exists and is syntactically valid (`docker buildx build --check . -f apps/api/Dockerfile` if available).

- [ ] **Step 4: Commit**

```bash
git add apps/api/Dockerfile apps/api/.dockerignore
git commit -m "chore(api): minimal Dockerfile + .dockerignore"
```

---

## Task 23: Final verification

- [ ] **Step 1: Full Python test suite**

Run: `uv run pytest -v`
Expected: ~80+ tests passing across libs/domain (16), libs/application (25), libs/infrastructure (~25), apps/api (~25).

- [ ] **Step 2: import-linter**

Run: `uv run lint-imports`
Expected: `Contracts: 1 kept, 0 broken.`

- [ ] **Step 3: Nx test**

Run: `pnpm nx run-many -t test`
Expected: `@golf/contracts` vitest passes 3/3.

- [ ] **Step 4: Lint**

Run: `pnpm exec biome check . && uv run ruff check .`
Expected: No errors.

- [ ] **Step 5: Pre-commit**

Run: `uv tool run pre-commit run --all-files`
Expected: All hooks pass.

- [ ] **Step 6: Tag**

```bash
git tag v0.2.0-backend
git log --oneline | head -25
```

---

## Done criteria

- All adapters in `libs/infrastructure` implement Plan 1 ports against real Mongo / R2 / Redis with passing integration tests using mongomock-motor / moto / fakeredis.
- `apps/api` exposes auth + sessions + shots + upload + export + SSE endpoints; all routes pass integration tests against in-memory fakes via DI override.
- Pydantic Contracts package available at `golf_contracts` for wire-format DTOs.
- `docker-compose.dev.yml` brings up mongo/redis/minio for local dev.
- import-linter green for the 4-layer architecture (domain ← application ← infrastructure ← api).
- Tag `v0.2.0-backend` set.

## Carry-overs / known gaps

- **Worker is still a stub** — `start_processing` enqueues a Celery job but no consumer exists. Plan 3 builds `apps/worker` and the actual CV/audio pipeline.
- **Single-user dev auth** — `_DEV_USERS = {"dev@local": "dev"}`. Plan 5 wires real user storage.
- **Contracts codegen via tsx** is best-effort — falls back to hand-written Pydantic if codegen tooling is fragile. Plan 4 (frontend) revisits.
- **Pre-roll/post-roll edge case** — `t_start = max(0, t_impact - pre_roll)` clamping plus the `Shot` invariant `t_start < t_impact` is unsafe if `t_impact == 0`. Use cases never produce that today, but worker pipeline (Plan 3) should refuse `t_impact ≤ pre_roll` candidates.
