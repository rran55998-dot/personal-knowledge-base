from __future__ import annotations

from typing import Optional

from pydantic import Field

from app.schemas.common import CamelModel


class DeleteDocumentRequest(CamelModel):
    id: int


class ListDocumentRequest(CamelModel):
    category_id: Optional[int] = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=200)
    keyword: Optional[str] = None


class GetDocumentRequest(CamelModel):
    id: int


class UpdateDocumentRequest(CamelModel):
    id: int
    title: Optional[str] = Field(default=None, min_length=1, max_length=200)
    content_text: Optional[str] = None
    category_id: Optional[int] = None


class CreateDocumentRequest(CamelModel):
    title: str = Field(..., min_length=1, max_length=200)
    category_id: int
    content_text: str = ""


class DocumentItem(CamelModel):
    id: int
    category_id: Optional[int] = None
    title: str
    file_name: str
    file_type: str
    status: str
    created_at: str
    updated_at: str
    content_preview: Optional[str] = None
    content_text: Optional[str] = None


class ImportDocumentResponse(CamelModel):
    id: int
    title: str
    file_name: str
    file_type: str
    category_id: Optional[int] = None
    chunk_count: int = 0
