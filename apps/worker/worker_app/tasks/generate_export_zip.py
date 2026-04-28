import asyncio
import os
import tempfile
import urllib.request
import zipfile

from celery import shared_task

from app.repository.queue.celery_app import GENERATE_EXPORT_ZIP_TASK
from worker_app.container import WorkerContainer


@shared_task(name=GENERATE_EXPORT_ZIP_TASK)
def generate_export_zip(payload: dict) -> None:
    asyncio.run(_run(payload))


async def _run(payload: dict) -> None:
    container = WorkerContainer()
    shots_repo = container.shots_repo()
    storage = container.storage_repo()

    session_id = payload["sessionId"]
    export_id = payload["exportId"]
    out_key = f"exports/{session_id}/{export_id}.zip"

    try:
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
    finally:
        try:
            container.mongo_client().close()
        except Exception:
            pass
        try:
            await container.redis().aclose()
        except Exception:
            pass
