"""SQLite 实现的 BaseStore：跨会话长期记忆持久化。

替代 memories/*.txt 的散落文件方案，提供结构化、可检索、多 namespace 隔离的记忆存储。
重启进程后记忆不丢；以后升级到 Postgres 只需换 import 和 conn_string。

使用方式：
    from stores.sqlite_store import SqliteStore
    import sqlite3
    store = SqliteStore(conn=sqlite3.connect("memories.db"))
    store.put(("default", "researcher"), "search-001", {"topic": "金价", "count": 5})
    items = store.search(("default", "researcher"), limit=20)
"""

from __future__ import annotations

import json
import sqlite3
import threading
from collections.abc import Iterable
from datetime import datetime, timezone
from typing import Any

from langgraph.store.base import (
    BaseStore,
    GetOp,
    Item,
    ListNamespacesOp,
    PutOp,
    SearchItem,
    SearchOp,
)

# Op 和 Result 的类型（从 base 模块导出）
Op = Any
Result = Any


class SqliteStore(BaseStore):
    """SQLite 持久化 Store。

    核心表结构：
        store_items(namespace TEXT, key TEXT, value TEXT, created_at TEXT, updated_at TEXT)
        - namespace: 用 "/" 拼接的层级路径，例 "default/researcher"
        - key: namespace 内的唯一标识
        - value: JSON 字符串
        - 主键 (namespace, key)

    FTS5 全文检索（可选，第 5 步启用）：
        store_fts 虚拟表，对 value 做全文索引，支持按语义找历史记忆。
    """

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn
        self._conn.row_factory = sqlite3.Row
        # SQLite 写入需要串行化，多线程访问时加锁
        self._lock = threading.Lock()
        self._init_tables()

    def _init_tables(self) -> None:
        """建表（幂等，已存在则跳过）"""
        with self._lock:
            cur = self._conn.cursor()
            # 主表：namespace + key 联合主键
            cur.execute("""
                CREATE TABLE IF NOT EXISTS store_items (
                    namespace   TEXT NOT NULL,
                    key         TEXT NOT NULL,
                    value       TEXT NOT NULL,
                    created_at  TEXT NOT NULL,
                    updated_at  TEXT NOT NULL,
                    PRIMARY KEY (namespace, key)
                )
            """)
            # namespace 前缀检索索引
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_namespace ON store_items(namespace)"
            )
            # FTS5 全文检索虚拟表（第 5 步用）
            # content='store_items' 让 FTS 表关联主表，external content 模式
            cur.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS store_fts
                USING fts5(value, content='store_items', content_rowid='rowid')
            """)
            self._conn.commit()

    # ================== BaseStore 抽象方法实现 ==================

    def batch(self, ops: Iterable[Op]) -> list[Result]:
        """同步批量执行操作（get/put/search/list_namespaces）。

        BaseStore 的 get/put/search/delete/list_namespaces 都会走这个方法，
        我们在这里按 op 类型分发到对应的处理函数。
        """
        results: list[Result] = []
        ops_list = list(ops)
        with self._lock:
            for op in ops_list:
                if isinstance(op, GetOp):
                    results.append(self._handle_get(op))
                elif isinstance(op, SearchOp):
                    results.append(self._handle_search(op))
                elif isinstance(op, PutOp):
                    results.append(self._handle_put(op))
                elif isinstance(op, ListNamespacesOp):
                    results.append(self._handle_list_namespaces(op))
                else:
                    raise ValueError(f"未知的操作类型: {type(op)}")
            self._conn.commit()
        return results

    async def abatch(self, ops: Iterable[Op]) -> list[Result]:
        """异步批量执行（SQLite 是同步的，直接走 sync 实现）"""
        return self.batch(ops)

    # ================== 操作处理器 ==================

    def _ns_to_str(self, namespace: tuple[str, ...]) -> str:
        """把 namespace 元组拼成字符串，例 ('default','researcher') → 'default/researcher'"""
        return "/".join(namespace)

    def _str_to_ns(self, ns_str: str) -> tuple[str, ...]:
        """字符串还原成 namespace 元组"""
        return tuple(ns_str.split("/")) if ns_str else ()

    def _row_to_item(self, row: sqlite3.Row) -> Item:
        """数据库行 → Item 对象"""
        return Item(
            value=json.loads(row["value"]),
            key=row["key"],
            namespace=self._str_to_ns(row["namespace"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def _handle_get(self, op: GetOp) -> Item | None:
        """按 namespace + key 精确查一条"""
        ns_str = self._ns_to_str(op.namespace)
        cur = self._conn.cursor()
        cur.execute(
            "SELECT * FROM store_items WHERE namespace=? AND key=?",
            (ns_str, op.key),
        )
        row = cur.fetchone()
        return self._row_to_item(row) if row else None

    def _handle_put(self, op: PutOp) -> None:
        """写入或删除一条记忆。

        op.value is None 表示删除（BaseStore.delete 走的就是 put(None)）
        """
        ns_str = self._ns_to_str(op.namespace)
        if op.value is None:
            # 删除
            cur = self._conn.cursor()
            cur.execute(
                "DELETE FROM store_items WHERE namespace=? AND key=?",
                (ns_str, op.key),
            )
            # 同步删 FTS 索引
            cur.execute(
                "DELETE FROM store_fts WHERE rowid IN "
                "(SELECT rowid FROM store_items WHERE namespace=? AND key=?)",
                (ns_str, op.key),
            )
            return

        now = datetime.now(timezone.utc).isoformat()
        value_json = json.dumps(op.value, ensure_ascii=False)

        # 检查是否已存在（决定 created_at 是否更新）
        cur = self._conn.cursor()
        cur.execute(
            "SELECT created_at FROM store_items WHERE namespace=? AND key=?",
            (ns_str, op.key),
        )
        existing = cur.fetchone()
        created_at = existing["created_at"] if existing else now

        # UPSERT（INSERT OR REPLACE 会保留主键约束）
        cur.execute(
            """
            INSERT INTO store_items (namespace, key, value, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(namespace, key) DO UPDATE SET
                value=excluded.value,
                updated_at=excluded.updated_at
            """,
            (ns_str, op.key, value_json, created_at, now),
        )

        # 同步更新 FTS 索引（先删后插）
        cur.execute(
            "DELETE FROM store_fts WHERE rowid IN "
            "(SELECT rowid FROM store_items WHERE namespace=? AND key=?)",
            (ns_str, op.key),
        )
        cur.execute(
            "INSERT INTO store_fts(rowid, value) "
            "SELECT rowid, value FROM store_items WHERE namespace=? AND key=?",
            (ns_str, op.key),
        )

    def _handle_search(self, op: SearchOp) -> list[SearchItem]:
        """按 namespace 前缀搜索，支持 filter 和全文检索（query 参数）"""
        ns_prefix = self._ns_to_str(op.namespace_prefix)
        cur = self._conn.cursor()

        # 构建 SQL：namespace 前缀匹配
        # 例 prefix="default" → 匹配 "default"、"default/researcher"、"default/xxx"
        params: list[Any] = [ns_prefix, ns_prefix + "/"]

        where_clause = "WHERE (namespace = ? OR namespace LIKE ?)"
        filter_clauses: list[str] = []

        # filter 是 value 内字段的精确匹配，在 Python 层做（SQLite 的 JSON 支持有限）
        # query 是全文检索，走 FTS5
        if op.query:
            # FTS5 全文检索：先查 FTS 表拿 rowid，再 join 主表
            # 注意：FTS5 的 MATCH 语法对中文支持一般，靠分词
            fts_sql = """
                SELECT s.* FROM store_items s
                JOIN store_fts f ON s.rowid = f.rowid
                WHERE (s.namespace = ? OR s.namespace LIKE ?)
                  AND store_fts MATCH ?
                ORDER BY rank
                LIMIT ? OFFSET ?
            """
            params_with_query = params + [op.query, op.limit, op.offset]
            cur.execute(fts_sql, params_with_query)
        else:
            # 无 query：纯 namespace 前缀 + filter
            sql = f"""
                SELECT * FROM store_items
                {where_clause}
                ORDER BY updated_at DESC
                LIMIT ? OFFSET ?
            """
            cur.execute(sql, params + [op.limit, op.offset])

        rows = cur.fetchall()
        items = [self._row_to_item(r) for r in rows]

        # filter 在 Python 层过滤（value 内字段匹配）
        if op.filter:
            items = [
                it for it in items
                if all(it.value.get(k) == v for k, v in op.filter.items())
            ]

        # 转 SearchItem（SearchItem 是 Item 的子类，多了 score 字段）
        return [
            SearchItem(
                value=it.value,
                key=it.key,
                namespace=it.namespace,
                created_at=it.created_at,
                updated_at=it.updated_at,
            )
            for it in items
        ]

    def _handle_list_namespaces(self, op: ListNamespacesOp) -> list[tuple[str, ...]]:
        """列出所有 namespace（可按 prefix/suffix/max_depth 过滤）"""
        cur = self._conn.cursor()
        cur.execute("SELECT DISTINCT namespace FROM store_items")
        all_ns = [self._str_to_ns(row["namespace"]) for row in cur.fetchall()]

        # 按 prefix 过滤
        if op.prefix:
            all_ns = [ns for ns in all_ns if ns[: len(op.prefix)] == tuple(op.prefix)]
        # 按 suffix 过滤
        if op.suffix:
            all_ns = [ns for ns in all_ns if ns[-len(op.suffix):] == tuple(op.suffix)]
        # 按 max_depth 截断
        if op.max_depth:
            all_ns = [ns[: op.max_depth] for ns in all_ns]
        # 去重 + 排序
        all_ns = sorted(set(all_ns))
        return all_ns[: op.limit]
