from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.response import success
from app.schemas.chat import AskDeepSeekRequest
from app.services.deepseek_service import deepseek_service

router = APIRouter(tags=["chat"])


@router.post("/askDeepSeek")
def ask_deepseek(req: AskDeepSeekRequest):
    try:
        data = deepseek_service.ask(req)
        return success(data=data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
