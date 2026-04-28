# Plan 4 — Worker Pipeline (Audio Detection MVP)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development.

**Goal:** Build `apps/worker` — a Celery consumer that picks up `process_video` jobs enqueued by `apps/api`, runs an audio-onset → clip-cut pipeline on the uploaded raw video, and feeds the resulting candidates back through `ProcessingService.process(...)`. After this plan, an end-to-end smoke test (upload → process → review → export) works against a real video file.

**Scope:** Audio-only onset detection (Phase 1). Pose verification stays a stub (`always True`); real MediaPipe verification lands in Plan 4.5. Tracer + swing analysis are Phase 2/3 (separate plans).

**Architecture:** `apps/worker` mirrors `apps/api`'s `app/` layout. It shares `app.core.models`, `app.repository.*`, and `app.services.processing_service` by depending on the `golf-api` workspace package — no code duplication. New code lives under `apps/worker/app/{pipeline, tasks, container}`.

```
apps/worker/
  pyproject.toml                # uv member golf-worker; deps include golf-api + librosa + ffmpeg-python + mediapipe + opencv-python-headless
  Dockerfile
  app/
    __init__.py
    main.py                     # Celery() instance bootstrap + autodiscover tasks
    container.py                # WorkerContainer (subset of API Container — repos, clock, ids, publisher; no JWT)
    pipeline/
      __init__.py
      audio_onset.py            # AudioOnsetDetector (librosa)
      pose_verifier.py          # PoseVerifier (stub for now)
      clip_cutter.py            # ClipCutter (ffmpeg stream copy)
      types.py                  # Onset, ClipResult dataclasses
      pipeline.py               # Pipeline orchestrator
    tasks/
      __init__.py
      process_video.py          # Celery task → calls Pipeline + ProcessingService
      generate_export_zip.py    # Celery task → builds ZIP, uploads to R2
  tests/
    __init__.py
    conftest.py
    pipeline/
      test_audio_onset.py
      test_pose_verifier.py
      test_clip_cutter.py
      test_pipeline.py          # orchestrator with mocked stages
    tasks/
      test_process_video.py
      test_generate_export_zip.py
    fixtures/
      sample_audio.wav          # ~3s tone with 2 distinct impacts (synthetic)
      sample_video.mp4          # ~5s test video
```

**Tech additions:** `librosa>=0.10`, `numpy>=1.24,<2.0`, `ffmpeg-python>=0.2`, `mediapipe>=0.10` (stubbed but kept as dep for Plan 4.5), `opencv-python-headless>=4.10`.

**Pre-state:** HEAD `e149c45` on `main`, tag `v0.3.0-refactor`. 98 pytest passing + 1 skipped. Layout is Tevadin-style Service+Repository.

---

## Task 1: Scaffold `apps/worker` package

**Files:**
- Create: `apps/worker/pyproject.toml`
- Create: `apps/worker/app/__init__.py`
- Create: `apps/worker/app/main.py` (minimal placeholder)
- Modify: root `pyproject.toml` to re-add `apps/worker` workspace member

- [ ] **Step 1: Create `apps/worker/pyproject.toml`**

```toml
[project]
name = "golf-worker"
version = "0.0.0"
requires-python = ">=3.11"
dependencies = [
    "golf-api",
    "celery>=5.4",
    "redis>=5.1",
    "ffmpeg-python>=0.2",
    "librosa>=0.10",
    "numpy>=1.24,<2.0",
    "soundfile>=0.12",
    "opencv-python-headless>=4.10",
    "mediapipe>=0.10",
]

[tool.uv.sources]
golf-api = { workspace = true }

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["app"]
```

NOTE: both `apps/api` and `apps/worker` declare `packages = ["app"]`. That means BOTH packages provide a top-level Python module named `app`. uv will install BOTH editable to the venv — second one wins on import path. To avoid this conflict, change the worker package paths.

**Resolution:** rename worker's package to `worker_app`:

In `apps/worker/pyproject.toml`:
```toml
[tool.hatch.build.targets.wheel]
packages = ["worker_app"]
```

And rename the directory: `apps/worker/worker_app/` instead of `apps/worker/app/`.

Update the file structure in the plan to use `worker_app/` consistently. The shared imports from `app.*` (golf-api's package) keep working — `worker_app` is a separate top-level module.

So actual folders:
- `apps/worker/worker_app/__init__.py`
- `apps/worker/worker_app/main.py`
- `apps/worker/worker_app/container.py`
- `apps/worker/worker_app/pipeline/...`
- `apps/worker/worker_app/tasks/...`

- [ ] **Step 2: Update root `pyproject.toml`**

Add `apps/worker` to workspace:
```toml
[tool.uv.workspace]
members = ["apps/api", "apps/worker"]
```

- [ ] **Step 3: Create `apps/worker/worker_app/__init__.py`**

```python
"""Celery worker for golf-shot-cutter — consumes process_video + export ZIP jobs."""
```

- [ ] **Step 4: Create placeholder `apps/worker/worker_app/main.py`**

```python
"""Celery worker entry point. Container + tasks are wired in later tasks."""

from celery import Celery


# Placeholder — Task 3 replaces this with a real factory + autodiscover.
celery_app = Celery("golf_worker", broker="redis://localhost:6379/0")
```

- [ ] **Step 5: Sync workspace**

Run: `uv sync --all-packages`
Expected: `golf-worker==0.0.0` registered. New deps installed (librosa, numpy<2, opencv-python-headless, mediapipe, ffmpeg-python, soundfile).

NOTE: librosa pulls a lot. If install fails, check Python 3.14 compatibility (some ML libs lag). Falling back to Python 3.11 may be needed; document if so.

- [ ] **Step 6: Verify import**

Run: `uv run python -c "import worker_app; from worker_app.main import celery_app; print(celery_app.main)"`
Expected: `golf_worker`.

- [ ] **Step 7: Commit**

```bash
git add apps/worker pyproject.toml uv.lock
git commit -m "chore(worker): scaffold golf-worker package + ML deps"
```

---

## Task 2: Worker DI container

**Files:**
- Create: `apps/worker/worker_app/container.py`

The worker container is a SUBSET of the API container — drops auth (no JWT), drops storage_service-like wrappers, keeps repos + clock + ids + publisher + a Celery app instance.

- [ ] **Step 1: Implement `worker_app/container.py`**

```python
"""Worker DI container — subset of the API Container."""

from celery import Celery
from dependency_injector import containers, providers
from motor.motor_asyncio import AsyncIOMotorClient
from redis.asyncio import Redis

from app.core.config import Settings
from app.repository.clock import SystemClock
from app.repository.id_generator import UlidIdGenerator
from app.repository.mongo.client import get_database, make_client
from app.repository.mongo.session_repository import MongoSessionRepository
from app.repository.mongo.shot_repository import MongoShotRepository
from app.repository.queue.celery_app import make_celery_app
from app.repository.queue.event_publisher_repository import (
    RedisEventPublisherRepository,
)
from app.repository.r2.storage_repository import R2StorageRepository
from app.services.processing_service import ProcessingService


class WorkerContainer(containers.DeclarativeContainer):
    wiring_config = containers.WiringConfiguration(
        modules=[
            "worker_app.tasks.process_video",
            "worker_app.tasks.generate_export_zip",
        ]
    )

    settings = providers.Singleton(Settings)

    mongo_client = providers.Singleton(make_client, uri=settings.provided.mongodb_uri)
    mongo_database = providers.Singleton(
        get_database,
        client=mongo_client,
        name=settings.provided.mongodb_database,
    )
    redis = providers.Singleton(
        lambda url: Redis.from_url(url, decode_responses=True),
        url=settings.provided.redis_url,
    )
    celery_app = providers.Singleton(
        make_celery_app,
        broker_url=settings.provided.redis_url,
        result_backend=settings.provided.redis_url,
    )

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
    publisher_repo = providers.Singleton(RedisEventPublisherRepository, client=redis)

    clock = providers.Singleton(SystemClock)
    ids = providers.Singleton(UlidIdGenerator)

    processing_service = providers.Factory(
        ProcessingService,
        sessions_repo=sessions_repo,
        shots_repo=shots_repo,
        events=publisher_repo,
        clock=clock,
        ids=ids,
    )
```

- [ ] **Step 2: Verify import**

Run: `uv run python -c "from worker_app.container import WorkerContainer; print(WorkerContainer.__name__)"`
Expected: `WorkerContainer`.

- [ ] **Step 3: Commit**

```bash
git add apps/worker
git commit -m "feat(worker): WorkerContainer (subset of API Container)"
```

---

## Task 3: Celery app + main.py bootstrap

**Files:**
- Modify: `apps/worker/worker_app/main.py` (replace placeholder)
- Create: `apps/worker/worker_app/tasks/__init__.py` (empty)

- [ ] **Step 1: Update `worker_app/main.py`**

```python
"""Celery worker bootstrap. Container is wired before tasks are discovered."""

from worker_app.container import WorkerContainer


def make_celery():
    container = WorkerContainer()
    container.wire()
    celery = container.celery_app()
    celery.autodiscover_tasks(["worker_app.tasks"], related_name=None, force=True)
    # Stash container on the celery app so tasks can grab it via Provide.
    celery.conf.update(worker_container=container)
    return celery


celery_app = make_celery()
```

- [ ] **Step 2: Create `worker_app/tasks/__init__.py`** (empty)

- [ ] **Step 3: Commit**

```bash
git add apps/worker
git commit -m "feat(worker): bootstrap celery_app via WorkerContainer"
```

---

## Task 4: Pipeline types + interfaces (TDD scaffolding)

**Files:**
- Create: `apps/worker/worker_app/pipeline/__init__.py` (empty)
- Create: `apps/worker/worker_app/pipeline/types.py`
- Create: `apps/worker/worker_app/pipeline/audio_onset.py` — `AudioOnsetDetector` interface only
- Create: `apps/worker/worker_app/pipeline/pose_verifier.py` — `PoseVerifier` interface only
- Create: `apps/worker/worker_app/pipeline/clip_cutter.py` — `ClipCutter` interface only
- Create: `apps/worker/worker_app/pipeline/pipeline.py` — orchestrator
- Create: `apps/worker/tests/__init__.py`
- Create: `apps/worker/tests/conftest.py`
- Create: `apps/worker/tests/pipeline/test_pipeline.py`

- [ ] **Step 1: Implement `pipeline/types.py`**

```python
from pydantic import BaseModel, Field


class Onset(BaseModel):
    """A candidate impact moment detected from audio (or other signals)."""
    t: float = Field(ge=0.0)
    confidence: float = Field(ge=0.0, le=1.0)


class ClipResult(BaseModel):
    """Output of cutting a single clip from the source video."""
    t_start: float = Field(ge=0.0)
    t_end: float
    clip_path: str  # local path on the worker filesystem
    clip_key: str   # R2 object key (final destination)
```

- [ ] **Step 2: Implement `pipeline/audio_onset.py` interface**

```python
from typing import Protocol

from .types import Onset


class AudioOnsetDetector(Protocol):
    def detect(self, audio_path: str) -> list[Onset]: ...
```

(Concrete librosa implementation comes in Task 6.)

- [ ] **Step 3: Implement `pipeline/pose_verifier.py` interface**

```python
from typing import Protocol


class PoseVerifier(Protocol):
    def verify(self, video_path: str, t_impact: float) -> bool: ...
```

(Stub implementation lands in Task 7; real MediaPipe in Plan 4.5.)

- [ ] **Step 4: Implement `pipeline/clip_cutter.py` interface**

```python
from typing import Protocol


class ClipCutter(Protocol):
    def cut(
        self, *, source_path: str, t_start: float, t_end: float, out_path: str
    ) -> None: ...
```

(Concrete ffmpeg implementation comes in Task 8.)

- [ ] **Step 5: Failing test FIRST: `apps/worker/tests/pipeline/test_pipeline.py`**

```python
import pytest
from pydantic import BaseModel

from app.services.processing_service import ShotCandidate
from worker_app.pipeline.pipeline import Pipeline
from worker_app.pipeline.types import ClipResult, Onset


class FakeAudioDetector:
    def __init__(self, onsets: list[Onset]) -> None:
        self._onsets = onsets

    def detect(self, audio_path: str) -> list[Onset]:
        return self._onsets


class FakePoseVerifier:
    def __init__(self, accept_all: bool = True) -> None:
        self._accept = accept_all

    def verify(self, video_path: str, t_impact: float) -> bool:
        return self._accept


class FakeClipCutter:
    def __init__(self) -> None:
        self.calls: list[tuple[float, float, str]] = []

    def cut(self, *, source_path: str, t_start: float, t_end: float, out_path: str) -> None:
        self.calls.append((t_start, t_end, out_path))


def test_pipeline_runs_end_to_end_with_two_onsets():
    audio = FakeAudioDetector([
        Onset(t=10.0, confidence=0.9),
        Onset(t=30.0, confidence=0.85),
    ])
    pose = FakePoseVerifier(accept_all=True)
    cutter = FakeClipCutter()

    pipeline = Pipeline(
        audio_onset=audio,
        pose_verifier=pose,
        clip_cutter=cutter,
    )

    candidates = pipeline.run(
        session_id="ses_1",
        source_video_path="/tmp/v.mp4",
        clips_dir="/tmp/clips",
        pre_roll_seconds=2.0,
        post_roll_seconds=5.0,
    )

    # 2 onsets accepted → 2 candidates
    assert len(candidates) == 2
    assert all(isinstance(c, ShotCandidate) for c in candidates)
    assert candidates[0].t_impact == 10.0
    assert candidates[1].t_impact == 30.0

    # ClipCutter called twice with correct windows
    assert cutter.calls == [
        (8.0, 15.0, "/tmp/clips/shot_001.mp4"),
        (28.0, 35.0, "/tmp/clips/shot_002.mp4"),
    ]

    # ShotCandidate clip_key is the R2 destination, derived from session_id + index
    assert candidates[0].clip_key == "clips/ses_1/shot_001.mp4"
    assert candidates[1].clip_key == "clips/ses_1/shot_002.mp4"


def test_pipeline_filters_pose_rejected_onsets():
    audio = FakeAudioDetector([
        Onset(t=10.0, confidence=0.9),
        Onset(t=30.0, confidence=0.85),
    ])

    class _PartialPose:
        def verify(self, video_path: str, t_impact: float) -> bool:
            return t_impact < 20.0  # only first onset accepted

    cutter = FakeClipCutter()
    pipeline = Pipeline(
        audio_onset=audio,
        pose_verifier=_PartialPose(),
        clip_cutter=cutter,
    )
    candidates = pipeline.run(
        session_id="ses_1",
        source_video_path="/tmp/v.mp4",
        clips_dir="/tmp/clips",
        pre_roll_seconds=2.0,
        post_roll_seconds=5.0,
    )
    assert len(candidates) == 1
    assert candidates[0].t_impact == 10.0


def test_pipeline_clamps_t_start_to_zero():
    audio = FakeAudioDetector([Onset(t=1.0, confidence=0.9)])  # t_impact - pre_roll = -1.0
    pipeline = Pipeline(
        audio_onset=audio,
        pose_verifier=FakePoseVerifier(),
        clip_cutter=FakeClipCutter(),
    )
    candidates = pipeline.run(
        session_id="ses_x",
        source_video_path="/tmp/v.mp4",
        clips_dir="/tmp/clips",
        pre_roll_seconds=2.0,
        post_roll_seconds=5.0,
    )
    # t_start is clamped to 0 by max(); but Shot invariant requires t_start < t_impact.
    # 0.0 < 1.0 < 6.0 → valid.
    assert candidates[0].t_impact == 1.0


def test_pipeline_returns_empty_when_no_onsets():
    audio = FakeAudioDetector([])
    pipeline = Pipeline(
        audio_onset=audio,
        pose_verifier=FakePoseVerifier(),
        clip_cutter=FakeClipCutter(),
    )
    candidates = pipeline.run(
        session_id="ses_1",
        source_video_path="/tmp/v.mp4",
        clips_dir="/tmp/clips",
        pre_roll_seconds=2.0,
        post_roll_seconds=5.0,
    )
    assert candidates == []
```

- [ ] **Step 6: Run failing test**

Run: `uv run pytest apps/worker/tests/pipeline/test_pipeline.py -v`
Expected: FAIL — `worker_app.pipeline.pipeline` not importable.

- [ ] **Step 7: Implement `pipeline/pipeline.py`**

```python
import os

from app.services.processing_service import ShotCandidate

from .audio_onset import AudioOnsetDetector
from .clip_cutter import ClipCutter
from .pose_verifier import PoseVerifier
from .types import Onset


class Pipeline:
    def __init__(
        self,
        *,
        audio_onset: AudioOnsetDetector,
        pose_verifier: PoseVerifier,
        clip_cutter: ClipCutter,
    ) -> None:
        self._audio = audio_onset
        self._pose = pose_verifier
        self._cutter = clip_cutter

    def run(
        self,
        *,
        session_id: str,
        source_video_path: str,
        clips_dir: str,
        pre_roll_seconds: float,
        post_roll_seconds: float,
    ) -> list[ShotCandidate]:
        os.makedirs(clips_dir, exist_ok=True)
        onsets = self._audio.detect(source_video_path)
        verified: list[Onset] = [
            o for o in onsets if self._pose.verify(source_video_path, o.t)
        ]

        candidates: list[ShotCandidate] = []
        for index, onset in enumerate(verified, start=1):
            t_start = max(0.0, onset.t - pre_roll_seconds)
            t_end = onset.t + post_roll_seconds
            clip_filename = f"shot_{index:03d}.mp4"
            clip_path = os.path.join(clips_dir, clip_filename)
            clip_key = f"clips/{session_id}/{clip_filename}"

            self._cutter.cut(
                source_path=source_video_path,
                t_start=t_start,
                t_end=t_end,
                out_path=clip_path,
            )
            candidates.append(
                ShotCandidate(
                    t_impact=onset.t,
                    confidence=onset.confidence,
                    clip_key=clip_key,
                )
            )
        return candidates
```

- [ ] **Step 8: Implement empty `apps/worker/tests/__init__.py` and `apps/worker/tests/conftest.py`** (`conftest.py` empty for now; tasks 6-9 add fixtures.)

- [ ] **Step 9: Run passing test**

Run: `uv run pytest apps/worker/tests/pipeline/test_pipeline.py -v`
Expected: PASS — 4/4.

- [ ] **Step 10: Update root `pyproject.toml` testpaths**

`[tool.pytest.ini_options]`:
```toml
asyncio_mode = "auto"
testpaths = ["apps/api/tests", "apps/worker/tests"]
pythonpath = ["apps/api/tests"]
```

(Worker tests don't need pythonpath — `worker_app` is importable via the workspace install.)

- [ ] **Step 11: Run full test suite**

Run: `uv run pytest 2>&1 | tail -3`
Expected: 102 passed + 1 skipped (98 prior + 4 new pipeline tests).

- [ ] **Step 12: Commit**

```bash
git add apps/worker pyproject.toml
git commit -m "feat(worker): Pipeline orchestrator + Protocol-based stage interfaces"
```

---

## Task 5: Stage stubs (TDD-friendly)

**Files:**
- Create: `apps/worker/worker_app/pipeline/audio_onset_stub.py`
- Create: `apps/worker/worker_app/pipeline/pose_verifier_stub.py`
- Create: `apps/worker/worker_app/pipeline/clip_cutter_stub.py`

These provide deterministic, no-IO implementations for tests + local dev.

- [ ] **Step 1: `audio_onset_stub.py`**

```python
from .types import Onset


class StubAudioOnsetDetector:
    """Always returns a fixed onset list — for unit tests + local-dev smoke."""

    def __init__(self, fixed_onsets: list[Onset] | None = None) -> None:
        self._onsets = fixed_onsets if fixed_onsets is not None else []

    def detect(self, audio_path: str) -> list[Onset]:
        return list(self._onsets)
```

- [ ] **Step 2: `pose_verifier_stub.py`**

```python
class StubPoseVerifier:
    """Always-True pose verifier. Plan 4.5 replaces with real MediaPipe impl."""

    def verify(self, video_path: str, t_impact: float) -> bool:
        return True
```

- [ ] **Step 3: `clip_cutter_stub.py`**

```python
import pathlib


class StubClipCutter:
    """Touches a zero-byte file at out_path — tests can verify the call shape."""

    def cut(
        self, *, source_path: str, t_start: float, t_end: float, out_path: str
    ) -> None:
        pathlib.Path(out_path).touch()
```

- [ ] **Step 4: Commit**

```bash
git add apps/worker
git commit -m "feat(worker): pipeline stage stubs for tests + local dev"
```

---

## Task 6: Real `LibrosaAudioOnsetDetector` (TDD with synthetic WAV fixture)

**Files:**
- Create: `apps/worker/worker_app/pipeline/audio_onset_librosa.py`
- Create: `apps/worker/tests/pipeline/test_audio_onset_librosa.py`
- Create: `apps/worker/tests/fixtures/__init__.py`
- Create: `apps/worker/tests/fixtures/make_audio.py` — generates synthetic WAV on-the-fly

The test fixture synthesizes a WAV with two distinct "impact" transients — short bursts of broadband noise — so the real librosa onset detector can find them. No checked-in audio files needed.

- [ ] **Step 1: `tests/fixtures/make_audio.py`**

```python
import numpy as np
import soundfile as sf


def synth_two_impacts(out_path: str, sr: int = 22050, duration_s: float = 5.0) -> None:
    """Write a WAV with two impact-like bursts at t=1.0s and t=3.0s."""
    n = int(sr * duration_s)
    sig = np.zeros(n, dtype=np.float32)

    # Add two brief broadband-noise bursts (3-8 ms attack + 50ms decay)
    rng = np.random.default_rng(seed=42)
    for t_burst in (1.0, 3.0):
        start = int(t_burst * sr)
        burst_len = int(0.05 * sr)
        envelope = np.exp(-np.linspace(0, 5, burst_len)).astype(np.float32)
        burst = rng.standard_normal(burst_len).astype(np.float32) * envelope
        sig[start:start + burst_len] += burst

    # Add low background noise
    sig += rng.standard_normal(n).astype(np.float32) * 0.005

    sf.write(out_path, sig, sr)
```

- [ ] **Step 2: Failing test FIRST: `tests/pipeline/test_audio_onset_librosa.py`**

```python
import os
import tempfile

import pytest

from worker_app.pipeline.audio_onset_librosa import LibrosaAudioOnsetDetector
from tests.fixtures.make_audio import synth_two_impacts


@pytest.fixture
def synth_wav():
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "synth.wav")
        synth_two_impacts(path)
        yield path


def test_detects_both_impacts(synth_wav):
    detector = LibrosaAudioOnsetDetector(min_separation_seconds=0.5)
    onsets = detector.detect(synth_wav)
    times = [o.t for o in onsets]

    # Should find both impacts within ~100ms of ground truth.
    found_first = any(abs(t - 1.0) < 0.2 for t in times)
    found_second = any(abs(t - 3.0) < 0.2 for t in times)
    assert found_first, f"missed first impact (~1.0s); got {times}"
    assert found_second, f"missed second impact (~3.0s); got {times}"


def test_min_separation_dedupes_close_events(synth_wav):
    detector = LibrosaAudioOnsetDetector(min_separation_seconds=0.05)
    onsets = detector.detect(synth_wav)
    # No two onsets should be within 0.05s of each other after dedup.
    times = sorted(o.t for o in onsets)
    for a, b in zip(times, times[1:]):
        assert b - a >= 0.05
```

NOTE on test pythonpath: the test does `from tests.fixtures.make_audio import synth_two_impacts`. For this to resolve, `apps/worker/tests` should be importable. Update root `[tool.pytest.ini_options].pythonpath` to include `apps/worker/tests`:
```toml
pythonpath = ["apps/api/tests", "apps/worker/tests"]
```

- [ ] **Step 3: Run failing test**

Run: `uv run pytest apps/worker/tests/pipeline/test_audio_onset_librosa.py -v`
Expected: FAIL — module not found.

- [ ] **Step 4: Implement `pipeline/audio_onset_librosa.py`**

```python
import numpy as np
import librosa

from .types import Onset


class LibrosaAudioOnsetDetector:
    """Onset detection via librosa.onset.onset_detect with a min-separation filter.

    Designed for golf-impact transients — sharp broadband attacks ~3-8ms.
    """

    def __init__(
        self,
        *,
        sr: int = 22050,
        hop_length: int = 512,
        min_separation_seconds: float = 0.5,
        delta: float = 0.07,
    ) -> None:
        self._sr = sr
        self._hop_length = hop_length
        self._min_separation = min_separation_seconds
        self._delta = delta

    def detect(self, audio_path: str) -> list[Onset]:
        y, sr = librosa.load(audio_path, sr=self._sr, mono=True)
        onset_frames = librosa.onset.onset_detect(
            y=y,
            sr=sr,
            hop_length=self._hop_length,
            backtrack=False,
            delta=self._delta,
            units="frames",
        )
        onset_times = librosa.frames_to_time(
            onset_frames, sr=sr, hop_length=self._hop_length
        )
        if onset_times.size == 0:
            return []

        # Compute strength for confidence ranking.
        env = librosa.onset.onset_strength(y=y, sr=sr, hop_length=self._hop_length)
        max_env = float(np.max(env)) if env.size > 0 else 1.0

        onsets: list[Onset] = []
        last_t = -float("inf")
        for t in onset_times:
            if t - last_t < self._min_separation:
                continue
            frame = int(t * sr / self._hop_length)
            strength = float(env[frame]) if frame < env.size else 0.0
            confidence = min(1.0, max(0.0, strength / (max_env or 1.0)))
            onsets.append(Onset(t=float(t), confidence=confidence))
            last_t = float(t)

        return onsets
```

- [ ] **Step 5: Run passing test**

Run: `uv run pytest apps/worker/tests/pipeline/test_audio_onset_librosa.py -v`
Expected: PASS — both tests.

If detection misses one of the synthetic impacts, tune `delta` or `min_separation_seconds`. The test allows ±200ms tolerance from the ground-truth t.

- [ ] **Step 6: Commit**

```bash
git add apps/worker pyproject.toml
git commit -m "feat(worker): LibrosaAudioOnsetDetector with synthetic-WAV test"
```

---

## Task 7: Real `FfmpegClipCutter` (TDD with sample video)

**Files:**
- Create: `apps/worker/worker_app/pipeline/clip_cutter_ffmpeg.py`
- Create: `apps/worker/tests/pipeline/test_clip_cutter_ffmpeg.py`
- Create: `apps/worker/tests/fixtures/make_video.py` — generates a small test video on-the-fly

- [ ] **Step 1: `tests/fixtures/make_video.py`**

```python
import subprocess


def synth_test_video(out_path: str, duration_s: int = 5) -> None:
    """Generate a small mp4 with a color-changing test pattern + silent audio.

    Uses ffmpeg's testsrc + anullsrc filters; no external assets needed.
    """
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", f"testsrc=duration={duration_s}:size=320x240:rate=30",
        "-f", "lavfi", "-i", f"anullsrc=channel_layout=stereo:sample_rate=22050",
        "-shortest",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-t", str(duration_s),
        out_path,
    ]
    subprocess.run(cmd, check=True, capture_output=True)
```

The test that uses this requires `ffmpeg` on PATH. If unavailable in CI, the test should `pytest.skip` with a clear reason.

- [ ] **Step 2: Failing test FIRST: `tests/pipeline/test_clip_cutter_ffmpeg.py`**

```python
import os
import shutil
import subprocess
import tempfile

import pytest

from worker_app.pipeline.clip_cutter_ffmpeg import FfmpegClipCutter
from tests.fixtures.make_video import synth_test_video


@pytest.fixture
def has_ffmpeg() -> bool:
    return shutil.which("ffmpeg") is not None


@pytest.fixture
def sample_video(has_ffmpeg) -> str:
    if not has_ffmpeg:
        pytest.skip("ffmpeg not on PATH")
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "v.mp4")
        synth_test_video(path, duration_s=5)
        yield path


def test_cut_produces_clip_of_expected_length(sample_video: str):
    out_dir = os.path.dirname(sample_video)
    out_path = os.path.join(out_dir, "clip.mp4")
    cutter = FfmpegClipCutter()
    cutter.cut(source_path=sample_video, t_start=1.0, t_end=4.0, out_path=out_path)

    assert os.path.exists(out_path) and os.path.getsize(out_path) > 0

    probe = subprocess.run(
        [
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", out_path,
        ],
        check=True, capture_output=True, text=True,
    )
    duration = float(probe.stdout.strip())
    assert 2.5 < duration < 3.5  # ~3s expected, allow margin
```

- [ ] **Step 3: Run failing test**

Expected: FAIL — module missing (assuming ffmpeg available).

- [ ] **Step 4: Implement `pipeline/clip_cutter_ffmpeg.py`**

```python
import subprocess


class FfmpegClipCutter:
    """Stream-copy clip cutter via ffmpeg subprocess.

    Uses `-ss -to -c copy` for fast cuts without re-encoding. Quality stays
    identical to source; cuts may snap to nearest keyframe.
    """

    def cut(
        self, *, source_path: str, t_start: float, t_end: float, out_path: str
    ) -> None:
        if t_end <= t_start:
            raise ValueError("t_end must be greater than t_start")
        subprocess.run(
            [
                "ffmpeg", "-y",
                "-ss", str(t_start),
                "-to", str(t_end),
                "-i", source_path,
                "-c", "copy",
                "-avoid_negative_ts", "make_zero",
                out_path,
            ],
            check=True,
            capture_output=True,
        )
```

- [ ] **Step 5: Run passing test**

Expected: PASS (or SKIP with reason if ffmpeg unavailable).

- [ ] **Step 6: Commit**

```bash
git add apps/worker
git commit -m "feat(worker): FfmpegClipCutter (stream-copy via subprocess)"
```

---

## Task 8: Pose verifier — keep stub, defer real impl

The plan defers the MediaPipe pose verifier to Plan 4.5. For Phase 1 MVP, ship the StubPoseVerifier (always True) as the production binding. UI lets users delete false positives.

- [ ] **Step 1: Add a brief test confirming stub behavior**

Write `apps/worker/tests/pipeline/test_pose_verifier_stub.py`:
```python
from worker_app.pipeline.pose_verifier_stub import StubPoseVerifier


def test_stub_always_returns_true():
    v = StubPoseVerifier()
    assert v.verify("/tmp/x.mp4", 1.0) is True
    assert v.verify("/tmp/x.mp4", 100.0) is True
```

- [ ] **Step 2: Run + commit**

```bash
uv run pytest apps/worker/tests/pipeline/test_pose_verifier_stub.py -v
git add apps/worker
git commit -m "test(worker): smoke test for StubPoseVerifier"
```

---

## Task 9: `process_video` Celery task

**Files:**
- Create: `apps/worker/worker_app/tasks/process_video.py`
- Create: `apps/worker/tests/tasks/__init__.py`
- Create: `apps/worker/tests/tasks/test_process_video.py`

The task downloads the raw video from R2, extracts audio to a temp WAV, runs Pipeline, then calls ProcessingService.process(). Failure → SessionFailed event + status = FAILED.

- [ ] **Step 1: Implement `tasks/process_video.py`**

```python
import asyncio
import os
import subprocess
import tempfile

from celery import shared_task
from dependency_injector.wiring import Provide, inject

from app.core.models.events import SessionFailed
from app.repository.queue.celery_app import PROCESS_VIDEO_TASK
from app.repository.r2.storage_repository import R2StorageRepository
from app.services.processing_service import (
    ProcessingService,
    ProcessVideoInput,
)
from worker_app.container import WorkerContainer
from worker_app.pipeline.audio_onset_librosa import LibrosaAudioOnsetDetector
from worker_app.pipeline.clip_cutter_ffmpeg import FfmpegClipCutter
from worker_app.pipeline.pipeline import Pipeline
from worker_app.pipeline.pose_verifier_stub import StubPoseVerifier


@shared_task(name=PROCESS_VIDEO_TASK)
def process_video(payload: dict) -> None:
    """Sync wrapper that runs the async pipeline driver."""
    asyncio.run(_run(payload))


@inject
async def _run(
    payload: dict,
    storage: R2StorageRepository = Provide[WorkerContainer.storage_repo],
    publisher = Provide[WorkerContainer.publisher_repo],
    sessions_repo = Provide[WorkerContainer.sessions_repo],
    processing: ProcessingService = Provide[WorkerContainer.processing_service],
    clock = Provide[WorkerContainer.clock],
) -> None:
    session_id = payload["sessionId"]

    try:
        session = await sessions_repo.get(session_id)
    except Exception as e:
        # Can't even fetch the session — bubble up so Celery retries.
        raise

    with tempfile.TemporaryDirectory() as workdir:
        try:
            # 1. Download raw video from R2 to local temp.
            raw_path = os.path.join(workdir, "raw.mp4")
            await _download_object(storage, session.raw_video_key, raw_path)

            # 2. Extract audio track.
            audio_path = os.path.join(workdir, "audio.wav")
            _extract_audio(raw_path, audio_path)

            # 3. Run pipeline.
            pipeline = Pipeline(
                audio_onset=LibrosaAudioOnsetDetector(),
                pose_verifier=StubPoseVerifier(),
                clip_cutter=FfmpegClipCutter(),
            )

            # AudioOnsetDetector needs the audio file, not the video.
            # Patch for now: pipeline takes source_video_path; we pass audio_path
            # to detector indirectly. Cleanest fix: have Pipeline accept separate
            # audio + video paths. (See Task 9 Step 2 for the shim.)
            clips_dir = os.path.join(workdir, "clips")
            candidates = pipeline.run(
                session_id=session_id,
                source_video_path=raw_path,
                clips_dir=clips_dir,
                pre_roll_seconds=session.pre_roll_seconds,
                post_roll_seconds=session.post_roll_seconds,
            )

            # 4. Upload clips to R2.
            for c in candidates:
                local = os.path.join(clips_dir, os.path.basename(c.clip_key))
                await _upload_object(storage, local, c.clip_key)

            # 5. Persist + publish via ProcessingService.
            await processing.process(
                ProcessVideoInput(session_id=session_id, candidates=candidates)
            )

        except Exception as exc:
            now = clock.now()
            failed = session.mark_failed(stage="pipeline", message=str(exc))
            await sessions_repo.update(failed)
            await publisher.publish(
                SessionFailed(
                    session_id=session_id,
                    stage="pipeline",
                    message=str(exc),
                    occurred_at=now,
                )
            )
            raise


async def _download_object(storage: R2StorageRepository, key: str, out_path: str) -> None:
    """Stream-download via signed GET URL → local file. Synchronous request."""
    import urllib.request
    signed = await storage.signed_get_url(key)
    urllib.request.urlretrieve(signed.url, out_path)


async def _upload_object(storage: R2StorageRepository, local_path: str, key: str) -> None:
    """Upload via signed PUT URL."""
    import urllib.request
    signed = await storage.signed_put_url(key, content_type="video/mp4")
    with open(local_path, "rb") as f:
        req = urllib.request.Request(
            signed.url, data=f.read(), method="PUT",
            headers={"Content-Type": "video/mp4"},
        )
        urllib.request.urlopen(req)


def _extract_audio(video_path: str, audio_out_path: str) -> None:
    subprocess.run(
        [
            "ffmpeg", "-y", "-i", video_path,
            "-vn", "-ac", "1", "-ar", "22050",
            audio_out_path,
        ],
        check=True, capture_output=True,
    )
```

NOTE on `Pipeline.run` audio source: as written, the Pipeline calls `AudioOnsetDetector.detect(source_video_path)` — but librosa can decode mp4's audio track directly via its underlying audio backend (audioread). However, that's flaky on some setups. For robustness, extract the audio first (as `_extract_audio` does in the task) and update Pipeline to optionally accept an `audio_path` separate from video. **Task 9 Step 2 below adds that.**

- [ ] **Step 2: Update `pipeline/pipeline.py` to accept optional `audio_path`**

Add to `Pipeline.run` signature:
```python
def run(
    self,
    *,
    session_id: str,
    source_video_path: str,
    clips_dir: str,
    pre_roll_seconds: float,
    post_roll_seconds: float,
    audio_path: str | None = None,
) -> list[ShotCandidate]:
    os.makedirs(clips_dir, exist_ok=True)
    audio_source = audio_path or source_video_path
    onsets = self._audio.detect(audio_source)
    # ...rest unchanged
```

Update the existing pipeline tests to verify the new signature works without breaking (default param means existing tests pass with no changes).

Update `tasks/process_video.py` to pass `audio_path=audio_path` to `pipeline.run(...)`.

- [ ] **Step 3: Failing test FIRST: `tests/tasks/test_process_video.py`**

```python
import asyncio
from datetime import UTC, datetime

import pytest

from app.core.models import Session, SessionStatus
from worker_app.container import WorkerContainer
from worker_app.tasks.process_video import _run


def _processing_session() -> Session:
    now = datetime(2026, 4, 28, tzinfo=UTC)
    return Session(
        id="ses_w1",
        user_id=None,
        raw_video_key="raw/ses_w1/v.mp4",
        status=SessionStatus.PROCESSING,
        pre_roll_seconds=2.0,
        post_roll_seconds=5.0,
        shot_count=0,
        duration_seconds=5.0,
        error=None,
        created_at=now,
        updated_at=now,
    )


@pytest.mark.skip(reason="end-to-end task test requires ffmpeg + R2 mock + asyncio container override; covered manually in Plan 4 smoke")
async def test_process_video_runs_full_pipeline_against_fakes():
    """Placeholder — full integration test deferred to manual smoke + Plan 5."""
    pass


def test_process_video_celery_task_is_registered():
    """Confirm the task is registered with Celery under the expected name."""
    from app.repository.queue.celery_app import PROCESS_VIDEO_TASK
    from worker_app.main import celery_app

    assert PROCESS_VIDEO_TASK in celery_app.tasks
```

The integration test is non-trivial because:
- the worker container must be wired with overrides (in-memory repos, fake storage)
- the dependency_injector + asyncio mix is finicky in test contexts
- ffmpeg + librosa run real subprocesses

For Plan 4, settle for the registration smoke test + manual end-to-end verification (Step 4 below).

- [ ] **Step 4: Manual smoke test** (NOT automated)

In a docker-compose dev stack with mongo + redis + minio:
1. `docker compose -f docker-compose.dev.yml up -d`
2. `cp .env.example .env` and edit minio/redis/mongo URLs.
3. Start API: `uv run --package golf-api uvicorn app.main:app --port 8000`
4. Start worker: `uv run --package golf-worker celery -A worker_app.main:celery_app worker --loglevel=INFO --queues video,export`
5. Use curl/Postman: login → POST /sessions → upload video to signed PUT URL → POST /sessions/{id}/process.
6. Watch worker logs; expect `process_video` invoked, candidates returned, session reaches READY.
7. GET /sessions/{id}; verify shots present.

Document the smoke procedure in a follow-up `MANUAL_E2E.md` (optional).

- [ ] **Step 5: Run unit tests**

Run: `uv run pytest apps/worker/tests -v`
Expected: PASS (the registration test passes; the integration test is skipped).

- [ ] **Step 6: Commit**

```bash
git add apps/worker
git commit -m "feat(worker): process_video Celery task + Pipeline audio_path option"
```

---

## Task 10: `generate_export_zip` Celery task

**Files:**
- Create: `apps/worker/worker_app/tasks/generate_export_zip.py`
- Create: `apps/worker/tests/tasks/test_generate_export_zip.py`

When a user clicks "export" in the UI, the API enqueues this task. The worker downloads each clip, zips them, uploads to `exports/{sessionId}/{exportId}.zip`. (Note: `ExportService` in apps/api currently returns a signed URL pointing at where the worker will eventually upload. The download succeeds only after the worker completes the upload.)

For Plan 4, the API ExportService change isn't required — the task just produces the zip at the deterministic location.

- [ ] **Step 1: Implement `tasks/generate_export_zip.py`**

```python
import asyncio
import os
import tempfile
import urllib.request
import zipfile

from celery import shared_task
from dependency_injector.wiring import Provide, inject

from app.repository.mongo.shot_repository import MongoShotRepository
from app.repository.queue.celery_app import GENERATE_EXPORT_ZIP_TASK
from app.repository.r2.storage_repository import R2StorageRepository
from worker_app.container import WorkerContainer


@shared_task(name=GENERATE_EXPORT_ZIP_TASK)
def generate_export_zip(payload: dict) -> None:
    asyncio.run(_run(payload))


@inject
async def _run(
    payload: dict,
    shots_repo: MongoShotRepository = Provide[WorkerContainer.shots_repo],
    storage: R2StorageRepository = Provide[WorkerContainer.storage_repo],
) -> None:
    session_id = payload["sessionId"]
    export_id = payload["exportId"]
    out_key = f"exports/{session_id}/{export_id}.zip"

    shots = await shots_repo.list_by_session(session_id)

    with tempfile.TemporaryDirectory() as workdir:
        zip_path = os.path.join(workdir, "out.zip")
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_STORED) as zf:
            for s in shots:
                if not s.clip_key:
                    continue
                local = os.path.join(workdir, os.path.basename(s.clip_key))
                signed = await storage.signed_get_url(s.clip_key)
                urllib.request.urlretrieve(signed.url, local)
                zf.write(local, arcname=os.path.basename(s.clip_key))

        # Upload zip to R2.
        signed_put = await storage.signed_put_url(out_key, content_type="application/zip")
        with open(zip_path, "rb") as f:
            req = urllib.request.Request(
                signed_put.url, data=f.read(), method="PUT",
                headers={"Content-Type": "application/zip"},
            )
            urllib.request.urlopen(req)
```

- [ ] **Step 2: Failing test: `tests/tasks/test_generate_export_zip.py`**

```python
def test_export_zip_task_is_registered():
    from app.repository.queue.celery_app import GENERATE_EXPORT_ZIP_TASK
    from worker_app.main import celery_app

    assert GENERATE_EXPORT_ZIP_TASK in celery_app.tasks
```

- [ ] **Step 3: Run + commit**

```bash
uv run pytest apps/worker/tests/tasks -v
git add apps/worker
git commit -m "feat(worker): generate_export_zip Celery task"
```

---

## Task 11: Worker Dockerfile

**Files:**
- Create: `apps/worker/Dockerfile`
- Create: `apps/worker/.dockerignore`

- [ ] **Step 1: Create `apps/worker/Dockerfile`**

```dockerfile
# syntax=docker/dockerfile:1.7

FROM python:3.11-slim AS base
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
RUN apt-get update -y && apt-get install -y --no-install-recommends \
    curl ca-certificates ffmpeg libsndfile1 libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:$PATH"

WORKDIR /app

COPY pyproject.toml uv.lock ./
COPY apps/api/pyproject.toml apps/api/pyproject.toml
COPY apps/worker/pyproject.toml apps/worker/pyproject.toml

RUN uv sync --frozen --no-dev --all-packages || uv sync --no-dev --all-packages

COPY apps/api ./apps/api
COPY apps/worker ./apps/worker

CMD ["uv", "run", "--package", "golf-worker", "celery", "-A", "worker_app.main:celery_app", "worker", "--loglevel=INFO", "--queues", "video,export"]
```

- [ ] **Step 2: Create `apps/worker/.dockerignore`**

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

- [ ] **Step 3: Commit**

```bash
git add apps/worker/Dockerfile apps/worker/.dockerignore
git commit -m "chore(worker): minimal Dockerfile + .dockerignore"
```

---

## Task 12: Final verification + tag

- [ ] **Step 1: Full test suite**

Run: `uv run pytest 2>&1 | tail -3`
Expected: ~107 passed + 2 skipped (98 prior + ~7 worker tests; one new skip in process_video integration test).

- [ ] **Step 2: Linters**

Run: `uv run ruff check . && pnpm exec biome check . && uv tool run pre-commit run --all-files`
Expected: all green.

- [ ] **Step 3: TypeScript tests**

Run: `pnpm nx run-many -t test`
Expected: contracts vitest 3/3.

- [ ] **Step 4: Tag + commit**

```bash
git tag v0.4.0-worker
git log --oneline | head -15
```

---

## Done criteria

- `apps/worker` exists as a uv member with Pipeline + 3 stages (librosa audio onset, stub pose verifier, ffmpeg clip cutter).
- `process_video` Celery task wires Pipeline + ProcessingService and is registered.
- `generate_export_zip` Celery task is registered.
- Worker Dockerfile + .dockerignore.
- Tests cover Pipeline orchestration (4) + audio onset (2) + ffmpeg cutter (1) + stub verifier (1) + task registration (2) = ~10 tests.
- Tag `v0.4.0-worker` set.

## Carry-overs

- **Real MediaPipe pose verification** → Plan 4.5.
- **End-to-end automated integration test** → Plan 4.5 or Plan 5 (frontend) e2e suite.
- **Idempotent download/upload retries** → Plan 5 (production hardening).
- **Worker autoscaling (KEDA)** → Plan 5.
- IDOR/ownership checks (carry-over from Plan 2 review).
