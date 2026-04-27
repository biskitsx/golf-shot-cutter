# Golf Shot Cutter — Design Spec

**Date:** 2026-04-27
**Status:** Draft (pending review)

## 1. Problem

ผู้ใช้ถ่ายวิดีโอตอนตีกอล์ฟที่ไดรฟ์ 10–20 นาที/เซสชัน โดยต้องนั่งตัดคลิปแต่ละ shot ด้วยมือซึ่งใช้เวลานาน ต้องการ automation ที่
ตัดคลิปแยกแต่ละ shot อัตโนมัติ และต่อยอดไปยังฟีเจอร์ tracer (เส้นวิถีบอล) และวิเคราะห์วงสวิง

## 2. Goals & Non-Goals

### Goals (Phase 1 / MVP)
- Upload วิดีโอ → auto-detect แต่ละ shot → ได้คลิปย่อยพร้อม metadata
- Review UI ให้ผู้ใช้ปรับขอบ in/out ของคลิป, ลบ false positive, เพิ่ม shot ที่ระบบหาไม่เจอ
- Export เป็น ZIP รวมคลิปทั้งหมด หรือเลือกบาง shot
- Pre-roll/post-roll ปรับได้ทั้ง session

### Non-Goals (Phase 1)
- ไม่ทำ tracer (ดู Phase 2)
- ไม่ทำ swing analysis / metrics (ดู Phase 3)
- ไม่ทำ multi-user / sharing / social features
- ไม่ทำ mobile app (web responsive ก็พอ)
- ไม่ทำ live streaming / on-device processing

## 3. User Decisions (Brainstorm Outcome)

| คำถาม | คำตอบ |
|---|---|
| Platform | Web app (cloud processing) |
| Recording setup | กล้องตั้งด้านหลัง — เห็นทั้งสวิงและบอลลอย |
| Clip scope | Configurable pre-roll/post-roll (default 2s / 5s) |
| Detection signal | Audio (impact) + Pose verification |
| MVP scope | ตัดคลิปอัตโนมัติเท่านั้น; tracer/analysis เป็น phase ถัดไป |

## 4. Architecture

### 4.1 High-level

```
┌──────────────────────────────────────────────────────────────┐
│                       User (Browser)                          │
│  apps/web (Next.js) — presentation only, NO business logic    │
└─────────────────────────┬────────────────────────────────────┘
                          │ REST + SSE (cookies/JWT)
                          ▼
┌──────────────────────────────────────────────────────────────┐
│  apps/api (FastAPI)                                           │
│  Routers → Use Cases → Domain                                 │
│  + JWT auth (httpOnly cookies)  + R2 signed URLs  + queue     │
└──────────┬─────────────────────────┬─────────────────────────┘
           │                         │
           ▼                         ▼
┌──────────────────┐        ┌────────────────────────┐
│  Cloudflare R2   │        │  Redis (queue + cache) │
│  raw / clips /   │        └──────────┬─────────────┘
│  exports / tracer│                   │
└──────────────────┘                   ▼
                              ┌────────────────────────┐
                              │  apps/worker (Python)  │
                              │  Celery consumer       │
                              │  1. AudioOnsetDetector │  ← librosa
                              │  2. PoseVerifier       │  ← MediaPipe
                              │  3. ClipCutter         │  ← FFmpeg
                              │  4. ResultPublisher    │
                              └────────┬───────────────┘
                                       │
                                       ▼
                              ┌────────────────────────┐
                              │  MongoDB Atlas         │
                              │  sessions, shots       │
                              └────────────────────────┘
```

FastAPI เป็น **single source of business logic**. Next.js เรียกผ่าน REST/SSE เท่านั้น
Python worker (Celery) แชร์ libs/{domain,application,infrastructure} กับ FastAPI โดยตรง — ทำให้ pipeline result, repository write, event publish ใช้ code path เดียวกัน ไม่ต้องสำเนา domain logic

### 4.2 Clean Architecture Layers

แต่ละ layer พึ่งพาเฉพาะ layer "ใน" (inward dependency rule):

```
┌────────────────── apps (Frameworks & Drivers) ──────────────────┐
│  apps/web · Next.js (TS)        apps/api · FastAPI (Py)         │
│  (presentation only)            apps/worker · Celery (Py)       │
└─────────────────────────────┬───────────────────────────────────┘
                              ▼
┌──────────────── libs/infrastructure (Python pkg) ───────────────┐
│  MongoRepositories · R2StorageAdapter · RedisQueueAdapter       │
│  JwtAuthAdapter · ConfigService · Logger                        │
└─────────────────────────────┬───────────────────────────────────┘
                              ▼
┌──────────────── libs/application (Python pkg) ──────────────────┐
│  CreateSessionUseCase · ProcessVideoUseCase                     │
│  ListShotsUseCase · UpdateShotBoundaryUseCase                   │
│  AddManualShotUseCase · ExportZipUseCase                        │
│  + Repository interfaces (Protocol/ABC ports)                   │
└─────────────────────────────┬───────────────────────────────────┘
                              ▼
┌──────────────── libs/domain (Python pkg) ───────────────────────┐
│  Session · Shot · TimeRange · Confidence                        │
│  Domain events: ShotDetected, SessionReady                      │
│  Pure Python — Pydantic v2 / dataclasses, no framework imports  │
└─────────────────────────────────────────────────────────────────┘
```

`apps/web` ใช้เฉพาะ TypeScript — ไม่ import Python libs ตรง — สื่อสารกับ `apps/api` ผ่าน REST/SSE
contracts (DTO/wire-format) อยู่ใน `libs/contracts` (ทั้ง zod schemas สำหรับ TS และ Pydantic models สำหรับ Python — generate จาก source เดียวกัน)

### 4.3 Nx + uv Hybrid Monorepo Layout

Nx จัดการ TS workspace; **uv workspace** จัดการ Python packages/apps ในที่เดียวกัน

```
golf-shot-cutter/                # repo root
  pnpm-workspace.yaml            # TS workspace (web + ts libs)
  pyproject.toml                 # uv workspace root (api + worker + py libs)
  uv.lock
  nx.json
  package.json
  tsconfig.base.json

  apps/
    web/                         # Next.js 16 — presentation only (TS)
      project.json               # Nx project
    api/                         # FastAPI — routers, DI wiring (Python)
      pyproject.toml             # uv member
      project.json               # Nx project (uses @nxlv/python or custom executors)
    worker/                      # Celery worker (Python)
      pyproject.toml             # uv member
      project.json               # Nx project

  libs/
    # ── Python packages (consumed by apps/api + apps/worker) ──
    domain/
      pyproject.toml             # uv member
      src/golf_domain/           # entities, value objects, events (Pydantic v2)
    application/
      pyproject.toml             # uv member
      src/golf_application/      # use cases + ports (ABC/Protocol)
    infrastructure/
      pyproject.toml             # uv member
      src/golf_infrastructure/   # mongo, r2, celery adapters

    # ── TS packages (consumed by apps/web) ──
    contracts/                   # zod schemas → generates TS types + Pydantic models
      src/                       # source-of-truth schemas
      generated/ts/              # → consumed by apps/web
      generated/python/          # → consumed by libs/domain (DTO boundary only)
    shared/                      # cross-cutting TS helpers (Result type, formatters)
    ui/                          # shadcn components (if extracted)
```

**Why uv (not Poetry):** เร็วกว่ามาก, lockfile เดียว, รองรับ workspace native, เข้ากับ Docker multi-stage build ดี

**Dependency rules (Python: enforce via [import-linter]; TS: enforce via Nx tags)**
- `libs/domain` → no deps (only stdlib + pydantic)
- `libs/application` → `libs/domain` only
- `libs/infrastructure` → `libs/application` + `libs/domain`
- `apps/api` → `libs/{infrastructure,application,domain,contracts}`
- `apps/worker` → `libs/{infrastructure,application,domain,contracts}`
- `apps/web` (TS) → `libs/{contracts,ui,shared}` (TS only) — ห้าม import Python libs; พูดกับ api ผ่าน REST/SSE

### 4.4 Tech Stack

**Frontend (`apps/web`)**
- Next.js 16 (App Router) + TypeScript strict
- pnpm
- Tailwind CSS v4 + shadcn/ui
- TanStack Query (`staleTime: Infinity`, `gcTime: 30min`, `retry: 1`, `refetchOnWindowFocus: false`)
- next-intl (Thai default + English)
- Auth: JWT จาก NestJS via httpOnly cookies (ไม่มี frontend auth lib)
- Linting: Biome
- SSE invalidation pattern: backend push → `useRealtimeInvalidation` invalidates query keys

**Backend (`apps/api`)**
- FastAPI + Python 3.11+
- Pydantic v2 (request/response, settings)
- Motor (async MongoDB driver) หรือ Beanie ODM — ตัดสินใจใน plan
- Celery client (Redis broker) เป็น producer
- `python-jose` + `fastapi.Cookie` สำหรับ JWT httpOnly cookie auth
- SSE: `sse-starlette`

**Worker (`apps/worker`)**
- Python 3.11+
- Celery (Redis broker; matches API's enqueue format)
- librosa, MediaPipe, OpenCV, FFmpeg
- แชร์ libs/domain + libs/application + libs/infrastructure กับ apps/api → ใช้ use case `ProcessVideoUseCase` ตรงๆ ไม่ต้องสำเนา logic

**Storage / Infra**
- Cloudflare R2 (S3-compatible) — raw / clips / exports / tracer
- MongoDB Atlas (M0 free tier OK สำหรับ MVP)
- Redis (queue + cache)
- Deployment: **Docker → Azure Container Registry → ArgoCD → AKS**

### 4.5 Data Flow

1. User เปิด `apps/web` → SignIn → JWT cookie set
2. User upload: `apps/web` ขอ signed PUT URL จาก `apps/api` → upload ตรงเข้า R2 (ไม่ผ่าน server)
3. `apps/web` แจ้ง `POST /sessions/:id/process` → NestJS use case enqueue job ไปที่ Redis
4. `apps/worker` consume job → ทำ 4 stage → write ผ่าน infrastructure interface → publish `SessionReady` event
5. NestJS push SSE event ที่ frontend → `useRealtimeInvalidation` → refetch
6. User review timeline → drag handles → mutation → `PATCH /sessions/:id/shots/:shotId` → invalidate query
7. Export: `POST /sessions/:id/export` → NestJS enqueue lightweight zip job → R2 signed download URL

## 5. Components

### 5.1 `apps/web` — Next.js Frontend (presentation only)

#### Folder structure
```
apps/web/
  src/
    app/[locale]/                 # App Router; route groups (auth), (dashboard)
      (dashboard)/
        sessions/
          page.tsx                # session list
          [id]/page.tsx           # review timeline
        upload/page.tsx
    features/
      sessions/
        components/               # SessionCard, SessionStatusBadge
        hooks/                    # useSessionsQuery, useCreateSessionMutation
        types/                    # local view-model types (re-export from contracts)
      shots/
        components/               # TimelineRuler, ShotMarker, DragHandle, ShotSidebarItem
        hooks/                    # useShotsQuery, useUpdateShotBoundaryMutation, useDeleteShotMutation
        types/
      upload/
        components/               # UploadDropzone, UploadProgress
        hooks/                    # useSignedUploadUrl, useUploadVideoMutation
        types/
      review/
        components/               # ReviewTimeline (composes shots/* + video player)
        hooks/                    # usePlayerSync
      realtime/
        hooks/                    # useRealtimeInvalidation (SSE → invalidateQueries)
    lib/
      api-client.ts               # axios + JWT cookie + refresh interceptor
      query-client.ts             # global TanStack Query config (Infinity stale, etc.)
      utils.ts
    i18n/
      config.ts
      messages/{th,en}.json
    components/                   # shared shadcn/ui (Button, Card, Dialog, ...)
    hooks/                        # cross-feature (e.g. useDebouncedValue)
    styles/                       # global Tailwind layers
    contracts/                    # auto-generated from libs/contracts/ — never edit
    types/                        # cross-feature view-model types
    proxy.ts                      # rewrite/proxy helper
```

#### Constraints (จาก user requirement)
- **Components ไม่เรียก axios/fetch ตรงๆ** — ต้องผ่าน hook
- TanStack Query global config: `staleTime: Infinity`, `gcTime: 30min`, `retry: 1`, `refetchOnWindowFocus: false`
- ห้ามใส่ `refetchOnWindowFocus: true` / `staleTime: 0` / `refetchOnMount: "always"` ใน feature hooks (ป้องกัน blast หลายๆ query เมื่อ refocus tab)
- Freshness มาจาก mutation `invalidateQueries(...)` + SSE invalidation เท่านั้น
- Query keys ใช้ prefix ตรงกับ event ที่ backend emit (เช่น `["sessions", sessionId, "shots"]`)
- **ไม่เขียน test ใหม่** (no-new-tests rule); existing test commands ยัง verify ได้
- Lint: Biome
- i18n: ทุก string ผ่าน `next-intl`

### 5.2 `apps/api` — FastAPI Backend (Clean Architecture host)

#### Module layout
```
apps/api/src/golf_api/
  main.py                          # FastAPI app, lifespan, middleware, CORS
  routers/
    sessions.py                    # POST/GET sessions, /process
    shots.py                       # PATCH/POST/DELETE shots
    upload.py                      # signed PUT URL endpoints
    export.py                      # POST /export, GET status
    realtime.py                    # SSE stream
    auth.py                        # login/logout/refresh
  deps/
    auth.py                        # cookie-based JWT dependency (Depends)
    container.py                   # wires libs/application use cases with libs/infrastructure adapters
  middleware/
    error_handler.py
    request_id.py
  settings.py                      # Pydantic BaseSettings (env)
```

#### REST endpoints
- `POST /sessions` — create session, return `{ sessionId, signedUploadUrl }`
- `POST /sessions/{id}/process` — enqueue processing job (Celery)
- `GET /sessions` — list sessions (current user)
- `GET /sessions/{id}` — session + shots
- `PATCH /sessions/{id}/shots/{shotId}` — update in/out (calls `UpdateShotBoundaryUseCase`)
- `POST /sessions/{id}/shots` — manual add (`AddManualShotUseCase`)
- `DELETE /sessions/{id}/shots/{shotId}`
- `POST /sessions/{id}/export` — enqueue zip job, return `{ exportId }`
- `GET /sessions/{id}/export/{exportId}` — signed download URL when ready
- `GET /sessions/{id}/events` (SSE via `sse-starlette`) — push processing progress + ready events

Routers ทำหน้าที่ map HTTP ↔ Use Case input/output เท่านั้น **ห้ามมี business logic ใน router**
DI ด้วย `Depends()` เรียก factory ใน `deps/container.py` ที่ instantiate use cases พร้อม injected adapters

### 5.3 `libs/domain` (Python)

Pure Python entities (Pydantic v2 BaseModel หรือ dataclasses), ไม่มี framework import:
```python
# golf_domain/entities.py
class Session(BaseModel):
    id: SessionId
    user_id: UserId | None
    raw_video_key: str
    status: SessionStatus  # uploading|queued|processing|ready|failed
    pre_roll_seconds: float
    post_roll_seconds: float
    ...

class Shot(BaseModel):
    id: ShotId
    session_id: SessionId
    index: int
    t_impact: float
    t_start: float
    t_end: float
    confidence: Confidence
    source: ShotSource  # auto | manual
    clip_key: str | None

class TimeRange(BaseModel): ...
class Confidence(BaseModel): value: float  # validates 0..1

# golf_domain/events.py
SessionCreated, SessionProcessingStarted, ShotDetected,
SessionReady, SessionFailed, ShotBoundaryUpdated, ShotDeleted
```

Domain rules ที่ enforce ใน entity (raise `DomainError`):
- `Shot.adjust_boundary(t_start, t_end)` — validate `t_start < t_impact < t_end`, max duration
- `Session.assert_editable()` — only when status = "ready"
- Pre/post-roll validation

### 5.4 `libs/application` (Python) — Use Cases + Ports

```
golf_application/
  use_cases/
    create_session.py              # CreateSessionUseCase
    request_signed_upload_url.py
    start_processing.py            # enqueue Celery job
    process_video.py               # called from worker — orchestrates pipeline result
    list_sessions.py
    get_session_with_shots.py
    update_shot_boundary.py
    add_manual_shot.py
    delete_shot.py
    export_session_zip.py
  ports/                           # Protocol/ABC interfaces
    session_repository.py
    shot_repository.py
    storage_gateway.py             # signed_put_url, signed_get_url, delete_object
    job_queue.py                   # enqueue, consume
    event_publisher.py             # publish domain events (→ SSE bridge)
    clock.py
    id_generator.py
  errors.py                        # ApplicationError hierarchy
```

แต่ละ use case รับ port ผ่าน constructor injection (ไม่ import infrastructure ตรง)
Test ได้ด้วย in-memory implementations (เช่น `InMemorySessionRepository`)

### 5.5 `libs/infrastructure` (Python) — Adapters

```
golf_infrastructure/
  mongo/
    session_repository.py          # MongoSessionRepository (Motor or Beanie)
    shot_repository.py             # MongoShotRepository
    documents.py                   # ODM models / dict mappers
    indexes.py                     # ensure indexes on startup
  r2/
    storage_gateway.py             # R2StorageGateway via boto3 (S3-compatible endpoint)
  queue/
    celery_job_queue.py            # CeleryJobQueue (producer)
    celery_event_publisher.py      # publishes domain events via Redis pub/sub
  auth/
    jwt_service.py                 # python-jose; cookie helpers
  config/
    settings.py                    # Pydantic BaseSettings
  logging/
    structured_logger.py           # structlog
```

ทุก adapter implement port จาก `libs/application/ports/*` ตรงๆ — สามารถ swap ได้

### 5.6 `libs/contracts` — Wire-format DTOs (cross-language)

- **Source of truth:** zod schemas ใน `libs/contracts/src/`
- **Generated outputs:**
  - `generated/ts/` — TS types สำหรับ `apps/web` (auto-imported เป็น `apps/web/src/contracts/`)
  - `generated/python/` — Pydantic v2 models สำหรับ `apps/api` (response models) และ `libs/domain` (DTO boundary)
- **Sync script:** `scripts/sync-contracts.mjs` รันใน CI + pre-commit
  - ใช้ `zod-to-json-schema` → `datamodel-code-generator` สร้าง Pydantic models

ตัวอย่าง: `SessionDto`, `ShotDto`, `CreateSessionRequest`, `UpdateShotBoundaryRequest`, `SseEventEnvelope`

### 5.7 `apps/worker` — Celery Pipeline

Worker แชร์ libs/{domain,application,infrastructure} กับ apps/api → ProcessVideoUseCase ตัวเดียวกัน, ไม่สำเนา logic

```
apps/worker/
  pyproject.toml                  # uv workspace member
  src/golf_worker/
    main.py                       # Celery app entry, autodiscover tasks
    tasks/
      process_video.py            # @app.task → builds container → calls ProcessVideoUseCase
      generate_export_zip.py
    pipeline/                     # pure CV/audio code (no I/O)
      audio_onset.py              # AudioOnsetDetector
      pose_verifier.py            # PoseVerifier (MediaPipe)
      clip_cutter.py              # ClipCutter (FFmpeg stream copy)
      result_publisher.py         # composes pipeline → calls use case
    container.py                  # wires use case + adapters (mirror of api's deps/container.py)
  Dockerfile                      # python:3.11-slim + ffmpeg + opencv deps
```

Worker pipeline (เหมือนเดิม):

- **AudioOnsetDetector** — ffmpeg → WAV → bandpass 2-8 kHz → librosa.onset → amplitude + transient sharpness < 5ms
- **PoseVerifier** — MediaPipe pose ทุก 3 frames ใน window `[t-1.0s, t+0.3s]` → wrist angular velocity + shoulder rotation + hip-shoulder separation
- **ClipCutter** — ffmpeg `-ss -to -c copy` stream copy
- **ResultPublisher** — upload R2 + write Mongo + emit `SessionReady` event ผ่าน `EventPublisher` port (Redis pub/sub) → FastAPI realtime router subscribe → push SSE

### 5.8 Data Model (MongoDB)

ใช้ 2 collections; embed `shots` ใน `sessions` ก็ได้แต่แยกออกมาเพื่อให้ update shot รายตัวง่าย (PATCH in/out point) และ query/index ตรงๆ ได้

**`sessions` collection**
```js
{
  _id: ObjectId,
  userId: ObjectId | null,         // nullable for v1 (single-user)
  rawVideoKey: "raw/{sessionId}/{filename}",   // R2 object key
  rawVideoUrl: "https://...",                  // optional cached signed URL
  status: "uploading" | "queued" | "processing" | "ready" | "failed",
  preRollSeconds: 2.0,
  postRollSeconds: 5.0,
  shotCount: 12,                   // denormalized for list views
  durationSeconds: 923.4,
  error: { stage, message } | null,
  createdAt: ISODate,
  updatedAt: ISODate
}
```
Indexes: `{ userId: 1, createdAt: -1 }`, `{ status: 1 }`

**`shots` collection**
```js
{
  _id: ObjectId,
  sessionId: ObjectId,
  index: 3,                        // 1-based ordering within session
  tImpact: 42.518,                 // seconds
  tStart: 40.518,                  // user-editable (after pre-roll)
  tEnd: 47.518,                    // user-editable (after post-roll)
  confidence: 0.87,                // 0..1
  source: "auto" | "manual",
  clipKey: "clips/{sessionId}/shot_003.mp4",   // R2 object key
  createdAt: ISODate,
  updatedAt: ISODate
}
```
Indexes: `{ sessionId: 1, index: 1 }`

## 6. Detection Algorithm (Phase 1)

### Performance estimate (15-min input, 4-core CPU worker)
| Stage | Time |
|---|---|
| Upload (LTE) | ~30-60s |
| Audio onset | ~10s |
| Pose verify | ~30-60s |
| FFmpeg cut | ~5s |
| **Total** | **~1-2 min** |

### Edge cases
- **เสียงคนข้างๆ ตี** → pose verify กรองออก (ไม่มีคนสวิงในเฟรม)
- **Practice swing** (ไม่โดนบอล) → ไม่มีเสียง impact → ไม่ผ่านขั้น 1
- **Whiff/Top ball** (เสียงเบา) → threshold รับเสียงเบาได้, อาจเพิ่ม false positive → review UI ให้ลบ
- **คนเดินผ่านกล้อง** → pose verify กรอง (ไม่ใช่ swing pose)
- **หา 0 shots** → แสดงข้อความแนะนำ + ให้ user เพิ่ม shot ด้วยมือ

## 7. Error Handling

| Scenario | Behavior |
|---|---|
| Upload fail | Retry button, reuse signed URL ถ้ายัง valid |
| Audio extract fail | Mark stage failed, ส่ง error เฉพาะ stage นั้น |
| Pose detect fail | Skip pose verify, fall back to audio-only (low confidence) |
| FFmpeg cut fail | Retry stage; ถ้า fail ซ้ำ mark session failed |
| Worker crash | Celery retry policy: 3 attempts, exponential backoff |
| 0 shots detected | UI แนะนำ + เปิด manual mode |

## 8. Testing Strategy

> **No-new-tests rule** สำหรับ `apps/web`: ตามข้อกำหนดของ user — Vitest/RTL/Playwright suites ที่มีอยู่ยัง verify ผ่าน `pnpm verify` ได้ แต่ไม่เพิ่ม test ใหม่ในฝั่ง frontend
>
> สำหรับ `libs/domain`, `libs/application`, `libs/infrastructure`, `apps/api`, `apps/worker` — ใส่ test ตามปกติ เพราะเป็น greenfield และเป็นที่อยู่ของ business logic

### `libs/domain` (pytest, fast)
- Entity invariants — `Shot.adjust_boundary` reject case เลย impact, shot duration ติดลบ ฯลฯ

### `libs/application` (pytest, in-memory adapters)
- Each use case test ด้วย in-memory `SessionRepository` / `ShotRepository` / `JobQueue`
- เน้น coverage ของ branching logic — ไม่ต้อง mock framework

### `libs/infrastructure` (pytest integration)
- Mongo adapters: ใช้ `mongomock-motor` หรือ container `mongodb` ใน CI
- R2 adapter: ใช้ MinIO local container เป็น S3-compatible substitute
- Queue adapter: real Redis container ใน CI

### `apps/api` (pytest + httpx AsyncClient)
- TestClient หา router-level — happy path ของแต่ละ endpoint
- DI override: ใส่ in-memory adapters เพื่อ test routing/auth/serialization

### `apps/worker` (pytest)
- AudioOnsetDetector: feed WAV ที่มี/ไม่มี impact → ตรวจ output timestamps
- PoseVerifier: feed frames ของ swing/non-swing → ตรวจ classification
- ClipCutter: feed video + timestamps → ตรวจ output file duration & playable

### End-to-end (manual, no automation in v1)
- Upload จริงบน staging → review timeline → ปรับ → export → ตรวจ ZIP

### `pnpm verify`
- root script orchestrates: `nx run-many -t lint,build,test` (TS) + `uv run pytest` (Python libs+apps)
- รันครั้งเดียวตอน end-of-task (ไม่รันกลางทาง)

## 8.1 Storage Layout (R2)

โครงสร้าง object key ใน R2 bucket:
```
raw/{sessionId}/{originalFilename}        ← uploaded raw video
clips/{sessionId}/shot_{index:03d}.mp4    ← cut clips (Phase 1)
exports/{sessionId}/{exportId}.zip        ← generated ZIP (lazy, expires)
tracer/{sessionId}/shot_{index:03d}.mp4   ← Phase 2 only
```

- ใช้ **signed URLs** ทุกการ upload/download (ไม่เปิด bucket public)
- **Lifecycle rule**: ลบ `raw/*` หลัง 30 วัน, `exports/*` หลัง 7 วัน, `clips/*` ตามที่ user ตั้ง (default 90 วัน)
- R2 ไม่มี egress fee → คุ้มกว่า S3 มากเมื่อมีการ download คลิปบ่อย

## 9. Phase 2 — Tracer (~3-5 สัปดาห์)

ต่อยอดจาก Phase 1 โดยเพิ่ม pipeline stage:

```
1. Audio Onset       (เดิม)
2. Pose Verify       (เดิม)
3. Ball Tracker      ← ใหม่
4. Tracer Renderer   ← ใหม่
5. FFmpeg Cut        (เดิม, encode ใหม่เพราะมี overlay)
```

### Implementation
- Reuse pose data: รู้ impact frame แม่นยำจาก v1 → เริ่ม track ball เฉพาะหลัง impact
- Background subtraction (MOG2) + small object tracker (CSRT) → track 10-30 frames หลัง impact
- Parabolic curve fitting เติมเส้นช่วงที่ track หาย
- OpenCV/FFmpeg overlay เส้นโค้ง + fade trail
- **Optional GPU worker pool** หาก detection accuracy ไม่พอ → YOLOv8 fine-tuned

### Limitations (ที่ต้องบอกผู้ใช้)
- กล้องมือถือ 30/60fps มี motion blur — ไม่ได้ระดับ ProTracer
- ลูกหายเมื่อระยะไกล → ใช้ parabolic fit แทน
- ผลลัพธ์เทียบเคียง Rapsodo / 18Birdies app (ดูได้ ไม่ใช่ระดับ broadcast)

### Architecture impact
- เพิ่ม 2 stage ใน worker pipeline
- เพิ่ม `tracerClipKey` ใน `shots` document (rendered version)
- Frontend อาจมี toggle "show tracer" ระหว่าง raw clip / tracer clip

## 10. Phase 3 — Swing Analysis (~6-8 สัปดาห์)

### Features
- **Phase segmentation:** address → backswing → top → downswing → impact → follow-through
- **Metrics:** tempo (backswing:downswing ratio), shoulder turn, hip rotation, swing plane angle, head movement, weight shift
- **Comparison view:** ghost overlay shot ของวันนี้ vs baseline (best shot ก่อนหน้า)
- **AI commentary:** ใช้ LLM (Claude API) สรุปข้อสังเกต เช่น "Backswing สั้นกว่าปกติ 15%, ลำตัวเปิดเร็ว"
- **Trend dashboard:** tempo trend ตามเวลา, consistency score

### Implementation
- Reuse pose data ของทุก shot ที่ track ไว้แล้ว
- New service `SwingAnalyzer` คำนวณ metric per shot, persist ใน `swing_metrics` collection
- New `comparisons` UI หน้า ghost-overlay
- Claude API integration สำหรับ commentary (with prompt caching)

### Architecture impact
- เพิ่ม `SwingAnalyzer` worker stage
- เพิ่ม `swing_metrics` collection + `analysis_runs` collection
- Dashboard UI ใหม่

## 11. Cost Estimate

| Phase | Compute | Per video (15 min) |
|---|---|---|
| 1 — MVP | CPU only | ~$0.01-0.03 |
| 2 — Tracer | CPU (+ optional GPU) | ~$0.03-0.10 |
| 3 — Swing Analysis | CPU + LLM API | ~$0.10-0.20 |

## 12. Deployment

ใช้ pipeline เดียวกันทุก app: **Docker → Azure Container Registry → ArgoCD → AKS**

```
apps/web/Dockerfile       → ACR: golf-shot-cutter/web:<sha>
apps/api/Dockerfile       → ACR: golf-shot-cutter/api:<sha>
apps/worker/Dockerfile    → ACR: golf-shot-cutter/worker:<sha>
```

- **CI** (GitHub Actions): nx affected → build → push image แต่ละ service ที่เปลี่ยน
- **CD**: GitOps repo ถือ Helm/Kustomize manifests → ArgoCD sync ไปยัง AKS namespace
- AKS pods:
  - `web` deployment (3 replicas, autoscale CPU)
  - `api` deployment (3 replicas) + Service + Ingress
  - `worker` deployment (เริ่ม 1 replica, KEDA scaler ตาม Redis queue depth)
- Secrets ผ่าน AKS-integrated Azure Key Vault: `MONGODB_URI`, `REDIS_URL`, `R2_ACCESS_KEY`, `R2_SECRET_KEY`, `JWT_SECRET`, `R2_ENDPOINT`

## 13. Nx + Python Conventions

### TS side — Nx tags (`nx.json` projects.tags)
- `type:app`, `type:lib`
- `scope:web`, `scope:contracts`, `scope:shared`, `scope:ui`

Nx `enforce-module-boundaries` rule (Biome custom):
```
web (app)       → tag scope:contracts | shared | ui
contracts       → no deps
shared, ui      → no app deps
```

### Python side — `import-linter` contracts (`.importlinter` ที่ root)
```ini
[importlinter:contract:layered]
type = layers
layers =
    apps.api | apps.worker
    libs.infrastructure
    libs.application
    libs.domain
```
Run ใน CI: `lint-imports` — fail ถ้ามี layer ละเมิด

### Generators
- TS: `nx g @nx/next:app web`
- Python: ใช้ template script `scripts/scaffold-py-pkg.sh <name>` (ตั้ง pyproject ตาม convention) — หรือ `@nxlv/python` ถ้าอยากให้ Nx จัด

### Build orchestration
- Nx: TS pipeline (lint, build web, generate contracts TS)
- uv: Python pipeline (`uv sync`, `uv run pytest`, `uv build`)
- Top-level npm scripts ผูกทั้งคู่:
  ```json
  "scripts": {
    "verify": "nx run-many -t lint,build,test && uv run pytest",
    "dev:web": "nx serve web",
    "dev:api": "uv run --package golf-api fastapi dev",
    "dev:worker": "uv run --package golf-worker celery -A golf_worker.main worker"
  }
  ```

## 14. Open Questions (สำหรับ implementation plan)

- Mongo client: **Motor (async) + manual mappers** vs **Beanie ODM** vs **Pymongo + sync workers** — ตัดสินตอน plan
- Python package manager: confirm **uv** (recommend) vs Poetry
- Nx Python integration: ใช้ **@nxlv/python** plugin หรือ Nx project.json + custom executors เรียก uv ตรงๆ
- Auth: ต้อง multi-user ตั้งแต่ v1 หรือ single-user ก่อน?
- R2 jurisdiction: APAC vs default global
- MongoDB host: Atlas M0 (free) vs self-host บน AKS
- ขนาดไฟล์สูงสุด: 1 GB? 2 GB?
- Retention: raw กี่วัน, clip กี่วัน
- Locale default: `th` แล้ว fallback `en` — confirm

---

**Next step:** หลัง user review spec นี้แล้ว → invoke `superpowers:writing-plans` skill เพื่อสร้าง implementation plan สำหรับ Phase 1 (MVP)
