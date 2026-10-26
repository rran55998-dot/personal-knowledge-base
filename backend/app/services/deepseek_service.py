from __future__ import annotations

import httpx

from app.config import get_settings
from app.schemas.chat import AskDeepSeekRequest, AskDeepSeekResponse, SourceItem
from app.services.search_service import search_service
from app.services.web_search_service import web_search_service


class DeepSeekService:
    def ask(self, req: AskDeepSeekRequest) -> AskDeepSeekResponse:
        settings = get_settings()
        if not settings.deepseek_api_key:
            raise ValueError("未配置 DEEPSEEK_API_KEY，请在 backend/.env 中设置")

        kb_hits = search_service.retrieve_chunks(
            question=req.question,
            top_k=req.top_k,
            category_id=req.category_id,
        )
        web_hits: list[dict] = []
        web_used = False
        if req.enable_web_search:
            try:
                web_hits = web_search_service.search(
                    query=req.question,
                    count=req.web_count,
                    ori_question=req.question,
                    need_content=False,
                )
                web_used = True
            except ValueError as exc:
                # 联网失败时降级为仅知识库，并把原因带进回答上下文
                web_hits = [
                    {
                        "title": "联网搜索不可用",
                        "url": "",
                        "content": str(exc),
                        "score": 0,
                    }
                ]
                web_used = False

        context = self._build_context(kb_hits, web_hits, req.enable_web_search)
        answer = self._chat(settings, req.question, context, req.enable_web_search)

        sources: list[SourceItem] = []
        for hit in kb_hits:
            sources.append(
                SourceItem(
                    source_type="knowledge",
                    document_id=int(hit["document_id"]),
                    title=str(hit.get("title") or ""),
                    chunk_index=int(hit.get("chunk_index") or 0),
                    content=str(hit.get("content") or ""),
                    score=round(float(hit.get("score") or 0), 4),
                )
            )
        if req.enable_web_search:
            for hit in web_hits:
                if hit.get("title") == "联网搜索不可用":
                    continue
                sources.append(
                    SourceItem(
                        source_type="web",
                        title=str(hit.get("title") or ""),
                        content=str(hit.get("content") or ""),
                        score=round(float(hit.get("score") or 0), 4),
                        url=str(hit.get("url") or "") or None,
                    )
                )
        return AskDeepSeekResponse(answer=answer, sources=sources, web_used=web_used)

    def _build_context(
        self,
        kb_hits: list[dict],
        web_hits: list[dict],
        enable_web_search: bool,
    ) -> str:
        parts = []
        if kb_hits:
            parts.append("【知识库资料】")
            for index, hit in enumerate(kb_hits, start=1):
                parts.append(
                    f"[知识库{index}] 标题: {hit.get('title')}\n内容: {hit.get('content')}"
                )
        else:
            parts.append("【知识库资料】\n（未检索到相关资料）")

        if enable_web_search:
            parts.append("【联网搜索结果】")
            if web_hits:
                for index, hit in enumerate(web_hits, start=1):
                    url = hit.get("url") or ""
                    parts.append(
                        f"[网页{index}] 标题: {hit.get('title')}\n链接: {url}\n内容: {hit.get('content')}"
                    )
            else:
                parts.append("（未检索到相关网页）")
        return "\n\n".join(parts)

    def _chat(self, settings, question: str, context: str, enable_web_search: bool) -> str:
        if enable_web_search:
            system_prompt = (
                "你是资料文档库助手，同时可参考联网搜索结果。"
                "请综合【知识库资料】与【联网搜索结果】回答。"
                "优先使用知识库中的准确内容；知识库不足时，可使用联网结果补充。"
                "引用网页时尽量说明来源标题或链接。"
                "若两边资料都不足，请明确说明。"
                "回答使用简体中文，条理清晰。"
            )
        else:
            system_prompt = (
                "你是资料文档库助手。请优先依据给定资料回答用户问题。"
                "若资料不足，请明确说明，并谨慎补充一般性知识。"
                "回答使用简体中文，条理清晰。"
            )
        user_prompt = f"参考资料:\n{context}\n\n用户问题:\n{question}"
        url = settings.deepseek_base_url.rstrip("/") + "/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {settings.deepseek_api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": settings.deepseek_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.3,
        }
        with httpx.Client(timeout=90.0) as client:
            response = client.post(url, headers=headers, json=payload)
            if response.status_code >= 400:
                raise ValueError(f"DeepSeek 调用失败: {response.status_code} {response.text}")
            data = response.json()
        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ValueError(f"DeepSeek 返回格式异常: {data}") from exc


deepseek_service = DeepSeekService()
