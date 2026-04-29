from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field

from app.core.container import Container
from app.core.schemas.responses import ResponseSuccess
from app.deps.auth import authenticate, current_user_id
from app.infrastructure.auth.jwt_service import JwtService


router = APIRouter(prefix="/auth", tags=["auth"])
_COOKIE_NAME = "auth"


class LoginRequest(BaseModel):
    email: str = Field(min_length=1)
    password: str = Field(min_length=1)


def _cookie_secure(request: Request) -> bool:
    return request.url.scheme == "https"


@router.post("/login", status_code=204)
@inject
async def login(
    req: LoginRequest,
    request: Request,
    response: Response,
    jwt_repo: JwtService = Depends(Provide[Container.jwt_repo]),
) -> None:
    user_id = authenticate(req.email, req.password)
    if user_id is None:
        raise HTTPException(status_code=401, detail="invalid_credentials")
    token = jwt_repo.issue(subject=user_id)
    response.set_cookie(
        _COOKIE_NAME,
        token,
        httponly=True,
        samesite="lax",
        secure=_cookie_secure(request),
        max_age=jwt_repo._ttl,  # noqa: SLF001
    )


@router.post("/logout", status_code=204)
async def logout(response: Response) -> None:
    response.delete_cookie(_COOKIE_NAME)


@router.get("/me")
async def me(user_id: str = Depends(current_user_id)) -> ResponseSuccess:
    return ResponseSuccess(data={"userId": user_id})
