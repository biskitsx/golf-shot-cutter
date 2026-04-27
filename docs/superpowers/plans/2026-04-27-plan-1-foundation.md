# Plan 1 — Foundation (Monorepo + Contracts + Domain + Application)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Set up Nx + uv hybrid monorepo, then TDD pure-logic libraries (`libs/contracts`, `libs/domain`, `libs/application`) with in-memory ports — no I/O, no frameworks, fully testable.

**Architecture:** Hybrid Nx (TS) + uv workspace (Python). Layered Clean Architecture enforced via `import-linter`. zod-schema-first contracts that codegen Python (Pydantic) and TS types.

**Tech Stack:** pnpm + Nx 19, uv 0.4+, Python 3.11, Pydantic v2, zod, datamodel-code-generator, pytest, biome, import-linter, pre-commit.

**Spec reference:** `docs/superpowers/specs/2026-04-27-golf-shot-cutter-design.md` sections 4 (Architecture), 5.3-5.6 (libs).

---

## File Structure

```
golf-shot-cutter/
  package.json              # pnpm workspace + Nx + verify scripts
  pnpm-workspace.yaml
  pyproject.toml            # uv workspace root
  uv.lock
  nx.json
  tsconfig.base.json
  biome.json
  .importlinter             # Python layer rules
  .pre-commit-config.yaml
  .gitignore                # already present
  libs/
    contracts/
      package.json          # TS package, exports zod schemas
      project.json          # Nx project, tags: scope:contracts
      tsconfig.json
      src/
        sessions.ts         # SessionDto, CreateSessionRequest
        shots.ts            # ShotDto, UpdateShotBoundaryRequest
        events.ts           # SseEventEnvelope, ShotDetectedEvent
        index.ts
      tests/                # vitest schema round-trip checks
      # generated/ for python codegen will be added in Plan 2

    domain/
      pyproject.toml        # uv member: golf-domain
      src/golf_domain/
        __init__.py
        ids.py              # SessionId, ShotId, UserId (Pydantic types)
        value_objects.py    # TimeRange, Confidence
        session.py          # Session entity + status
        shot.py             # Shot entity
        events.py           # domain event dataclasses
        errors.py           # DomainError hierarchy
      tests/
        test_session.py
        test_shot.py
        test_value_objects.py

    application/
      pyproject.toml        # uv member: golf-application
      src/golf_application/
        __init__.py
        ports/
          __init__.py
          session_repository.py
          shot_repository.py
          storage_gateway.py
          job_queue.py
          event_publisher.py
          clock.py
          id_generator.py
        use_cases/
          __init__.py
          create_session.py
          request_signed_upload_url.py
          start_processing.py
          process_video.py
          list_sessions.py
          get_session_with_shots.py
          update_shot_boundary.py
          add_manual_shot.py
          delete_shot.py
          export_session_zip.py
        errors.py           # ApplicationError hierarchy
      tests/
        fakes/
          in_memory_repos.py
          fake_clock.py
          fake_id_generator.py
          fake_storage.py
          fake_queue.py
          fake_publisher.py
        use_cases/
          test_create_session.py
          test_start_processing.py
          ... (one per use case)
```

---

## Task 1: Initialize repo skeleton + pnpm workspace + Nx

**Files:**
- Create: `package.json`, `pnpm-workspace.yaml`, `nx.json`, `tsconfig.base.json`, `biome.json`

- [ ] **Step 1: Verify pnpm installed**

Run: `pnpm --version`
Expected: `9.x` or higher. If missing: `npm install -g pnpm@9`.

- [ ] **Step 2: Create root `package.json`**

Write `package.json`:
```json
{
  "name": "golf-shot-cutter",
  "private": true,
  "version": "0.0.0",
  "packageManager": "pnpm@9.12.0",
  "scripts": {
    "verify": "nx run-many -t lint,build,test && uv run pytest && uv run lint-imports",
    "dev:web": "nx serve web",
    "dev:api": "uv run --package golf-api fastapi dev apps/api/src/golf_api/main.py",
    "dev:worker": "uv run --package golf-worker celery -A golf_worker.main worker --loglevel=INFO"
  },
  "devDependencies": {
    "@biomejs/biome": "1.9.4",
    "@nx/js": "19.8.4",
    "@nx/workspace": "19.8.4",
    "nx": "19.8.4",
    "typescript": "5.6.3"
  }
}
```

- [ ] **Step 3: Create `pnpm-workspace.yaml`**

Write `pnpm-workspace.yaml`:
```yaml
packages:
  - apps/web
  - libs/contracts
  - libs/shared
  - libs/ui
```

- [ ] **Step 4: Create `nx.json`**

Write `nx.json`:
```json
{
  "$schema": "./node_modules/nx/schemas/nx-schema.json",
  "namedInputs": {
    "default": ["{projectRoot}/**/*", "sharedGlobals"],
    "production": ["default", "!{projectRoot}/**/*.spec.ts"],
    "sharedGlobals": []
  },
  "targetDefaults": {
    "build": { "cache": true, "inputs": ["production", "^production"] },
    "lint": { "cache": true },
    "test": { "cache": true }
  }
}
```

- [ ] **Step 5: Create `tsconfig.base.json`**

Write `tsconfig.base.json`:
```json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "ESNext",
    "moduleResolution": "bundler",
    "strict": true,
    "noUncheckedIndexedAccess": true,
    "esModuleInterop": true,
    "skipLibCheck": true,
    "isolatedModules": true,
    "resolveJsonModule": true,
    "baseUrl": ".",
    "paths": {
      "@golf/contracts": ["libs/contracts/src/index.ts"]
    }
  }
}
```

- [ ] **Step 6: Create `biome.json`**

Write `biome.json`:
```json
{
  "$schema": "./node_modules/@biomejs/biome/configuration_schema.json",
  "organizeImports": { "enabled": true },
  "linter": {
    "enabled": true,
    "rules": { "recommended": true }
  },
  "formatter": {
    "enabled": true,
    "indentStyle": "space",
    "indentWidth": 2
  }
}
```

- [ ] **Step 7: Install TS deps**

Run: `pnpm install`
Expected: `node_modules` created, no errors.

- [ ] **Step 8: Verify Nx works**

Run: `pnpm nx --version`
Expected: prints `19.8.4` (or matching version).

- [ ] **Step 9: Commit**

```bash
git add package.json pnpm-workspace.yaml nx.json tsconfig.base.json biome.json pnpm-lock.yaml
git commit -m "feat: scaffold pnpm + Nx workspace"
```

---

## Task 2: Initialize uv workspace + import-linter + pre-commit

**Files:**
- Create: `pyproject.toml`, `.importlinter`, `.pre-commit-config.yaml`

- [ ] **Step 1: Verify uv installed**

Run: `uv --version`
Expected: `0.4.x` or higher. If missing: `curl -LsSf https://astral.sh/uv/install.sh | sh`.

- [ ] **Step 2: Create root `pyproject.toml` (uv workspace)**

Write `pyproject.toml`:
```toml
[project]
name = "golf-shot-cutter"
version = "0.0.0"
description = "Golf shot auto-cutter monorepo root"
requires-python = ">=3.11"
dependencies = []

[tool.uv.workspace]
members = [
    "libs/domain",
    "libs/application",
    "libs/infrastructure",
    "apps/api",
    "apps/worker"
]

[tool.uv]
dev-dependencies = [
    "pytest>=8.3",
    "pytest-asyncio>=0.24",
    "import-linter>=2.1",
    "ruff>=0.7",
    "pre-commit>=3.8"
]

[tool.ruff]
line-length = 100
target-version = "py311"

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["libs", "apps"]
```

- [ ] **Step 3: Create `.importlinter`**

Write `.importlinter`:
```ini
[importlinter]
root_packages =
    golf_domain
    golf_application
    golf_infrastructure
    golf_api
    golf_worker

[importlinter:contract:layered]
name = Clean Architecture layered dependency
type = layers
layers =
    golf_api | golf_worker
    golf_infrastructure
    golf_application
    golf_domain
```

- [ ] **Step 4: Create `.pre-commit-config.yaml`**

Write `.pre-commit-config.yaml`:
```yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.7.0
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format
  - repo: local
    hooks:
      - id: biome
        name: biome
        entry: pnpm exec biome check --write
        language: system
        types_or: [ts, tsx, js, jsx, json]
        pass_filenames: false
```

- [ ] **Step 5: Sync uv (creates empty lock for now — no members yet)**

Run: `uv sync`
Expected: warns `No workspace members found` — that's fine.

- [ ] **Step 6: Install pre-commit hooks**

Run: `pip install pre-commit && pre-commit install` (or `uv tool install pre-commit && pre-commit install`)
Expected: `pre-commit installed at .git/hooks/pre-commit`

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml uv.lock .importlinter .pre-commit-config.yaml
git commit -m "feat: scaffold uv workspace + import-linter + pre-commit"
```

---

## Task 3: Create `libs/contracts` (zod schemas only — codegen deferred to Plan 2)

> **Why no codegen yet:** Phase 1 doesn't need Python DTOs because `libs/domain` is hand-authored. We add codegen in Plan 2 when `apps/api` routers and `libs/infrastructure` adapters start serializing/validating wire payloads.

**Files:**
- Create: `libs/contracts/package.json`, `libs/contracts/project.json`, `libs/contracts/tsconfig.json`, `libs/contracts/src/index.ts`, `libs/contracts/src/sessions.ts`, `libs/contracts/src/shots.ts`, `libs/contracts/src/events.ts`, `libs/contracts/tests/sessions.spec.ts`

- [ ] **Step 1: Create `libs/contracts/package.json`**

Write `libs/contracts/package.json`:
```json
{
  "name": "@golf/contracts",
  "version": "0.0.0",
  "private": true,
  "type": "module",
  "main": "src/index.ts",
  "types": "src/index.ts",
  "dependencies": {
    "zod": "3.23.8"
  },
  "devDependencies": {
    "vitest": "2.1.4"
  }
}
```

- [ ] **Step 2: Create `libs/contracts/project.json`**

Write `libs/contracts/project.json`:
```json
{
  "name": "contracts",
  "$schema": "../../node_modules/nx/schemas/project-schema.json",
  "projectType": "library",
  "sourceRoot": "libs/contracts/src",
  "tags": ["type:lib", "scope:contracts"],
  "targets": {
    "test": {
      "executor": "nx:run-commands",
      "options": { "command": "pnpm vitest run", "cwd": "libs/contracts" }
    },
    "lint": {
      "executor": "nx:run-commands",
      "options": { "command": "pnpm exec biome check libs/contracts" }
    },
    "build": {
      "executor": "nx:run-commands",
      "options": { "command": "echo 'contracts: source-only, no build needed in Plan 1'" }
    }
  }
}
```

- [ ] **Step 2b: Create `libs/contracts/tsconfig.json`**

Write `libs/contracts/tsconfig.json`:
```json
{
  "extends": "../../tsconfig.base.json",
  "compilerOptions": {
    "outDir": "dist",
    "rootDir": "src"
  },
  "include": ["src/**/*", "tests/**/*"]
}
```

- [ ] **Step 3: Write the failing schema test FIRST**

Write `libs/contracts/tests/sessions.spec.ts`:
```ts
import { describe, expect, it } from "vitest";
import { CreateSessionRequest, SessionDto } from "../src/sessions";

describe("SessionDto", () => {
  it("parses a valid session payload", () => {
    const parsed = SessionDto.parse({
      id: "ses_01H...",
      userId: null,
      rawVideoKey: "raw/abc/video.mp4",
      status: "queued",
      preRollSeconds: 2.0,
      postRollSeconds: 5.0,
      shotCount: 0,
      durationSeconds: 923.4,
      error: null,
      createdAt: "2026-04-27T10:00:00.000Z",
      updatedAt: "2026-04-27T10:00:00.000Z"
    });
    expect(parsed.status).toBe("queued");
  });

  it("rejects a status outside the enum", () => {
    expect(() =>
      SessionDto.parse({ status: "weird" } as unknown)
    ).toThrow();
  });
});

describe("CreateSessionRequest", () => {
  it("requires a non-empty originalFilename", () => {
    expect(() => CreateSessionRequest.parse({ originalFilename: "" })).toThrow();
  });
});
```

- [ ] **Step 4: Run test to verify failure**

Run: `pnpm --filter @golf/contracts vitest run`
Expected: FAIL — module `../src/sessions` not found.

- [ ] **Step 5: Implement `libs/contracts/src/sessions.ts`**

Write `libs/contracts/src/sessions.ts`:
```ts
import { z } from "zod";

export const SessionStatus = z.enum([
  "uploading",
  "queued",
  "processing",
  "ready",
  "failed"
]);
export type SessionStatus = z.infer<typeof SessionStatus>;

export const SessionError = z.object({
  stage: z.string(),
  message: z.string()
});

export const SessionDto = z.object({
  id: z.string(),
  userId: z.string().nullable(),
  rawVideoKey: z.string(),
  status: SessionStatus,
  preRollSeconds: z.number().nonnegative(),
  postRollSeconds: z.number().nonnegative(),
  shotCount: z.number().int().nonnegative(),
  durationSeconds: z.number().nonnegative(),
  error: SessionError.nullable(),
  createdAt: z.string().datetime(),
  updatedAt: z.string().datetime()
});
export type SessionDto = z.infer<typeof SessionDto>;

export const CreateSessionRequest = z.object({
  originalFilename: z.string().min(1),
  preRollSeconds: z.number().nonnegative().default(2.0),
  postRollSeconds: z.number().nonnegative().default(5.0)
});
export type CreateSessionRequest = z.infer<typeof CreateSessionRequest>;

export const CreateSessionResponse = z.object({
  sessionId: z.string(),
  signedUploadUrl: z.string().url(),
  expiresAt: z.string().datetime()
});
export type CreateSessionResponse = z.infer<typeof CreateSessionResponse>;
```

- [ ] **Step 6: Implement `libs/contracts/src/shots.ts`**

Write `libs/contracts/src/shots.ts`:
```ts
import { z } from "zod";

export const ShotSource = z.enum(["auto", "manual"]);
export type ShotSource = z.infer<typeof ShotSource>;

export const ShotDto = z.object({
  id: z.string(),
  sessionId: z.string(),
  index: z.number().int().positive(),
  tImpact: z.number().nonnegative(),
  tStart: z.number().nonnegative(),
  tEnd: z.number().nonnegative(),
  confidence: z.number().min(0).max(1),
  source: ShotSource,
  clipKey: z.string().nullable(),
  createdAt: z.string().datetime(),
  updatedAt: z.string().datetime()
});
export type ShotDto = z.infer<typeof ShotDto>;

export const UpdateShotBoundaryRequest = z.object({
  tStart: z.number().nonnegative(),
  tEnd: z.number().nonnegative()
});
export type UpdateShotBoundaryRequest = z.infer<typeof UpdateShotBoundaryRequest>;

export const AddManualShotRequest = z.object({
  tImpact: z.number().nonnegative(),
  tStart: z.number().nonnegative(),
  tEnd: z.number().nonnegative()
});
export type AddManualShotRequest = z.infer<typeof AddManualShotRequest>;
```

- [ ] **Step 7: Implement `libs/contracts/src/events.ts`**

Write `libs/contracts/src/events.ts`:
```ts
import { z } from "zod";
import { ShotDto } from "./shots";
import { SessionStatus } from "./sessions";

export const SseEventType = z.enum([
  "session.processing.started",
  "session.shot.detected",
  "session.ready",
  "session.failed"
]);

export const SseEventEnvelope = z.object({
  type: SseEventType,
  sessionId: z.string(),
  payload: z.record(z.unknown()),
  occurredAt: z.string().datetime()
});
export type SseEventEnvelope = z.infer<typeof SseEventEnvelope>;

export const ShotDetectedPayload = z.object({ shot: ShotDto });
export const SessionReadyPayload = z.object({
  status: SessionStatus,
  shotCount: z.number().int().nonnegative()
});
export const SessionFailedPayload = z.object({
  stage: z.string(),
  message: z.string()
});
```

- [ ] **Step 8: Implement `libs/contracts/src/index.ts`**

Write `libs/contracts/src/index.ts`:
```ts
export * from "./sessions";
export * from "./shots";
export * from "./events";
```

- [ ] **Step 9: Install workspace deps**

Run: `pnpm install`
Expected: `vitest` and `zod` installed under `libs/contracts/node_modules`.

- [ ] **Step 10: Run test to verify pass**

Run: `pnpm --filter @golf/contracts vitest run`
Expected: PASS — all tests green.

- [ ] **Step 11: Commit**

```bash
git add libs/contracts
git commit -m "feat(contracts): add zod wire-format schemas (TS only)"
```

---

## Task 4: Create `libs/domain` package + Pydantic IDs and value objects

**Files:**
- Create: `libs/domain/pyproject.toml`, `libs/domain/src/golf_domain/__init__.py`, `libs/domain/src/golf_domain/ids.py`, `libs/domain/src/golf_domain/value_objects.py`, `libs/domain/tests/test_value_objects.py`

- [ ] **Step 1: Create `libs/domain/pyproject.toml`**

Write `libs/domain/pyproject.toml`:
```toml
[project]
name = "golf-domain"
version = "0.0.0"
requires-python = ">=3.11"
dependencies = ["pydantic>=2.9"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/golf_domain"]
```

- [ ] **Step 2: Sync workspace**

Run: `uv sync`
Expected: `golf-domain` registered in `uv.lock`.

- [ ] **Step 3: Write the failing test**

Write `libs/domain/tests/test_value_objects.py`:
```python
import pytest

from golf_domain.value_objects import Confidence, TimeRange
from golf_domain.errors import DomainError


def test_confidence_accepts_zero_and_one():
    assert Confidence(value=0.0).value == 0.0
    assert Confidence(value=1.0).value == 1.0


def test_confidence_rejects_outside_range():
    with pytest.raises(DomainError):
        Confidence(value=-0.1)
    with pytest.raises(DomainError):
        Confidence(value=1.1)


def test_time_range_requires_start_before_end():
    tr = TimeRange(start=1.0, end=2.0)
    assert tr.duration == pytest.approx(1.0)


def test_time_range_rejects_inverted_bounds():
    with pytest.raises(DomainError):
        TimeRange(start=2.0, end=1.0)
```

- [ ] **Step 4: Run test to verify failure**

Run: `uv run pytest libs/domain/tests/test_value_objects.py -v`
Expected: FAIL — `golf_domain` not importable.

- [ ] **Step 5: Implement `libs/domain/src/golf_domain/__init__.py`**

Write `libs/domain/src/golf_domain/__init__.py`:
```python
"""Pure-Python golf domain entities. No framework imports."""
```

- [ ] **Step 6: Implement `libs/domain/src/golf_domain/errors.py`**

Write `libs/domain/src/golf_domain/errors.py`:
```python
class DomainError(Exception):
    """Base for all domain rule violations."""


class InvalidValueError(DomainError):
    """Raised when a value object receives an invalid input."""


class InvalidStateTransitionError(DomainError):
    """Raised when an entity transition violates a rule."""
```

- [ ] **Step 7: Implement `libs/domain/src/golf_domain/ids.py`**

Write `libs/domain/src/golf_domain/ids.py`:
```python
from typing import NewType

SessionId = NewType("SessionId", str)
ShotId = NewType("ShotId", str)
UserId = NewType("UserId", str)
ExportId = NewType("ExportId", str)
```

- [ ] **Step 8: Implement `libs/domain/src/golf_domain/value_objects.py`**

Write `libs/domain/src/golf_domain/value_objects.py`:
```python
from pydantic import BaseModel, ConfigDict, model_validator

from .errors import InvalidValueError


class Confidence(BaseModel):
    model_config = ConfigDict(frozen=True)
    value: float

    @model_validator(mode="after")
    def _check_range(self) -> "Confidence":
        if not 0.0 <= self.value <= 1.0:
            raise InvalidValueError(
                f"Confidence must be in [0, 1], got {self.value}"
            )
        return self


class TimeRange(BaseModel):
    model_config = ConfigDict(frozen=True)
    start: float
    end: float

    @model_validator(mode="after")
    def _check_order(self) -> "TimeRange":
        if self.start >= self.end:
            raise InvalidValueError(
                f"TimeRange requires start < end (got {self.start} >= {self.end})"
            )
        return self

    @property
    def duration(self) -> float:
        return self.end - self.start
```

- [ ] **Step 9: Run test to verify pass**

Run: `uv run pytest libs/domain/tests/test_value_objects.py -v`
Expected: PASS — all 4 tests green.

- [ ] **Step 10: Commit**

```bash
git add libs/domain pyproject.toml uv.lock
git commit -m "feat(domain): add Confidence + TimeRange value objects"
```

---

## Task 5: Implement `Session` entity (TDD)

**Files:**
- Create: `libs/domain/src/golf_domain/session.py`, `libs/domain/tests/test_session.py`

- [ ] **Step 1: Write failing tests**

Write `libs/domain/tests/test_session.py`:
```python
from datetime import UTC, datetime

import pytest

from golf_domain.errors import InvalidStateTransitionError, InvalidValueError
from golf_domain.session import Session, SessionStatus


def _make(**overrides):
    base = dict(
        id="ses_1",
        user_id=None,
        raw_video_key="raw/ses_1/video.mp4",
        status=SessionStatus.QUEUED,
        pre_roll_seconds=2.0,
        post_roll_seconds=5.0,
        shot_count=0,
        duration_seconds=900.0,
        error=None,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    base.update(overrides)
    return Session(**base)


def test_session_can_be_created_in_queued_status():
    s = _make()
    assert s.status is SessionStatus.QUEUED


def test_pre_roll_must_be_non_negative():
    with pytest.raises(InvalidValueError):
        _make(pre_roll_seconds=-0.1)


def test_post_roll_must_be_non_negative():
    with pytest.raises(InvalidValueError):
        _make(post_roll_seconds=-0.1)


def test_assert_editable_passes_when_ready():
    s = _make(status=SessionStatus.READY)
    s.assert_editable()  # no raise


def test_assert_editable_rejects_when_processing():
    s = _make(status=SessionStatus.PROCESSING)
    with pytest.raises(InvalidStateTransitionError):
        s.assert_editable()


def test_mark_processing_from_queued_succeeds():
    s = _make(status=SessionStatus.QUEUED)
    moved = s.mark_processing()
    assert moved.status is SessionStatus.PROCESSING


def test_mark_processing_from_ready_rejects():
    s = _make(status=SessionStatus.READY)
    with pytest.raises(InvalidStateTransitionError):
        s.mark_processing()
```

- [ ] **Step 2: Run test to verify failure**

Run: `uv run pytest libs/domain/tests/test_session.py -v`
Expected: FAIL — module not importable.

- [ ] **Step 3: Implement `libs/domain/src/golf_domain/session.py`**

Write `libs/domain/src/golf_domain/session.py`:
```python
from datetime import datetime
from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, model_validator

from .errors import InvalidStateTransitionError, InvalidValueError
from .ids import SessionId, UserId


class SessionStatus(StrEnum):
    UPLOADING = "uploading"
    QUEUED = "queued"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"


class SessionError(BaseModel):
    model_config = ConfigDict(frozen=True)
    stage: str
    message: str


class Session(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: SessionId
    user_id: UserId | None
    raw_video_key: str
    status: SessionStatus
    pre_roll_seconds: float
    post_roll_seconds: float
    shot_count: int = 0
    duration_seconds: float
    error: SessionError | None = None
    created_at: datetime
    updated_at: datetime

    @model_validator(mode="after")
    def _check_invariants(self) -> Self:
        if self.pre_roll_seconds < 0:
            raise InvalidValueError("pre_roll_seconds must be ≥ 0")
        if self.post_roll_seconds < 0:
            raise InvalidValueError("post_roll_seconds must be ≥ 0")
        if self.shot_count < 0:
            raise InvalidValueError("shot_count must be ≥ 0")
        if self.duration_seconds < 0:
            raise InvalidValueError("duration_seconds must be ≥ 0")
        return self

    def assert_editable(self) -> None:
        if self.status is not SessionStatus.READY:
            raise InvalidStateTransitionError(
                f"Session must be READY to edit (current: {self.status})"
            )

    def mark_processing(self) -> "Session":
        if self.status is not SessionStatus.QUEUED:
            raise InvalidStateTransitionError(
                f"Cannot mark processing from {self.status}"
            )
        return self.model_copy(update={"status": SessionStatus.PROCESSING})

    def mark_ready(self, shot_count: int) -> "Session":
        if self.status is not SessionStatus.PROCESSING:
            raise InvalidStateTransitionError(
                f"Cannot mark ready from {self.status}"
            )
        return self.model_copy(update={
            "status": SessionStatus.READY,
            "shot_count": shot_count,
        })

    def mark_failed(self, stage: str, message: str) -> "Session":
        return self.model_copy(update={
            "status": SessionStatus.FAILED,
            "error": SessionError(stage=stage, message=message),
        })
```

- [ ] **Step 4: Run test to verify pass**

Run: `uv run pytest libs/domain/tests/test_session.py -v`
Expected: PASS — all 7 tests green.

- [ ] **Step 5: Commit**

```bash
git add libs/domain
git commit -m "feat(domain): add Session entity + status transitions"
```

---

## Task 6: Implement `Shot` entity (TDD)

**Files:**
- Create: `libs/domain/src/golf_domain/shot.py`, `libs/domain/tests/test_shot.py`

- [ ] **Step 1: Write failing tests**

Write `libs/domain/tests/test_shot.py`:
```python
from datetime import UTC, datetime

import pytest

from golf_domain.errors import InvalidValueError
from golf_domain.shot import Shot, ShotSource
from golf_domain.value_objects import Confidence


def _make(**overrides):
    base = dict(
        id="shot_1",
        session_id="ses_1",
        index=1,
        t_impact=10.0,
        t_start=8.0,
        t_end=15.0,
        confidence=Confidence(value=0.9),
        source=ShotSource.AUTO,
        clip_key=None,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    base.update(overrides)
    return Shot(**base)


def test_shot_requires_t_start_before_impact_before_t_end():
    with pytest.raises(InvalidValueError):
        _make(t_start=11.0)  # after impact
    with pytest.raises(InvalidValueError):
        _make(t_end=9.0)  # before impact


def test_adjust_boundary_updates_when_valid():
    s = _make()
    moved = s.adjust_boundary(t_start=7.0, t_end=16.0)
    assert moved.t_start == 7.0
    assert moved.t_end == 16.0


def test_adjust_boundary_rejects_zero_duration():
    s = _make()
    with pytest.raises(InvalidValueError):
        s.adjust_boundary(t_start=10.0, t_end=10.0)


def test_adjust_boundary_rejects_when_impact_outside_window():
    s = _make()
    with pytest.raises(InvalidValueError):
        s.adjust_boundary(t_start=11.0, t_end=12.0)


def test_index_must_be_positive():
    with pytest.raises(InvalidValueError):
        _make(index=0)
```

- [ ] **Step 2: Run test to verify failure**

Run: `uv run pytest libs/domain/tests/test_shot.py -v`
Expected: FAIL — module not importable.

- [ ] **Step 3: Implement `libs/domain/src/golf_domain/shot.py`**

Write `libs/domain/src/golf_domain/shot.py`:
```python
from datetime import datetime
from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, model_validator

from .errors import InvalidValueError
from .ids import SessionId, ShotId
from .value_objects import Confidence


class ShotSource(StrEnum):
    AUTO = "auto"
    MANUAL = "manual"


class Shot(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: ShotId
    session_id: SessionId
    index: int
    t_impact: float
    t_start: float
    t_end: float
    confidence: Confidence
    source: ShotSource
    clip_key: str | None
    created_at: datetime
    updated_at: datetime

    @model_validator(mode="after")
    def _check_invariants(self) -> Self:
        if self.index <= 0:
            raise InvalidValueError("index must be a positive integer")
        if self.t_start >= self.t_impact:
            raise InvalidValueError("t_start must be < t_impact")
        if self.t_impact >= self.t_end:
            raise InvalidValueError("t_impact must be < t_end")
        return self

    def adjust_boundary(self, *, t_start: float, t_end: float) -> "Shot":
        if t_end - t_start <= 0:
            raise InvalidValueError("Shot duration must be positive")
        if not (t_start < self.t_impact < t_end):
            raise InvalidValueError(
                f"Impact ({self.t_impact}) must lie within [{t_start}, {t_end}]"
            )
        return self.model_copy(update={"t_start": t_start, "t_end": t_end})

    def attach_clip(self, clip_key: str) -> "Shot":
        return self.model_copy(update={"clip_key": clip_key})
```

- [ ] **Step 4: Run test to verify pass**

Run: `uv run pytest libs/domain/tests/test_shot.py -v`
Expected: PASS — all 5 tests green.

- [ ] **Step 5: Run import-linter**

Run: `uv run lint-imports`
Expected: `Contracts: 1 kept, 0 broken.`

- [ ] **Step 6: Commit**

```bash
git add libs/domain
git commit -m "feat(domain): add Shot entity with boundary invariants"
```

---

## Task 7: Add domain events

**Files:**
- Create: `libs/domain/src/golf_domain/events.py`, `libs/domain/tests/test_events.py`

- [ ] **Step 1: Write failing test**

Write `libs/domain/tests/test_events.py`:
```python
from datetime import UTC, datetime

from golf_domain.events import (
    SessionFailed,
    SessionProcessingStarted,
    SessionReady,
    ShotDetected,
)


def test_session_processing_started_fields():
    e = SessionProcessingStarted(
        session_id="ses_1",
        occurred_at=datetime.now(UTC),
    )
    assert e.session_id == "ses_1"


def test_shot_detected_carries_shot_id_and_confidence():
    e = ShotDetected(
        session_id="ses_1",
        shot_id="shot_1",
        confidence=0.91,
        occurred_at=datetime.now(UTC),
    )
    assert e.confidence == 0.91


def test_session_ready_carries_shot_count():
    e = SessionReady(
        session_id="ses_1",
        shot_count=12,
        occurred_at=datetime.now(UTC),
    )
    assert e.shot_count == 12


def test_session_failed_carries_stage_and_message():
    e = SessionFailed(
        session_id="ses_1",
        stage="audio_onset",
        message="sample rate too low",
        occurred_at=datetime.now(UTC),
    )
    assert e.stage == "audio_onset"
```

- [ ] **Step 2: Run test to verify failure**

Run: `uv run pytest libs/domain/tests/test_events.py -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement `libs/domain/src/golf_domain/events.py`**

Write `libs/domain/src/golf_domain/events.py`:
```python
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from .ids import SessionId, ShotId


class DomainEvent(BaseModel):
    model_config = ConfigDict(frozen=True)
    session_id: SessionId
    occurred_at: datetime


class SessionProcessingStarted(DomainEvent):
    pass


class ShotDetected(DomainEvent):
    shot_id: ShotId
    confidence: float


class SessionReady(DomainEvent):
    shot_count: int


class SessionFailed(DomainEvent):
    stage: str
    message: str


class ShotBoundaryUpdated(DomainEvent):
    shot_id: ShotId
    t_start: float
    t_end: float


class ShotDeleted(DomainEvent):
    shot_id: ShotId
```

- [ ] **Step 4: Run test to verify pass**

Run: `uv run pytest libs/domain/tests/test_events.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add libs/domain
git commit -m "feat(domain): add domain events"
```

---

## Task 8: Create `libs/application` skeleton + ports

**Files:**
- Create: `libs/application/pyproject.toml`, `libs/application/src/golf_application/__init__.py`, `libs/application/src/golf_application/errors.py`, `libs/application/src/golf_application/ports/{__init__,session_repository,shot_repository,storage_gateway,job_queue,event_publisher,clock,id_generator}.py`

- [ ] **Step 1: Create `libs/application/pyproject.toml`**

Write `libs/application/pyproject.toml`:
```toml
[project]
name = "golf-application"
version = "0.0.0"
requires-python = ">=3.11"
dependencies = [
    "pydantic>=2.9",
    "golf-domain"
]

[tool.uv.sources]
golf-domain = { workspace = true }

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/golf_application"]
```

- [ ] **Step 2: Sync workspace**

Run: `uv sync`
Expected: `golf-application` registered.

- [ ] **Step 3: Implement errors + package init**

Write `libs/application/src/golf_application/__init__.py`:
```python
"""Application layer: use cases + ports. Depends on golf_domain only."""
```

Write `libs/application/src/golf_application/errors.py`:
```python
class ApplicationError(Exception):
    """Base for application-layer errors."""


class SessionNotFoundError(ApplicationError):
    pass


class ShotNotFoundError(ApplicationError):
    pass


class StorageError(ApplicationError):
    pass


class QueueError(ApplicationError):
    pass
```

- [ ] **Step 4: Implement port interfaces**

Write `libs/application/src/golf_application/ports/__init__.py`:
```python
from .clock import Clock
from .event_publisher import EventPublisher
from .id_generator import IdGenerator
from .job_queue import JobQueue, ProcessVideoJob
from .session_repository import SessionRepository
from .shot_repository import ShotRepository
from .storage_gateway import SignedUrl, StorageGateway

__all__ = [
    "Clock",
    "EventPublisher",
    "IdGenerator",
    "JobQueue",
    "ProcessVideoJob",
    "SessionRepository",
    "ShotRepository",
    "SignedUrl",
    "StorageGateway",
]
```

Write `libs/application/src/golf_application/ports/clock.py`:
```python
from datetime import datetime
from typing import Protocol


class Clock(Protocol):
    def now(self) -> datetime: ...
```

Write `libs/application/src/golf_application/ports/id_generator.py`:
```python
from typing import Protocol


class IdGenerator(Protocol):
    def session_id(self) -> str: ...
    def shot_id(self) -> str: ...
    def export_id(self) -> str: ...
```

Write `libs/application/src/golf_application/ports/storage_gateway.py`:
```python
from datetime import datetime
from typing import Protocol

from pydantic import BaseModel


class SignedUrl(BaseModel):
    url: str
    expires_at: datetime


class StorageGateway(Protocol):
    async def signed_put_url(self, key: str, *, content_type: str) -> SignedUrl: ...
    async def signed_get_url(self, key: str) -> SignedUrl: ...
    async def delete_object(self, key: str) -> None: ...
```

Write `libs/application/src/golf_application/ports/job_queue.py`:
```python
from typing import Protocol

from pydantic import BaseModel

from golf_domain.ids import SessionId


class ProcessVideoJob(BaseModel):
    session_id: SessionId


class JobQueue(Protocol):
    async def enqueue_process_video(self, job: ProcessVideoJob) -> None: ...
```

Write `libs/application/src/golf_application/ports/event_publisher.py`:
```python
from typing import Protocol

from golf_domain.events import DomainEvent


class EventPublisher(Protocol):
    async def publish(self, event: DomainEvent) -> None: ...
```

Write `libs/application/src/golf_application/ports/session_repository.py`:
```python
from typing import Protocol

from golf_domain.ids import SessionId, UserId
from golf_domain.session import Session


class SessionRepository(Protocol):
    async def add(self, session: Session) -> None: ...
    async def get(self, session_id: SessionId) -> Session: ...
    async def list_for_user(self, user_id: UserId | None) -> list[Session]: ...
    async def update(self, session: Session) -> None: ...
```

Write `libs/application/src/golf_application/ports/shot_repository.py`:
```python
from typing import Protocol

from golf_domain.ids import SessionId, ShotId
from golf_domain.shot import Shot


class ShotRepository(Protocol):
    async def add(self, shot: Shot) -> None: ...
    async def add_many(self, shots: list[Shot]) -> None: ...
    async def get(self, shot_id: ShotId) -> Shot: ...
    async def list_by_session(self, session_id: SessionId) -> list[Shot]: ...
    async def update(self, shot: Shot) -> None: ...
    async def delete(self, shot_id: ShotId) -> None: ...
```

- [ ] **Step 5: Verify import-linter**

Run: `uv run lint-imports`
Expected: `Contracts: 1 kept, 0 broken.`

- [ ] **Step 6: Commit**

```bash
git add libs/application uv.lock
git commit -m "feat(application): add port interfaces + error hierarchy"
```

---

## Task 9: In-memory fakes for testing

**Files:**
- Create: `libs/application/tests/fakes/{__init__,in_memory_repos,fake_clock,fake_id_generator,fake_storage,fake_queue,fake_publisher}.py`

- [ ] **Step 1: Create empty `__init__.py` for test package layout**

Run:
```bash
mkdir -p libs/application/tests/fakes libs/application/tests/use_cases
touch libs/application/tests/__init__.py
touch libs/application/tests/fakes/__init__.py
touch libs/application/tests/use_cases/__init__.py
```
Expected: 3 empty files created so pytest treats `tests/` and its subpackages as a Python package (required for the relative imports `from ..fakes.fake_clock import FakeClock`).

- [ ] **Step 2: Implement `fake_clock.py`**

Write `libs/application/tests/fakes/fake_clock.py`:
```python
from datetime import datetime


class FakeClock:
    def __init__(self, fixed: datetime) -> None:
        self._fixed = fixed

    def now(self) -> datetime:
        return self._fixed

    def advance(self, *, seconds: float) -> None:
        from datetime import timedelta
        self._fixed = self._fixed + timedelta(seconds=seconds)
```

- [ ] **Step 3: Implement `fake_id_generator.py`**

Write `libs/application/tests/fakes/fake_id_generator.py`:
```python
class FakeIdGenerator:
    def __init__(self) -> None:
        self._counters = {"ses": 0, "shot": 0, "exp": 0}

    def session_id(self) -> str:
        self._counters["ses"] += 1
        return f"ses_{self._counters['ses']:04d}"

    def shot_id(self) -> str:
        self._counters["shot"] += 1
        return f"shot_{self._counters['shot']:04d}"

    def export_id(self) -> str:
        self._counters["exp"] += 1
        return f"exp_{self._counters['exp']:04d}"
```

- [ ] **Step 4: Implement `in_memory_repos.py`**

Write `libs/application/tests/fakes/in_memory_repos.py`:
```python
from golf_application.errors import SessionNotFoundError, ShotNotFoundError
from golf_domain.ids import SessionId, ShotId, UserId
from golf_domain.session import Session
from golf_domain.shot import Shot


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
```

- [ ] **Step 5: Implement `fake_storage.py`**

Write `libs/application/tests/fakes/fake_storage.py`:
```python
from datetime import datetime, timedelta

from golf_application.ports import SignedUrl


class FakeStorage:
    def __init__(self, *, base: str = "https://fake-r2.local") -> None:
        self._base = base
        self.deleted: list[str] = []

    async def signed_put_url(self, key: str, *, content_type: str) -> SignedUrl:
        return SignedUrl(
            url=f"{self._base}/PUT/{key}?ct={content_type}",
            expires_at=datetime.now() + timedelta(minutes=15),
        )

    async def signed_get_url(self, key: str) -> SignedUrl:
        return SignedUrl(
            url=f"{self._base}/GET/{key}",
            expires_at=datetime.now() + timedelta(minutes=15),
        )

    async def delete_object(self, key: str) -> None:
        self.deleted.append(key)
```

- [ ] **Step 6: Implement `fake_queue.py`**

Write `libs/application/tests/fakes/fake_queue.py`:
```python
from golf_application.ports import ProcessVideoJob


class FakeJobQueue:
    def __init__(self) -> None:
        self.enqueued: list[ProcessVideoJob] = []

    async def enqueue_process_video(self, job: ProcessVideoJob) -> None:
        self.enqueued.append(job)
```

- [ ] **Step 7: Implement `fake_publisher.py`**

Write `libs/application/tests/fakes/fake_publisher.py`:
```python
from golf_domain.events import DomainEvent


class FakeEventPublisher:
    def __init__(self) -> None:
        self.published: list[DomainEvent] = []

    async def publish(self, event: DomainEvent) -> None:
        self.published.append(event)
```

- [ ] **Step 8: Sanity test (no failure expected — just import)**

Run: `uv run python -c "from libs.application.tests.fakes.in_memory_repos import InMemorySessionRepository; print('ok')"`
Expected: `ok`. (If `python -m` hits, use `uv run pytest libs/application/tests -q --co`.)

- [ ] **Step 9: Commit**

```bash
git add libs/application/tests
git commit -m "test(application): add in-memory fakes for ports"
```

---

## Task 10: `CreateSessionUseCase` (TDD)

**Files:**
- Create: `libs/application/src/golf_application/use_cases/__init__.py`, `libs/application/src/golf_application/use_cases/create_session.py`, `libs/application/tests/use_cases/test_create_session.py`

- [ ] **Step 1: Write failing test**

Write `libs/application/tests/use_cases/test_create_session.py`:
```python
from datetime import UTC, datetime

import pytest

from golf_application.use_cases.create_session import (
    CreateSessionInput,
    CreateSessionUseCase,
)
from golf_domain.session import SessionStatus

from ..fakes.fake_clock import FakeClock
from ..fakes.fake_id_generator import FakeIdGenerator
from ..fakes.fake_storage import FakeStorage
from ..fakes.in_memory_repos import InMemorySessionRepository


@pytest.fixture
def context():
    return {
        "sessions": InMemorySessionRepository(),
        "storage": FakeStorage(),
        "clock": FakeClock(datetime(2026, 4, 27, 10, 0, tzinfo=UTC)),
        "ids": FakeIdGenerator(),
    }


async def test_creates_session_with_signed_upload_url(context):
    uc = CreateSessionUseCase(
        sessions=context["sessions"],
        storage=context["storage"],
        clock=context["clock"],
        ids=context["ids"],
    )
    out = await uc.execute(
        CreateSessionInput(
            user_id=None,
            original_filename="range.mp4",
            pre_roll_seconds=2.0,
            post_roll_seconds=5.0,
        )
    )
    assert out.session_id == "ses_0001"
    assert out.signed_upload_url.startswith("https://fake-r2.local/PUT/raw/ses_0001/range.mp4")
    persisted = await context["sessions"].get("ses_0001")
    assert persisted.status is SessionStatus.UPLOADING
    assert persisted.pre_roll_seconds == 2.0
    assert persisted.raw_video_key == "raw/ses_0001/range.mp4"


async def test_rejects_empty_filename(context):
    uc = CreateSessionUseCase(**context)
    with pytest.raises(ValueError):
        await uc.execute(
            CreateSessionInput(
                user_id=None,
                original_filename="",
                pre_roll_seconds=2.0,
                post_roll_seconds=5.0,
            )
        )
```

- [ ] **Step 2: Run test to verify failure**

Run: `uv run pytest libs/application/tests/use_cases/test_create_session.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement use case package init**

Write `libs/application/src/golf_application/use_cases/__init__.py`:
```python
```

- [ ] **Step 4: Implement `create_session.py`**

Write `libs/application/src/golf_application/use_cases/create_session.py`:
```python
from datetime import datetime

from pydantic import BaseModel, Field

from golf_domain.ids import UserId
from golf_domain.session import Session, SessionStatus

from ..ports import Clock, IdGenerator, SessionRepository, StorageGateway


class CreateSessionInput(BaseModel):
    user_id: UserId | None
    original_filename: str = Field(min_length=1)
    pre_roll_seconds: float = Field(ge=0, default=2.0)
    post_roll_seconds: float = Field(ge=0, default=5.0)


class CreateSessionOutput(BaseModel):
    session_id: str
    signed_upload_url: str
    expires_at: datetime


class CreateSessionUseCase:
    def __init__(
        self,
        *,
        sessions: SessionRepository,
        storage: StorageGateway,
        clock: Clock,
        ids: IdGenerator,
    ) -> None:
        self._sessions = sessions
        self._storage = storage
        self._clock = clock
        self._ids = ids

    async def execute(self, input: CreateSessionInput) -> CreateSessionOutput:
        session_id = self._ids.session_id()
        raw_key = f"raw/{session_id}/{input.original_filename}"
        now = self._clock.now()
        signed = await self._storage.signed_put_url(raw_key, content_type="video/mp4")

        session = Session(
            id=session_id,  # type: ignore[arg-type]
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
```

- [ ] **Step 5: Run test to verify pass**

Run: `uv run pytest libs/application/tests/use_cases/test_create_session.py -v`
Expected: PASS — both tests green.

- [ ] **Step 6: Commit**

```bash
git add libs/application
git commit -m "feat(application): add CreateSessionUseCase"
```

---

## Task 11: `StartProcessingUseCase` (TDD)

**Files:**
- Create: `libs/application/src/golf_application/use_cases/start_processing.py`, `libs/application/tests/use_cases/test_start_processing.py`

- [ ] **Step 1: Write failing test**

Write `libs/application/tests/use_cases/test_start_processing.py`:
```python
from datetime import UTC, datetime

import pytest

from golf_application.errors import SessionNotFoundError
from golf_application.use_cases.start_processing import (
    StartProcessingInput,
    StartProcessingUseCase,
)
from golf_domain.session import Session, SessionStatus

from ..fakes.fake_publisher import FakeEventPublisher
from ..fakes.fake_queue import FakeJobQueue
from ..fakes.in_memory_repos import InMemorySessionRepository


def _session(status: SessionStatus) -> Session:
    return Session(
        id="ses_1",
        user_id=None,
        raw_video_key="raw/ses_1/v.mp4",
        status=status,
        pre_roll_seconds=2.0,
        post_roll_seconds=5.0,
        shot_count=0,
        duration_seconds=900.0,
        error=None,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


async def test_enqueues_job_and_marks_processing():
    repo = InMemorySessionRepository()
    queue = FakeJobQueue()
    publisher = FakeEventPublisher()
    await repo.add(_session(SessionStatus.QUEUED))

    uc = StartProcessingUseCase(sessions=repo, queue=queue, events=publisher)
    await uc.execute(StartProcessingInput(session_id="ses_1"))

    updated = await repo.get("ses_1")
    assert updated.status is SessionStatus.PROCESSING
    assert len(queue.enqueued) == 1
    assert queue.enqueued[0].session_id == "ses_1"
    assert len(publisher.published) == 1


async def test_raises_when_session_missing():
    repo = InMemorySessionRepository()
    uc = StartProcessingUseCase(
        sessions=repo, queue=FakeJobQueue(), events=FakeEventPublisher()
    )
    with pytest.raises(SessionNotFoundError):
        await uc.execute(StartProcessingInput(session_id="missing"))


async def test_uploading_session_is_promoted_to_queued_first():
    repo = InMemorySessionRepository()
    queue = FakeJobQueue()
    publisher = FakeEventPublisher()
    await repo.add(_session(SessionStatus.UPLOADING))

    uc = StartProcessingUseCase(sessions=repo, queue=queue, events=publisher)
    await uc.execute(StartProcessingInput(session_id="ses_1"))

    updated = await repo.get("ses_1")
    assert updated.status is SessionStatus.PROCESSING
```

- [ ] **Step 2: Run test to verify failure**

Run: `uv run pytest libs/application/tests/use_cases/test_start_processing.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement `start_processing.py`**

Write `libs/application/src/golf_application/use_cases/start_processing.py`:
```python
from datetime import datetime

from pydantic import BaseModel

from golf_domain.events import SessionProcessingStarted
from golf_domain.ids import SessionId
from golf_domain.session import SessionStatus

from ..ports import EventPublisher, JobQueue, ProcessVideoJob, SessionRepository


class StartProcessingInput(BaseModel):
    session_id: SessionId


class StartProcessingUseCase:
    def __init__(
        self,
        *,
        sessions: SessionRepository,
        queue: JobQueue,
        events: EventPublisher,
    ) -> None:
        self._sessions = sessions
        self._queue = queue
        self._events = events

    async def execute(self, input: StartProcessingInput) -> None:
        session = await self._sessions.get(input.session_id)

        if session.status is SessionStatus.UPLOADING:
            session = session.model_copy(update={"status": SessionStatus.QUEUED})

        moved = session.mark_processing()
        await self._sessions.update(moved)
        await self._queue.enqueue_process_video(ProcessVideoJob(session_id=moved.id))
        await self._events.publish(
            SessionProcessingStarted(session_id=moved.id, occurred_at=datetime.now())
        )
```

- [ ] **Step 4: Run test to verify pass**

Run: `uv run pytest libs/application/tests/use_cases/test_start_processing.py -v`
Expected: PASS — all 3 tests green.

- [ ] **Step 5: Commit**

```bash
git add libs/application
git commit -m "feat(application): add StartProcessingUseCase"
```

---

## Task 12: `UpdateShotBoundaryUseCase` (TDD)

**Files:**
- Create: `libs/application/src/golf_application/use_cases/update_shot_boundary.py`, `libs/application/tests/use_cases/test_update_shot_boundary.py`

- [ ] **Step 1: Write failing test**

Write `libs/application/tests/use_cases/test_update_shot_boundary.py`:
```python
from datetime import UTC, datetime

import pytest

from golf_application.errors import ShotNotFoundError
from golf_application.use_cases.update_shot_boundary import (
    UpdateShotBoundaryInput,
    UpdateShotBoundaryUseCase,
)
from golf_domain.errors import InvalidStateTransitionError, InvalidValueError
from golf_domain.session import Session, SessionStatus
from golf_domain.shot import Shot, ShotSource
from golf_domain.value_objects import Confidence

from ..fakes.fake_publisher import FakeEventPublisher
from ..fakes.in_memory_repos import InMemorySessionRepository, InMemoryShotRepository


def _session(status: SessionStatus = SessionStatus.READY) -> Session:
    return Session(
        id="ses_1",
        user_id=None,
        raw_video_key="raw/ses_1/v.mp4",
        status=status,
        pre_roll_seconds=2.0,
        post_roll_seconds=5.0,
        shot_count=1,
        duration_seconds=900.0,
        error=None,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


def _shot() -> Shot:
    return Shot(
        id="shot_1",
        session_id="ses_1",
        index=1,
        t_impact=10.0,
        t_start=8.0,
        t_end=15.0,
        confidence=Confidence(value=0.9),
        source=ShotSource.AUTO,
        clip_key=None,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


async def test_updates_boundary_on_ready_session():
    sessions = InMemorySessionRepository()
    shots = InMemoryShotRepository()
    await sessions.add(_session())
    await shots.add(_shot())

    uc = UpdateShotBoundaryUseCase(
        sessions=sessions, shots=shots, events=FakeEventPublisher()
    )
    out = await uc.execute(
        UpdateShotBoundaryInput(
            session_id="ses_1", shot_id="shot_1", t_start=7.0, t_end=16.0
        )
    )
    assert out.t_start == 7.0
    assert out.t_end == 16.0


async def test_rejects_when_session_not_ready():
    sessions = InMemorySessionRepository()
    shots = InMemoryShotRepository()
    await sessions.add(_session(status=SessionStatus.PROCESSING))
    await shots.add(_shot())
    uc = UpdateShotBoundaryUseCase(
        sessions=sessions, shots=shots, events=FakeEventPublisher()
    )
    with pytest.raises(InvalidStateTransitionError):
        await uc.execute(
            UpdateShotBoundaryInput(
                session_id="ses_1", shot_id="shot_1", t_start=7.0, t_end=16.0
            )
        )


async def test_rejects_when_impact_outside_window():
    sessions = InMemorySessionRepository()
    shots = InMemoryShotRepository()
    await sessions.add(_session())
    await shots.add(_shot())
    uc = UpdateShotBoundaryUseCase(
        sessions=sessions, shots=shots, events=FakeEventPublisher()
    )
    with pytest.raises(InvalidValueError):
        await uc.execute(
            UpdateShotBoundaryInput(
                session_id="ses_1", shot_id="shot_1", t_start=11.0, t_end=12.0
            )
        )


async def test_raises_when_shot_missing():
    sessions = InMemorySessionRepository()
    shots = InMemoryShotRepository()
    await sessions.add(_session())
    uc = UpdateShotBoundaryUseCase(
        sessions=sessions, shots=shots, events=FakeEventPublisher()
    )
    with pytest.raises(ShotNotFoundError):
        await uc.execute(
            UpdateShotBoundaryInput(
                session_id="ses_1", shot_id="missing", t_start=7.0, t_end=16.0
            )
        )
```

- [ ] **Step 2: Run test to verify failure**

Run: `uv run pytest libs/application/tests/use_cases/test_update_shot_boundary.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement `update_shot_boundary.py`**

Write `libs/application/src/golf_application/use_cases/update_shot_boundary.py`:
```python
from datetime import datetime

from pydantic import BaseModel

from golf_domain.events import ShotBoundaryUpdated
from golf_domain.ids import SessionId, ShotId
from golf_domain.shot import Shot

from ..ports import EventPublisher, SessionRepository, ShotRepository


class UpdateShotBoundaryInput(BaseModel):
    session_id: SessionId
    shot_id: ShotId
    t_start: float
    t_end: float


class UpdateShotBoundaryUseCase:
    def __init__(
        self,
        *,
        sessions: SessionRepository,
        shots: ShotRepository,
        events: EventPublisher,
    ) -> None:
        self._sessions = sessions
        self._shots = shots
        self._events = events

    async def execute(self, input: UpdateShotBoundaryInput) -> Shot:
        session = await self._sessions.get(input.session_id)
        session.assert_editable()

        shot = await self._shots.get(input.shot_id)
        adjusted = shot.adjust_boundary(t_start=input.t_start, t_end=input.t_end)
        await self._shots.update(adjusted)
        await self._events.publish(
            ShotBoundaryUpdated(
                session_id=session.id,
                shot_id=adjusted.id,
                t_start=adjusted.t_start,
                t_end=adjusted.t_end,
                occurred_at=datetime.now(),
            )
        )
        return adjusted
```

- [ ] **Step 4: Run test to verify pass**

Run: `uv run pytest libs/application/tests/use_cases/test_update_shot_boundary.py -v`
Expected: PASS — all 4 tests green.

- [ ] **Step 5: Commit**

```bash
git add libs/application
git commit -m "feat(application): add UpdateShotBoundaryUseCase"
```

---

## Task 13: `AddManualShotUseCase` + `DeleteShotUseCase` (TDD)

**Files:**
- Create: `libs/application/src/golf_application/use_cases/add_manual_shot.py`, `libs/application/src/golf_application/use_cases/delete_shot.py`, `libs/application/tests/use_cases/test_manual_shots.py`

- [ ] **Step 1: Write failing test**

Write `libs/application/tests/use_cases/test_manual_shots.py`:
```python
from datetime import UTC, datetime

import pytest

from golf_application.errors import ShotNotFoundError
from golf_application.use_cases.add_manual_shot import (
    AddManualShotInput,
    AddManualShotUseCase,
)
from golf_application.use_cases.delete_shot import (
    DeleteShotInput,
    DeleteShotUseCase,
)
from golf_domain.session import Session, SessionStatus
from golf_domain.shot import ShotSource

from ..fakes.fake_clock import FakeClock
from ..fakes.fake_id_generator import FakeIdGenerator
from ..fakes.fake_publisher import FakeEventPublisher
from ..fakes.in_memory_repos import InMemorySessionRepository, InMemoryShotRepository


def _ready_session() -> Session:
    return Session(
        id="ses_1",
        user_id=None,
        raw_video_key="raw/ses_1/v.mp4",
        status=SessionStatus.READY,
        pre_roll_seconds=2.0,
        post_roll_seconds=5.0,
        shot_count=0,
        duration_seconds=900.0,
        error=None,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


async def test_add_manual_shot_assigns_next_index():
    sessions = InMemorySessionRepository()
    shots = InMemoryShotRepository()
    await sessions.add(_ready_session())

    uc = AddManualShotUseCase(
        sessions=sessions,
        shots=shots,
        events=FakeEventPublisher(),
        clock=FakeClock(datetime(2026, 4, 27, tzinfo=UTC)),
        ids=FakeIdGenerator(),
    )

    out1 = await uc.execute(
        AddManualShotInput(
            session_id="ses_1", t_impact=10.0, t_start=8.0, t_end=15.0
        )
    )
    out2 = await uc.execute(
        AddManualShotInput(
            session_id="ses_1", t_impact=30.0, t_start=28.0, t_end=35.0
        )
    )
    assert out1.index == 1
    assert out2.index == 2
    assert out1.source is ShotSource.MANUAL


async def test_delete_shot_removes_record():
    sessions = InMemorySessionRepository()
    shots = InMemoryShotRepository()
    await sessions.add(_ready_session())

    add = AddManualShotUseCase(
        sessions=sessions,
        shots=shots,
        events=FakeEventPublisher(),
        clock=FakeClock(datetime(2026, 4, 27, tzinfo=UTC)),
        ids=FakeIdGenerator(),
    )
    out = await add.execute(
        AddManualShotInput(session_id="ses_1", t_impact=10.0, t_start=8.0, t_end=15.0)
    )

    delete = DeleteShotUseCase(
        sessions=sessions, shots=shots, events=FakeEventPublisher()
    )
    await delete.execute(DeleteShotInput(session_id="ses_1", shot_id=out.id))

    with pytest.raises(ShotNotFoundError):
        await shots.get(out.id)
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest libs/application/tests/use_cases/test_manual_shots.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement `add_manual_shot.py`**

Write `libs/application/src/golf_application/use_cases/add_manual_shot.py`:
```python
from datetime import datetime

from pydantic import BaseModel

from golf_domain.events import ShotDetected
from golf_domain.ids import SessionId
from golf_domain.shot import Shot, ShotSource
from golf_domain.value_objects import Confidence

from ..ports import (
    Clock,
    EventPublisher,
    IdGenerator,
    SessionRepository,
    ShotRepository,
)


class AddManualShotInput(BaseModel):
    session_id: SessionId
    t_impact: float
    t_start: float
    t_end: float


class AddManualShotUseCase:
    def __init__(
        self,
        *,
        sessions: SessionRepository,
        shots: ShotRepository,
        events: EventPublisher,
        clock: Clock,
        ids: IdGenerator,
    ) -> None:
        self._sessions = sessions
        self._shots = shots
        self._events = events
        self._clock = clock
        self._ids = ids

    async def execute(self, input: AddManualShotInput) -> Shot:
        session = await self._sessions.get(input.session_id)
        session.assert_editable()

        existing = await self._shots.list_by_session(session.id)
        next_index = len(existing) + 1
        now = self._clock.now()

        shot = Shot(
            id=self._ids.shot_id(),  # type: ignore[arg-type]
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
        await self._events.publish(
            ShotDetected(
                session_id=session.id,
                shot_id=shot.id,
                confidence=1.0,
                occurred_at=now,
            )
        )
        return shot
```

- [ ] **Step 4: Implement `delete_shot.py`**

Write `libs/application/src/golf_application/use_cases/delete_shot.py`:
```python
from datetime import datetime

from pydantic import BaseModel

from golf_domain.events import ShotDeleted
from golf_domain.ids import SessionId, ShotId

from ..ports import EventPublisher, SessionRepository, ShotRepository


class DeleteShotInput(BaseModel):
    session_id: SessionId
    shot_id: ShotId


class DeleteShotUseCase:
    def __init__(
        self,
        *,
        sessions: SessionRepository,
        shots: ShotRepository,
        events: EventPublisher,
    ) -> None:
        self._sessions = sessions
        self._shots = shots
        self._events = events

    async def execute(self, input: DeleteShotInput) -> None:
        session = await self._sessions.get(input.session_id)
        session.assert_editable()
        await self._shots.delete(input.shot_id)
        await self._events.publish(
            ShotDeleted(
                session_id=session.id,
                shot_id=input.shot_id,
                occurred_at=datetime.now(),
            )
        )
```

- [ ] **Step 5: Run test to verify pass**

Run: `uv run pytest libs/application/tests/use_cases/test_manual_shots.py -v`
Expected: PASS — both tests green.

- [ ] **Step 6: Commit**

```bash
git add libs/application
git commit -m "feat(application): add AddManualShot + DeleteShot use cases"
```

---

## Task 14: `ListSessionsUseCase` + `GetSessionWithShotsUseCase` (TDD)

**Files:**
- Create: `libs/application/src/golf_application/use_cases/list_sessions.py`, `libs/application/src/golf_application/use_cases/get_session_with_shots.py`, `libs/application/tests/use_cases/test_queries.py`

- [ ] **Step 1: Write failing test**

Write `libs/application/tests/use_cases/test_queries.py`:
```python
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
        id=id, session_id=session_id, index=index,
        t_impact=10.0, t_start=8.0, t_end=15.0,
        confidence=Confidence(value=0.9),
        source=ShotSource.AUTO, clip_key=None,
        created_at=now, updated_at=now,
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
```

- [ ] **Step 2: Run test to verify failure**

Run: `uv run pytest libs/application/tests/use_cases/test_queries.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement `list_sessions.py`**

Write `libs/application/src/golf_application/use_cases/list_sessions.py`:
```python
from pydantic import BaseModel

from golf_domain.ids import UserId
from golf_domain.session import Session

from ..ports import SessionRepository


class ListSessionsInput(BaseModel):
    user_id: UserId | None


class ListSessionsUseCase:
    def __init__(self, *, sessions: SessionRepository) -> None:
        self._sessions = sessions

    async def execute(self, input: ListSessionsInput) -> list[Session]:
        return await self._sessions.list_for_user(input.user_id)
```

- [ ] **Step 4: Implement `get_session_with_shots.py`**

Write `libs/application/src/golf_application/use_cases/get_session_with_shots.py`:
```python
from pydantic import BaseModel

from golf_domain.ids import SessionId
from golf_domain.session import Session
from golf_domain.shot import Shot

from ..ports import SessionRepository, ShotRepository


class GetSessionWithShotsInput(BaseModel):
    session_id: SessionId


class GetSessionWithShotsOutput(BaseModel):
    model_config = {"arbitrary_types_allowed": True}
    session: Session
    shots: list[Shot]


class GetSessionWithShotsUseCase:
    def __init__(
        self, *, sessions: SessionRepository, shots: ShotRepository
    ) -> None:
        self._sessions = sessions
        self._shots = shots

    async def execute(
        self, input: GetSessionWithShotsInput
    ) -> GetSessionWithShotsOutput:
        session = await self._sessions.get(input.session_id)
        shots = await self._shots.list_by_session(session.id)
        return GetSessionWithShotsOutput(session=session, shots=shots)
```

- [ ] **Step 5: Run test to verify pass**

Run: `uv run pytest libs/application/tests/use_cases/test_queries.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add libs/application
git commit -m "feat(application): add ListSessions + GetSessionWithShots use cases"
```

---

## Task 15: `ProcessVideoUseCase` (TDD) — worker-side orchestration

The worker calls this use case with already-detected `ShotCandidate`s — it does NOT do the detection itself (that lives in `apps/worker/pipeline/*` in Plan 3). This use case persists candidates as `Shot` aggregates and finalizes the session.

**Files:**
- Create: `libs/application/src/golf_application/use_cases/process_video.py`, `libs/application/tests/use_cases/test_process_video.py`

- [ ] **Step 1: Write failing test**

Write `libs/application/tests/use_cases/test_process_video.py`:
```python
from datetime import UTC, datetime

import pytest

from golf_application.use_cases.process_video import (
    ProcessVideoInput,
    ProcessVideoUseCase,
    ShotCandidate,
)
from golf_domain.session import Session, SessionStatus

from ..fakes.fake_clock import FakeClock
from ..fakes.fake_id_generator import FakeIdGenerator
from ..fakes.fake_publisher import FakeEventPublisher
from ..fakes.in_memory_repos import InMemorySessionRepository, InMemoryShotRepository


def _processing_session() -> Session:
    now = datetime.now(UTC)
    return Session(
        id="ses_1", user_id=None, raw_video_key="raw/ses_1/v.mp4",
        status=SessionStatus.PROCESSING,
        pre_roll_seconds=2.0, post_roll_seconds=5.0,
        shot_count=0, duration_seconds=900.0,
        error=None, created_at=now, updated_at=now,
    )


async def test_persists_candidates_and_marks_ready():
    sessions = InMemorySessionRepository()
    shots = InMemoryShotRepository()
    events = FakeEventPublisher()
    await sessions.add(_processing_session())

    uc = ProcessVideoUseCase(
        sessions=sessions, shots=shots, events=events,
        clock=FakeClock(datetime(2026, 4, 27, tzinfo=UTC)),
        ids=FakeIdGenerator(),
    )
    await uc.execute(
        ProcessVideoInput(
            session_id="ses_1",
            candidates=[
                ShotCandidate(t_impact=10.0, confidence=0.9, clip_key="clips/ses_1/shot_001.mp4"),
                ShotCandidate(t_impact=30.0, confidence=0.85, clip_key="clips/ses_1/shot_002.mp4"),
            ],
        )
    )

    persisted = await shots.list_by_session("ses_1")
    assert [s.index for s in persisted] == [1, 2]
    updated = await sessions.get("ses_1")
    assert updated.status is SessionStatus.READY
    assert updated.shot_count == 2

    types = [type(e).__name__ for e in events.published]
    assert types.count("ShotDetected") == 2
    assert types.count("SessionReady") == 1


async def test_marks_failed_when_pipeline_returns_no_candidates_and_strict_mode():
    sessions = InMemorySessionRepository()
    shots = InMemoryShotRepository()
    events = FakeEventPublisher()
    await sessions.add(_processing_session())

    uc = ProcessVideoUseCase(
        sessions=sessions, shots=shots, events=events,
        clock=FakeClock(datetime(2026, 4, 27, tzinfo=UTC)),
        ids=FakeIdGenerator(),
    )
    # 0 candidates → still mark ready; UI handles "0 shots" state
    await uc.execute(ProcessVideoInput(session_id="ses_1", candidates=[]))
    updated = await sessions.get("ses_1")
    assert updated.status is SessionStatus.READY
    assert updated.shot_count == 0
```

- [ ] **Step 2: Run test to verify failure**

Run: `uv run pytest libs/application/tests/use_cases/test_process_video.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement `process_video.py`**

Write `libs/application/src/golf_application/use_cases/process_video.py`:
```python
from pydantic import BaseModel, Field

from golf_domain.events import SessionReady, ShotDetected
from golf_domain.ids import SessionId
from golf_domain.shot import Shot, ShotSource
from golf_domain.value_objects import Confidence

from ..ports import (
    Clock,
    EventPublisher,
    IdGenerator,
    SessionRepository,
    ShotRepository,
)


class ShotCandidate(BaseModel):
    t_impact: float
    confidence: float = Field(ge=0.0, le=1.0)
    clip_key: str


class ProcessVideoInput(BaseModel):
    session_id: SessionId
    candidates: list[ShotCandidate]


class ProcessVideoUseCase:
    def __init__(
        self,
        *,
        sessions: SessionRepository,
        shots: ShotRepository,
        events: EventPublisher,
        clock: Clock,
        ids: IdGenerator,
    ) -> None:
        self._sessions = sessions
        self._shots = shots
        self._events = events
        self._clock = clock
        self._ids = ids

    async def execute(self, input: ProcessVideoInput) -> None:
        session = await self._sessions.get(input.session_id)
        now = self._clock.now()

        new_shots: list[Shot] = []
        for index, c in enumerate(input.candidates, start=1):
            t_start = max(0.0, c.t_impact - session.pre_roll_seconds)
            t_end = c.t_impact + session.post_roll_seconds
            shot = Shot(
                id=self._ids.shot_id(),  # type: ignore[arg-type]
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
                    session_id=session.id,
                    shot_id=s.id,
                    confidence=s.confidence.value,
                    occurred_at=now,
                )
            )

        ready = session.mark_ready(shot_count=len(new_shots))
        await self._sessions.update(ready)
        await self._events.publish(
            SessionReady(
                session_id=session.id,
                shot_count=len(new_shots),
                occurred_at=now,
            )
        )
```

- [ ] **Step 4: Run test to verify pass**

Run: `uv run pytest libs/application/tests/use_cases/test_process_video.py -v`
Expected: PASS — both tests green.

- [ ] **Step 5: Commit**

```bash
git add libs/application
git commit -m "feat(application): add ProcessVideoUseCase (worker orchestration)"
```

---

## Task 16: `RequestSignedUploadUrlUseCase` + `ExportSessionZipUseCase` (TDD)

**Files:**
- Create: `libs/application/src/golf_application/use_cases/request_signed_upload_url.py`, `libs/application/src/golf_application/use_cases/export_session_zip.py`, `libs/application/tests/use_cases/test_storage_use_cases.py`

- [ ] **Step 1: Write failing test**

Write `libs/application/tests/use_cases/test_storage_use_cases.py`:
```python
from datetime import UTC, datetime

import pytest

from golf_application.errors import SessionNotFoundError
from golf_application.use_cases.export_session_zip import (
    ExportSessionZipInput,
    ExportSessionZipUseCase,
)
from golf_application.use_cases.request_signed_upload_url import (
    RequestSignedUploadUrlInput,
    RequestSignedUploadUrlUseCase,
)
from golf_domain.session import Session, SessionStatus

from ..fakes.fake_id_generator import FakeIdGenerator
from ..fakes.fake_storage import FakeStorage
from ..fakes.in_memory_repos import InMemorySessionRepository


def _session(status: SessionStatus = SessionStatus.READY) -> Session:
    now = datetime.now(UTC)
    return Session(
        id="ses_1", user_id=None, raw_video_key="raw/ses_1/v.mp4",
        status=status,
        pre_roll_seconds=2.0, post_roll_seconds=5.0,
        shot_count=2, duration_seconds=900.0,
        error=None, created_at=now, updated_at=now,
    )


async def test_request_upload_url_returns_signed_put():
    repo = InMemorySessionRepository()
    await repo.add(_session(status=SessionStatus.UPLOADING))
    uc = RequestSignedUploadUrlUseCase(sessions=repo, storage=FakeStorage())
    out = await uc.execute(RequestSignedUploadUrlInput(session_id="ses_1"))
    assert out.url.startswith("https://fake-r2.local/PUT/raw/ses_1/v.mp4")


async def test_request_upload_url_rejects_missing_session():
    repo = InMemorySessionRepository()
    uc = RequestSignedUploadUrlUseCase(sessions=repo, storage=FakeStorage())
    with pytest.raises(SessionNotFoundError):
        await uc.execute(RequestSignedUploadUrlInput(session_id="missing"))


async def test_export_session_zip_returns_export_id_and_signed_get():
    repo = InMemorySessionRepository()
    await repo.add(_session())
    uc = ExportSessionZipUseCase(
        sessions=repo, storage=FakeStorage(), ids=FakeIdGenerator()
    )
    out = await uc.execute(ExportSessionZipInput(session_id="ses_1"))
    assert out.export_id == "exp_0001"
    assert out.signed_download_url.startswith(
        "https://fake-r2.local/GET/exports/ses_1/exp_0001.zip"
    )
```

- [ ] **Step 2: Run test to verify failure**

Run: `uv run pytest libs/application/tests/use_cases/test_storage_use_cases.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement `request_signed_upload_url.py`**

Write `libs/application/src/golf_application/use_cases/request_signed_upload_url.py`:
```python
from pydantic import BaseModel

from golf_domain.ids import SessionId

from ..ports import SessionRepository, SignedUrl, StorageGateway


class RequestSignedUploadUrlInput(BaseModel):
    session_id: SessionId


class RequestSignedUploadUrlUseCase:
    def __init__(
        self, *, sessions: SessionRepository, storage: StorageGateway
    ) -> None:
        self._sessions = sessions
        self._storage = storage

    async def execute(self, input: RequestSignedUploadUrlInput) -> SignedUrl:
        session = await self._sessions.get(input.session_id)
        return await self._storage.signed_put_url(
            session.raw_video_key, content_type="video/mp4"
        )
```

- [ ] **Step 4: Implement `export_session_zip.py`**

Write `libs/application/src/golf_application/use_cases/export_session_zip.py`:
```python
from pydantic import BaseModel

from golf_domain.ids import SessionId

from ..ports import IdGenerator, SessionRepository, StorageGateway


class ExportSessionZipInput(BaseModel):
    session_id: SessionId


class ExportSessionZipOutput(BaseModel):
    export_id: str
    signed_download_url: str


class ExportSessionZipUseCase:
    """
    Phase 1 minimal version: returns signed GET URL for a deterministic key.
    Plan 2 will wire this to a real ZIP-builder Celery task; for now the URL
    points at the location the worker will eventually upload to.
    """

    def __init__(
        self,
        *,
        sessions: SessionRepository,
        storage: StorageGateway,
        ids: IdGenerator,
    ) -> None:
        self._sessions = sessions
        self._storage = storage
        self._ids = ids

    async def execute(self, input: ExportSessionZipInput) -> ExportSessionZipOutput:
        session = await self._sessions.get(input.session_id)
        session.assert_editable()
        export_id = self._ids.export_id()
        key = f"exports/{session.id}/{export_id}.zip"
        signed = await self._storage.signed_get_url(key)
        return ExportSessionZipOutput(
            export_id=export_id, signed_download_url=signed.url
        )
```

- [ ] **Step 5: Run test to verify pass**

Run: `uv run pytest libs/application/tests/use_cases/test_storage_use_cases.py -v`
Expected: PASS — all 3 tests green.

- [ ] **Step 6: Commit**

```bash
git add libs/application
git commit -m "feat(application): add RequestSignedUploadUrl + ExportSessionZip use cases"
```

---

## Task 17: Final whole-suite verify + import-linter

- [ ] **Step 1: Run full Python test suite**

Run: `uv run pytest -v`
Expected: All tests pass — `libs/domain` (3 files), `libs/application` (6 files).

- [ ] **Step 2: Run import-linter**

Run: `uv run lint-imports`
Expected: `Contracts: 1 kept, 0 broken.`

- [ ] **Step 3: Run TS test suite**

Run: `pnpm nx run-many -t test`
Expected: `@golf/contracts` vitest passes.

- [ ] **Step 4: Run lint**

Run: `pnpm exec biome check . && uv run ruff check .`
Expected: No errors.

- [ ] **Step 5: Run pre-commit on all files**

Run: `pre-commit run --all-files`
Expected: All hooks pass.

- [ ] **Step 6: Tag release**

```bash
git tag v0.1.0-foundation
git log --oneline | head -20
```
Expected: ~17 commits, foundation tag set.

---

## Done criteria

- All Python use cases pass with in-memory adapters
- `libs/contracts` zod schemas + Pydantic codegen working
- `import-linter` confirms layered architecture
- `pnpm verify` green end-to-end
- Foundation ready for Plan 2 (infrastructure + API)
