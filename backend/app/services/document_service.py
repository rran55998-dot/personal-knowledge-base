from __future__ import annotations

import uuid
from pathlib import Path
from typing import Optional

from app.config import UPLOAD_DIR, get_settings
from app.db import get_connection
from app.schemas.common import PageResult
from app.schemas.document import (
    CreateDocumentRequest,
    DeleteDocumentRequest,
    DocumentItem,
    GetDocumentRequest,
    ImportDocumentResponse,
    ListDocumentRequest,
    UpdateDocumentRequest,
)
from app.services.parser import extract_text, split_text
from app.services.vector_store import get_vector_store


class DocumentService:
    def import_document(
        self,
        file_name: str,
        file_bytes: bytes,
        category_id: Optional[int] = None,
        title: Optional[str] = None,
    ) -> ImportDocumentResponse:
        settings = get_settings()
        if category_id is not None:
            self._ensure_category(category_id)

        suffix = Path(file_name).suffix.lower()
        safe_name = f"{uuid.uuid4().hex}{suffix}"
        target = UPLOAD_DIR / safe_name
        target.write_bytes(file_bytes)

        try:
            content_text = extract_text(target)
        except Exception:
            target.unlink(missing_ok=True)
            raise

        doc_title = (title or Path(file_name).stem or "未命名文档").strip()
        chunks = split_text(content_text, settings.chunk_size, settings.chunk_overlap)

        with get_connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO documents
                (category_id, title, file_name, file_type, file_path, content_text, status)
                VALUES (?, ?, ?, ?, ?, ?, 'ready')
                """,
                (category_id, doc_title, file_name, suffix.lstrip("."), str(target), content_text),
            )
            document_id = int(cursor.lastrowid)
            for index, chunk in enumerate(chunks):
                conn.execute(
                    """
                    INSERT INTO document_chunks (document_id, chunk_index, content)
                    VALUES (?, ?, ?)
                    """,
                    (document_id, index, chunk),
                )

        self._rebuild_chunks_fts(document_id)
        self._rebuild_vector_index()

        return ImportDocumentResponse(
            id=document_id,
            title=doc_title,
            file_name=file_name,
            file_type=suffix.lstrip("."),
            category_id=category_id,
            chunk_count=len(chunks),
        )

    def create(self, req: CreateDocumentRequest) -> DocumentItem:
        settings = get_settings()
        title = req.title.strip()
        if not title:
            raise ValueError("标题不能为空")
        self._ensure_category(req.category_id)

        content_text = req.content_text or ""
        file_name = f"{title}.note"
        safe_name = f"{uuid.uuid4().hex}.note"
        target = UPLOAD_DIR / safe_name
        target.write_text(content_text, encoding="utf-8")
        chunks = split_text(content_text, settings.chunk_size, settings.chunk_overlap)

        with get_connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO documents
                (category_id, title, file_name, file_type, file_path, content_text, status)
                VALUES (?, ?, ?, ?, ?, ?, 'ready')
                """,
                (req.category_id, title, file_name, "note", str(target), content_text),
            )
            document_id = int(cursor.lastrowid)
            for index, chunk in enumerate(chunks):
                conn.execute(
                    """
                    INSERT INTO document_chunks (document_id, chunk_index, content)
                    VALUES (?, ?, ?)
                    """,
                    (document_id, index, chunk),
                )

        self._rebuild_chunks_fts(document_id)
        self._rebuild_vector_index()
        return self.get(GetDocumentRequest(id=document_id))

    def delete(self, req: DeleteDocumentRequest) -> None:
        with get_connection() as conn:
            row = conn.execute("SELECT * FROM documents WHERE id = ?", (req.id,)).fetchone()
            if not row:
                raise ValueError("文档不存在")
            file_path = Path(row["file_path"])
            conn.execute("DELETE FROM chunks_fts WHERE document_id = ?", (req.id,))
            conn.execute("DELETE FROM document_chunks WHERE document_id = ?", (req.id,))
            conn.execute("DELETE FROM documents WHERE id = ?", (req.id,))

        if file_path.exists():
            file_path.unlink(missing_ok=True)
        self._rebuild_vector_index()

    def list(self, req: ListDocumentRequest) -> PageResult[DocumentItem]:
        where = []
        params: list = []
        if req.category_id is not None:
            where.append("category_id = ?")
            params.append(req.category_id)
        if req.keyword:
            where.append("(title LIKE ? OR file_name LIKE ?)")
            like = f"%{req.keyword.strip()}%"
            params.extend([like, like])

        where_sql = f"WHERE {' AND '.join(where)}" if where else ""
        offset = (req.page - 1) * req.page_size

        with get_connection() as conn:
            total = conn.execute(
                f"SELECT COUNT(1) AS cnt FROM documents {where_sql}",
                params,
            ).fetchone()["cnt"]
            rows = conn.execute(
                f"""
                SELECT * FROM documents
                {where_sql}
                ORDER BY id DESC
                LIMIT ? OFFSET ?
                """,
                [*params, req.page_size, offset],
            ).fetchall()

        items = [self._to_item(row, include_content=False) for row in rows]
        return PageResult(items=items, total=total, page=req.page, page_size=req.page_size)

    def get(self, req: GetDocumentRequest) -> DocumentItem:
        with get_connection() as conn:
            row = conn.execute("SELECT * FROM documents WHERE id = ?", (req.id,)).fetchone()
        if not row:
            raise ValueError("文档不存在")
        return self._to_item(row, include_content=True)

    def update(self, req: UpdateDocumentRequest) -> DocumentItem:
        settings = get_settings()
        with get_connection() as conn:
            row = conn.execute("SELECT * FROM documents WHERE id = ?", (req.id,)).fetchone()
            if not row:
                raise ValueError("文档不存在")

        fields = []
        values = []
        content_changed = False

        if req.title is not None:
            title = req.title.strip()
            if not title:
                raise ValueError("标题不能为空")
            fields.append("title = ?")
            values.append(title)

        if "category_id" in req.model_fields_set:
            if req.category_id is not None:
                self._ensure_category(req.category_id)
            fields.append("category_id = ?")
            values.append(req.category_id)

        if req.content_text is not None:
            content_changed = True
            fields.append("content_text = ?")
            values.append(req.content_text)

        if not fields:
            raise ValueError("没有可更新的字段")

        fields.append("updated_at = datetime('now', 'localtime')")
        values.append(req.id)

        with get_connection() as conn:
            conn.execute(
                f"UPDATE documents SET {', '.join(fields)} WHERE id = ?",
                values,
            )
            if content_changed:
                conn.execute("DELETE FROM chunks_fts WHERE document_id = ?", (req.id,))
                conn.execute("DELETE FROM document_chunks WHERE document_id = ?", (req.id,))
                chunks = split_text(req.content_text or "", settings.chunk_size, settings.chunk_overlap)
                for index, chunk in enumerate(chunks):
                    conn.execute(
                        """
                        INSERT INTO document_chunks (document_id, chunk_index, content)
                        VALUES (?, ?, ?)
                        """,
                        (req.id, index, chunk),
                    )

        if content_changed:
            self._rebuild_chunks_fts(req.id)
            self._rebuild_vector_index()

        return self.get(GetDocumentRequest(id=req.id))

    def _ensure_category(self, category_id: int) -> None:
        with get_connection() as conn:
            row = conn.execute("SELECT id FROM categories WHERE id = ?", (category_id,)).fetchone()
        if not row:
            raise ValueError("分类不存在")

    def _to_item(self, row, include_content: bool = False) -> DocumentItem:
        preview = (row["content_text"] or "")[:200]
        return DocumentItem(
            id=row["id"],
            category_id=row["category_id"],
            title=row["title"],
            file_name=row["file_name"],
            file_type=row["file_type"],
            status=row["status"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            content_preview=preview,
            content_text=row["content_text"] if include_content else None,
        )

    def _rebuild_chunks_fts(self, document_id: int) -> None:
        with get_connection() as conn:
            conn.execute("DELETE FROM chunks_fts WHERE document_id = ?", (document_id,))
            rows = conn.execute(
                """
                SELECT id, content, document_id
                FROM document_chunks
                WHERE document_id = ?
                ORDER BY chunk_index ASC
                """,
                (document_id,),
            ).fetchall()
            for row in rows:
                conn.execute(
                    """
                    INSERT INTO chunks_fts(rowid, content, document_id)
                    VALUES (?, ?, ?)
                    """,
                    (row["id"], row["content"], row["document_id"]),
                )

    def _rebuild_vector_index(self) -> None:
        with get_connection() as conn:
            rows = conn.execute(
                """
                SELECT id, document_id, chunk_index, content
                FROM document_chunks
                ORDER BY id ASC
                """
            ).fetchall()
        payload = [dict(row) for row in rows]
        get_vector_store().rebuild(payload)


document_service = DocumentService()
