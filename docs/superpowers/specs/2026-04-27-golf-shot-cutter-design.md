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

```
┌─────────────────────────────────────────────────────────┐
│                   User (Browser)                         │
│         Next.js Frontend  (upload, review, download)     │
└─────────────────┬───────────────────────────────────────┘
                  │ HTTPS
                  ▼
┌─────────────────────────────────────────────────────────┐
│               API Gateway / Backend                      │
│         FastAPI (Python) — REST + signed URLs            │
└─────┬─────────────────────────────────┬─────────────────┘
      │                                 │
      ▼                                 ▼
┌─────────────────┐         ┌──────────────────────────┐
│  Object Store   │         │  Job Queue (Redis)       │
│  S3 / R2 / GCS  │         │  Celery workers          │
└─────────────────┘         └────────────┬─────────────┘
                                         │
                                         ▼
                          ┌──────────────────────────┐
                          │  Worker (CPU)            │
                          │  1. AudioOnsetDetector   │  ← librosa
                          │  2. PoseVerifier         │  ← MediaPipe
                          │  3. ClipCutter           │  ← FFmpeg
                          │  4. ResultPublisher      │
                          └──────────────────────────┘
                                         │
                                         ▼
                          ┌──────────────────────────┐
                          │  Postgres                │
                          │  sessions, shots         │
                          └──────────────────────────┘
```

### Tech Stack
- **Frontend:** Next.js + TypeScript + Tailwind
- **Backend:** FastAPI (Python 3.11+)
- **Workers:** Celery + Redis broker
- **Storage:** Object store (S3/R2/GCS) + Postgres + Redis
- **Video processing:** FFmpeg, librosa, MediaPipe, OpenCV

### Data Flow
1. User เปิดเว็บ → ขอ signed upload URL → upload ตรงเข้า object store (ไม่ผ่าน server)
2. Server enqueue job → Worker ดึงไฟล์มาประมวลผล
3. Worker ทำ 4 stage: audio onset → pose verify → ffmpeg cut → publish
4. Frontend poll/SSE → แสดง timeline ให้ user review/แก้ → export ZIP

## 5. Components

### 5.1 Frontend (Next.js)
- **Upload page** — drag/drop, ขอ signed URL, progress bar
- **Session list** — รายการ session พร้อม status (poll)
- **Review timeline** — video player + timeline พร้อม shot markers, drag handles ปรับ in/out, sidebar list
- **Export** — ZIP download ผ่าน signed URL

### 5.2 API (FastAPI)
- `POST /sessions` — สร้าง session, return signed upload URL + sessionId
- `POST /sessions/{id}/process` — enqueue job หลัง upload เสร็จ
- `GET /sessions/{id}` — สถานะ + รายการ shot
- `PATCH /sessions/{id}/shots/{shotId}` — แก้ in/out point
- `POST /sessions/{id}/shots` — เพิ่ม shot ด้วยมือ
- `DELETE /sessions/{id}/shots/{shotId}` — ลบ shot
- `POST /sessions/{id}/export` — generate ZIP, return signed download URL

### 5.3 Worker Pipeline
แต่ละ stage เป็น pure function (input → output) ไม่แตะ I/O โดยตรง → test แยกได้, swap ได้

- **AudioOnsetDetector**
  - Input: video file path
  - Process: ffmpeg extract WAV → bandpass 2-8 kHz → librosa.onset.onset_detect → amplitude threshold + transient sharpness (rise time < 5ms)
  - Output: `[timestamp_seconds, ...]` candidate impact times
- **PoseVerifier**
  - Input: video + candidate timestamps
  - Process: extract frames `[t-1.0s, t+0.3s]` ทุก 3 frames → MediaPipe Pose → compute wrist angular velocity, shoulder rotation, hip-shoulder separation → classify swing vs not
  - Output: `[(timestamp, confidence), ...]` confirmed
- **ClipCutter**
  - Input: video + confirmed timestamps + pre/post-roll
  - Process: คำนวณ in/out, merge overlapping windows, ffmpeg `-ss -to -c copy` (stream copy, ไม่ encode ใหม่)
  - Output: ไฟล์คลิปย่อย shot_001.mp4, ...
- **ResultPublisher**
  - Input: clip files + metadata
  - Process: upload ขึ้น object store, insert metadata Postgres, notify API
  - Output: session status = "ready"

### 5.4 Data Model (Postgres)
```
sessions
  id (uuid pk)
  user_id (fk, nullable for v1)
  raw_video_url (text)
  status (enum: uploading, queued, processing, ready, failed)
  pre_roll_seconds (float, default 2.0)
  post_roll_seconds (float, default 5.0)
  created_at, updated_at

shots
  id (uuid pk)
  session_id (fk)
  t_impact (float)         -- seconds
  t_start (float)          -- seconds (after pre-roll, user-editable)
  t_end (float)            -- seconds (after post-roll, user-editable)
  confidence (float)       -- 0..1
  source (enum: auto, manual)
  clip_url (text, nullable)
  created_at, updated_at
```

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

### Unit tests (per pipeline stage)
- AudioOnsetDetector: feed WAV ที่มี/ไม่มี impact → ตรวจ output timestamps
- PoseVerifier: feed frames ของ swing/non-swing → ตรวจ classification
- ClipCutter: feed video + timestamps → ตรวจ output file duration & playable

### Integration tests
- Test fixture: 2-3 short videos จริง (ตัวเองตี + เสียงรบกวน)
- Run full pipeline → assert จำนวน shot, range, file integrity

### Manual / E2E
- Upload จริง บน staging → ดู timeline → ปรับ → export → ตรวจ ZIP

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
- เพิ่ม `tracer_clip_url` ใน `shots` table (rendered version)
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
- New service `SwingAnalyzer` คำนวณ metric per shot, persist ใน `swing_metrics` table
- New `comparisons` UI หน้า ghost-overlay
- Claude API integration สำหรับ commentary (with prompt caching)

### Architecture impact
- เพิ่ม `SwingAnalyzer` worker stage
- เพิ่ม `swing_metrics` table + `analysis_runs` table
- Dashboard UI ใหม่

## 11. Cost Estimate

| Phase | Compute | Per video (15 min) |
|---|---|---|
| 1 — MVP | CPU only | ~$0.01-0.03 |
| 2 — Tracer | CPU (+ optional GPU) | ~$0.03-0.10 |
| 3 — Swing Analysis | CPU + LLM API | ~$0.10-0.20 |

## 12. Open Questions (สำหรับ implementation plan)

- Hosting target: self-host (DigitalOcean/Hetzner) หรือ managed (Vercel + Railway/Fly)?
- Auth: ต้อง multi-user ตั้งแต่ v1 หรือ single-user ก่อน?
- Storage region: ใช้ที่ใกล้ผู้ใช้ (เอเชียตะวันออก/ใต้) เพื่อลด upload latency
- ขนาดไฟล์สูงสุดที่รับ: 1 GB? 2 GB?
- Retention: เก็บ raw video กี่วัน? คลิปย่อยเก็บกี่วัน?

---

**Next step:** หลัง user review spec นี้แล้ว → invoke `superpowers:writing-plans` skill เพื่อสร้าง implementation plan สำหรับ Phase 1 (MVP)
