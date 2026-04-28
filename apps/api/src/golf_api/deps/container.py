from dataclasses import dataclass

from celery import Celery
from motor.motor_asyncio import AsyncIOMotorClient
from redis.asyncio import Redis

from golf_application.use_cases.add_manual_shot import AddManualShotUseCase
from golf_application.use_cases.create_session import CreateSessionUseCase
from golf_application.use_cases.delete_shot import DeleteShotUseCase
from golf_application.use_cases.export_session_zip import ExportSessionZipUseCase
from golf_application.use_cases.get_session_with_shots import (
    GetSessionWithShotsUseCase,
)
from golf_application.use_cases.list_sessions import ListSessionsUseCase
from golf_application.use_cases.process_video import ProcessVideoUseCase
from golf_application.use_cases.request_signed_upload_url import (
    RequestSignedUploadUrlUseCase,
)
from golf_application.use_cases.start_processing import StartProcessingUseCase
from golf_application.use_cases.update_shot_boundary import UpdateShotBoundaryUseCase
from golf_infrastructure.auth.jwt_service import JwtService
from golf_infrastructure.clock import SystemClock
from golf_infrastructure.ids import UlidIdGenerator
from golf_infrastructure.mongo.client import get_database, make_client
from golf_infrastructure.mongo.indexes import ensure_indexes
from golf_infrastructure.mongo.session_repository import MongoSessionRepository
from golf_infrastructure.mongo.shot_repository import MongoShotRepository
from golf_infrastructure.queue.celery_app import make_celery_app
from golf_infrastructure.queue.event_publisher import RedisEventPublisher
from golf_infrastructure.queue.job_queue import CeleryJobQueue
from golf_infrastructure.r2.storage_gateway import R2StorageGateway
from golf_infrastructure.settings import Settings


@dataclass
class Container:
    settings: Settings
    mongo_client: AsyncIOMotorClient
    redis: Redis
    celery: Celery
    jwt: JwtService
    sessions_repo: MongoSessionRepository
    shots_repo: MongoShotRepository
    storage: R2StorageGateway
    queue: CeleryJobQueue
    publisher: RedisEventPublisher
    clock: SystemClock
    ids: UlidIdGenerator

    create_session: CreateSessionUseCase
    request_upload_url: RequestSignedUploadUrlUseCase
    start_processing: StartProcessingUseCase
    list_sessions: ListSessionsUseCase
    get_session: GetSessionWithShotsUseCase
    update_shot_boundary: UpdateShotBoundaryUseCase
    add_manual_shot: AddManualShotUseCase
    delete_shot: DeleteShotUseCase
    process_video: ProcessVideoUseCase
    export_session_zip: ExportSessionZipUseCase


async def build_container(settings: Settings) -> Container:
    mongo_client = make_client(settings.mongodb_uri)
    db = get_database(mongo_client, settings.mongodb_database)
    await ensure_indexes(db)

    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    celery = make_celery_app(broker_url=settings.redis_url, result_backend=settings.redis_url)

    jwt = JwtService(
        secret=settings.jwt_secret,
        issuer=settings.jwt_issuer,
        ttl_seconds=settings.jwt_ttl_seconds,
    )

    sessions_repo = MongoSessionRepository(db)
    shots_repo = MongoShotRepository(db)
    storage = R2StorageGateway(
        endpoint=settings.r2_endpoint,
        access_key=settings.r2_access_key,
        secret_key=settings.r2_secret_key,
        bucket=settings.r2_bucket,
        region=settings.r2_region,
        ttl_seconds=settings.signed_url_ttl_seconds,
    )
    queue = CeleryJobQueue(celery)
    publisher = RedisEventPublisher(redis)
    clock = SystemClock()
    ids = UlidIdGenerator()

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
        create_session=CreateSessionUseCase(
            sessions=sessions_repo, storage=storage, clock=clock, ids=ids
        ),
        request_upload_url=RequestSignedUploadUrlUseCase(sessions=sessions_repo, storage=storage),
        start_processing=StartProcessingUseCase(
            sessions=sessions_repo, queue=queue, events=publisher, clock=clock
        ),
        list_sessions=ListSessionsUseCase(sessions=sessions_repo),
        get_session=GetSessionWithShotsUseCase(sessions=sessions_repo, shots=shots_repo),
        update_shot_boundary=UpdateShotBoundaryUseCase(
            sessions=sessions_repo,
            shots=shots_repo,
            events=publisher,
            clock=clock,
        ),
        add_manual_shot=AddManualShotUseCase(
            sessions=sessions_repo,
            shots=shots_repo,
            events=publisher,
            clock=clock,
            ids=ids,
        ),
        delete_shot=DeleteShotUseCase(
            sessions=sessions_repo,
            shots=shots_repo,
            events=publisher,
            clock=clock,
        ),
        process_video=ProcessVideoUseCase(
            sessions=sessions_repo,
            shots=shots_repo,
            events=publisher,
            clock=clock,
            ids=ids,
        ),
        export_session_zip=ExportSessionZipUseCase(
            sessions=sessions_repo, storage=storage, ids=ids
        ),
    )


async def shutdown_container(c: Container) -> None:
    c.mongo_client.close()
    await c.redis.aclose()
