from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.response import success
from app.schemas.document import (
    CreateDocumentRequest,
    DeleteDocumentRequest,
    GetDocumentRequest,
    ListDocumentRequest,
    UpdateDocumentRequest,
)
from app.services.document_service import document_service
from app.services.parser import SUPPORTED_EXTENSIONS

router = APIRouter(tags=["document"])


@router.post("/importDocument")
async def import_document(
    file: UploadFile = File(...),
    categoryId: Optional[int] = Form(default=None),
    title: Optional[str] = Form(default=None),
):
    file_name = file.filename or "upload.bin"
    suffix = "." + file_name.rsplit(".", 1)[-1].lower() if "." in file_name else ""
    if suffix not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"暂不支持的文件类型，请使用: {', '.join(sorted(SUPPORTED_EXTENSIONS))}",
        )
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="文件内容为空")
    try:
        data = document_service.import_document(
            file_name=file_name,
            file_bytes=content,
            category_id=categoryId,
            title=title,
        )
        return success(data=data, message="导入成功")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/deleteDocument")
def delete_document(req: DeleteDocumentRequest):
    try:
        document_service.delete(req)
        return success(message="删除成功")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/listDocument")
def list_document(req: ListDocumentRequest):
    data = document_service.list(req)
    return success(data=data)


@router.post("/getDocument")
def get_document(req: GetDocumentRequest):
    try:
        data = document_service.get(req)
        return success(data=data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/updateDocument")
def update_document(req: UpdateDocumentRequest):
    try:
        data = document_service.update(req)
        return success(data=data, message="保存成功")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/createDocument")
def create_document(req: CreateDocumentRequest):
    try:
        data = document_service.create(req)
        return success(data=data, message="创建成功")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
