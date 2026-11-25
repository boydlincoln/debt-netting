"""SQLite 本地持久层：主体、债务、材料、方案、审计。

图谱数据以关系表保存（debt 行即一条有向加权边），
仓储接口与具体存储解耦，便于按技术方案替换为 Neo4j 实现。
"""
from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Sequence

SCHEMA = """
CREATE TABLE IF NOT EXISTS entities (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    credit_code TEXT NOT NULL DEFAULT '',
    account TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT '正常经营',
    available_cash_cents INTEGER NOT NULL DEFAULT 0,
    litigation INTEGER NOT NULL DEFAULT 0,
    enforced INTEGER NOT NULL DEFAULT 0,
    note TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS debts (
    id TEXT PRIMARY KEY,
    debtor_id TEXT NOT NULL,
    creditor_id TEXT NOT NULL,
    principal_cents INTEGER NOT NULL DEFAULT 0,
    interest_cents INTEGER NOT NULL DEFAULT 0,
    amount_cents INTEGER NOT NULL DEFAULT 0,
    due_date TEXT NOT NULL DEFAULT '',
    disputed INTEGER NOT NULL DEFAULT 0,
    frozen INTEGER NOT NULL DEFAULT 0,
    no_setoff_clause INTEGER NOT NULL DEFAULT 0,
    priority_group TEXT NOT NULL DEFAULT 'ordinary',
    status TEXT NOT NULL DEFAULT 'confirmed',
    source TEXT NOT NULL DEFAULT 'manual',
    material_id TEXT,
    note TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_debts_debtor ON debts(debtor_id);
CREATE INDEX IF NOT EXISTS idx_debts_creditor ON debts(creditor_id);
CREATE INDEX IF NOT EXISTS idx_debts_status ON debts(status);

CREATE TABLE IF NOT EXISTS materials (
    id TEXT PRIMARY KEY,
    filename TEXT NOT NULL,
    stored_name TEXT NOT NULL DEFAULT '',
    sha256 TEXT NOT NULL DEFAULT '',
    size INTEGER NOT NULL DEFAULT 0,
    text TEXT NOT NULL DEFAULT '',
    meta TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS plans (
    id TEXT PRIMARY KEY,
    seq INTEGER,
    name TEXT,
    created_at TEXT NOT NULL,
    as_of_date TEXT NOT NULL,
    payload TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS audit (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    action TEXT NOT NULL,
    actor TEXT NOT NULL DEFAULT '本地用户',
    detail TEXT NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_audit_ts ON audit(ts);
"""


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:10]}"


class Database:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.path), timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        return conn

    @contextmanager
    def session(self):
        conn = self.connect()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def init(self) -> None:
        with self._lock, self.session() as conn:
            conn.executescript(SCHEMA)
            plan_columns = {row["name"] for row in conn.execute("PRAGMA table_info(plans)").fetchall()}
            if "seq" not in plan_columns:
                conn.execute("ALTER TABLE plans ADD COLUMN seq INTEGER")
            if "name" not in plan_columns:
                conn.execute("ALTER TABLE plans ADD COLUMN name TEXT")
            conn.execute("UPDATE plans SET seq = rowid WHERE seq IS NULL")
            conn.execute("UPDATE plans SET name = '核算 #' || seq WHERE name IS NULL OR name = ''")

    # ---------- 通用查询 ----------
    def query(self, sql: str, params: Sequence[Any] = ()) -> list[dict]:
        with self.session() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [dict(row) for row in rows]

    def query_one(self, sql: str, params: Sequence[Any] = ()) -> dict | None:
        rows = self.query(sql, params)
        return rows[0] if rows else None

    def execute(self, sql: str, params: Sequence[Any] = ()) -> int:
        with self._lock, self.session() as conn:
            cur = conn.execute(sql, params)
            return cur.rowcount

    def insert(self, table: str, data: dict) -> None:
        cols = ", ".join(data.keys())
        marks = ", ".join(["?"] * len(data))
        self.execute(f"INSERT INTO {table} ({cols}) VALUES ({marks})", tuple(data.values()))

    def update(self, table: str, row_id: str, data: dict) -> int:
        if not data:
            return 0
        sets = ", ".join(f"{key} = ?" for key in data)
        return self.execute(
            f"UPDATE {table} SET {sets} WHERE id = ?", tuple(data.values()) + (row_id,)
        )

    def delete(self, table: str, row_id: str) -> int:
        return self.execute(f"DELETE FROM {table} WHERE id = ?", (row_id,))

    # ---------- 审计 ----------
    def audit(self, action: str, detail: dict | None = None, actor: str = "本地用户") -> None:
        self.insert(
            "audit",
            {
                "ts": now_iso(),
                "action": action,
                "actor": actor,
                "detail": json.dumps(detail or {}, ensure_ascii=False),
            },
        )

    def list_audit(self, limit: int = 100) -> list[dict]:
        rows = self.query("SELECT * FROM audit ORDER BY id DESC LIMIT ?", (limit,))
        for row in rows:
            try:
                row["detail"] = json.loads(row["detail"])
            except (TypeError, ValueError):
                row["detail"] = {}
        return rows

    # ---------- 方案 ----------
    def next_plan_seq(self) -> int:
        row = self.query_one("SELECT COALESCE(MAX(seq), 0) + 1 AS next_seq FROM plans")
        return int((row or {}).get("next_seq") or 1)

    def save_plan(self, plan: dict) -> None:
        self.insert(
            "plans",
            {
                "id": plan["id"],
                "seq": int(plan.get("seq") or self.next_plan_seq()),
                "name": plan.get("name") or f"核算 #{plan.get('seq', '')}",
                "created_at": plan["created_at"],
                "as_of_date": plan["as_of_date"],
                "payload": json.dumps(plan, ensure_ascii=False),
            },
        )

    @staticmethod
    def _attach_plan_meta(payload: dict, row: dict) -> dict:
        payload.setdefault("seq", row.get("seq"))
        if not payload.get("name"):
            payload["name"] = row.get("name") or f"核算 #{row.get('seq')}"
        if payload.get("seq") is None:
            payload["seq"] = row.get("seq")
        return payload

    def get_plan(self, plan_id: str) -> dict | None:
        row = self.query_one("SELECT payload, seq, name FROM plans WHERE id = ?", (plan_id,))
        if not row:
            return None
        return self._attach_plan_meta(json.loads(row["payload"]), row)

    def list_plans(self, limit: int = 30) -> list[dict]:
        rows = self.query(
            "SELECT id, seq, name, created_at, as_of_date, payload FROM plans ORDER BY seq DESC LIMIT ?",
            (limit,),
        )
        result = []
        for row in rows:
            payload = json.loads(row["payload"])
            result.append(
                {
                    "id": row["id"],
                    "seq": row["seq"],
                    "name": row["name"] or f"核算 #{row['seq']}",
                    "created_at": row["created_at"],
                    "as_of_date": row["as_of_date"],
                    "summary": payload.get("summary", {}),
                }
            )
        return result

    def latest_plan(self) -> dict | None:
        row = self.query_one("SELECT payload, seq, name FROM plans ORDER BY seq DESC LIMIT 1")
        if not row:
            return None
        return self._attach_plan_meta(json.loads(row["payload"]), row)

    # ---------- 清空 ----------
    def clear_business_data(self) -> None:
        with self._lock, self.session() as conn:
            for table in ("debts", "entities", "materials", "plans", "audit"):
                conn.execute(f"DELETE FROM {table}")
