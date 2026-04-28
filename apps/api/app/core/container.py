"""Application DI container using dependency-injector."""

from dependency_injector import containers, providers
from redis.asyncio import Redis

from app.core.config import Settings
from app.infrastructure.auth.jwt_service import JwtService
from app.infrastructure.clock import SystemClock
from app.infrastructure.id_generator import UlidIdGenerator
from app.infrastructure.queue.celery_app import make_celery_app
from app.infrastructure.queue.celery_job_queue import CeleryJobQueue
from app.infrastructure.queue.redis_event_publisher import RedisEventPublisher
from app.infrastructure.storage.r2_storage import R2Storage
from app.persistence.mongo.client import get_database, make_client
from app.persistence.mongo.session_repository import MongoSessionRepository
from app.persistence.mongo.shot_repository import MongoShotRepository
from app.services.export_service import ExportService
from app.services.processing_service import ProcessingService
from app.services.session_service import SessionService
from app.services.shot_service import ShotService


class Container(containers.DeclarativeContainer):
    wiring_config = containers.WiringConfiguration(
        modules=[
            "app.api.v1.endpoints.health",
            "app.api.v1.endpoints.auth",
            "app.api.v1.endpoints.sessions",
            "app.api.v1.endpoints.shots",
            "app.api.v1.endpoints.upload",
            "app.api.v1.endpoints.export",
            "app.api.v1.endpoints.realtime",
            "app.deps.auth",
        ]
    )

    settings = providers.Singleton(Settings)

    # Infrastructure clients
    mongo_client = providers.Singleton(
        make_client,
        uri=settings.provided.mongodb_uri,
    )
    mongo_database = providers.Singleton(
        get_database,
        client=mongo_client,
        name=settings.provided.mongodb_database,
    )
    redis = providers.Singleton(
        lambda url: Redis.from_url(url, decode_responses=True),
        url=settings.provided.redis_url,
    )
    celery = providers.Singleton(
        make_celery_app,
        broker_url=settings.provided.redis_url,
        result_backend=settings.provided.redis_url,
    )

    # Repositories (singletons)
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
    queue_repo = providers.Singleton(CeleryJobQueue, app=celery, eager=False)
    publisher_repo = providers.Singleton(RedisEventPublisher, client=redis)
    jwt_repo = providers.Singleton(
        JwtService,
        secret=settings.provided.jwt_secret,
        issuer=settings.provided.jwt_issuer,
        ttl_seconds=settings.provided.jwt_ttl_seconds,
    )
    clock = providers.Singleton(SystemClock)
    ids = providers.Singleton(UlidIdGenerator)

    # Services (factories)
    session_service = providers.Factory(
        SessionService,
        sessions_repo=sessions_repo,
        shots_repo=shots_repo,
        storage=storage_repo,
        queue=queue_repo,
        events=publisher_repo,
        clock=clock,
        ids=ids,
    )
    shot_service = providers.Factory(
        ShotService,
        sessions_repo=sessions_repo,
        shots_repo=shots_repo,
        events=publisher_repo,
        clock=clock,
        ids=ids,
    )
    processing_service = providers.Factory(
        ProcessingService,
        sessions_repo=sessions_repo,
        shots_repo=shots_repo,
        events=publisher_repo,
        clock=clock,
        ids=ids,
    )
    export_service = providers.Factory(
        ExportService,
        sessions_repo=sessions_repo,
        storage=storage_repo,
        queue=queue_repo,
        ids=ids,
    )
