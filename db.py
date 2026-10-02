"""SQLite 持久化层（标准库 sqlite3，不引入 ORM）。

为什么不用 ORM：
  * 单表 CRUD，SQL 直白可读，答辩时能逐行讲清楚；
  * 少一个依赖，Render 免费实例冷启动更快。

为什么要持久化到数据库（而不是前端 localStorage）：
  * 换浏览器 / 换设备 / 刷新页面历史都还在；
  * 清空浏览器缓存不会丢数据；
  * 这是"前后端分离"作业里后端必须承担的职责。

线程安全说明：
  FastAPI 的同步路由跑在线程池里，sqlite3 连接不能跨线程复用，
  因此这里**每次操作新建连接、用完即关**（SQLite 连接开销极小），
  并开启 WAL 模式提升读写并发。

表结构（calculation_history）：
  id          INTEGER  主键，自增
  expression  TEXT     用户输入的原始表达式
  result      TEXT     后端计算出的结果（字符串保存，避免浮点精度丢失）
  created_at  TEXT     记录创建时间，ISO 8601（UTC）
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from errors import DatabaseError

DEFAULT_DB_PATH = Path(__file__).resolve().parent / "data" / "calculator.db"

SCHEMA_STATEMENTS: tuple[str, ...] = (
    """
    CREATE TABLE IF NOT EXISTS calculation_history (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        expression TEXT    NOT NULL,
        result     TEXT    NOT NULL,
        created_at TEXT    NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_history_created_at ON calculation_history (created_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_history_expression ON calculation_history (expression)",
)

_SELECT_COLUMNS = "id, expression, result, created_at"


def _now_iso() -> str:
    """当前 UTC 时间，秒级精度，带时区偏移（前端可直接 new Date() 解析）。"""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "expression": row["expression"],
        "result": row["result"],
        "created_at": row["created_at"],
    }


class HistoryRepository:
    """计算历史的仓储对象：封装建表与增删查。"""

    def __init__(self, db_path: Path | str = DEFAULT_DB_PATH) -> None:
        self._db_path = Path(db_path)

    @property
    def db_path(self) -> Path:
        return self._db_path

    # ------------------------------------------------------------------ 连接
    def _connect(self) -> sqlite3.Connection:
        try:
            self._db_path.parent.mkdir(parents=True, exist_ok=True)
            connection = sqlite3.connect(self._db_path, timeout=10.0)
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute("PRAGMA synchronous=NORMAL")
            return connection
        except sqlite3.Error as exc:  # pragma: no cover - 环境异常
            raise DatabaseError(f"无法连接数据库：{exc}") from exc

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        connection = self._connect()
        try:
            yield connection
            connection.commit()
        except sqlite3.Error as exc:
            connection.rollback()
            raise DatabaseError(f"数据库操作失败：{exc}") from exc
        finally:
            connection.close()

    # ------------------------------------------------------------------ 建表
    def init_schema(self) -> None:
        """应用启动时调用：幂等建表 + 建索引。"""
        with self._connection() as connection:
            for statement in SCHEMA_STATEMENTS:
                connection.execute(statement)

    # ------------------------------------------------------------------ 写入
    def create(self, expression: str, result: str) -> dict[str, Any]:
        """新增一条历史记录并返回完整记录（含数据库生成的 id 与时间）。"""
        created_at = _now_iso()
        with self._connection() as connection:
            cursor = connection.execute(
                "INSERT INTO calculation_history (expression, result, created_at) VALUES (?, ?, ?)",
                (expression, result, created_at),
            )
            new_id = int(cursor.lastrowid)
        return {"id": new_id, "expression": expression, "result": result, "created_at": created_at}

    # ------------------------------------------------------------------ 查询
    def list_all(
        self,
        keyword: str | None = None,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """按 id 倒序返回历史记录；keyword 支持按表达式/结果模糊过滤。"""
        sql = f"SELECT {_SELECT_COLUMNS} FROM calculation_history"
        params: list[Any] = []
        if keyword:
            sql += " WHERE expression LIKE ? OR result LIKE ?"
            pattern = f"%{keyword}%"
            params.extend([pattern, pattern])
        sql += " ORDER BY id DESC"
        if limit is not None:
            sql += " LIMIT ? OFFSET ?"
            params.extend([limit, offset])
        with self._connection() as connection:
            rows = connection.execute(sql, params).fetchall()
        return [_row_to_dict(row) for row in rows]

    def count(self, keyword: str | None = None) -> int:
        sql = "SELECT COUNT(*) AS total FROM calculation_history"
        params: list[Any] = []
        if keyword:
            sql += " WHERE expression LIKE ? OR result LIKE ?"
            pattern = f"%{keyword}%"
            params.extend([pattern, pattern])
        with self._connection() as connection:
            row = connection.execute(sql, params).fetchone()
        return int(row["total"]) if row else 0

    def get(self, record_id: int) -> dict[str, Any] | None:
        with self._connection() as connection:
            row = connection.execute(
                f"SELECT {_SELECT_COLUMNS} FROM calculation_history WHERE id = ?", (record_id,)
            ).fetchone()
        return _row_to_dict(row) if row else None

    # ------------------------------------------------------------------ 删除
    def delete(self, record_id: int) -> bool:
        """删除单条记录，返回是否真的删掉了。"""
        with self._connection() as connection:
            cursor = connection.execute("DELETE FROM calculation_history WHERE id = ?", (record_id,))
        return cursor.rowcount > 0

    def clear(self) -> int:
        """清空全部历史（扩展功能「一键清空」用）。"""
        with self._connection() as connection:
            cursor = connection.execute("DELETE FROM calculation_history")
        return int(cursor.rowcount)
