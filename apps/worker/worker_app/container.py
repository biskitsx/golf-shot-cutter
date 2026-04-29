"""Worker DI container — subset of the API Container."""

from dependency_injector import containers, providers
from redis.asyncio import Redis

from app.core.config import Settings
from app.infrastructure.clock import SystemClock
from app.infrastructure.id_generator import UlidIdGenerator
from app.infrastructure.queue.celery_app import make_celery_app
from app.infrastructure.queue.redis_event_publisher import RedisEventPublisher
from app.infrastructure.storage.r2_storage import R2Storage
from app.persistence.mongo.client import get_database, make_client
from app.persistence.mongo.session_repository import MongoSessionRepository
from app.persistence.mongo.shot_repository import MongoShotRepository
from app.services.processing_service import ProcessingService


TASK_MODULES = [
    "worker_app.tasks.process_video",
    "worker_app.tasks.generate_export_zip",
    "worker_app.tasks.generate_pose_clip",
]


class WorkerContainer(containers.DeclarativeContainer):
    # Wiring is performed explicitly in make_celery() (worker_app/main.py) so that
    # the container can be imported in tests without the task modules existing yet.
    wiring_config = containers.WiringConfiguration(modules=[])

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
        R2Storage,
        endpoint=settings.provided.r2_endpoint,
        access_key=settings.provided.r2_access_key,
        secret_key=settings.provided.r2_secret_key,
        bucket=settings.provided.r2_bucket,
        region=settings.provided.r2_region,
        ttl_seconds=settings.provided.signed_url_ttl_seconds,
    )
    publisher_repo = providers.Singleton(RedisEventPublisher, client=redis)

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
