from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.response import success
from app.schemas.category import (
    CreateCategoryRequest,
    DeleteCategoryRequest,
    ListCategoryRequest,
    UpdateCategoryRequest,
)
from app.services.category_service import category_service

router = APIRouter(tags=["category"])


@router.post("/createCategory")
def create_category(req: CreateCategoryRequest):
    try:
        data = category_service.create(req)
        return success(data=data, message="创建成功")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/updateCategory")
def update_category(req: UpdateCategoryRequest):
    try:
        data = category_service.update(req)
        return success(data=data, message="更新成功")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/deleteCategory")
def delete_category(req: DeleteCategoryRequest):
    try:
        category_service.delete(req)
        return success(message="删除成功")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/listCategory")
def list_category(req: ListCategoryRequest):
    data = category_service.list(req)
    return success(data=data)
