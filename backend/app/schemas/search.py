from __future__ import annotations

from typing import List, Optional

from pydantic import Field

from app.schemas.common import CamelModel


class SearchDocumentRequest(CamelModel):
    keyword: str = Field(..., min_length=1)
    category_id: Optional[int] = None
    limit: int = Field(default=20, ge=1, le=100)


class SearchDocumentItem(CamelModel):
    id: int
    category_id: Optional[int] = None
    title: str
    file_name: str
    file_type: str
    snippet: str
    score: float = 0.0
    match_terms: List[str] = Field(default_factory=list)
