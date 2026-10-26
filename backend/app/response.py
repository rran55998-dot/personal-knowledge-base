from __future__ import annotations

from typing import Any, Optional

from fastapi.responses import JSONResponse

from app.schemas.common import ApiResponse


def success(data: Any = None, message: str = "ok", status_code: int = 200) -> JSONResponse:
    payload = ApiResponse(success=True, message=message, data=data)
    return JSONResponse(
        status_code=status_code,
        content=payload.model_dump(by_alias=True, mode="json"),
    )
