# Plan 3 — Refactor to Service + Repository pattern (Tevadin-style)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development.

**Goal:** Restructure the Python codebase from a uv-workspace Clean Architecture (`libs/domain` + `libs/application` + `libs/infrastructure` + `apps/api`) into a single-package Service + Repository layout matching the Tevadin AI pattern, using `dependency-injector` for DI. Business logic is preserved; only structure changes.

**Architecture target:**

```
apps/api/
  pyproject.toml                  # the only Python project; absorbs all libs
  Dockerfile
  app/
    main.py                       # FastAPI app + lifespan
    core/
      config.py                   # Settings (UPPERCASE Field-based; was libs/infrastructure/settings.py)
      container.py                # dependency_injector DeclarativeContainer
      models/                     # domain entities (was libs/domain/)
        __init__.py
        ids.py
        value_objects.py
        session.py
        shot.py
        events.py
        errors.py
      schemas/                    # wire DTOs (was libs/contracts/python + per-router models)
        __init__.py
        sessions.py
        shots.py
        events.py
        responses.py              # ResponseSuccess + ResponseError envelope
    api/
      v1/
        __init__.py
        endpoints/
          __init__.py
          health.py
          auth.py
          sessions.py
          shots.py
          upload.py
          export.py
          realtime.py
    services/                     # business logic (was libs/application/use_cases/)
      __init__.py
      session_service.py          # consolidates create/list/get/start_processing/request_upload_url
      shot_service.py             # consolidates update_boundary/add_manual/delete
      processing_service.py       # ProcessVideo orchestration (worker entry)
      export_service.py
      errors.py                   # ApplicationError hierarchy (was libs/application/errors.py)
    repository/                   # data access (was libs/infrastructure/{mongo,r2,queue,auth})
      __init__.py
      mongo/
        client.py
        documents.py
        indexes.py
        session_repository.py     # MongoSessionRepository → SessionRepository
        shot_repository.py
      r2/
        storage_repository.py     # R2StorageGateway → R2StorageRepository
      queue/
        celery_app.py
        job_queue_repository.py
        event_publisher_repository.py
      auth/
        jwt_repository.py
      clock.py
      id_generator.py
    middleware/
      request_id.py
      error_handler.py
    deps/
      auth.py                     # current_user_id (JWT cookie)
  tests/
    __init__.py
    conftest.py
    test_health.py
    test_middleware.py
    test_auth.py
    test_sessions.py
    test_shots.py
    test_upload.py
    test_export.py
    test_realtime.py
    services/
      test_session_service.py
      test_shot_service.py
      test_processing_service.py
      test_export_service.py
    repository/
      mongo/
        test_documents.py
        test_session_repository.py
        test_shot_repository.py
        test_indexes.py
      r2/
        test_storage_repository.py
      queue/
        test_job_queue.py
        test_event_publisher.py
      auth/
        test_jwt_repository.py
      test_clock_and_ids.py
      test_settings.py
    fakes/
      in_memory_repos.py
      fake_clock.py
      fake_id_generator.py
      fake_storage.py
      fake_queue.py
      fake_publisher.py
```

After the refactor, **only `apps/api` is a Python project**. `libs/contracts/` (TypeScript zod) stays for Plan 5 frontend; everything else under `libs/` gets removed.

**Conventions (from Tevadin):**
- All config vars UPPERCASE.
- `dependency_injector.containers.DeclarativeContainer` with `providers.Singleton` for repos + clock + ids + jwt + redis + mongo, `providers.Factory` for services.
- Endpoints use `@inject` + `Depends(Provide[Container.x])` instead of reaching into `request.app.state.container`.
- All endpoints return `ResponseSuccess(data=...)` or raise — middleware turns errors into `ResponseError`.
- No Protocol-based ports. Services depend on concrete `Repository` classes typed directly.
- Drop `import-linter`. Architecture compliance via folder layout + code review.

**Tech additions:** `dependency-injector >= 4.42`. Everything else carries over.

**Pre-state:** HEAD `e397c24` on `main`, tag `v0.2.0-backend`. 98 pytest passing + 1 skipped (SSE e2e).

---

## Task 1: Add `dependency-injector` dep + scaffold `apps/api/app/` skeleton

**Files:**
- Modify: `apps/api/pyproject.toml` (absorb all infra/domain/application/contracts deps; add `dependency-injector`)
- Create: `apps/api/app/__init__.py`
- Create: `apps/api/app/core/__init__.py`
- Modify: root `pyproject.toml` workspace members (drop libs, leave only `apps/api`)

- [ ] **Step 1: Update `apps/api/pyproject.toml`**

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
    "pydantic>=2.9",
    "pydantic-settings>=2.5",
    "dependency-injector>=4.42",
    "motor>=3.6",
    "boto3>=1.35",
    "celery>=5.4",
    "redis>=5.1",
    "python-jose[cryptography]>=3.3",
    "python-ulid>=2.7",
    "structlog>=24.4",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["app"]
```

(Drop `[tool.uv.sources]` and the `golf-domain`/`golf-application`/`golf-infrastructure`/`golf-contracts` workspace deps; package `app/` directly.)

- [ ] **Step 2: Update root `pyproject.toml`**

Replace `[tool.uv.workspace]` block with:
```toml
[tool.uv.workspace]
members = ["apps/api"]
```

(`apps/worker` will be re-added in Plan 4. `libs/contracts/generated/python` is gone — Pydantic schemas now live inside `apps/api/app/core/schemas/`.)

Also drop `pythonpath = ["libs/application/tests"]` from `[tool.pytest.ini_options]` — fakes will live in `apps/api/tests/fakes/` natively.

- [ ] **Step 3: Create skeleton dirs + init files**

```bash
mkdir -p apps/api/app/{core/models,core/schemas,api/v1/endpoints,services,repository/mongo,repository/r2,repository/queue,repository/auth,middleware,deps}
touch apps/api/app/__init__.py
touch apps/api/app/core/__init__.py
touch apps/api/app/core/models/__init__.py
touch apps/api/app/core/schemas/__init__.py
touch apps/api/app/api/__init__.py
touch apps/api/app/api/v1/__init__.py
touch apps/api/app/api/v1/endpoints/__init__.py
touch apps/api/app/services/__init__.py
touch apps/api/app/repository/__init__.py
touch apps/api/app/repository/mongo/__init__.py
touch apps/api/app/repository/r2/__init__.py
touch apps/api/app/repository/queue/__init__.py
touch apps/api/app/repository/auth/__init__.py
touch apps/api/app/middleware/__init__.py
touch apps/api/app/deps/__init__.py
```

- [ ] **Step 4: Sync workspace**

Run: `uv sync --all-packages`
Expected: `golf-api==0.0.0` only; old workspace members gone from lockfile.

If sync errors because `apps/worker` listed but missing — already fixed in Step 2. If anything else complains, investigate.

- [ ] **Step 5: Commit**

```bash
git add apps/api pyproject.toml uv.lock
git commit -m "chore: scaffold app/ layout + dependency-injector dep + collapse workspace"
```

---

## Task 2: Move domain models → `app/core/models/`

Pure file moves with `git mv` to preserve history, then update internal imports.

**Files (rename, not copy):**
- `libs/domain/src/golf_domain/ids.py` → `apps/api/app/core/models/ids.py`
- `libs/domain/src/golf_domain/value_objects.py` → `apps/api/app/core/models/value_objects.py`
- `libs/domain/src/golf_domain/session.py` → `apps/api/app/core/models/session.py`
- `libs/domain/src/golf_domain/shot.py` → `apps/api/app/core/models/shot.py`
- `libs/domain/src/golf_domain/events.py` → `apps/api/app/core/models/events.py`
- `libs/domain/src/golf_domain/errors.py` → `apps/api/app/core/models/errors.py`
- `libs/domain/src/golf_domain/__init__.py` → `apps/api/app/core/models/__init__.py` (overwrite)

- [ ] **Step 1: Move with git**

```bash
git mv libs/domain/src/golf_domain/ids.py apps/api/app/core/models/ids.py
git mv libs/domain/src/golf_domain/value_objects.py apps/api/app/core/models/value_objects.py
git mv libs/domain/src/golf_domain/session.py apps/api/app/core/models/session.py
git mv libs/domain/src/golf_domain/shot.py apps/api/app/core/models/shot.py
git mv libs/domain/src/golf_domain/events.py apps/api/app/core/models/events.py
git mv libs/domain/src/golf_domain/errors.py apps/api/app/core/models/errors.py
```

(Don't move `__init__.py` directly — overwrite the placeholder created in Task 1 instead. Then delete the old `libs/domain/src/golf_domain/__init__.py`.)

- [ ] **Step 2: Update `apps/api/app/core/models/__init__.py`**

```python
"""Pure-Python domain models. No framework imports beyond Pydantic."""

from .errors import (
    DomainError,
    InvalidStateTransitionError,
    InvalidValueError,
)
from .events import (
    DomainEvent,
    SessionFailed,
    SessionProcessingStarted,
    SessionReady,
    ShotBoundaryUpdated,
    ShotDeleted,
    ShotDetected,
)
from .ids import ExportId, SessionId, ShotId, UserId
from .session import Session, SessionError, SessionStatus
from .shot import Shot, ShotSource
from .value_objects import Confidence, TimeRange

__all__ = [
    "Confidence",
    "DomainError",
    "DomainEvent",
    "ExportId",
    "InvalidStateTransitionError",
    "InvalidValueError",
    "Session",
    "SessionError",
    "SessionFailed",
    "SessionId",
    "SessionProcessingStarted",
    "SessionReady",
    "SessionStatus",
    "Shot",
    "ShotBoundaryUpdated",
    "ShotDeleted",
    "ShotDetected",
    "ShotId",
    "ShotSource",
    "TimeRange",
    "UserId",
]
```

- [ ] **Step 3: Update relative imports inside the moved files**

Each moved file's relative imports (`from .errors import ...`, `from .ids import ...`) keep the same form — they still work since the files are in the same package. No changes needed inside the files themselves; only their location moved.

- [ ] **Step 4: Verify import works**

Run: `uv run python -c "from app.core.models import Session, Shot, Confidence; print(Session.__module__)"`
Expected: `app.core.models.session`.

If the import fails because `app/` isn't on the Python path, run from `apps/api` directory: `cd apps/api && uv run python -c "from app.core.models import Session"`. The Hatchling `packages = ["app"]` config in pyproject should make this work after `uv sync`.

- [ ] **Step 5: Commit**

```bash
git add apps/api/app/core/models libs/domain
git commit -m "refactor: move domain models → app/core/models/"
```

(`libs/domain/` should now be empty except possibly `pyproject.toml` and `tests/`. Don't delete those yet — Task 7 handles cleanup.)

---

## Task 3: Move repositories → `app/repository/` (rename to *Repository)

Rename infrastructure adapters to follow the Tevadin Repository naming convention. Strip the Protocol-based port abstraction (services will type against concrete classes).

**Renames:**
- `MongoSessionRepository` → keep as-is (already has Repository suffix)
- `MongoShotRepository` → keep
- `R2StorageGateway` → `R2StorageRepository`
- `CeleryJobQueue` → `CeleryJobQueueRepository`
- `RedisEventPublisher` → `RedisEventPublisherRepository`
- `JwtService` → `JwtRepository`

**File moves:**
- `libs/infrastructure/src/golf_infrastructure/mongo/*.py` → `apps/api/app/repository/mongo/*.py`
- `libs/infrastructure/src/golf_infrastructure/r2/storage_gateway.py` → `apps/api/app/repository/r2/storage_repository.py`
- `libs/infrastructure/src/golf_infrastructure/queue/celery_app.py` → `apps/api/app/repository/queue/celery_app.py`
- `libs/infrastructure/src/golf_infrastructure/queue/job_queue.py` → `apps/api/app/repository/queue/job_queue_repository.py`
- `libs/infrastructure/src/golf_infrastructure/queue/event_publisher.py` → `apps/api/app/repository/queue/event_publisher_repository.py`
- `libs/infrastructure/src/golf_infrastructure/auth/jwt_service.py` → `apps/api/app/repository/auth/jwt_repository.py`
- `libs/infrastructure/src/golf_infrastructure/clock.py` → `apps/api/app/repository/clock.py`
- `libs/infrastructure/src/golf_infrastructure/ids.py` → `apps/api/app/repository/id_generator.py`
- `libs/infrastructure/src/golf_infrastructure/settings.py` → `apps/api/app/core/config.py`

- [ ] **Step 1: `git mv` all 11 files** (one per `git mv`)

- [ ] **Step 2: Within each moved file:**

  - Update `from golf_application.errors import SessionNotFoundError` → `from app.services.errors import SessionNotFoundError`
  - Update `from golf_application.ports import SignedUrl, ProcessVideoJob` → repository helpers should now be defined inline OR imported from a shared `app/repository/types.py`. Define them locally:
  
    In `apps/api/app/repository/r2/storage_repository.py`, add at the top:
    ```python
    from datetime import datetime
    from pydantic import BaseModel
    
    class SignedUrl(BaseModel):
        url: str
        expires_at: datetime
    ```
    Drop the `from golf_application.ports import SignedUrl` import.
  
    In `apps/api/app/repository/queue/job_queue_repository.py`:
    ```python
    from pydantic import BaseModel
    from app.core.models.ids import SessionId
    
    class ProcessVideoJob(BaseModel):
        session_id: SessionId
    ```
    Drop the import from `golf_application.ports`.

  - Update `from golf_domain.X import Y` → `from app.core.models.X import Y`
  - Update `from golf_domain.events import DomainEvent` → `from app.core.models.events import DomainEvent`
  - Class renames in source: `R2StorageGateway` → `R2StorageRepository`; `CeleryJobQueue` → `CeleryJobQueueRepository`; `RedisEventPublisher` → `RedisEventPublisherRepository`; `JwtService` → `JwtRepository`. (`MongoSessionRepository` and `MongoShotRepository` already have correct names.)
  - `JwtVerifyError` stays as-is in `jwt_repository.py`.
  - `UlidIdGenerator` and `SystemClock` keep names (no Repository suffix — they're infrastructure utilities, not data access).

- [ ] **Step 3: Update `apps/api/app/core/config.py`**

The Settings class itself needs no changes (already uses `Field(alias="UPPERCASE")` per Plan 2 Task 2). Just verify the import at the top still works after the move.

Add `__all__ = ["Settings"]` and rename `app/core/__init__.py` to expose the module path:

`apps/api/app/core/__init__.py`:
```python
"""Core application primitives: config, container, models, schemas."""
```

- [ ] **Step 4: Verify imports**

Run: `uv run python -c "from app.repository.mongo.session_repository import MongoSessionRepository; from app.repository.r2.storage_repository import R2StorageRepository; from app.core.config import Settings; print('ok')"`
Expected: `ok`.

- [ ] **Step 5: Commit**

```bash
git add apps/api/app libs/infrastructure
git commit -m "refactor: move infrastructure → app/repository/ + rename to *Repository"
```

---

## Task 4: Consolidate use cases → `app/services/` (4 services)

Use cases get grouped by resource into 4 service classes. Each old use case becomes a method.

**Mapping:**

| Old class (libs/application/use_cases/) | New class (app/services/) | Method |
|---|---|---|
| `CreateSessionUseCase` | `SessionService` | `create(input)` |
| `RequestSignedUploadUrlUseCase` | `SessionService` | `request_upload_url(session_id)` |
| `StartProcessingUseCase` | `SessionService` | `start_processing(session_id)` |
| `ListSessionsUseCase` | `SessionService` | `list(user_id)` |
| `GetSessionWithShotsUseCase` | `SessionService` | `get_with_shots(session_id)` |
| `UpdateShotBoundaryUseCase` | `ShotService` | `update_boundary(input)` |
| `AddManualShotUseCase` | `ShotService` | `add_manual(input)` |
| `DeleteShotUseCase` | `ShotService` | `delete(input)` |
| `ProcessVideoUseCase` | `ProcessingService` | `process(input)` |
| `ExportSessionZipUseCase` | `ExportService` | `export(session_id)` |

Inputs/outputs (Pydantic models) stay the same shape, but renamed: `CreateSessionInput` → in-class types or moved to `app/core/schemas/sessions.py`. To keep the diff small, keep them as nested classes or top-level models adjacent to the service:

```python
# app/services/session_service.py

from datetime import datetime
from pydantic import BaseModel, Field

from app.core.models import (
    Session, SessionStatus, SessionId, UserId,
    SessionProcessingStarted,
)
from app.repository.clock import SystemClock
from app.repository.id_generator import UlidIdGenerator
from app.repository.mongo.session_repository import MongoSessionRepository
from app.repository.queue.event_publisher_repository import (
    RedisEventPublisherRepository,
)
from app.repository.queue.job_queue_repository import (
    CeleryJobQueueRepository, ProcessVideoJob,
)
from app.repository.r2.storage_repository import R2StorageRepository, SignedUrl
from app.services.errors import SessionNotFoundError


class CreateSessionInput(BaseModel):
    user_id: UserId | None
    original_filename: str = Field(min_length=1)
    pre_roll_seconds: float = Field(ge=0, default=2.0)
    post_roll_seconds: float = Field(ge=0, default=5.0)


class CreateSessionOutput(BaseModel):
    session_id: str
    signed_upload_url: str
    expires_at: datetime


class StartProcessingInput(BaseModel):
    session_id: SessionId


class ListSessionsInput(BaseModel):
    user_id: UserId | None


class GetSessionWithShotsInput(BaseModel):
    session_id: SessionId


class GetSessionWithShotsOutput(BaseModel):
    model_config = {"arbitrary_types_allowed": True}
    session: Session
    shots: list  # list[Shot]


class RequestSignedUploadUrlInput(BaseModel):
    session_id: SessionId


class SessionService:
    def __init__(
        self,
        *,
        sessions_repo: MongoSessionRepository,
        shots_repo,  # MongoShotRepository (forward ref)
        storage: R2StorageRepository,
        queue: CeleryJobQueueRepository,
        events: RedisEventPublisherRepository,
        clock: SystemClock,
        ids: UlidIdGenerator,
    ) -> None:
        self._sessions = sessions_repo
        self._shots = shots_repo
        self._storage = storage
        self._queue = queue
        self._events = events
        self._clock = clock
        self._ids = ids

    async def create(self, input: CreateSessionInput) -> CreateSessionOutput:
        # Same body as Plan 1 Task 10's CreateSessionUseCase.execute
        session_id = self._ids.session_id()
        raw_key = f"raw/{session_id}/{input.original_filename}"
        now = self._clock.now()
        signed = await self._storage.signed_put_url(raw_key, content_type="video/mp4")

        session = Session(
            id=session_id,
            user_id=input.user_id,
            raw_video_key=raw_key,
            status=SessionStatus.UPLOADING,
            pre_roll_seconds=input.pre_roll_seconds,
            post_roll_seconds=input.post_roll_seconds,
            shot_count=0,
            duration_seconds=0.0,
            error=None,
            created_at=now,
            updated_at=now,
        )
        await self._sessions.add(session)
        return CreateSessionOutput(
            session_id=session_id,
            signed_upload_url=signed.url,
            expires_at=signed.expires_at,
        )

    async def request_upload_url(self, input: RequestSignedUploadUrlInput) -> SignedUrl:
        session = await self._sessions.get(input.session_id)
        return await self._storage.signed_put_url(
            session.raw_video_key, content_type="video/mp4"
        )

    async def start_processing(self, input: StartProcessingInput) -> None:
        session = await self._sessions.get(input.session_id)

        if session.status is SessionStatus.UPLOADING:
            session = session.model_copy(
                update={"status": SessionStatus.QUEUED, "updated_at": self._clock.now()}
            )

        now = self._clock.now()
        moved = session.mark_processing(now=now)
        await self._sessions.update(moved)
        await self._queue.enqueue_process_video(ProcessVideoJob(session_id=moved.id))
        await self._events.publish(
            SessionProcessingStarted(session_id=moved.id, occurred_at=now)
        )

    async def list(self, input: ListSessionsInput) -> list[Session]:
        return await self._sessions.list_for_user(input.user_id)

    async def get_with_shots(
        self, input: GetSessionWithShotsInput
    ) -> GetSessionWithShotsOutput:
        session = await self._sessions.get(input.session_id)
        shots = await self._shots.list_by_session(session.id)
        return GetSessionWithShotsOutput(session=session, shots=shots)
```

Repeat for `ShotService`, `ProcessingService`, `ExportService` — copy the bodies from the corresponding old use case classes verbatim, just rename the public methods (e.g., `execute` → resource-specific verb).

- [ ] **Step 1: Create `app/services/errors.py`**

Move `libs/application/errors.py` → `apps/api/app/services/errors.py`. Same content, no edits.

```bash
git mv libs/application/src/golf_application/errors.py apps/api/app/services/errors.py
```

- [ ] **Step 2: Create the 4 service files**

Write each of: `apps/api/app/services/session_service.py`, `shot_service.py`, `processing_service.py`, `export_service.py`. Body details mirror the old use cases in the mapping table above.

For `ShotService`:
```python
# app/services/shot_service.py
from datetime import datetime
from pydantic import BaseModel

from app.core.models import (
    Confidence, SessionId, Shot, ShotBoundaryUpdated, ShotDeleted, ShotDetected,
    ShotId, ShotSource,
)
from app.repository.clock import SystemClock
from app.repository.id_generator import UlidIdGenerator
from app.repository.mongo.session_repository import MongoSessionRepository
from app.repository.mongo.shot_repository import MongoShotRepository
from app.repository.queue.event_publisher_repository import (
    RedisEventPublisherRepository,
)


class UpdateShotBoundaryInput(BaseModel):
    session_id: SessionId
    shot_id: ShotId
    t_start: float
    t_end: float


class AddManualShotInput(BaseModel):
    session_id: SessionId
    t_impact: float
    t_start: float
    t_end: float


class DeleteShotInput(BaseModel):
    session_id: SessionId
    shot_id: ShotId


class ShotService:
    def __init__(
        self,
        *,
        sessions_repo: MongoSessionRepository,
        shots_repo: MongoShotRepository,
        events: RedisEventPublisherRepository,
        clock: SystemClock,
        ids: UlidIdGenerator,
    ) -> None:
        self._sessions = sessions_repo
        self._shots = shots_repo
        self._events = events
        self._clock = clock
        self._ids = ids

    async def update_boundary(self, input: UpdateShotBoundaryInput) -> Shot:
        session = await self._sessions.get(input.session_id)
        session.assert_editable()
        shot = await self._shots.get(input.shot_id)
        now = self._clock.now()
        adjusted = shot.adjust_boundary(t_start=input.t_start, t_end=input.t_end, now=now)
        await self._shots.update(adjusted)
        await self._events.publish(
            ShotBoundaryUpdated(
                session_id=session.id, shot_id=adjusted.id,
                t_start=adjusted.t_start, t_end=adjusted.t_end,
                occurred_at=now,
            )
        )
        return adjusted

    async def add_manual(self, input: AddManualShotInput) -> Shot:
        session = await self._sessions.get(input.session_id)
        session.assert_editable()
        existing = await self._shots.list_by_session(session.id)
        next_index = (max(s.index for s in existing) + 1) if existing else 1
        now = self._clock.now()
        shot = Shot(
            id=self._ids.shot_id(),
            session_id=session.id,
            index=next_index,
            t_impact=input.t_impact,
            t_start=input.t_start,
            t_end=input.t_end,
            confidence=Confidence(value=1.0),
            source=ShotSource.MANUAL,
            clip_key=None,
            created_at=now,
            updated_at=now,
        )
        await self._shots.add(shot)
        # Update session.shot_count
        updated_session = session.model_copy(
            update={"shot_count": session.shot_count + 1, "updated_at": now}
        )
        await self._sessions.update(updated_session)
        await self._events.publish(
            ShotDetected(
                session_id=session.id, shot_id=shot.id,
                confidence=1.0, occurred_at=now,
            )
        )
        return shot

    async def delete(self, input: DeleteShotInput) -> None:
        session = await self._sessions.get(input.session_id)
        session.assert_editable()
        await self._shots.delete(input.shot_id)
        now = self._clock.now()
        new_count = max(0, session.shot_count - 1)
        updated_session = session.model_copy(
            update={"shot_count": new_count, "updated_at": now}
        )
        await self._sessions.update(updated_session)
        await self._events.publish(
            ShotDeleted(
                session_id=session.id, shot_id=input.shot_id, occurred_at=now,
            )
        )
```

For `ProcessingService`:
```python
# app/services/processing_service.py
from pydantic import BaseModel, Field

from app.core.models import (
    Confidence, SessionId, SessionReady, Shot, ShotDetected, ShotSource,
)
from app.repository.clock import SystemClock
from app.repository.id_generator import UlidIdGenerator
from app.repository.mongo.session_repository import MongoSessionRepository
from app.repository.mongo.shot_repository import MongoShotRepository
from app.repository.queue.event_publisher_repository import (
    RedisEventPublisherRepository,
)


class ShotCandidate(BaseModel):
    t_impact: float
    confidence: float = Field(ge=0.0, le=1.0)
    clip_key: str


class ProcessVideoInput(BaseModel):
    session_id: SessionId
    candidates: list[ShotCandidate]


class ProcessingService:
    def __init__(
        self,
        *,
        sessions_repo: MongoSessionRepository,
        shots_repo: MongoShotRepository,
        events: RedisEventPublisherRepository,
        clock: SystemClock,
        ids: UlidIdGenerator,
    ) -> None:
        self._sessions = sessions_repo
        self._shots = shots_repo
        self._events = events
        self._clock = clock
        self._ids = ids

    async def process(self, input: ProcessVideoInput) -> None:
        session = await self._sessions.get(input.session_id)
        now = self._clock.now()

        new_shots: list[Shot] = []
        for index, c in enumerate(input.candidates, start=1):
            t_start = max(0.0, c.t_impact - session.pre_roll_seconds)
            t_end = c.t_impact + session.post_roll_seconds
            shot = Shot(
                id=self._ids.shot_id(),
                session_id=session.id,
                index=index,
                t_impact=c.t_impact,
                t_start=t_start,
                t_end=t_end,
                confidence=Confidence(value=c.confidence),
                source=ShotSource.AUTO,
                clip_key=c.clip_key,
                created_at=now,
                updated_at=now,
            )
            new_shots.append(shot)

        await self._shots.add_many(new_shots)
        for s in new_shots:
            await self._events.publish(
                ShotDetected(
                    session_id=session.id, shot_id=s.id,
                    confidence=s.confidence.value, occurred_at=now,
                )
            )

        ready = session.mark_ready(shot_count=len(new_shots), now=now)
        await self._sessions.update(ready)
        await self._events.publish(
            SessionReady(
                session_id=session.id, shot_count=len(new_shots), occurred_at=now,
            )
        )
```

For `ExportService`:
```python
# app/services/export_service.py
from pydantic import BaseModel

from app.core.models import SessionId
from app.repository.id_generator import UlidIdGenerator
from app.repository.mongo.session_repository import MongoSessionRepository
from app.repository.r2.storage_repository import R2StorageRepository


class ExportSessionZipInput(BaseModel):
    session_id: SessionId


class ExportSessionZipOutput(BaseModel):
    export_id: str
    signed_download_url: str


class ExportService:
    def __init__(
        self,
        *,
        sessions_repo: MongoSessionRepository,
        storage: R2StorageRepository,
        ids: UlidIdGenerator,
    ) -> None:
        self._sessions = sessions_repo
        self._storage = storage
        self._ids = ids

    async def export(self, input: ExportSessionZipInput) -> ExportSessionZipOutput:
        session = await self._sessions.get(input.session_id)
        session.assert_editable()
        export_id = self._ids.export_id()
        key = f"exports/{session.id}/{export_id}.zip"
        signed = await self._storage.signed_get_url(key)
        return ExportSessionZipOutput(
            export_id=export_id, signed_download_url=signed.url
        )
```

- [ ] **Step 3: Verify imports**

Run from `/Users/user/golf-shot-cutter`:
```
uv run python -c "from app.services.session_service import SessionService; from app.services.shot_service import ShotService; from app.services.processing_service import ProcessingService; from app.services.export_service import ExportService; print('ok')"
```
Expected: `ok`.

- [ ] **Step 4: Commit**

```bash
git add apps/api/app/services libs/application
git commit -m "refactor: consolidate use cases → 4 services in app/services/"
```

(`libs/application/` is now mostly stale — Task 7 cleans it up.)

---

## Task 5: Build `dependency_injector` Container

**Files:**
- Create: `apps/api/app/core/container.py`

```python
"""Application DI container using dependency-injector."""

from celery import Celery
from dependency_injector import containers, providers
from motor.motor_asyncio import AsyncIOMotorClient
from redis.asyncio import Redis

from app.core.config import Settings
from app.repository.auth.jwt_repository import JwtRepository
from app.repository.clock import SystemClock
from app.repository.id_generator import UlidIdGenerator
from app.repository.mongo.client import get_database, make_client
from app.repository.mongo.session_repository import MongoSessionRepository
from app.repository.mongo.shot_repository import MongoShotRepository
from app.repository.queue.celery_app import make_celery_app
from app.repository.queue.event_publisher_repository import (
    RedisEventPublisherRepository,
)
from app.repository.queue.job_queue_repository import CeleryJobQueueRepository
from app.repository.r2.storage_repository import R2StorageRepository
from app.services.export_service import ExportService
from app.services.processing_service import ProcessingService
from app.services.session_service import SessionService
from app.services.shot_service import ShotService


class Container(containers.DeclarativeContainer):
    wiring_config = containers.WiringConfiguration(
        modules=[
            "app.api.v1.endpoints.health",
            "app.api.v1.endpoints.auth",
            "app.api.v1.endpoints.sessions",
            "app.api.v1.endpoints.shots",
            "app.api.v1.endpoints.upload",
            "app.api.v1.endpoints.export",
            "app.api.v1.endpoints.realtime",
            "app.deps.auth",
        ]
    )

    settings = providers.Singleton(Settings)

    # Infrastructure clients
    mongo_client = providers.Singleton(
        make_client,
        uri=settings.provided.mongodb_uri,
    )
    mongo_database = providers.Singleton(
        get_database,
        client=mongo_client,
        name=settings.provided.mongodb_database,
    )
    redis = providers.Singleton(
        lambda url: Redis.from_url(url, decode_responses=True),
        url=settings.provided.redis_url,
    )
    celery = providers.Singleton(
        make_celery_app,
        broker_url=settings.provided.redis_url,
        result_backend=settings.provided.redis_url,
    )

    # Repositories (singletons)
    sessions_repo = providers.Singleton(MongoSessionRepository, db=mongo_database)
    shots_repo = providers.Singleton(MongoShotRepository, db=mongo_database)
    storage_repo = providers.Singleton(
        R2StorageRepository,
        endpoint=settings.provided.r2_endpoint,
        access_key=settings.provided.r2_access_key,
        secret_key=settings.provided.r2_secret_key,
        bucket=settings.provided.r2_bucket,
        region=settings.provided.r2_region,
        ttl_seconds=settings.provided.signed_url_ttl_seconds,
    )
    queue_repo = providers.Singleton(CeleryJobQueueRepository, app=celery, eager=False)
    publisher_repo = providers.Singleton(RedisEventPublisherRepository, client=redis)
    jwt_repo = providers.Singleton(
        JwtRepository,
        secret=settings.provided.jwt_secret,
        issuer=settings.provided.jwt_issuer,
        ttl_seconds=settings.provided.jwt_ttl_seconds,
    )
    clock = providers.Singleton(SystemClock)
    ids = providers.Singleton(UlidIdGenerator)

    # Services (factories — fresh per request, but cheap to construct)
    session_service = providers.Factory(
        SessionService,
        sessions_repo=sessions_repo,
        shots_repo=shots_repo,
        storage=storage_repo,
        queue=queue_repo,
        events=publisher_repo,
        clock=clock,
        ids=ids,
    )
    shot_service = providers.Factory(
        ShotService,
        sessions_repo=sessions_repo,
        shots_repo=shots_repo,
        events=publisher_repo,
        clock=clock,
        ids=ids,
    )
    processing_service = providers.Factory(
        ProcessingService,
        sessions_repo=sessions_repo,
        shots_repo=shots_repo,
        events=publisher_repo,
        clock=clock,
        ids=ids,
    )
    export_service = providers.Factory(
        ExportService,
        sessions_repo=sessions_repo,
        storage=storage_repo,
        ids=ids,
    )
```

- [ ] **Step 1: Write `apps/api/app/core/container.py`** with the content above.

- [ ] **Step 2: Verify imports**

Run: `uv run python -c "from app.core.container import Container; print(Container.__name__)"`
Expected: `Container`.

If `dependency_injector` import fails, run `uv sync --all-packages` to ensure the dep installed.

- [ ] **Step 3: Commit**

```bash
git add apps/api/app/core/container.py
git commit -m "feat(core): dependency-injector Container with all services + repositories"
```

---

## Task 6: Move test fakes → `apps/api/tests/fakes/`

The fakes (in-memory repos, fake clock, etc.) live in `libs/application/tests/fakes/`. Move them.

- [ ] **Step 1: `git mv` the fake files**

```bash
mkdir -p apps/api/tests/fakes
git mv libs/application/tests/fakes/__init__.py apps/api/tests/fakes/__init__.py
git mv libs/application/tests/fakes/fake_clock.py apps/api/tests/fakes/fake_clock.py
git mv libs/application/tests/fakes/fake_id_generator.py apps/api/tests/fakes/fake_id_generator.py
git mv libs/application/tests/fakes/fake_publisher.py apps/api/tests/fakes/fake_publisher.py
git mv libs/application/tests/fakes/fake_queue.py apps/api/tests/fakes/fake_queue.py
git mv libs/application/tests/fakes/fake_storage.py apps/api/tests/fakes/fake_storage.py
git mv libs/application/tests/fakes/in_memory_repos.py apps/api/tests/fakes/in_memory_repos.py
```

- [ ] **Step 2: Update fakes' imports**

Inside each fake:
- `from golf_application.errors import ...` → `from app.services.errors import ...`
- `from golf_application.ports import SignedUrl` → `from app.repository.r2.storage_repository import SignedUrl`
- `from golf_application.ports import ProcessVideoJob` → `from app.repository.queue.job_queue_repository import ProcessVideoJob`
- `from golf_domain.X import Y` → `from app.core.models.X import Y` (or `from app.core.models import Y`)
- `from golf_domain.events import DomainEvent` → `from app.core.models.events import DomainEvent`

- [ ] **Step 3: Drop the obsolete pythonpath setting**

In root `pyproject.toml` `[tool.pytest.ini_options]`, the `pythonpath = ["libs/application/tests"]` line was added in Plan 2 Task 16. Remove it.

- [ ] **Step 4: Verify import**

Run: `uv run python -c "import sys; sys.path.insert(0, 'apps/api/tests'); from fakes.in_memory_repos import InMemorySessionRepository; print('ok')"`
Expected: `ok`.

- [ ] **Step 5: Commit**

```bash
git add apps/api/tests/fakes libs/application pyproject.toml
git commit -m "refactor: move test fakes → apps/api/tests/fakes/"
```

---

## Task 7: Migrate domain + application + infrastructure tests

Move the existing test files into the `apps/api/tests/` tree, updating import paths.

**File moves (parallel structure):**
- `libs/domain/tests/test_value_objects.py` → `apps/api/tests/core/models/test_value_objects.py`
- `libs/domain/tests/test_session.py` → `apps/api/tests/core/models/test_session.py`
- `libs/domain/tests/test_shot.py` → `apps/api/tests/core/models/test_shot.py`
- `libs/domain/tests/test_events.py` → `apps/api/tests/core/models/test_events.py`
- `libs/application/tests/use_cases/test_create_session.py` → `apps/api/tests/services/test_session_service.py`
- `libs/application/tests/use_cases/test_start_processing.py` → folded INTO `apps/api/tests/services/test_session_service.py` as additional test functions.
- `libs/application/tests/use_cases/test_queries.py` → folded INTO `apps/api/tests/services/test_session_service.py`.
- `libs/application/tests/use_cases/test_storage_use_cases.py` → split: signed-upload-url tests fold into `test_session_service.py`; export tests go to `apps/api/tests/services/test_export_service.py`.
- `libs/application/tests/use_cases/test_update_shot_boundary.py` → `apps/api/tests/services/test_shot_service.py`
- `libs/application/tests/use_cases/test_manual_shots.py` → folded INTO `apps/api/tests/services/test_shot_service.py`.
- `libs/application/tests/use_cases/test_process_video.py` → `apps/api/tests/services/test_processing_service.py`
- `libs/infrastructure/tests/*` → `apps/api/tests/repository/*` (mongo/, r2/, queue/, auth/, test_settings.py, test_clock_and_ids.py).

This is a lot of file moves. Do them as `git mv` to preserve blame, then update imports + class names + method names in each file:

- `from golf_domain.X import Y` → `from app.core.models.X import Y`
- `from golf_application.use_cases.create_session import CreateSessionInput, CreateSessionUseCase` → `from app.services.session_service import CreateSessionInput, SessionService`
- `CreateSessionUseCase(...)` → `SessionService(...)`
- `uc.execute(...)` calls become method calls — `service.create(...)`, `service.start_processing(...)`, etc. (Mapping table in Task 4 lists each use case's new method name.)
- `from ..fakes.X import Y` (relative) → `from tests.fakes.X import Y` if pytest can resolve, OR `from fakes.X import Y` with `pythonpath = ["apps/api/tests"]` in root pytest config. Pick whichever works after dropping the old `pythonpath = ["libs/application/tests"]`.

- [ ] **Step 1: Add a pytest pythonpath for the new fakes location**

In root `pyproject.toml` `[tool.pytest.ini_options]`:
```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["apps/api/tests"]
pythonpath = ["apps/api/tests"]
```

(Drop the old `testpaths = ["libs", "apps"]` and old `pythonpath`.)

- [ ] **Step 2: Move + edit test files** in batches:

  a. Domain tests → `apps/api/tests/core/models/`. Update imports only.
  b. Application use-case tests → `apps/api/tests/services/`. Update imports + class names + method calls.
  c. Infrastructure tests → `apps/api/tests/repository/`. Update imports.

  Don't try to do all at once. Work file by file. After each file's move + edits, run the relevant test path:

  ```
  uv run pytest apps/api/tests/core/models/ -v
  uv run pytest apps/api/tests/services/test_session_service.py -v
  ...
  ```

  Make each green before moving the next.

- [ ] **Step 3: Move existing apps/api tests too**

The Plan 2 router tests (`apps/api/tests/test_health.py`, `test_auth.py`, etc.) stay in place but their conftest needs updating:
- `from golf_api.deps.container import Container` → `from app.core.container import Container`
- `from golf_api.main import create_app` → `from app.main import create_app`
- `from golf_application.tests.fakes.X` → `from fakes.X` (after pythonpath update)
- The Plan 2 test pattern of building a Container manually with kwargs no longer works — `dependency_injector.Container` is wired declaratively. For tests, **override providers**:

  ```python
  @pytest.fixture
  def container():
      from app.core.container import Container
      from fakes.fake_clock import FakeClock
      from fakes.fake_id_generator import FakeIdGenerator
      # ... etc
      from datetime import UTC, datetime

      c = Container()
      c.sessions_repo.override(InMemorySessionRepository())
      c.shots_repo.override(InMemoryShotRepository())
      c.storage_repo.override(FakeStorage())
      c.queue_repo.override(FakeJobQueue())
      c.publisher_repo.override(FakeEventPublisher())
      c.clock.override(FakeClock(datetime(2026, 4, 28, tzinfo=UTC)))
      c.ids.override(FakeIdGenerator())
      c.jwt_repo.override(JwtRepository(secret="x"*32, issuer="golf-test", ttl_seconds=3600))
      c.wire()  # finalize wiring
      return c
  ```

  And set `app.state.container = container` OR rely on `Container.wire()` having registered overrides for the `@inject` decorators.

  Detail: when using `dependency-injector`, the `@inject` decorator looks up providers via the container that's been wired. Tests that override providers must call `.override()` BEFORE the endpoint is called. The wiring picks up overrides automatically.

- [ ] **Step 4: Run full test suite**

Run: `uv run pytest 2>&1 | tail -3`
Expected: 98 (or 99 with the post-Plan-2 patch test) passing + 1 skipped.

If tests fail because `@inject` + provider overrides have subtle behavior, debug one test at a time. Common issues:
- `Provide[Container.x]` resolves at function-decoration time, not call time → make sure the container is wired before tests run. Move `Container().wire()` to an autouse fixture or to module load.
- `app.state.container` was the Plan 2 approach; the Tevadin pattern doesn't need it, but harmless to keep for transition.

- [ ] **Step 5: Commit**

```bash
git add apps/api/tests pyproject.toml
git commit -m "refactor: move all tests under apps/api/tests/ + override-based DI in conftest"
```

---

## Task 8: Migrate routers → endpoints with @inject + ResponseSuccess envelope

Move the FastAPI router files into `app/api/v1/endpoints/` and rewrite to use `@inject` + Provide + standardized response envelope.

**Files:**
- Move: `apps/api/src/golf_api/routers/*.py` → `apps/api/app/api/v1/endpoints/*.py`
- Move: `apps/api/src/golf_api/middleware/*.py` → `apps/api/app/middleware/*.py`
- Move: `apps/api/src/golf_api/deps/auth.py` → `apps/api/app/deps/auth.py`
- Move: `apps/api/src/golf_api/main.py` → `apps/api/app/main.py`
- Create: `apps/api/app/core/schemas/responses.py` — ResponseSuccess + ResponseError
- Create: `apps/api/app/core/schemas/sessions.py`, `shots.py`, `events.py` — wire DTOs (re-export from old `golf_contracts`)

- [ ] **Step 1: Create `app/core/schemas/responses.py`**

```python
from typing import Any

from pydantic import BaseModel


class ResponseStatus(BaseModel):
    code: int
    message: str


class BaseResponse(BaseModel):
    status: ResponseStatus
    data: Any


class ResponseSuccess(BaseResponse):
    def __init__(self, data: Any = None, message: str = "Success", code: int = 200) -> None:
        super().__init__(
            status=ResponseStatus(code=code, message=message),
            data=data if data is not None else {},
        )


class ResponseError(BaseResponse):
    def __init__(self, message: str, code: int = 400, data: Any = None) -> None:
        super().__init__(
            status=ResponseStatus(code=code, message=message),
            data=data if data is not None else {},
        )
```

- [ ] **Step 2: Create `app/core/schemas/sessions.py`, `shots.py`, `events.py`**

Move the contents of `libs/contracts/generated/python/golf_contracts/_models.py` (Pydantic v2 DTOs) split by resource:

- `app/core/schemas/sessions.py`: `SessionStatus`, `SessionError`, `SessionDto`, `CreateSessionRequest`, `CreateSessionResponse`
- `app/core/schemas/shots.py`: `ShotSource`, `ShotDto`, `UpdateShotBoundaryRequest`, `AddManualShotRequest`
- `app/core/schemas/events.py`: `SseEventEnvelope`

Plus an `app/core/schemas/__init__.py` that re-exports everything for convenience.

After these are written, you can drop `libs/contracts/generated/python/` (Task 9 cleanup).

- [ ] **Step 3: Move main.py + middleware + deps**

```bash
git mv apps/api/src/golf_api/main.py apps/api/app/main.py
git mv apps/api/src/golf_api/middleware/request_id.py apps/api/app/middleware/request_id.py
git mv apps/api/src/golf_api/middleware/error_handler.py apps/api/app/middleware/error_handler.py
git mv apps/api/src/golf_api/deps/auth.py apps/api/app/deps/auth.py
```

Update imports in each:
- `from .deps.container import build_container, shutdown_container` → drop (replaced by Container)
- `from .middleware.error_handler import install_error_handlers` → `from app.middleware.error_handler import install_error_handlers`
- `from .middleware.request_id import RequestIdMiddleware` → `from app.middleware.request_id import RequestIdMiddleware`
- `from .settings import Settings` → drop (Container manages Settings)
- Inside `error_handler.py`: `from golf_application.errors import ...` → `from app.services.errors import ...`; `from golf_domain.errors import ...` → `from app.core.models.errors import ...`
- Inside `deps/auth.py`: `from golf_api.deps.container import Container` → `from app.core.container import Container`; `from golf_infrastructure.auth.jwt_service import JwtVerifyError` → `from app.repository.auth.jwt_repository import JwtVerifyError`. Replace `Depends(get_container)` style with `@inject` style — see Step 4 below.

- [ ] **Step 4: Rewrite endpoints with @inject + Provide + ResponseSuccess**

Each router becomes an endpoint module. Pattern:

```python
# app/api/v1/endpoints/sessions.py
from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, status

from app.core.container import Container
from app.core.schemas.responses import ResponseSuccess
from app.core.schemas.sessions import (
    CreateSessionRequest, CreateSessionResponse, SessionDto,
)
from app.core.schemas.shots import ShotDto
from app.deps.auth import current_user_id
from app.services.session_service import (
    CreateSessionInput, GetSessionWithShotsInput, ListSessionsInput,
    SessionService, StartProcessingInput,
)


router = APIRouter(prefix="/api/v1/sessions", tags=["sessions"])


@router.post("", status_code=status.HTTP_201_CREATED)
@inject
async def create_session(
    req: CreateSessionRequest,
    user_id: str = Depends(current_user_id),
    service: SessionService = Depends(Provide[Container.session_service]),
) -> ResponseSuccess:
    out = await service.create(
        CreateSessionInput(
            user_id=user_id,
            original_filename=req.original_filename,
            pre_roll_seconds=req.pre_roll_seconds,
            post_roll_seconds=req.post_roll_seconds,
        )
    )
    return ResponseSuccess(
        data={
            "sessionId": out.session_id,
            "signedUploadUrl": out.signed_upload_url,
            "expiresAt": out.expires_at.isoformat(),
        },
        code=201,
    )


# ... (and so on for list/get/start_processing)
```

NOTE: the Tevadin pattern routes everything under `/api/v1/...`. Existing tests expect `/sessions` etc. To preserve test compatibility, choose ONE:

- (a) Mount routers without `/api/v1` prefix and update endpoint paths in tests later (preserves Plan 2 routes). Simpler.
- (b) Add `/api/v1` prefix and update all existing tests to hit `/api/v1/sessions`, `/api/v1/auth/login`, etc. More invasive but matches Tevadin example exactly.

Pick (a) for Plan 3 (smaller diff). Plan 5 (production hardening) can move to /api/v1.

So: prefix stays `/sessions`, `/auth`, `/health`, etc. Just put the source files under `app/api/v1/endpoints/` for organization.

- [ ] **Step 5: Update `app/main.py`**

```python
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.container import Container
from app.core.config import Settings
from app.middleware.error_handler import install_error_handlers
from app.middleware.request_id import RequestIdMiddleware
from app.api.v1.endpoints import auth, export, realtime, sessions, shots, upload


def create_app(env: str = "production") -> FastAPI:
    container = Container()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if env != "test":
            container.wire()
        # else: tests wire the container themselves (after applying overrides)
        yield

    app = FastAPI(title="golf-shot-cutter API", version="0.3.0", lifespan=lifespan)
    app.state.container = container

    cors_origins: list[str] = []
    if env != "test":
        try:
            cors_origins = Settings().cors_origins
        except Exception:
            cors_origins = []

    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins or ["http://localhost:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(RequestIdMiddleware)
    install_error_handlers(app)

    app.include_router(auth.router)
    app.include_router(sessions.router)
    app.include_router(shots.router)
    app.include_router(upload.router)
    app.include_router(export.router)
    app.include_router(realtime.router)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app(env=os.environ.get("APP_ENV", "production"))
```

- [ ] **Step 6: Run full test suite**

Run: `uv run pytest 2>&1 | tail -3`
Expected: 98+ passing (count may shift slightly due to consolidation but no regressions).

Resolve test failures one by one. Common issues:
- `@inject` doesn't pick up overrides → ensure `container.wire()` runs in conftest after overrides are applied.
- `Depends(Provide[Container.x])` in test — the FastAPI `Depends` + `dependency-injector`'s `Provide` interplay needs the container wired. Conftest must wire BEFORE TestClient builds.

- [ ] **Step 7: Commit**

```bash
git add apps/api/app
git commit -m "refactor: routers → app/api/v1/endpoints/ with @inject + ResponseSuccess"
```

---

## Task 9: Cleanup — drop libs/, drop import-linter, final verify

- [ ] **Step 1: Delete the old library packages**

```bash
git rm -r libs/domain libs/application libs/infrastructure libs/contracts/generated/python
git rm -r apps/api/src
```

(`libs/contracts/src` — TypeScript zod schemas — stays for Plan 5.)

If `libs/domain/pyproject.toml`, `libs/application/pyproject.toml`, etc. still exist after the file moves in earlier tasks, this step removes them.

- [ ] **Step 2: Drop `.importlinter`**

```bash
git rm .importlinter
```

The `import-linter` dev dependency in root `pyproject.toml` can also be removed:
```toml
[tool.uv]
dev-dependencies = [
    "pytest>=8.3",
    "pytest-asyncio>=0.24",
    "ruff>=0.7",
    "pre-commit>=3.8",
    "mongomock-motor>=0.0.34",
    "moto[s3]>=5.0",
    "fakeredis>=2.26",
    "httpx>=0.27"
]
```
(Drop `import-linter` and `datamodel-code-generator` since neither is used post-refactor.)

- [ ] **Step 3: Sync + verify**

```bash
uv sync --all-packages
uv run pytest 2>&1 | tail -3
pnpm exec biome check . 2>&1 | tail -2
uv run ruff check . 2>&1 | tail -2
uv tool run pre-commit run --all-files 2>&1 | tail -5
```

All should be green. Test count might shift slightly from consolidation; aim for ≥ 90 passing.

- [ ] **Step 4: Tag**

```bash
git tag v0.3.0-refactor
git log --oneline | head -15
```

- [ ] **Step 5: Commit any remaining cleanup**

```bash
git add -A
git commit -m "chore: remove libs/ + import-linter (refactor complete)"
```

---

## Done criteria

- Single `apps/api/` Python project; `libs/` contains only `contracts/src/` (TS).
- All Python code lives under `apps/api/app/{core,api,services,repository,middleware,deps}` matching Tevadin layout.
- `dependency_injector.containers.DeclarativeContainer` replaces the dataclass Container; `@inject` decorators on endpoints.
- Use cases consolidated into 4 services (Session, Shot, Processing, Export).
- Repositories renamed with `*Repository` suffix; no more Protocol-based ports.
- All endpoints return `ResponseSuccess` envelope.
- Tests live under `apps/api/tests/` with parallel structure to `app/`.
- Tag `v0.3.0-refactor` set.

## Carry-overs

- Plan 4 (worker) needs to be re-scoped: `apps/worker` will share `app/` source via direct import (since there's no longer a `libs/` shared package). Worker can also use the same Container approach.
- IDOR + ownership checks (Plan 2 review I3) still open.
- Pre-roll vs t_impact edge case (Plan 2 carry-over).
- SSE e2e test still skipped (Plan 2 carry-over).
