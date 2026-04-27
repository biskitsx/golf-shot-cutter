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
│  apps/api (NestJS)                                            │
│  Controllers → Use Cases → Domain                             │
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
                              │  consumes queue jobs   │
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

NestJS เป็น **single source of business logic**. Next.js เรียกผ่าน REST/SSE เท่านั้น
Python worker เป็น specialized service สำหรับ heavy CV/audio work — เชื่อมกับ NestJS ผ่าน Redis queue + เขียน MongoDB ผ่าน infrastructure layer ร่วมกับ NestJS

### 4.2 Clean Architecture Layers

แต่ละ layer พึ่งพาเฉพาะ layer "ใน" (inward dependency rule):

```
┌────────────────── apps (Frameworks & Drivers) ──────────────────┐
│  apps/web · Next.js                  apps/api · NestJS          │
│  (presentation only)                 (controllers, gateways)    │
│                                      apps/worker · Python       │
└─────────────────────────────┬───────────────────────────────────┘
                              ▼
┌──────────────── libs/infrastructure (Adapters) ─────────────────┐
│  MongoRepositories · R2StorageAdapter · RedisQueueAdapter       │
│  JwtAuthAdapter · ConfigService · Logger                        │
└─────────────────────────────┬───────────────────────────────────┘
                              ▼
┌──────────────── libs/application (Use Cases) ───────────────────┐
│  CreateSessionUseCase · ProcessVideoUseCase                     │
│  ListShotsUseCase · UpdateShotBoundaryUseCase                   │
│  AddManualShotUseCase · ExportZipUseCase                        │
│  + Repository interfaces (ports)                                │
└─────────────────────────────┬───────────────────────────────────┘
                              ▼
┌──────────────── libs/domain (Entities & Rules) ─────────────────┐
│  Session · Shot · TimeRange · Confidence                        │
│  Domain events: ShotDetected, SessionReady                      │
│  Pure TypeScript — no framework imports                         │
└─────────────────────────────────────────────────────────────────┘
```

### 4.3 Nx Monorepo Layout

```
golf-shot-cutter/                # repo root
  pnpm-workspace.yaml
  nx.json
  package.json
  tsconfig.base.json

  apps/
    web/                         # Next.js 16 — presentation only
    api/                         # NestJS — controllers, gateways, DI wiring
    worker/                      # Python (NOT Nx-managed; sibling app)
                                 # uses apps/api's REST/queue contract via libs/contracts

  libs/
    domain/                      # entities, value objects, domain events (pure TS)
    application/                 # use cases + repository interfaces (depends on domain)
    infrastructure/              # repos, R2, Mongo, Redis (depends on application + domain)
    contracts/                   # generated DTOs/zod schemas shared between web + api + worker
    shared/                      # cross-cutting helpers (Result type, Either, Logger interface)
    ui/                          # shadcn components extracted ถ้าเริ่ม share
```

**Dependency rules (enforced via Nx tags):**
- `domain` → no deps
- `application` → `domain` only
- `infrastructure` → `application` + `domain`
- `apps/api` → `infrastructure` + `application` + `domain` + `contracts`
- `apps/web` → `contracts` + `ui` + `shared` (ห้าม import `domain` / `application` / `infrastructure` ตรงๆ — talk via REST)

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
- NestJS + TypeScript strict
- Mongoose / Prisma Mongo (ตัดสินใจตอน plan)
- Bull/BullMQ (Redis queue producer)
- @nestjs/jwt + cookie-parser

**Worker (`apps/worker`)**
- Python 3.11+
- BullMQ-compatible client (`bullmq` Python port) หรือใช้ Redis pub/sub format ที่ฝั่ง NestJS define
- Celery ทดแทนได้แต่จะมี broker schema ของตัวเอง — ถ้า NestJS produce ด้วย BullMQ ให้ Python ใช้ schema เดียวกัน
- librosa, MediaPipe, OpenCV, FFmpeg

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

### 5.2 `apps/api` — NestJS Backend (Clean Architecture host)

#### Module layout
```
apps/api/src/
  main.ts                         # bootstrap + cookie-parser + SSE
  app.module.ts                   # imports feature modules
  modules/
    sessions/
      sessions.controller.ts      # REST handlers
      sessions.module.ts          # binds use cases ↔ controllers
    shots/
    upload/
    export/
    realtime/                     # SSE endpoint
    auth/                         # JWT guard, cookie strategy
  composition/
    container.ts                  # wires libs/application use cases with libs/infrastructure adapters
  filters/, interceptors/, guards/
```

#### REST endpoints
- `POST /sessions` — create session, return `{ sessionId, signedUploadUrl }`
- `POST /sessions/:id/process` — enqueue processing job
- `GET /sessions` — list sessions (current user)
- `GET /sessions/:id` — session + shots
- `PATCH /sessions/:id/shots/:shotId` — update in/out (calls `UpdateShotBoundaryUseCase`)
- `POST /sessions/:id/shots` — manual add (`AddManualShotUseCase`)
- `DELETE /sessions/:id/shots/:shotId`
- `POST /sessions/:id/export` — enqueue zip job, return `{ exportId }`
- `GET /sessions/:id/export/:exportId` — signed download URL when ready
- `GET /sessions/:id/events` (SSE) — push processing progress + ready events

Controllers ทำหน้าที่ map HTTP ↔ Use Case input/output เท่านั้น **ห้ามมี business logic ใน controller**

### 5.3 `libs/domain`

Pure TypeScript entities, ไม่มี framework import:
```
Session(id, userId?, rawVideoKey, status, preRoll, postRoll, ...)
Shot(id, sessionId, index, tImpact, tStart, tEnd, confidence, source, clipKey?)
TimeRange(start, end)
Confidence(value: 0..1)

Domain events:
  SessionCreated, SessionProcessingStarted, ShotDetected,
  SessionReady, SessionFailed, ShotBoundaryUpdated, ShotDeleted
```

Domain rules ที่ enforce ใน entity:
- `Shot.adjustBoundary(tStart, tEnd)` — validate `tStart < tImpact < tEnd`, max duration
- `Session.allowEdit()` — only when status = "ready"
- Pre/post-roll validation

### 5.4 `libs/application` — Use Cases + Ports

```
use-cases/
  CreateSessionUseCase
  RequestSignedUploadUrlUseCase
  StartProcessingUseCase           # enqueue worker job
  ProcessVideoUseCase              # called from worker side (orchestrates pipeline result)
  ListSessionsUseCase
  GetSessionWithShotsUseCase
  UpdateShotBoundaryUseCase
  AddManualShotUseCase
  DeleteShotUseCase
  ExportSessionZipUseCase

ports/                              # interfaces — implementations live in infrastructure
  SessionRepository
  ShotRepository
  StorageGateway                   # signedPutUrl, signedGetUrl, deleteObject
  JobQueue                         # enqueue, consume
  EventPublisher                   # publish domain events (→ SSE bridge)
  Clock, IdGenerator               # for testability
```

แต่ละ use case รับ port ผ่าน DI (ไม่ import infrastructure ตรง). Test ได้ด้วย in-memory implementations

### 5.5 `libs/infrastructure` — Adapters

```
mongo/
  MongoSessionRepository (implements SessionRepository)
  MongoShotRepository
  schemas/ (mongoose / zod)
r2/
  R2StorageGateway (implements StorageGateway)  # AWS SDK v3 with R2 endpoint
queue/
  BullMqJobQueue (implements JobQueue)          # producer side
  BullMqEventPublisher
auth/
  JwtAuthService                                # cookie-based JWT
config/
  ConfigService                                 # env validation (zod)
logging/
  PinoLogger
```

### 5.6 `libs/contracts` — Wire-format DTOs

- Zod schemas (single source) → generate TS types สำหรับ web + api
- Generate JSON schemas สำหรับ Python worker (เพื่อ validate event payloads)
- Sync script `scripts/sync-contracts.mjs` (รัน in CI)

ตัวอย่าง: `SessionDto`, `ShotDto`, `CreateSessionRequest`, `UpdateShotBoundaryRequest`, `SseEventEnvelope`

### 5.7 `apps/worker` — Python Pipeline

Worker เป็น sibling app (ไม่ใช่ Nx project) ใช้ contract ที่ export จาก `libs/contracts`

```
apps/worker/
  pyproject.toml
  src/
    main.py                       # BullMQ consumer entry
    pipeline/
      audio_onset.py              # AudioOnsetDetector
      pose_verifier.py            # PoseVerifier (MediaPipe)
      clip_cutter.py              # ClipCutter (FFmpeg stream copy)
      result_publisher.py         # writes Mongo + emits SessionReady
    adapters/
      mongo_repo.py               # mirrors MongoShotRepository writes
      r2_client.py
      queue_consumer.py
    domain/                       # mirror of TS domain (minimal — Pydantic models from contracts)
  Dockerfile                      # python:3.11-slim + ffmpeg
```

Worker pipeline (เหมือนเดิม):

- **AudioOnsetDetector** — ffmpeg → WAV → bandpass 2-8 kHz → librosa.onset → amplitude + transient sharpness < 5ms
- **PoseVerifier** — MediaPipe pose ทุก 3 frames ใน window `[t-1.0s, t+0.3s]` → wrist angular velocity + shoulder rotation + hip-shoulder separation
- **ClipCutter** — ffmpeg `-ss -to -c copy` stream copy
- **ResultPublisher** — upload R2 + write Mongo + emit `SessionReady` event ผ่าน Redis pub/sub (NestJS realtime module subscribe + push SSE)

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
| Worker crash | BullMQ retry policy: 3 attempts, exponential backoff |
| 0 shots detected | UI แนะนำ + เปิด manual mode |

## 8. Testing Strategy

> **No-new-tests rule** สำหรับ `apps/web`: ตามข้อกำหนดของ user — Vitest/RTL/Playwright suites ที่มีอยู่ยัง verify ผ่าน `pnpm verify` ได้ แต่ไม่เพิ่ม test ใหม่ในฝั่ง frontend
>
> สำหรับ `libs/domain`, `libs/application`, `libs/infrastructure`, `apps/api`, `apps/worker` — ใส่ test ตามปกติ เพราะเป็น greenfield และเป็นที่อยู่ของ business logic

### `libs/domain` (Vitest, fast)
- Entity invariants — `Shot.adjustBoundary` reject case เลย impact, ลบ shot duration ติดลบ ฯลฯ

### `libs/application` (Vitest, in-memory adapters)
- Each use case test ด้วย in-memory `SessionRepository` / `ShotRepository` / `JobQueue`
- เน้น coverage ของ branching logic — ไม่ต้อง mock framework

### `libs/infrastructure` (integration)
- Mongo adapters: ใช้ `mongodb-memory-server`
- R2 adapter: ใช้ MinIO local container เป็น S3-compatible substitute
- Queue adapter: real Redis container ใน CI

### `apps/api` (e2e ใน NestJS)
- Supertest หา controller-level — happy path ของแต่ละ endpoint

### `apps/worker` (Python, pytest)
- AudioOnsetDetector: feed WAV ที่มี/ไม่มี impact → ตรวจ output timestamps
- PoseVerifier: feed frames ของ swing/non-swing → ตรวจ classification
- ClipCutter: feed video + timestamps → ตรวจ output file duration & playable

### End-to-end (manual, no automation in v1)
- Upload จริงบน staging → review timeline → ปรับ → export → ตรวจ ZIP

### `pnpm verify`
- รันที่ root: `nx run-many -t lint,build,test` + Python `pytest` ผ่าน script
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

## 13. Nx Conventions

### Tags (`nx.json` projects.tags)
- `type:app`, `type:lib`
- `scope:domain`, `scope:application`, `scope:infrastructure`, `scope:contracts`, `scope:web`, `scope:api`, `scope:shared`

### `enforce-module-boundaries` rule (eslint/biome custom)
```
domain          → no deps
application     → tag scope:domain only
infrastructure  → tag scope:application or scope:domain
api (app)       → tag scope:infrastructure | application | domain | contracts
web (app)       → tag scope:contracts | shared | ui   (NOT domain/application/infrastructure)
```

### Generators
- `nx g @nx/next:app web`
- `nx g @nx/nest:app api`
- `nx g @nx/js:lib domain --tags=type:lib,scope:domain --bundler=none`
- (similar for application / infrastructure / contracts)

## 14. Open Questions (สำหรับ implementation plan)

- Mongo client choice: **Mongoose vs Prisma Mongo** ใน `libs/infrastructure`?
- BullMQ on Python: ใช้ `bullmq` python port หรือเปลี่ยนเป็น raw Redis pub/sub schema (ฝั่ง NestJS publisher ใช้ matching format)?
- Auth: ต้อง multi-user ตั้งแต่ v1 หรือ single-user ก่อน?
- R2 jurisdiction: APAC (เอเชียตะวันออก) เพื่อลด upload latency, หรือ default global
- MongoDB host: Atlas M0 (free) vs self-host บน AKS
- ขนาดไฟล์สูงสุดที่รับ: 1 GB? 2 GB?
- Retention: เก็บ raw video กี่วัน? คลิปย่อยเก็บกี่วัน?
- Locale default: `th` ก่อนแล้ว fallback `en` (ตาม brief) — confirm

---

**Next step:** หลัง user review spec นี้แล้ว → invoke `superpowers:writing-plans` skill เพื่อสร้าง implementation plan สำหรับ Phase 1 (MVP)
