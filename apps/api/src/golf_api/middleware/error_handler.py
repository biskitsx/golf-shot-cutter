from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from golf_application.errors import (
    ApplicationError,
    SessionNotFoundError,
    ShotNotFoundError,
)
from golf_domain.errors import (
    DomainError,
    InvalidStateTransitionError,
    InvalidValueError,
)


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(SessionNotFoundError)
    async def _session_nf(_: Request, exc: SessionNotFoundError) -> JSONResponse:
        return JSONResponse(
            status_code=404, content={"error": "session_not_found", "message": str(exc)}
        )

    @app.exception_handler(ShotNotFoundError)
    async def _shot_nf(_: Request, exc: ShotNotFoundError) -> JSONResponse:
        return JSONResponse(
            status_code=404, content={"error": "shot_not_found", "message": str(exc)}
        )

    @app.exception_handler(InvalidStateTransitionError)
    async def _ist(_: Request, exc: InvalidStateTransitionError) -> JSONResponse:
        return JSONResponse(
            status_code=409, content={"error": "invalid_state", "message": str(exc)}
        )

    @app.exception_handler(InvalidValueError)
    async def _iv(_: Request, exc: InvalidValueError) -> JSONResponse:
        return JSONResponse(
            status_code=422, content={"error": "invalid_value", "message": str(exc)}
        )

    @app.exception_handler(DomainError)
    async def _de(_: Request, exc: DomainError) -> JSONResponse:
        return JSONResponse(status_code=400, content={"error": "domain_error", "message": str(exc)})

    @app.exception_handler(ApplicationError)
    async def _ae(_: Request, exc: ApplicationError) -> JSONResponse:
        return JSONResponse(
            status_code=400,
            content={"error": "application_error", "message": str(exc)},
        )
