"""Worker DI container — subset of the API Container."""

from dependency_injector import containers, providers
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
