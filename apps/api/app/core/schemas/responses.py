from typing import Any

from pydantic import BaseModel


class ResponseStatus(BaseModel):
    code: int
    message: str


class BaseResponse(BaseModel):
    status: ResponseStatus
    data: Any


class ResponseSuccess(BaseResponse):
    def __init__(self, data: Any = None, message: str = "Success", code: int = 200) -> None:
        super().__init__(
            status=ResponseStatus(code=code, message=message),
            data=data if data is not None else {},
        )


class ResponseError(BaseResponse):
    def __init__(self, message: str, code: int = 400, data: Any = None) -> None:
        super().__init__(
            status=ResponseStatus(code=code, message=message),
            data=data if data is not None else {},
        )
