from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.response import success
from app.schemas.search import SearchDocumentRequest
from app.services.search_service import search_service

router = APIRouter(tags=["search"])


@router.post("/searchDocument")
def search_document(req: SearchDocumentRequest):
    try:
        data = search_service.search_documents(req)
        return success(data=data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
