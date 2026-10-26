from __future__ import annotations

import io


def test_ask_deepseek_without_api_key(client, monkeypatch):
    import app.config as config

    monkeypatch.setenv("DEEPSEEK_API_KEY", "")
    config.get_settings.cache_clear()

    content = "知识库里有关于向量检索与 RAG 的说明。"
    files = {"file": ("rag.txt", io.BytesIO(content.encode("utf-8")), "text/plain")}
    import_resp = client.post("/api/importDocument", files=files, data={"title": "RAG说明"})
    assert import_resp.status_code == 200

    resp = client.post(
        "/api/askDeepSeek",
        json={"question": "什么是RAG", "topK": 3, "enableWebSearch": False},
    )
    assert resp.status_code == 400
    assert "DEEPSEEK_API_KEY" in resp.json()["detail"]


def test_ask_deepseek_with_mock(client, monkeypatch):
    import app.config as config
    import app.services.deepseek_service as deepseek_module

    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    config.get_settings.cache_clear()

    def fake_chat(self, settings, question, context, enable_web_search):
        assert "RAG" in context or "向量" in context or "知识库" in context
        assert enable_web_search is False
        return f"模拟回答: {question}"

    monkeypatch.setattr(deepseek_module.DeepSeekService, "_chat", fake_chat)

    content = "RAG 是检索增强生成，结合知识库检索与大模型回答。"
    files = {"file": ("rag.txt", io.BytesIO(content.encode("utf-8")), "text/plain")}
    import_resp = client.post("/api/importDocument", files=files, data={"title": "RAG说明"})
    assert import_resp.status_code == 200

    resp = client.post(
        "/api/askDeepSeek",
        json={"question": "什么是RAG", "topK": 3, "enableWebSearch": False},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert "模拟回答" in body["data"]["answer"]
    assert isinstance(body["data"]["sources"], list)
    assert body["data"]["webUsed"] is False


def test_ask_deepseek_with_web_search_mock(client, monkeypatch):
    import app.config as config
    import app.services.deepseek_service as deepseek_module
    import app.services.web_search_service as web_module

    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    config.get_settings.cache_clear()

    def fake_web_search(self, query, count=5, ori_question=None, need_content=False):
        return [
            {
                "title": "维基百科-RAG",
                "url": "https://example.com/rag",
                "content": "检索增强生成（RAG）是一种结合检索与生成的技术。",
                "score": 2.1,
            }
        ]

    def fake_chat(self, settings, question, context, enable_web_search):
        assert enable_web_search is True
        assert "联网搜索结果" in context
        assert "维基百科-RAG" in context
        return "综合知识库与联网结果的回答"

    monkeypatch.setattr(web_module.WebSearchService, "search", fake_web_search)
    monkeypatch.setattr(deepseek_module.DeepSeekService, "_chat", fake_chat)

    content = "知识库说明：RAG 可用于企业内部知识问答。"
    files = {"file": ("rag.txt", io.BytesIO(content.encode("utf-8")), "text/plain")}
    client.post("/api/importDocument", files=files, data={"title": "内部RAG"})

    resp = client.post(
        "/api/askDeepSeek",
        json={"question": "什么是RAG", "topK": 3, "enableWebSearch": True, "webCount": 3},
    )
    assert resp.status_code == 200
    body = resp.json()["data"]
    assert body["webUsed"] is True
    assert "综合知识库与联网结果" in body["answer"]
    assert any(item.get("sourceType") == "web" for item in body["sources"])
    assert any(item.get("url") for item in body["sources"] if item.get("sourceType") == "web")
