"""Render an on-demand pose-overlay preview clip for a single shot.

Triggered by the API when the user clicks "Show pose" on a shot card. Reads
the existing source clip from object storage, runs MediaPipe pose detection
on every frame, draws the skeleton, and uploads a new H.264 MP4 alongside
the original (under `clips-pose/{session_id}/...`).
"""

from __future__ import annotations

import asyncio
import os
import tempfile
import urllib.request

from celery import shared_task

from app.infrastructure.queue.celery_app import GENERATE_POSE_CLIP_TASK
from app.infrastructure.storage.r2_storage import R2Storage
from worker_app.container import WorkerContainer
from worker_app.pipeline.pose_overlay import render_pose_overlay


@shared_task(name=GENERATE_POSE_CLIP_TASK)
def generate_pose_clip(payload: dict) -> dict:
    """Synchronous entrypoint. Returns `{"key": <output_key>}` on success."""
    return asyncio.run(_run(payload))


async def _run(payload: dict) -> dict:
    source_key: str = payload["sourceKey"]
    output_key: str = payload["outputKey"]

    container = WorkerContainer()
    storage = container.storage_repo()
    try:
        with tempfile.TemporaryDirectory() as workdir:
            src_path = os.path.join(workdir, "src.mp4")
            out_path = os.path.join(workdir, "out.mp4")

            await _download(storage, source_key, src_path)
            render_pose_overlay(src_path, out_path)
            await _upload(storage, out_path, output_key)
        return {"key": output_key}
    finally:
        try:
            container.mongo_client().close()
        except Exception:
            pass
        try:
            await container.redis().aclose()
        except Exception:
            pass


async def _download(storage: R2Storage, key: str, out_path: str) -> None:
    signed = await storage.signed_get_url(key)
    urllib.request.urlretrieve(signed.url, out_path)


async def _upload(storage: R2Storage, local_path: str, key: str) -> None:
    signed = await storage.signed_put_url(key, content_type="video/mp4")
    with open(local_path, "rb") as f:
        req = urllib.request.Request(
            signed.url,
            data=f.read(),
            method="PUT",
            headers={"Content-Type": "video/mp4"},
        )
        urllib.request.urlopen(req)
