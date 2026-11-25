"""工作记录（Case）注册表。

每个工作记录拥有独立的 SQLite 数据库，债务、主体、材料、核算方案与审计
互不混用。注册表本身只保存工作记录的元数据和当前选中的记录，放在
data/cases.json。
"""
from __future__ import annotations

import json
import threading
from pathlib import Path

from .db import new_id, now_iso


class CaseRegistry:
    def __init__(self, data_dir: Path, default_db_path: Path):
        self.data_dir = Path(data_dir)
        self.default_db_path = Path(default_db_path)
        self.path = self.data_dir / "cases.json"
        self._lock = threading.RLock()
        self.data = self._load_or_bootstrap()

    # ---------- 持久化 ----------
    def _load_or_bootstrap(self) -> dict:
        if self.path.exists():
            try:
                data = json.loads(self.path.read_text(encoding="utf-8"))
                if isinstance(data, dict) and isinstance(data.get("cases"), list) and data["cases"]:
                    if not any(item.get("id") == data.get("active") for item in data["cases"]):
                        data["active"] = data["cases"][0]["id"]
                    return data
            except (OSError, ValueError):
                pass
        case = self._new_meta("工作记录 #1", 1)
        data = {"active": case["id"], "cases": [case]}
        self._save(data)
        return data

    def _save(self, data: dict | None = None) -> None:
        payload = data if data is not None else self.data
        self.data_dir.mkdir(parents=True, exist_ok=True)
        temp = self.path.with_suffix(".tmp")
        temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        temp.replace(self.path)

    def _new_meta(self, name: str, seq: int) -> dict:
        case_id = new_id("case")
        db_file = f"cases/{case_id}.db"
        if seq == 1:
            try:
                same_dir = self.default_db_path.resolve().parent == self.data_dir.resolve()
            except OSError:
                same_dir = False
            db_file = self.default_db_path.name if same_dir else str(self.default_db_path)
        timestamp = now_iso()
        return {
            "id": case_id,
            "seq": seq,
            "name": name,
            "db_file": db_file,
            "created_at": timestamp,
            "updated_at": timestamp,
        }

    # ---------- 查询 ----------
    def cases(self) -> list[dict]:
        with self._lock:
            return sorted(
                [dict(item) for item in self.data["cases"]],
                key=lambda item: int(item.get("seq") or 0),
            )

    def get(self, case_id: str | None = None) -> dict | None:
        with self._lock:
            target = case_id or self.data.get("active")
            for item in self.data["cases"]:
                if item.get("id") == target:
                    return dict(item)
            return None

    def active(self) -> dict:
        case = self.get()
        if not case:
            case = self.cases()[0]
            self.set_active(case["id"])
        return case

    def db_path(self, case: dict) -> Path:
        path = Path(case["db_file"])
        return path if path.is_absolute() else self.data_dir / path

    def public_case(self, case: dict) -> dict:
        return {
            "id": case["id"],
            "seq": case["seq"],
            "name": case["name"],
            "created_at": case.get("created_at"),
            "updated_at": case.get("updated_at"),
        }

    # ---------- 变更 ----------
    def set_active(self, case_id: str) -> dict:
        with self._lock:
            case = self.get(case_id)
            if not case:
                raise KeyError(case_id)
            self.data["active"] = case_id
            case["updated_at"] = now_iso()
            for index, item in enumerate(self.data["cases"]):
                if item["id"] == case_id:
                    self.data["cases"][index] = case
            self._save()
            return case

    def create(self, name: str | None = None) -> dict:
        with self._lock:
            seq = max([int(item.get("seq") or 0) for item in self.data["cases"]] + [0]) + 1
            case = self._new_meta((name or "").strip() or f"工作记录 #{seq}", seq)
            self.data["cases"].append(case)
            self._save()
            return case

    def touch(self, case_id: str) -> None:
        with self._lock:
            for index, item in enumerate(self.data["cases"]):
                if item["id"] == case_id:
                    item["updated_at"] = now_iso()
                    self.data["cases"][index] = item
                    self._save()
                    return
