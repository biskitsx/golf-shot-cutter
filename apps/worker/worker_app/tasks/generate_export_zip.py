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

        signed_put = await storage.signed_put_url(out_key, content_type="application/zip")
        with open(zip_path, "rb") as f:
            req = urllib.request.Request(
                signed_put.url,
                data=f.read(),
                method="PUT",
                headers={"Content-Type": "application/zip"},
            )
            urllib.request.urlopen(req)
