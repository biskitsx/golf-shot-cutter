import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.endpoints import auth, export, realtime, sessions, shots, upload
from app.middleware.error_handler import install_error_handlers
from app.middleware.request_id import RequestIdMiddleware


def create_app(env: str = "production") -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if env != "test":
            from app.core.container import Container
            from app.persistence.mongo.indexes import ensure_indexes

            container = Container()
            # Ensure mongo indexes on startup
            db = container.mongo_database()
            await ensure_indexes(db)
            app.state.container = container
        # else: container set by conftest.py
        yield

    app = FastAPI(title="golf-shot-cutter API", version="0.3.0", lifespan=lifespan)

    cors_origins: list[str] = []
    if env != "test":
        try:
            from app.core.config import Settings

            cors_origins = Settings().cors_origins
        except Exception:
            cors_origins = []

    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins or ["http://localhost:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(RequestIdMiddleware)
    install_error_handlers(app)
    app.include_router(auth.router)
    app.include_router(sessions.router)
    app.include_router(shots.router)
    app.include_router(upload.router)
    app.include_router(export.router)
    app.include_router(realtime.router)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app(env=os.environ.get("APP_ENV", "production"))
