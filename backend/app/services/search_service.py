from __future__ import annotations

import re
from typing import Optional

import jieba

from app.db import get_connection
from app.schemas.search import SearchDocumentItem, SearchDocumentRequest
from app.services.vector_store import get_vector_store

# 前后端约定的高亮标记，避免与正文常见符号冲突
MARK_L = "⟦"
MARK_R = "⟧"


class SearchService:
    def search_documents(self, req: SearchDocumentRequest) -> list[SearchDocumentItem]:
        """按选中分类范围做模糊查询（未选分类则查全部），并在摘要中标记命中词。"""
        keyword = req.keyword.strip()
        if not keyword:
            return []

        terms = self._match_terms(keyword)
        fts_rows = self._search_by_fts(keyword, terms, req.limit, req.category_id)
        like_rows = self._search_by_like(keyword, terms, req.limit, req.category_id)
        merged = self._merge_document_rows(fts_rows, like_rows, req.limit)

        results = []
        for row in merged:
            title = self._mark_terms(str(row.get("title") or ""), terms)
            snippet = self._mark_terms(str(row.get("snippet") or ""), terms)
            results.append(
                SearchDocumentItem(
                    id=row["id"],
                    category_id=row["category_id"],
                    title=title,
                    file_name=row["file_name"],
                    file_type=row["file_type"],
                    snippet=snippet,
                    score=round(float(row.get("score") or 0), 4),
                    match_terms=terms,
                )
            )
        return results

    def _search_by_fts(
        self,
        keyword: str,
        terms: list[str],
        limit: int,
        category_id: Optional[int] = None,
    ) -> list[dict]:
        fts_query = self._build_fts_query(keyword)
        if not fts_query:
            return []
        category_sql = ""
        params: list = [fts_query]
        if category_id is not None:
            category_sql = "AND d.category_id = ?"
            params.append(category_id)
        params.append(limit)
        with get_connection() as conn:
            rows = conn.execute(
                f"""
                SELECT
                    d.id,
                    d.category_id,
                    d.title,
                    d.file_name,
                    d.file_type,
                    d.content_text,
                    snippet(documents_fts, 1, '', '', '...', 32) AS snippet,
                    bm25(documents_fts) AS rank_score
                FROM documents_fts
                JOIN documents d ON d.id = documents_fts.rowid
                WHERE documents_fts MATCH ?
                {category_sql}
                ORDER BY rank_score
                LIMIT ?
                """,
                params,
            ).fetchall()
        results = []
        for row in rows:
            rank = abs(float(row["rank_score"])) if row["rank_score"] is not None else 1.0
            score = 1.0 / (1.0 + rank)
            snippet = row["snippet"] or self._build_like_snippet(
                row["content_text"] or "",
                row["title"] or "",
                terms,
            )
            results.append(
                {
                    "id": row["id"],
                    "category_id": row["category_id"],
                    "title": row["title"],
                    "file_name": row["file_name"],
                    "file_type": row["file_type"],
                    "snippet": snippet,
                    "score": score,
                }
            )
        return results

    def _search_by_like(
        self,
        keyword: str,
        terms: list[str],
        limit: int,
        category_id: Optional[int] = None,
    ) -> list[dict]:
        if not terms:
            return []

        # 优先完整关键字；否则要求分词全部命中（模糊但仍相关）
        primary = re.sub(r"[^\w\u4e00-\u9fff]+", "", keyword, flags=re.UNICODE)
        word_terms = [t for t in terms if len(t) >= 2] or terms[:1]

        where_parts = []
        params: list = []
        if primary:
            where_parts.append("(title LIKE ? OR content_text LIKE ? OR file_name LIKE ?)")
            like = f"%{primary}%"
            params.extend([like, like, like])

        and_parts = []
        and_params: list = []
        for token in word_terms:
            and_parts.append("(title LIKE ? OR content_text LIKE ? OR file_name LIKE ?)")
            like = f"%{token}%"
            and_params.extend([like, like, like])
        if and_parts:
            where_parts.append("(" + " AND ".join(and_parts) + ")")
            params.extend(and_params)

        where_sql = " OR ".join(where_parts)
        category_sql = ""
        if category_id is not None:
            category_sql = " AND category_id = ?"
            params.append(category_id)
        with get_connection() as conn:
            rows = conn.execute(
                f"""
                SELECT
                    id,
                    category_id,
                    title,
                    file_name,
                    file_type,
                    content_text
                FROM documents
                WHERE ({where_sql}){category_sql}
                ORDER BY id DESC
                LIMIT ?
                """,
                [*params, max(limit * 3, 50)],
            ).fetchall()

        results = []
        for row in rows:
            content = row["content_text"] or ""
            title = row["title"] or ""
            hit_count = sum(1 for token in terms if token in title or token in content)
            if primary and (primary in title or primary in content):
                hit_count += 2
            snippet = self._build_like_snippet(content, title, [primary, *terms] if primary else terms)
            results.append(
                {
                    "id": row["id"],
                    "category_id": row["category_id"],
                    "title": row["title"],
                    "file_name": row["file_name"],
                    "file_type": row["file_type"],
                    "snippet": snippet,
                    "score": min(0.99, 0.4 + hit_count * 0.12),
                }
            )
        results.sort(key=lambda item: item["score"], reverse=True)
        return results[:limit]

    def _merge_document_rows(self, fts_rows: list[dict], like_rows: list[dict], limit: int) -> list[dict]:
        merged: dict[int, dict] = {}
        for row in fts_rows:
            merged[int(row["id"])] = dict(row)
        for row in like_rows:
            key = int(row["id"])
            if key in merged:
                merged[key]["score"] = max(float(merged[key]["score"]), float(row["score"])) + 0.05
                # 优先保留带命中上下文的摘要
                if len(str(row.get("snippet") or "")) > len(str(merged[key].get("snippet") or "")):
                    merged[key]["snippet"] = row["snippet"]
            else:
                merged[key] = dict(row)
        ordered = sorted(merged.values(), key=lambda item: float(item.get("score") or 0), reverse=True)
        return ordered[:limit]

    def _match_terms(self, keyword: str) -> list[str]:
        primary = re.sub(r"[^\w\u4e00-\u9fff]+", "", keyword, flags=re.UNICODE)
        parts = [t.strip() for t in jieba.cut_for_search(keyword) if t.strip()]
        cleaned = []
        for token in parts:
            token = re.sub(r"[^\w\u4e00-\u9fff]+", "", token, flags=re.UNICODE)
            if token:
                cleaned.append(token)
        terms = []
        if primary:
            terms.append(primary)
        terms.extend(cleaned)
        # 去重，长词优先
        uniq = list(dict.fromkeys(terms))
        uniq.sort(key=len, reverse=True)
        return uniq

    def _mark_terms(self, text: str, terms: list[str]) -> str:
        if not text or not terms:
            return text
        # 先清掉旧标记，避免重复包裹
        plain = text.replace(MARK_L, "").replace(MARK_R, "")
        pattern = "|".join(re.escape(term) for term in terms if term)
        if not pattern:
            return plain

        def repl(match: re.Match) -> str:
            return f"{MARK_L}{match.group(0)}{MARK_R}"

        try:
            return re.sub(pattern, repl, plain, flags=re.IGNORECASE)
        except re.error:
            return plain

    def _build_like_snippet(self, content: str, title: str, tokens: list[str]) -> str:
        source = content or title or ""
        if not source:
            return ""
        pos = -1
        hit = ""
        for token in tokens:
            if not token:
                continue
            idx = source.find(token)
            if idx >= 0:
                pos = idx
                hit = token
                break
        if pos < 0:
            return source[:160]
        start = max(0, pos - 40)
        end = min(len(source), pos + max(len(hit), 1) + 100)
        snippet = source[start:end]
        if start > 0:
            snippet = "..." + snippet
        if end < len(source):
            snippet = snippet + "..."
        return snippet

    def retrieve_chunks(
        self,
        question: str,
        top_k: int = 5,
        category_id: Optional[int] = None,
    ) -> list[dict]:
        allowed_doc_ids: Optional[set[int]] = None
        if category_id is not None:
            with get_connection() as conn:
                rows = conn.execute(
                    "SELECT id FROM documents WHERE category_id = ?",
                    (category_id,),
                ).fetchall()
            allowed_doc_ids = {int(r["id"]) for r in rows}
            if not allowed_doc_ids:
                return []

        vector_hits = get_vector_store().search(
            question,
            top_k=top_k * 2,
            category_document_ids=allowed_doc_ids,
        )

        fts_hits = self._search_chunks_fts(question, top_k=top_k * 2, allowed_doc_ids=allowed_doc_ids)
        merged = self._merge_hits(vector_hits, fts_hits, top_k=top_k)

        if not merged:
            return []
        doc_ids = list({item["document_id"] for item in merged})
        placeholders = ",".join("?" for _ in doc_ids)
        with get_connection() as conn:
            rows = conn.execute(
                f"SELECT id, title FROM documents WHERE id IN ({placeholders})",
                doc_ids,
            ).fetchall()
        title_map = {int(r["id"]): r["title"] for r in rows}
        for item in merged:
            item["title"] = title_map.get(item["document_id"], f"文档{item['document_id']}")
        return merged

    def _search_chunks_fts(
        self,
        question: str,
        top_k: int,
        allowed_doc_ids: Optional[set[int]],
    ) -> list[dict]:
        fts_query = self._build_fts_query(question)
        if not fts_query:
            return []
        with get_connection() as conn:
            rows = conn.execute(
                """
                SELECT
                    rowid AS chunk_id,
                    document_id,
                    content,
                    bm25(chunks_fts) AS rank_score
                FROM chunks_fts
                WHERE chunks_fts MATCH ?
                ORDER BY rank_score
                LIMIT ?
                """,
                (fts_query, max(top_k * 3, 20)),
            ).fetchall()

        results = []
        for row in rows:
            document_id = int(row["document_id"])
            if allowed_doc_ids is not None and document_id not in allowed_doc_ids:
                continue
            rank = abs(float(row["rank_score"])) if row["rank_score"] is not None else 1.0
            score = 1.0 / (1.0 + rank)
            results.append(
                {
                    "chunk_id": int(row["chunk_id"]),
                    "document_id": document_id,
                    "chunk_index": 0,
                    "content": row["content"],
                    "score": score,
                }
            )
            if len(results) >= top_k:
                break

        if results:
            chunk_ids = [r["chunk_id"] for r in results]
            placeholders = ",".join("?" for _ in chunk_ids)
            with get_connection() as conn:
                index_rows = conn.execute(
                    f"SELECT id, chunk_index FROM document_chunks WHERE id IN ({placeholders})",
                    chunk_ids,
                ).fetchall()
            index_map = {int(r["id"]): int(r["chunk_index"]) for r in index_rows}
            for item in results:
                item["chunk_index"] = index_map.get(item["chunk_id"], 0)
        return results

    def _merge_hits(self, vector_hits: list[dict], fts_hits: list[dict], top_k: int) -> list[dict]:
        merged: dict[int, dict] = {}
        for hit in vector_hits:
            key = int(hit["chunk_id"])
            merged[key] = {
                **hit,
                "score": float(hit.get("score", 0)) * 1.0,
            }
        for hit in fts_hits:
            key = int(hit["chunk_id"])
            if key in merged:
                merged[key]["score"] = float(merged[key]["score"]) + float(hit.get("score", 0)) * 0.8
            else:
                merged[key] = {
                    **hit,
                    "score": float(hit.get("score", 0)) * 0.8,
                }
        ordered = sorted(merged.values(), key=lambda x: x["score"], reverse=True)
        return ordered[:top_k]

    def _build_fts_query(self, keyword: str) -> str:
        tokens = [t.strip() for t in jieba.cut_for_search(keyword) if t.strip()]
        cleaned = []
        for token in tokens:
            token = re.sub(r"[^\w\u4e00-\u9fff]+", "", token, flags=re.UNICODE)
            if token:
                cleaned.append(token)
        if not cleaned:
            fallback = re.sub(r"[^\w\u4e00-\u9fff]+", "", keyword, flags=re.UNICODE)
            return fallback
        uniq = list(dict.fromkeys(cleaned))
        return " OR ".join(uniq)


search_service = SearchService()
