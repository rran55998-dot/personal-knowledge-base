from __future__ import annotations

import httpx

from app.config import get_settings


class WebSearchService:
    """调用 DeepSeek 官方联网搜索接口。"""

    def search(
        self,
        query: str,
        count: int = 5,
        ori_question: str | None = None,
        need_content: bool = False,
    ) -> list[dict]:
        settings = get_settings()
        if not settings.deepseek_api_key:
            raise ValueError("未配置 DEEPSEEK_API_KEY，请在 backend/.env 中设置")

        q = (query or "").strip()
        if not q:
            return []
        # API 限制 query 最长 128 字符
        q = q[:128]
        url = settings.deepseek_base_url.rstrip("/") + "/v1/tools/search"
        headers = {
            "Authorization": f"Bearer {settings.deepseek_api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "query": q,
            "count": max(1, min(count, 50)),
            "need_content": need_content,
        }
        if ori_question:
            payload["ori_question"] = ori_question.strip()[:128]

        with httpx.Client(timeout=45.0) as client:
            response = client.post(url, headers=headers, json=payload)
            if response.status_code >= 400:
                raise ValueError(
                    f"联网搜索失败: {response.status_code} {response.text}"
                )
            data = response.json()

        results = data.get("results") or []
        parsed = []
        for item in results:
            title = str(item.get("title") or "").strip()
            link = str(item.get("url") or "").strip()
            summary = str(item.get("summary") or item.get("snippet") or "").strip()
            content = str(item.get("content") or "").strip()
            text = content or summary
            if not title and not text:
                continue
            score = float(item.get("rerank_score") or 0)
            parsed.append(
                {
                    "title": title or link or "网页结果",
                    "url": link,
                    "content": text[:1200],
                    "score": score,
                    "site_name": item.get("site_name"),
                }
            )
        return parsed


web_search_service = WebSearchService()
