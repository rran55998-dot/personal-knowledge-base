from __future__ import annotations

from typing import Optional

from app.db import get_connection
from app.schemas.category import (
    CategoryItem,
    CreateCategoryRequest,
    DeleteCategoryRequest,
    ListCategoryRequest,
    UpdateCategoryRequest,
)


class CategoryService:
    def create(self, req: CreateCategoryRequest) -> CategoryItem:
        name = req.name.strip()
        if not name:
            raise ValueError("分类名称不能为空")
        if req.parent_id is not None:
            self._ensure_exists(req.parent_id)

        with get_connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO categories (name, parent_id, sort)
                VALUES (?, ?, ?)
                """,
                (name, req.parent_id, req.sort),
            )
            category_id = int(cursor.lastrowid)
            row = conn.execute("SELECT * FROM categories WHERE id = ?", (category_id,)).fetchone()
        return self._to_item(row)

    def update(self, req: UpdateCategoryRequest) -> CategoryItem:
        self._ensure_exists(req.id)
        if req.parent_id is not None:
            if req.parent_id == req.id:
                raise ValueError("父分类不能是自身")
            self._ensure_exists(req.parent_id)
            if self._is_descendant(req.id, req.parent_id):
                raise ValueError("不能将分类移动到其子分类下")

        fields = []
        values = []
        if req.name is not None:
            name = req.name.strip()
            if not name:
                raise ValueError("分类名称不能为空")
            fields.append("name = ?")
            values.append(name)
        if req.parent_id is not None or (req.parent_id is None and "parent_id" in req.model_fields_set):
            # parent_id 显式传入 None 表示设为根分类
            if "parent_id" in req.model_fields_set:
                fields.append("parent_id = ?")
                values.append(req.parent_id)
        if req.sort is not None:
            fields.append("sort = ?")
            values.append(req.sort)

        if not fields:
            raise ValueError("没有可更新的字段")

        fields.append("updated_at = datetime('now', 'localtime')")
        values.append(req.id)

        with get_connection() as conn:
            conn.execute(f"UPDATE categories SET {', '.join(fields)} WHERE id = ?", values)
            row = conn.execute("SELECT * FROM categories WHERE id = ?", (req.id,)).fetchone()
        return self._to_item(row)

    def delete(self, req: DeleteCategoryRequest) -> None:
        self._ensure_exists(req.id)
        with get_connection() as conn:
            child = conn.execute(
                "SELECT id FROM categories WHERE parent_id = ? LIMIT 1",
                (req.id,),
            ).fetchone()
            if child:
                raise ValueError("请先删除子分类")
            doc = conn.execute(
                "SELECT id FROM documents WHERE category_id = ? LIMIT 1",
                (req.id,),
            ).fetchone()
            if doc:
                raise ValueError("分类下仍有文档，无法删除")
            conn.execute("DELETE FROM categories WHERE id = ?", (req.id,))

    def list(self, req: ListCategoryRequest) -> list[CategoryItem]:
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM categories ORDER BY sort ASC, id ASC"
            ).fetchall()
        items = [self._to_item(row) for row in rows]
        tree = self._build_tree(items)
        if req.parent_id is None:
            return tree
        # 仅返回指定父节点下的一层子树
        node = self._find_node(tree, req.parent_id)
        return node.children if node else []

    def _ensure_exists(self, category_id: int) -> None:
        with get_connection() as conn:
            row = conn.execute("SELECT id FROM categories WHERE id = ?", (category_id,)).fetchone()
        if not row:
            raise ValueError("分类不存在")

    def _is_descendant(self, ancestor_id: int, maybe_child_id: int) -> bool:
        with get_connection() as conn:
            current = maybe_child_id
            visited = set()
            while current is not None:
                if current in visited:
                    break
                visited.add(current)
                row = conn.execute(
                    "SELECT parent_id FROM categories WHERE id = ?",
                    (current,),
                ).fetchone()
                if not row:
                    break
                parent_id = row["parent_id"]
                if parent_id == ancestor_id:
                    return True
                current = parent_id
        return False

    def _to_item(self, row) -> CategoryItem:
        return CategoryItem(
            id=row["id"],
            name=row["name"],
            parent_id=row["parent_id"],
            sort=row["sort"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            children=[],
        )

    def _build_tree(self, items: list[CategoryItem]) -> list[CategoryItem]:
        mapping = {item.id: item for item in items}
        roots: list[CategoryItem] = []
        for item in items:
            if item.parent_id and item.parent_id in mapping:
                mapping[item.parent_id].children.append(item)
            else:
                roots.append(item)
        return roots

    def _find_node(self, nodes: list[CategoryItem], category_id: int) -> Optional[CategoryItem]:
        for node in nodes:
            if node.id == category_id:
                return node
            found = self._find_node(node.children, category_id)
            if found:
                return found
        return None


category_service = CategoryService()
