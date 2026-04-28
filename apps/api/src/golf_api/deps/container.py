"""
Thin compatibility shim: Container dataclass built from new app.* services.
Used by existing golf_api routers until they are migrated (Phase 2).
"""

from dataclasses import dataclass
from typing import Any

from redis.asyncio import Redis

from app.repository.auth.jwt_repository import JwtRepository
from app.repository.clock import SystemClock
from app.repository.id_generator import UlidIdGenerator
from app.repository.mongo.client import get_database, make_client
from app.repository.mongo.indexes import ensure_indexes
from app.repository.mongo.session_repository import MongoSessionRepository
from app.repository.mongo.shot_repository import MongoShotRepository
from app.repository.queue.celery_app import make_celery_app
from app.repository.queue.event_publisher_repository import RedisEventPublisherRepository
from app.repository.queue.job_queue_repository import CeleryJobQueueRepository
from app.repository.r2.storage_repository import R2StorageRepository
from app.services.export_service import ExportService
from app.services.processing_service import ProcessingService
from app.services.session_service import (
    SessionService,
)
from app.services.shot_service import (
    ShotService,
)


class _UcProxy:
    """Wraps a service method as use-case-style .execute()"""

    def __init__(self, svc, method: str):
        self._svc = svc
        self._method = method

    async def execute(self, inp):
        return await getattr(self._svc, self._method)(inp)


@dataclass
class Container:
    settings: Any
    mongo_client: Any
    redis: Any
    celery: Any
    jwt: JwtRepository
    sessions_repo: Any
    shots_repo: Any
    storage: Any
    queue: Any
    publisher: Any
    clock: Any
    ids: Any

    create_session: Any
    request_upload_url: Any
    start_processing: Any
    list_sessions: Any
    get_session: Any
    update_shot_boundary: Any
    add_manual_shot: Any
    delete_shot: Any
    process_video: Any
    export_session_zip: Any


async def build_container(settings) -> Container:
    mongo_client = make_client(settings.mongodb_uri)
    db = get_database(mongo_client, settings.mongodb_database)
    await ensure_indexes(db)

    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    celery = make_celery_app(broker_url=settings.redis_url, result_backend=settings.redis_url)

    jwt = JwtRepository(
        secret=settings.jwt_secret,
        issuer=settings.jwt_issuer,
        ttl_seconds=settings.jwt_ttl_seconds,
    )

    sessions_repo = MongoSessionRepository(db)
    shots_repo = MongoShotRepository(db)
    storage = R2StorageRepository(
        endpoint=settings.r2_endpoint,
        access_key=settings.r2_access_key,
        secret_key=settings.r2_secret_key,
        bucket=settings.r2_bucket,
        region=settings.r2_region,
        ttl_seconds=settings.signed_url_ttl_seconds,
    )
    queue = CeleryJobQueueRepository(celery)
    publisher = RedisEventPublisherRepository(redis)
    clock = SystemClock()
    ids = UlidIdGenerator()

    session_svc = SessionService(
        sessions_repo=sessions_repo,
        shots_repo=shots_repo,
        storage=storage,
        queue=queue,
        events=publisher,
        clock=clock,
        ids=ids,
    )
    shot_svc = ShotService(
        sessions_repo=sessions_repo,
        shots_repo=shots_repo,
        events=publisher,
        clock=clock,
        ids=ids,
    )
    processing_svc = ProcessingService(
        sessions_repo=sessions_repo,
        shots_repo=shots_repo,
        events=publisher,
        clock=clock,
        ids=ids,
    )
    export_svc = ExportService(sessions_repo=sessions_repo, storage=storage, ids=ids)

    return Container(
        settings=settings,
        mongo_client=mongo_client,
        redis=redis,
        celery=celery,
        jwt=jwt,
        sessions_repo=sessions_repo,
        shots_repo=shots_repo,
        storage=storage,
        queue=queue,
        publisher=publisher,
        clock=clock,
        ids=ids,
        create_session=_UcProxy(session_svc, "create"),
        request_upload_url=_UcProxy(session_svc, "request_upload_url"),
        start_processing=_UcProxy(session_svc, "start_processing"),
        list_sessions=_UcProxy(session_svc, "list"),
        get_session=_UcProxy(session_svc, "get_with_shots"),
        update_shot_boundary=_UcProxy(shot_svc, "update_boundary"),
        add_manual_shot=_UcProxy(shot_svc, "add_manual"),
        delete_shot=_UcProxy(shot_svc, "delete"),
        process_video=_UcProxy(processing_svc, "process"),
        export_session_zip=_UcProxy(export_svc, "export"),
    )


async def shutdown_container(c: Container) -> None:
    c.mongo_client.close()
    await c.redis.aclose()
