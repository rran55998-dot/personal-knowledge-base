from __future__ import annotations


def test_create_list_update_delete_category(client):
    create_resp = client.post("/api/createCategory", json={"name": "技术资料", "sort": 1})
    assert create_resp.status_code == 200
    body = create_resp.json()
    assert body["success"] is True
    category_id = body["data"]["id"]
    assert body["data"]["name"] == "技术资料"

    child_resp = client.post(
        "/api/createCategory",
        json={"name": "Python", "parentId": category_id, "sort": 1},
    )
    assert child_resp.status_code == 200
    child_id = child_resp.json()["data"]["id"]

    list_resp = client.post("/api/listCategory", json={})
    assert list_resp.status_code == 200
    tree = list_resp.json()["data"]
    assert len(tree) == 1
    assert tree[0]["id"] == category_id
    assert len(tree[0]["children"]) == 1
    assert tree[0]["children"][0]["id"] == child_id

    update_resp = client.post(
        "/api/updateCategory",
        json={"id": child_id, "name": "Python进阶"},
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["data"]["name"] == "Python进阶"

    # 有子分类时不能删父分类
    delete_parent = client.post("/api/deleteCategory", json={"id": category_id})
    assert delete_parent.status_code == 400

    delete_child = client.post("/api/deleteCategory", json={"id": child_id})
    assert delete_child.status_code == 200
    assert delete_child.json()["success"] is True

    delete_parent2 = client.post("/api/deleteCategory", json={"id": category_id})
    assert delete_parent2.status_code == 200


def test_create_category_empty_name(client):
    resp = client.post("/api/createCategory", json={"name": "  "})
    assert resp.status_code == 422 or resp.status_code == 400
