from __future__ import annotations

from typing import List, Optional

from pydantic import Field

from app.schemas.common import CamelModel


class AskDeepSeekRequest(CamelModel):
    question: str = Field(..., min_length=1)
    category_id: Optional[int] = None
    top_k: int = Field(default=5, ge=1, le=20)
    enable_web_search: bool = True
    web_count: int = Field(default=5, ge=1, le=20)


class SourceItem(CamelModel):
    source_type: str = "knowledge"
    document_id: Optional[int] = None
    title: str
    chunk_index: int = 0
    content: str
    score: float = 0.0
    url: Optional[str] = None


class AskDeepSeekResponse(CamelModel):
    answer: str
    sources: List[SourceItem] = Field(default_factory=list)
    web_used: bool = False
