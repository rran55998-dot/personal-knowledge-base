from __future__ import annotations

import io


def _create_category(client, name="默认分类"):
    resp = client.post("/api/createCategory", json={"name": name})
    assert resp.status_code == 200
    return resp.json()["data"]["id"]


def test_import_list_search_delete_document(client):
    category_id = _create_category(client)

    content = "个人知识库支持模糊查询与 DeepSeek 问答。这是一段测试文档内容。"
    files = {
        "file": ("demo.txt", io.BytesIO(content.encode("utf-8")), "text/plain"),
    }
    data = {"categoryId": str(category_id), "title": "测试文档"}
    import_resp = client.post("/api/importDocument", files=files, data=data)
    assert import_resp.status_code == 200
    import_body = import_resp.json()
    assert import_body["success"] is True
    document_id = import_body["data"]["id"]
    assert import_body["data"]["chunkCount"] >= 1

    list_resp = client.post(
        "/api/listDocument",
        json={"categoryId": category_id, "page": 1, "pageSize": 10},
    )
    assert list_resp.status_code == 200
    list_body = list_resp.json()["data"]
    assert list_body["total"] == 1
    assert list_body["items"][0]["id"] == document_id

    get_resp = client.post("/api/getDocument", json={"id": document_id})
    assert get_resp.status_code == 200
    assert "模糊查询" in get_resp.json()["data"]["contentText"]

    search_resp = client.post(
        "/api/searchDocument",
        json={"keyword": "模糊查询", "categoryId": category_id, "limit": 10},
    )
    assert search_resp.status_code == 200
    search_data = search_resp.json()["data"]
    assert len(search_data) >= 1
    assert search_data[0]["id"] == document_id

    delete_resp = client.post("/api/deleteDocument", json={"id": document_id})
    assert delete_resp.status_code == 200

    list_after = client.post("/api/listDocument", json={"categoryId": category_id})
    assert list_after.json()["data"]["total"] == 0


def test_import_unsupported_type(client):
    files = {"file": ("demo.exe", io.BytesIO(b"abc"), "application/octet-stream")}
    resp = client.post("/api/importDocument", files=files)
    assert resp.status_code == 400


def test_create_document(client):
    category_id = _create_category(client, "新建分类")
    create_resp = client.post(
        "/api/createDocument",
        json={
            "title": "我的笔记",
            "categoryId": category_id,
            "contentText": "这是新建的文档内容，支持后续编辑。",
        },
    )
    assert create_resp.status_code == 200
    body = create_resp.json()
    assert body["success"] is True
    assert body["data"]["title"] == "我的笔记"
    assert body["data"]["categoryId"] == category_id
    assert "新建的文档" in body["data"]["contentText"]

    document_id = body["data"]["id"]
    list_resp = client.post("/api/listDocument", json={"categoryId": category_id})
    assert list_resp.json()["data"]["total"] == 1
    assert list_resp.json()["data"]["items"][0]["id"] == document_id


def test_create_document_requires_category(client):
    resp = client.post(
        "/api/createDocument",
        json={"title": "无分类文档", "contentText": "x"},
    )
    assert resp.status_code == 422


def test_update_document_title_and_content(client):
    category_id = _create_category(client, "编辑分类")
    content = "原始内容：支持导入文档。"
    files = {"file": ("edit.txt", io.BytesIO(content.encode("utf-8")), "text/plain")}
    import_resp = client.post(
        "/api/importDocument",
        files=files,
        data={"categoryId": str(category_id), "title": "原始标题"},
    )
    assert import_resp.status_code == 200
    document_id = import_resp.json()["data"]["id"]

    update_resp = client.post(
        "/api/updateDocument",
        json={
            "id": document_id,
            "title": "更新后标题",
            "contentText": "更新后内容：支持编辑保存，并可模糊查询。",
        },
    )
    assert update_resp.status_code == 200
    body = update_resp.json()
    assert body["success"] is True
    assert body["data"]["title"] == "更新后标题"
    assert "编辑保存" in body["data"]["contentText"]

    get_resp = client.post("/api/getDocument", json={"id": document_id})
    assert get_resp.json()["data"]["title"] == "更新后标题"
    assert "编辑保存" in get_resp.json()["data"]["contentText"]

    search_resp = client.post(
        "/api/searchDocument",
        json={"keyword": "编辑保存", "limit": 10},
    )
    assert search_resp.status_code == 200
    assert any(item["id"] == document_id for item in search_resp.json()["data"])
