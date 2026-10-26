from __future__ import annotations

from typing import List, Optional

from pydantic import Field

from app.schemas.common import CamelModel


class CreateCategoryRequest(CamelModel):
    name: str = Field(..., min_length=1, max_length=100)
    parent_id: Optional[int] = None
    sort: int = 0


class UpdateCategoryRequest(CamelModel):
    id: int
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    parent_id: Optional[int] = None
    sort: Optional[int] = None


class DeleteCategoryRequest(CamelModel):
    id: int


class ListCategoryRequest(CamelModel):
    parent_id: Optional[int] = None


class CategoryItem(CamelModel):
    id: int
    name: str
    parent_id: Optional[int] = None
    sort: int = 0
    created_at: str
    updated_at: str
    children: List["CategoryItem"] = Field(default_factory=list)


CategoryItem.model_rebuild()
