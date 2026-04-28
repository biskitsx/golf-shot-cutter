import asyncio
import os
import subprocess
import tempfile
import urllib.request

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
    publisher=Provide[WorkerContainer.publisher_repo],
    sessions_repo=Provide[WorkerContainer.sessions_repo],
    processing: ProcessingService = Provide[WorkerContainer.processing_service],
    clock=Provide[WorkerContainer.clock],
) -> None:
    session_id = payload["sessionId"]

    session = await sessions_repo.get(session_id)

    with tempfile.TemporaryDirectory() as workdir:
        try:
            raw_path = os.path.join(workdir, "raw.mp4")
            await _download_object(storage, session.raw_video_key, raw_path)

            audio_path = os.path.join(workdir, "audio.wav")
            _extract_audio(raw_path, audio_path)

            clips_dir = os.path.join(workdir, "clips")
            pipeline = Pipeline(
                audio_onset=LibrosaAudioOnsetDetector(),
                pose_verifier=StubPoseVerifier(),
                clip_cutter=FfmpegClipCutter(),
            )
            candidates = pipeline.run(
                session_id=session_id,
                source_video_path=raw_path,
                clips_dir=clips_dir,
                pre_roll_seconds=session.pre_roll_seconds,
                post_roll_seconds=session.post_roll_seconds,
                audio_path=audio_path,
            )

            for c in candidates:
                local = os.path.join(clips_dir, os.path.basename(c.clip_key))
                await _upload_object(storage, local, c.clip_key)

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
    signed = await storage.signed_get_url(key)
    urllib.request.urlretrieve(signed.url, out_path)


async def _upload_object(storage: R2StorageRepository, local_path: str, key: str) -> None:
    signed = await storage.signed_put_url(key, content_type="video/mp4")
    with open(local_path, "rb") as f:
        req = urllib.request.Request(
            signed.url,
            data=f.read(),
            method="PUT",
            headers={"Content-Type": "video/mp4"},
        )
        urllib.request.urlopen(req)


def _extract_audio(video_path: str, audio_out_path: str) -> None:
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-i",
            video_path,
            "-vn",
            "-ac",
            "1",
            "-ar",
            "22050",
            audio_out_path,
        ],
        check=True,
        capture_output=True,
    )
