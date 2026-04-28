import os
from contextlib import asynccontextmanager

from fastapi import FastAPI

from .deps.container import build_container, shutdown_container
from .middleware.error_handler import install_error_handlers
from .middleware.request_id import RequestIdMiddleware
from .routers.auth import router as auth_router
from .routers.sessions import router as sessions_router
from .settings import Settings


def create_app(env: str = "production") -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if env != "test":
            settings = Settings()
            container = await build_container(settings)
            app.state.container = container
            try:
                yield
            finally:
                await shutdown_container(container)
        else:
            # Test mode: container set by conftest.py via dependency override.
            yield

    app = FastAPI(title="golf-shot-cutter API", version="0.2.0", lifespan=lifespan)
    app.add_middleware(RequestIdMiddleware)
    install_error_handlers(app)
    from .routers.shots import router as shots_router

    app.include_router(auth_router)
    app.include_router(sessions_router)
    app.include_router(shots_router)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app(env=os.environ.get("APP_ENV", "production"))
