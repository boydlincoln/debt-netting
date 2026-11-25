"""业务服务层：主体与债务台账、本体校验、净额轧差、材料抽取、导出与审计。"""
from __future__ import annotations

import hashlib
import json
import re
import threading
from collections import defaultdict
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from .cases import CaseRegistry
from .config import DB_PATH, EXPORT_DIR, MATERIAL_DIR, Settings
from .db import Database, new_id, now_iso
from .exports import (
    RISK_NOTES,
    export_agreement_docx,
    export_ledger_xlsx,
    export_plan_docx,
    export_plan_xlsx,
)
from .extract import (
    Masker,
    MaterialError,
    extract_text,
    local_extract,
    llm_extract,
    normalize_candidates,
    parse_amount_cents,
    parse_bool,
    parse_date,
)
from .graph import build_graph
from .llm import LLMClient, LLMError
from .netting import (
    build_liquidity_schedule,
    compute_positions,
    partition_zero_sum,
    settle_group,
)
from .ontology import DebtOntology, GROUP_LABELS, PRIORITY_GROUPS, get_ontology

GROUP_ORDER = ["ordinary", "mortgage", "wage", "tax", "custom"]
ALL_GROUP_LABEL = "全部债务（纯数学口径）"
MODE_LABELS = {
    "legal": "法律合规口径",
    "pure": "纯数学口径（忽略法规限制）",
}
PURE_RISK_NOTES = [
    "本方案为纯数学口径：忽略争议、查封冻结、到期状态、禁止抵销约定与优先顺位分组，全部非排除债务合并计算。",
    "纯数学结果只用于测算理论最少交易笔数与资金规模，不能作为清偿、抵销或签署协议的依据。",
]
STATUS_LABELS = {"confirmed": "已确认", "pending": "待复核", "rejected": "已排除"}


class ServiceError(RuntimeError):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


def yuan(cents: Any) -> float:
    return round(int(cents or 0) / 100, 2)


def _flag(value: Any) -> bool:
    return bool(int(value)) if isinstance(value, (int, str)) and str(value).isdigit() else bool(value)


class AppService:
    def __init__(
        self,
        db_path: Path | str = DB_PATH,
        settings: Settings | None = None,
        ontology: DebtOntology | None = None,
    ):
        self.db_path = Path(db_path)
        self.data_dir = self.db_path.parent
        self.registry = CaseRegistry(self.data_dir, self.db_path)
        self._case_lock = threading.RLock()
        self.case = self.registry.active()
        self.db = Database(self.registry.db_path(self.case))
        self.db.init()
        self.settings = settings or Settings()
        self.ontology = ontology or get_ontology()
        self.llm = LLMClient(self.settings)
        MATERIAL_DIR.mkdir(parents=True, exist_ok=True)
        EXPORT_DIR.mkdir(parents=True, exist_ok=True)

    # ================================================================== 工作记录
    def active_case(self) -> dict:
        return self.registry.public_case(self.case)

    def list_cases(self) -> List[dict]:
        result = []
        active_id = self.registry.active()["id"]
        for case in self.registry.cases():
            path = self.registry.db_path(case)
            item = self.registry.public_case(case)
            item["active"] = case["id"] == active_id
            try:
                if case["id"] == self.case["id"]:
                    db = self.db
                else:
                    db = Database(path)
                    db.init()
                entity_count = db.query_one("SELECT COUNT(*) AS n FROM entities")["n"]
                debt_count = db.query_one("SELECT COUNT(*) AS n FROM debts")["n"]
                material_count = db.query_one("SELECT COUNT(*) AS n FROM materials")["n"]
                plan_count = db.query_one("SELECT COUNT(*) AS n FROM plans")["n"]
                latest = db.latest_plan()
                item.update(
                    {
                        "entity_count": entity_count,
                        "debt_count": debt_count,
                        "material_count": material_count,
                        "plan_count": plan_count,
                        "latest_plan": (
                            {
                                "seq": latest.get("seq"),
                                "name": latest.get("name"),
                                "created_at": latest.get("created_at"),
                                "summary": latest.get("summary", {}),
                            }
                            if latest
                            else None
                        ),
                    }
                )
            except Exception:
                item.update(
                    {
                        "entity_count": 0,
                        "debt_count": 0,
                        "material_count": 0,
                        "plan_count": 0,
                        "latest_plan": None,
                        "broken": True,
                    }
                )
            result.append(item)
        return result

    def switch_case(self, case_id: str) -> dict:
        with self._case_lock:
            case = self.registry.get(case_id)
            if not case:
                raise ServiceError("工作记录不存在", 404)
            path = self.registry.db_path(case)
            if not path.exists():
                raise ServiceError("工作记录数据库文件不存在", 404)
            self.db = Database(path)
            self.db.init()
            self.case = self.registry.set_active(case_id)
            self.db.audit("case.open", {"case_id": case_id, "name": self.case.get("name")})
            return self.active_case()

    def create_case(self, name: str | None = None, with_demo: bool = False) -> dict:
        with self._case_lock:
            case = self.registry.create(name)
            path = self.registry.db_path(case)
            path.parent.mkdir(parents=True, exist_ok=True)
            db = Database(path)
            db.init()
            self.db = db
            self.case = self.registry.set_active(case["id"])
            if with_demo:
                self.seed_demo(force=True)
                self.run_netting("legal")
            else:
                self.db.audit("case.create", {"case_id": case["id"], "name": case.get("name")})
            return self.active_case()

    def rename_case(self, case_id: str, name: str) -> dict:
        with self._case_lock:
            if not self.registry.get(case_id):
                raise ServiceError("工作记录不存在", 404)
            clean = str(name or "").strip()
            if not clean:
                raise ServiceError("工作记录名称不能为空")
            # 直接修改注册表，避免依赖额外表
            for item in self.registry.data["cases"]:
                if item["id"] == case_id:
                    item["name"] = clean[:80]
            self.registry._save()
            if self.case["id"] == case_id:
                self.case = self.registry.active()
            return self.active_case() if self.case["id"] == case_id else self.registry.public_case(self.registry.get(case_id))

    def _touch_case(self) -> None:
        try:
            self.registry.touch(self.case["id"])
        except Exception:
            pass

    # ================================================================== 序列化
    def _entities_raw(self) -> List[dict]:
        return self.db.query("SELECT e.*, e.rowid AS seq FROM entities e ORDER BY e.rowid")

    def _entity_public(self, row: dict) -> dict:
        data = dict(row)
        data["available_cash"] = yuan(data.get("available_cash_cents"))
        data["available_cash_cents"] = int(data.get("available_cash_cents") or 0)
        data["litigation"] = bool(data.get("litigation"))
        data["enforced"] = bool(data.get("enforced"))
        return data

    def _debt_rows(self) -> List[dict]:
        return self.db.query(
            """
            SELECT d.*, d.rowid AS seq,
                   de.name AS debtor_name, ce.name AS creditor_name
            FROM debts d
            LEFT JOIN entities de ON de.id = d.debtor_id
            LEFT JOIN entities ce ON ce.id = d.creditor_id
            ORDER BY d.rowid
            """
        )

    def _debt_public(self, row: dict, evaluation: dict) -> dict:
        data = {
            "id": row["id"],
            "seq": row.get("seq"),
            "debtor_id": row["debtor_id"],
            "creditor_id": row["creditor_id"],
            "debtor_name": row.get("debtor_name") or row["debtor_id"],
            "creditor_name": row.get("creditor_name") or row["creditor_id"],
            "principal": yuan(row.get("principal_cents")),
            "interest": yuan(row.get("interest_cents")),
            "amount": yuan(row.get("amount_cents")),
            "principal_cents": int(row.get("principal_cents") or 0),
            "interest_cents": int(row.get("interest_cents") or 0),
            "amount_cents": int(row.get("amount_cents") or 0),
            "due_date": row.get("due_date") or "",
            "disputed": bool(row.get("disputed")),
            "frozen": bool(row.get("frozen")),
            "no_setoff_clause": bool(row.get("no_setoff_clause")),
            "priority_group": row.get("priority_group") or "ordinary",
            "priority_label": GROUP_LABELS.get(row.get("priority_group") or "ordinary", row.get("priority_group") or "ordinary"),
            "status": row.get("status") or "confirmed",
            "status_label": STATUS_LABELS.get(row.get("status"), row.get("status")),
            "source": row.get("source") or "manual",
            "source_label": {"manual": "人工录入", "ai": "AI 抽取", "import": "批量导入"}.get(row.get("source"), row.get("source")),
            "material_id": row.get("material_id"),
            "note": row.get("note") or "",
            "created_at": row.get("created_at"),
            "updated_at": row.get("updated_at"),
            "eligibility": evaluation,
        }
        return data

    def _evaluate(self, rows: Iterable[dict]) -> Dict[str, dict]:
        as_of = self.settings.as_of_date()
        return {row["id"]: self.ontology.evaluate(row, as_of) for row in rows}

    # ================================================================== 概览
    def dashboard(self) -> dict:
        entities = self._entities_raw()
        rows = self._debt_rows()
        evaluations = self._evaluate(rows)
        confirmed = [row for row in rows if row.get("status") == "confirmed"]
        eligible = [row for row in confirmed if evaluations[row["id"]]["eligible"]]
        pending = [row for row in rows if row.get("status") == "pending"]
        excluded = [row for row in confirmed if not evaluations[row["id"]]["eligible"]]
        total_amount = sum(int(row.get("amount_cents") or 0) for row in rows)
        pool_amount = sum(int(row.get("amount_cents") or 0) for row in eligible)
        latest = self.db.latest_plan()
        return {
            "as_of_date": self.settings.as_of_date(),
            "entities": len(entities),
            "debts": {
                "total": len(rows),
                "confirmed": len(confirmed),
                "pending": len(pending),
                "rejected": sum(1 for row in rows if row.get("status") == "rejected"),
                "eligible": len(eligible),
                "excluded": len(excluded),
            },
            "amount": {
                "total": yuan(total_amount),
                "eligible": yuan(pool_amount),
                "total_cents": total_amount,
                "eligible_cents": pool_amount,
            },
            "latest_plan": (
                {
                    "id": latest["id"],
                    "seq": latest.get("seq"),
                    "name": latest.get("name"),
                    "created_at": latest["created_at"],
                    "as_of_date": latest["as_of_date"],
                    "summary": latest.get("summary", {}),
                }
                if latest
                else None
            ),
            "plan_count": len(self.db.list_plans(limit=1000)),
            "ontology": self.ontology.health(),
            "rules": self.ontology.rules_catalog(),
            "recent_audit": self.db.list_audit(8),
            "active_case": self.active_case(),
            "case_count": len(self.registry.cases()),
            "settings": self.settings.public(),
        }

    # ================================================================== 主体
    def list_entities(self) -> List[dict]:
        return [self._entity_public(row) for row in self._entities_raw()]

    def _entity_row(self, entity_id: str) -> dict:
        row = self.db.query_one("SELECT e.*, e.rowid AS seq FROM entities e WHERE id = ?", (entity_id,))
        if not row:
            raise ServiceError("主体不存在", 404)
        return row

    def _entity_payload(self, payload: dict, partial: bool = False) -> dict:
        name = str(payload.get("name") or "").strip()
        if not name and not partial:
            raise ServiceError("主体名称不能为空")
        data: dict[str, Any] = {}
        if name:
            data["name"] = name
        for field in ("credit_code", "account", "status", "note"):
            if field in payload:
                data[field] = str(payload.get(field) or "").strip()
        for field in ("litigation", "enforced"):
            if field in payload:
                data[field] = 1 if bool(payload.get(field)) else 0
        if "available_cash" in payload:
            cents = parse_amount_cents(payload.get("available_cash"))
            data["available_cash_cents"] = max(0, cents or 0)
        return data

    def create_entity(self, payload: dict) -> dict:
        data = self._entity_payload(payload)
        data.setdefault("credit_code", "")
        data.setdefault("account", "")
        data.setdefault("status", "正常经营")
        data.setdefault("available_cash_cents", 0)
        data.setdefault("litigation", 0)
        data.setdefault("enforced", 0)
        data.setdefault("note", "")
        data["id"] = new_id("ent")
        data["created_at"] = data["updated_at"] = now_iso()
        self.db.insert("entities", data)
        self.db.audit("entity.create", {"id": data["id"], "name": data["name"]})
        return self._entity_public(self._entity_row(data["id"]))

    def update_entity(self, entity_id: str, payload: dict) -> dict:
        self._entity_row(entity_id)
        data = self._entity_payload(payload, partial=True)
        if not data:
            return self._entity_public(self._entity_row(entity_id))
        data["updated_at"] = now_iso()
        self.db.update("entities", entity_id, data)
        self.db.audit("entity.update", {"id": entity_id, "fields": list(data.keys())})
        return self._entity_public(self._entity_row(entity_id))

    def delete_entity(self, entity_id: str, cascade: bool = False) -> dict:
        self._entity_row(entity_id)
        related = self.db.query(
            "SELECT id FROM debts WHERE debtor_id = ? OR creditor_id = ?", (entity_id, entity_id)
        )
        if related and not cascade:
            raise ServiceError(f"该主体存在 {len(related)} 笔债务，需先删除债务或选择级联删除", 409)
        for row in related:
            self.db.delete("debts", row["id"])
        self.db.delete("entities", entity_id)
        self.db.audit("entity.delete", {"id": entity_id, "cascade_debts": len(related)})
        return {"deleted": entity_id, "debts_deleted": len(related)}

    # ================================================================== 债务
    def list_debts(self, status: str = "", group: str = "", keyword: str = "") -> List[dict]:
        rows = self._debt_rows()
        evaluations = self._evaluate(rows)
        result = []
        keyword = (keyword or "").strip()
        for row in rows:
            if status and row.get("status") != status:
                continue
            if group and (row.get("priority_group") or "ordinary") != group:
                continue
            if keyword:
                haystack = f"{row.get('debtor_name') or ''}{row.get('creditor_name') or ''}{row.get('note') or ''}{row['id']}"
                if keyword not in haystack:
                    continue
            result.append(self._debt_public(row, evaluations[row["id"]]))
        return result

    def get_debt(self, debt_id: str) -> dict:
        row = self.db.query_one(
            """
            SELECT d.*, d.rowid AS seq, de.name AS debtor_name, ce.name AS creditor_name
            FROM debts d
            LEFT JOIN entities de ON de.id = d.debtor_id
            LEFT JOIN entities ce ON ce.id = d.creditor_id
            WHERE d.id = ?
            """,
            (debt_id,),
        )
        if not row:
            raise ServiceError("债务不存在", 404)
        return self._debt_public(row, self.ontology.evaluate(row, self.settings.as_of_date()))

    def _debt_payload(self, payload: dict, partial: bool = False) -> dict:
        data: dict[str, Any] = {}
        for field in ("debtor_id", "creditor_id"):
            if field in payload:
                value = str(payload.get(field) or "").strip()
                if value:
                    self._entity_row(value)
                data[field] = value
        if not partial:
            if not data.get("debtor_id") or not data.get("creditor_id"):
                raise ServiceError("债务人和债权人均不能为空")

        amount_cents = parse_amount_cents(payload.get("amount")) if "amount" in payload else None
        principal_cents = parse_amount_cents(payload.get("principal")) if "principal" in payload else None
        interest_cents = parse_amount_cents(payload.get("interest")) if "interest" in payload else None

        if "amount" in payload or "principal" in payload or "interest" in payload:
            principal_cents = principal_cents if principal_cents is not None else 0
            interest_cents = interest_cents if interest_cents is not None else 0
            if amount_cents is None:
                amount_cents = principal_cents + interest_cents
            if principal_cents == 0 and interest_cents == 0 and amount_cents:
                principal_cents = amount_cents
            if amount_cents <= 0:
                raise ServiceError("债务金额必须大于零")
            data["amount_cents"] = amount_cents
            data["principal_cents"] = principal_cents
            data["interest_cents"] = interest_cents

        if "due_date" in payload:
            raw = payload.get("due_date")
            if raw:
                parsed = parse_date(raw)
                if not parsed:
                    raise ServiceError("到期日格式无法识别，请使用 YYYY-MM-DD")
                data["due_date"] = parsed
            else:
                data["due_date"] = ""

        for field in ("disputed", "frozen", "no_setoff_clause"):
            if field in payload:
                data[field] = 1 if bool(payload.get(field)) else 0
        if "priority_group" in payload:
            group = str(payload.get("priority_group") or "ordinary")
            if group not in GROUP_LABELS:
                raise ServiceError("未知的债权顺位分组")
            data["priority_group"] = group
        if "note" in payload:
            data["note"] = str(payload.get("note") or "").strip()
        if "status" in payload and payload.get("status") in STATUS_LABELS:
            data["status"] = payload["status"]
        return data

    def create_debt(self, payload: dict) -> dict:
        data = self._debt_payload(payload)
        data.setdefault("principal_cents", data.get("amount_cents", 0))
        data.setdefault("interest_cents", 0)
        data.setdefault("amount_cents", (data.get("principal_cents") or 0) + (data.get("interest_cents") or 0))
        data.setdefault("due_date", "")
        data.setdefault("disputed", 0)
        data.setdefault("frozen", 0)
        data.setdefault("no_setoff_clause", 0)
        data.setdefault("priority_group", "ordinary")
        data.setdefault("note", "")
        data.setdefault("status", "confirmed")
        data.setdefault("source", "manual")
        data["id"] = new_id("debt")
        data["created_at"] = data["updated_at"] = now_iso()
        self.db.insert("debts", data)
        self.db.audit(
            "debt.create",
            {"id": data["id"], "debtor": data["debtor_id"], "creditor": data["creditor_id"], "amount_cents": data["amount_cents"]},
        )
        return self.get_debt(data["id"])

    def update_debt(self, debt_id: str, payload: dict) -> dict:
        self.get_debt(debt_id)
        data = self._debt_payload(payload, partial=True)
        if not data:
            return self.get_debt(debt_id)
        data["updated_at"] = now_iso()
        self.db.update("debts", debt_id, data)
        self.db.audit("debt.update", {"id": debt_id, "fields": list(data.keys())})
        return self.get_debt(debt_id)

    def delete_debt(self, debt_id: str) -> dict:
        self.get_debt(debt_id)
        self.db.delete("debts", debt_id)
        self.db.audit("debt.delete", {"id": debt_id})
        return {"deleted": debt_id}

    def set_debt_status(self, debt_id: str, status: str) -> dict:
        if status not in STATUS_LABELS:
            raise ServiceError("未知的确认状态")
        self.get_debt(debt_id)
        self.db.update("debts", debt_id, {"status": status, "updated_at": now_iso()})
        self.db.audit(f"debt.{status}", {"id": debt_id})
        return self.get_debt(debt_id)

    def recheck_eligibility(self) -> dict:
        rows = self._debt_rows()
        evaluations = self._evaluate(rows)
        eligible = sum(1 for evaluation in evaluations.values() if evaluation["eligible"])
        blocked = sum(1 for evaluation in evaluations.values() if evaluation["blocking"])
        review = sum(1 for evaluation in evaluations.values() if evaluation["review"])
        self.db.audit("eligibility.recheck", {"debts": len(rows), "eligible": eligible})
        return {"total": len(rows), "eligible": eligible, "blocked": blocked, "review": review}

    # ================================================================== 轧差
    def run_netting(self, mode: str = "legal") -> dict:
        if mode not in MODE_LABELS:
            raise ServiceError("未知的计算口径")
        settings = self.settings.data
        as_of = self.settings.as_of_date()
        rows = self._debt_rows()
        evaluations = self._evaluate(rows)
        entities = {row["id"]: row for row in self._entities_raw()}
        entity_order = {entity_id: row["seq"] for entity_id, row in entities.items()}

        included: List[tuple[dict, dict]] = []
        excluded: List[dict] = []
        if mode == "pure":
            # 纯数学口径：只排除人工明确排除的债务；忽略抵销规则、到期、查封与优先分组
            for row in rows:
                amount_cents = int(row.get("amount_cents") or 0)
                reasons: List[str] = []
                if row.get("status") == "rejected":
                    reasons.append("已被人为排除，纯数学口径也不纳入")
                if amount_cents <= 0:
                    reasons.append("债务金额无效")
                if not row.get("debtor_id") or not row.get("creditor_id"):
                    reasons.append("债权债务主体不完整")
                if reasons:
                    excluded.append(
                        {
                            "debt_id": row["id"],
                            "debtor_name": row.get("debtor_name") or row["debtor_id"],
                            "creditor_name": row.get("creditor_name") or row["creditor_id"],
                            "amount": yuan(row.get("amount_cents")),
                            "amount_cents": amount_cents,
                            "due_date": row.get("due_date") or "",
                            "group_code": "all",
                            "group_label": ALL_GROUP_LABEL,
                            "status": row.get("status"),
                            "status_label": STATUS_LABELS.get(row.get("status"), row.get("status")),
                            "source": row.get("source"),
                            "reasons": reasons,
                            "rule_ids": [],
                            "blocking": [],
                            "review": [],
                        }
                    )
                else:
                    included.append(
                        (
                            row,
                            {
                                "eligible": True,
                                "group_code": "all",
                                "group_label": ALL_GROUP_LABEL,
                                "blocking": [],
                                "review": [],
                            },
                        )
                    )
        else:
            for row in rows:
                evaluation = evaluations[row["id"]]
                reasons: List[str] = []
                rule_ids: List[str] = []
                if row.get("status") == "pending":
                    reasons.append("债务尚未确认，待人工复核")
                elif row.get("status") == "rejected":
                    reasons.append("已被人为排除，不参与轧差")
                if not evaluation["eligible"]:
                    reasons.extend(item["message"] for item in evaluation["blocking"] + evaluation["review"])
                    rule_ids.extend(item["rule_id"] for item in evaluation["blocking"] + evaluation["review"])
                if (
                    evaluation["eligible"]
                    and row.get("status") == "confirmed"
                    and evaluation["group_code"] in PRIORITY_GROUPS
                    and not settings.get("include_priority_groups", True)
                ):
                    reasons.append("优先顺位分组未启用独立轧差")
                if reasons:
                    excluded.append(
                        {
                            "debt_id": row["id"],
                            "debtor_name": row.get("debtor_name") or row["debtor_id"],
                            "creditor_name": row.get("creditor_name") or row["creditor_id"],
                            "amount": yuan(row.get("amount_cents")),
                            "amount_cents": int(row.get("amount_cents") or 0),
                            "due_date": row.get("due_date") or "",
                            "group_code": evaluation["group_code"],
                            "group_label": evaluation["group_label"],
                            "status": row.get("status"),
                            "status_label": STATUS_LABELS.get(row.get("status"), row.get("status")),
                            "source": row.get("source"),
                            "reasons": list(dict.fromkeys(reasons)),
                            "rule_ids": list(dict.fromkeys(rule_ids)),
                            "blocking": evaluation["blocking"],
                            "review": evaluation["review"],
                        }
                    )
                else:
                    included.append((row, evaluation))

        grouped: Dict[str, List[tuple[dict, dict]]] = defaultdict(list)
        for row, evaluation in included:
            grouped[evaluation["group_code"]].append((row, evaluation))

        ordered_groups = [code for code in GROUP_ORDER if code in grouped]
        ordered_groups += sorted(code for code in grouped if code not in GROUP_ORDER)

        groups: List[dict] = []
        all_transactions: List[dict] = []
        all_participants: List[dict] = []
        checks: List[dict] = []
        total_tx_cents = 0
        proven_all = True
        doc_lower_bound = 0
        theoretical_min = 0

        for code in ordered_groups:
            items = grouped[code]
            debts_in_group = [row for row, _ in items]
            positions = compute_positions(debts_in_group)
            participants = []
            for entity_id, position in positions.items():
                net = int(position["net_cents"])
                zero_out = net == 0
                participant = {
                    "id": entity_id,
                    "name": (entities.get(entity_id) or {}).get("name") or entity_id,
                    "receivable_cents": int(position["receivable_cents"]),
                    "payable_cents": int(position["payable_cents"]),
                    "net_cents": net,
                    "net": yuan(net),
                    "role": position["role"],
                    "role_label": {"debtor": "净债务人", "creditor": "净债权人", "zero": "头寸归零"}[position["role"]],
                    "zero_out": zero_out,
                }
                participants.append(participant)
            participants.sort(key=lambda item: entity_order.get(item["id"], 10**9))

            net_items = [(item["id"], item["net_cents"]) for item in participants if item["net_cents"] != 0]
            m = sum(1 for _, amount in net_items if amount < 0)
            n = sum(1 for _, amount in net_items if amount > 0)
            partition = partition_zero_sum(
                net_items, seconds=float(settings.get("exact_solver_seconds", 3.0))
            )
            if not partition.proven:
                proven_all = False

            transactions: List[dict] = []
            for zero_sum_group in partition.groups:
                for tx in settle_group(zero_sum_group, entity_order):
                    transactions.append(tx)
            for tx in transactions:
                total_tx_cents += int(tx["amount_cents"])

            lower_bound = max(0, m + n - 1)
            doc_lower_bound += lower_bound
            theoretical_min += len(net_items) - len(partition.groups)

            outflow: Dict[str, int] = defaultdict(int)
            inflow: Dict[str, int] = defaultdict(int)
            for tx in transactions:
                outflow[tx["from"]] += int(tx["amount_cents"])
                inflow[tx["to"]] += int(tx["amount_cents"])

            group_checks = []
            total_receivable = sum(item["receivable_cents"] for item in participants)
            total_payable = sum(item["payable_cents"] for item in participants)
            group_checks.append(
                {
                    "name": "分组内应收与应付合计相等",
                    "ok": total_receivable == total_payable,
                    "detail": f"应收 {yuan(total_receivable):,.2f} 元 / 应付 {yuan(total_payable):,.2f} 元",
                }
            )
            balance_ok = True
            for participant in participants:
                if participant["role"] == "debtor" and outflow[participant["id"]] != -participant["net_cents"]:
                    balance_ok = False
                if participant["role"] == "creditor" and inflow[participant["id"]] != participant["net_cents"]:
                    balance_ok = False
                if participant["role"] == "zero" and (
                    outflow[participant["id"]] or inflow[participant["id"]]
                ):
                    balance_ok = False
            group_checks.append(
                {
                    "name": "各主体收付与净头寸一致",
                    "ok": balance_ok,
                    "detail": "净债务人付出等于净负债，净债权人收回等于净债权",
                }
            )
            group_checks.append(
                {
                    "name": "交易金额守恒",
                    "ok": sum(outflow.values()) == sum(inflow.values()) == total_payable,
                    "detail": f"交易合计 {yuan(sum(outflow.values())):,.2f} 元",
                }
            )
            group_checks.append(
                {
                    "name": "头寸归零主体未参与交易",
                    "ok": all(
                        item["id"] not in outflow and item["id"] not in inflow
                        for item in participants
                        if item["role"] == "zero"
                    ),
                    "detail": f"归零出局 {sum(1 for item in participants if item['role'] == 'zero')} 个",
                }
            )
            if partition.proven:
                expected_min = len(net_items) - len(partition.groups)
                group_checks.append(
                    {
                        "name": "交易笔数达到可证明的最少笔数",
                        "ok": len(transactions) == expected_min,
                        "detail": f"实际 {len(transactions)} 笔，理论 {expected_min} 笔",
                    }
                )

            group_label = ALL_GROUP_LABEL if code == "all" else GROUP_LABELS.get(code, code)
            group_result = {
                "code": code,
                "label": group_label,
                "debt_ids": [row["id"] for row in debts_in_group],
                "debt_count": len(debts_in_group),
                "m": m,
                "n": n,
                "participants": participants,
                "zero_out": [item for item in participants if item["role"] == "zero"],
                "transactions": [],
                "lower_bound": lower_bound,
                "theoretical_min": len(net_items) - len(partition.groups),
                "zero_sum_groups": [[participant_id for participant_id, _ in group] for group in partition.groups],
                "optimality": "proven" if partition.proven else "heuristic",
                "total_receivable_cents": total_receivable,
                "total_payable_cents": total_payable,
                "checks": group_checks,
                "group_count": len(partition.groups),
            }
            groups.append(group_result)
            all_participants.extend(participants)

            for tx in transactions:
                tx["seq"] = len(all_transactions) + 1
                tx["group_code"] = code
                tx["group_label"] = group_label
                tx["from_name"] = (entities.get(tx["from"]) or {}).get("name") or tx["from"]
                tx["to_name"] = (entities.get(tx["to"]) or {}).get("name") or tx["to"]
                tx["amount"] = yuan(tx["amount_cents"])
                all_transactions.append(tx)
            group_result["transactions"] = [
                tx for tx in all_transactions if tx["group_code"] == code
            ]

        # ---------------- 方案级校验
        pool_cents = sum(int(row.get("amount_cents") or 0) for row, _ in included)
        net_payable_cents = sum(
            -item["net_cents"] for item in all_participants if item["net_cents"] < 0
        )
        checks.append(
            {
                "name": "全部纳入债务已抵销结清",
                "ok": len(included) + len(excluded) == len(rows),
                "detail": f"纳入 {len(included)} 笔，未入池 {len(excluded)} 笔，台账合计 {len(rows)} 笔",
            }
        )
        checks.append(
            {
                "name": "清偿金额守恒",
                "ok": total_tx_cents == net_payable_cents,
                "detail": f"交易合计 {yuan(total_tx_cents):,.2f} 元，净债务合计 {yuan(net_payable_cents):,.2f} 元",
            }
        )
        checks.append(
            {
                "name": "分组隔离",
                "ok": all(
                    sum(item["net_cents"] for item in group["participants"]) == 0
                    for group in groups
                ),
                "detail": "；".join(f"{group['label']} {len(group['debt_ids'])} 笔" for group in groups) or "无",
            }
        )
        checks.append(
            {
                "name": "交易对手方不同",
                "ok": all(tx["from"] != tx["to"] for tx in all_transactions),
                "detail": f"共 {len(all_transactions)} 笔交易",
            }
        )
        checks.append(
            {
                "name": "交易笔数最优性",
                "ok": (not proven_all) or len(all_transactions) == theoretical_min,
                "detail": (
                    f"实际 {len(all_transactions)} 笔，"
                    + (f"理论最少 {theoretical_min} 笔" if proven_all else "时间预算内未完成最优性证明（启发式）")
                ),
            }
        )

        liquidity = self._liquidity(all_transactions, entities, as_of)
        total_tx = len(all_transactions)
        overall_positions = compute_positions([row for row, _ in included])
        overall_debtors = {
            entity_id for entity_id, position in overall_positions.items() if position["role"] == "debtor"
        }
        overall_creditors = {
            entity_id for entity_id, position in overall_positions.items() if position["role"] == "creditor"
        }
        overall_zero = {
            entity_id for entity_id, position in overall_positions.items()
            if position["role"] == "zero" and (position["receivable_cents"] or position["payable_cents"])
        }
        summary = {
            "mode": mode,
            "mode_label": MODE_LABELS[mode],
            "entity_count": len(overall_positions),
            "debt_count": len(rows),
            "included_count": len(included),
            "excluded_count": len(excluded),
            "pending_count": sum(1 for row in rows if row.get("status") == "pending"),
            "transaction_count": total_tx,
            "transaction_amount": yuan(total_tx_cents),
            "transaction_amount_cents": total_tx_cents,
            "pool_amount": yuan(pool_cents),
            "pool_amount_cents": pool_cents,
            "zero_out_count": len(overall_zero),
            "debtor_count": len(overall_debtors),
            "creditor_count": len(overall_creditors),
            "group_count": len(groups),
            "optimality": "proven" if proven_all else "heuristic",
            "doc_lower_bound": doc_lower_bound,
            "theoretical_min": theoretical_min,
        }

        seq = self.db.next_plan_seq()
        plan_name = f"核算 #{seq}"
        included_ids = {row["id"] for row, _ in included}
        excluded_by_id = {item["debt_id"]: item for item in excluded}
        debt_snapshot = []
        for row in rows:
            evaluation = evaluations[row["id"]]
            excluded_item = excluded_by_id.get(row["id"])
            legal_reasons = [
                item["message"] for item in evaluation.get("blocking", []) + evaluation.get("review", [])
            ]
            debt_snapshot.append(
                {
                    "id": row["id"],
                    "debtor_id": row["debtor_id"],
                    "creditor_id": row["creditor_id"],
                    "debtor_name": row.get("debtor_name") or row["debtor_id"],
                    "creditor_name": row.get("creditor_name") or row["creditor_id"],
                    "amount": yuan(row.get("amount_cents")),
                    "amount_cents": int(row.get("amount_cents") or 0),
                    "due_date": row.get("due_date") or "",
                    "priority_group": row.get("priority_group") or "ordinary",
                    "group_code": "all" if mode == "pure" else evaluation["group_code"],
                    "group_label": ALL_GROUP_LABEL if mode == "pure" else evaluation["group_label"],
                    "status": row.get("status") or "confirmed",
                    "status_label": STATUS_LABELS.get(row.get("status"), row.get("status")),
                    "source": row.get("source") or "manual",
                    "note": row.get("note") or "",
                    "included": row["id"] in included_ids,
                    "legal_eligible": bool(evaluation.get("eligible")),
                    "legal_reasons": legal_reasons,
                    "reasons": excluded_item.get("reasons", []) if excluded_item else [],
                    "rule_ids": excluded_item.get("rule_ids", []) if excluded_item else [],
                }
            )

        summary["seq"] = seq
        summary["name"] = plan_name
        plan = {
            "id": new_id("plan"),
            "seq": seq,
            "name": plan_name,
            "created_at": datetime.now().astimezone().isoformat(timespec="milliseconds"),
            "as_of_date": as_of,
            "mode": mode,
            "mode_label": MODE_LABELS[mode],
            "settings": {
                "mode": mode,
                "include_priority_groups": bool(settings.get("include_priority_groups", True)),
                "exact_solver_seconds": float(settings.get("exact_solver_seconds", 3.0)),
            },
            "summary": summary,
            "groups": groups,
            "transactions": all_transactions,
            "debt_snapshot": debt_snapshot,
            "included_debts": [
                {
                    "id": row["id"],
                    "debtor_name": row.get("debtor_name") or row["debtor_id"],
                    "creditor_name": row.get("creditor_name") or row["creditor_id"],
                    "amount": yuan(row.get("amount_cents")),
                    "amount_cents": int(row.get("amount_cents") or 0),
                    "due_date": row.get("due_date") or "",
                    "group_code": evaluation["group_code"],
                    "group_label": evaluation["group_label"],
                    "note": row.get("note") or "",
                }
                for row, evaluation in included
            ],
            "excluded": excluded,
            "checks": checks,
            "liquidity": liquidity,
            "risk_notes": RISK_NOTES + (PURE_RISK_NOTES if mode == "pure" else []),
            "entities": [
                {
                    "id": entity_id,
                    "name": (entities.get(entity_id) or {}).get("name") or entity_id,
                    "available_cash_cents": int((entities.get(entity_id) or {}).get("available_cash_cents") or 0),
                    "available_cash": yuan((entities.get(entity_id) or {}).get("available_cash_cents")),
                }
                for entity_id in {item["id"] for item in all_participants}
            ],
        }
        self.db.save_plan(plan)
        self.db.audit(
            "netting.run",
            {
                "plan_id": plan["id"],
                "seq": seq,
                "name": plan_name,
                "transactions": total_tx,
                "included": len(included),
                "excluded": len(excluded),
                "optimality": summary["optimality"],
            },
        )
        return plan

    def compare_netting(self) -> dict:
        """同时计算法律合规口径与纯数学口径，供使用者对照；纯口径方案不能用于签署协议。"""
        pure = self.run_netting("pure")
        legal = self.run_netting("legal")
        legal_excluded = {item["debt_id"]: item for item in legal.get("excluded", [])}
        pure_included = {item["id"]: item for item in pure.get("included_debts", [])}
        adjusted = []
        for debt_id, item in pure_included.items():
            if debt_id in legal_excluded:
                excluded_item = legal_excluded[debt_id]
                adjusted.append(
                    {
                        **item,
                        "legal_reasons": excluded_item.get("reasons", []),
                        "rule_ids": excluded_item.get("rule_ids", []),
                    }
                )
        comparison = {
            "transaction_count": {
                "legal": legal["summary"]["transaction_count"],
                "pure": pure["summary"]["transaction_count"],
                "difference": pure["summary"]["transaction_count"] - legal["summary"]["transaction_count"],
            },
            "amount_cents": {
                "legal": legal["summary"]["transaction_amount_cents"],
                "pure": pure["summary"]["transaction_amount_cents"],
                "difference": pure["summary"]["transaction_amount_cents"] - legal["summary"]["transaction_amount_cents"],
            },
            "included_count": {
                "legal": legal["summary"]["included_count"],
                "pure": pure["summary"]["included_count"],
            },
            "excluded_count": {
                "legal": legal["summary"]["excluded_count"],
                "pure": pure["summary"]["excluded_count"],
            },
            "adjusted_debts": adjusted,
        }
        self.db.audit(
            "netting.compare",
            {
                "legal_plan": legal["id"],
                "pure_plan": pure["id"],
                "legal_tx": legal["summary"]["transaction_count"],
                "pure_tx": pure["summary"]["transaction_count"],
            },
        )
        return {"legal": legal, "pure": pure, "comparison": comparison}

    def _liquidity(self, transactions: List[dict], entities: Dict[str, dict], as_of: str) -> dict:
        settings = self.settings.data.get("installments") or {}
        schedule = []
        if settings.get("enabled", True):
            schedule = build_liquidity_schedule(
                transactions,
                {},
                entities,
                period_days=int(settings.get("period_days", 30)),
                periods=int(settings.get("periods", 3)),
                base_date=as_of,
            )
        payables: Dict[str, int] = defaultdict(int)
        for tx in transactions:
            payables[tx["from"]] += int(tx["amount_cents"])
        constrained = []
        for entity_id, payable in payables.items():
            cash = int((entities.get(entity_id) or {}).get("available_cash_cents") or 0)
            if cash < payable:
                constrained.append(
                    {
                        "id": entity_id,
                        "name": (entities.get(entity_id) or {}).get("name") or entity_id,
                        "payable_cents": payable,
                        "available_cash_cents": cash,
                        "shortfall_cents": payable - cash,
                    }
                )
        for item in schedule:
            item["payer_name"] = (entities.get(item["payer"]) or {}).get("name") or item["payer"]
            item["payee_name"] = (entities.get(item["payee"]) or {}).get("name") or item["payee"]
            item["amount"] = yuan(item["amount_cents"])
        constrained.sort(key=lambda item: -item["shortfall_cents"])
        return {
            "constrained": constrained,
            "schedule": schedule,
            "total_shortfall_cents": sum(item["shortfall_cents"] for item in constrained),
            "enabled": bool(settings.get("enabled", True)),
            "periods": int(settings.get("periods", 3)),
            "period_days": int(settings.get("period_days", 30)),
        }

    # ================================================================== 方案
    def list_plans(self) -> List[dict]:
        return self.db.list_plans(500)

    def get_plan(self, plan_id: str | None = None) -> dict:
        plan = self.db.get_plan(plan_id) if plan_id else self.db.latest_plan()
        if not plan:
            raise ServiceError("尚未生成清偿方案", 404)
        return plan

    def delete_plan(self, plan_id: str) -> dict:
        if not self.db.get_plan(plan_id):
            raise ServiceError("方案不存在", 404)
        self.db.delete("plans", plan_id)
        self.db.audit("plan.delete", {"id": plan_id})
        return {"deleted": plan_id}

    def generate_narrative(self, plan_id: str | None = None) -> dict:
        """仅将已算出的数字方案交给线上模型做文字加工，不回传原始合同文本。"""
        plan = self.get_plan(plan_id)
        if not self.llm.configured():
            raise ServiceError("线上模型未启用或未配置密钥，无法生成 AI 解读；可继续使用本地导出的报告模板。")
        payload = {
            "基准日": plan["as_of_date"],
            "方案摘要": plan["summary"],
            "清偿清单": [
                {
                    "序号": tx["seq"],
                    "付款方": tx["from_name"],
                    "收款方": tx["to_name"],
                    "金额_元": tx["amount"],
                }
                for tx in plan["transactions"]
            ],
            "未入池债务数": len(plan.get("excluded", [])),
            "校验结果": [{"校验项": check["name"], "是否通过": check["ok"]} for check in plan.get("checks", [])],
        }
        system_prompt = (
            "你是债务重组方案说明撰写助手。只依据用户提供的数字方案撰写一段中文解读，"
            "不得修改任何金额、交易笔数、主体名称或清偿方向，不得新增未提供的数字。"
            "内容需说明方案如何消除三角债链条、为什么交易笔数最少、未入池债务的风险，"
            "并提醒签署多方抵销协议及法务终审。只输出 JSON：{\"narrative\": \"正文\"}。"
        )
        user_prompt = (
            "以下是本地求解器已经算好的方案，请据此撰写解读：\n"
            + json.dumps(payload, ensure_ascii=False)
        )
        try:
            response = self.llm.chat_json(system_prompt, user_prompt, max_tokens=2000)
        except LLMError as exc:
            raise ServiceError(str(exc), 502) from exc
        narrative = str(response.get("narrative") or "").strip()
        if not narrative:
            raise ServiceError("线上模型未返回有效解读文本", 502)
        plan["ai_narrative"] = {
            "content": narrative,
            "created_at": now_iso(),
            "model": self.llm.config().get("model") or "",
            "provider": self.llm.config().get("provider") or "",
        }
        self.db.update("plans", plan["id"], {"payload": json.dumps(plan, ensure_ascii=False)})
        self.db.audit("plan.narrative", {"plan_id": plan["id"], "chars": len(narrative)})
        return {"plan_id": plan["id"], "narrative": narrative, "created_at": plan["ai_narrative"]["created_at"]}

    # ================================================================== 图谱
    def graph(self, include_ineligible: bool = True) -> dict:
        rows = self._debt_rows()
        evaluations = self._evaluate(rows)
        entities = self._entities_raw()
        result = build_graph(entities, rows, evaluations, include_ineligible=include_ineligible)
        return result

    # ================================================================== 材料与抽取
    def _store_material(self, filename: str, data: bytes, text: str, meta: dict) -> dict:
        material_id = new_id("mat")
        suffix = Path(filename or "").suffix.lower()
        stored_name = f"{material_id}{suffix}"
        path = MATERIAL_DIR / stored_name
        path.write_bytes(data)
        record = {
            "id": material_id,
            "filename": filename or "未命名材料",
            "stored_name": stored_name,
            "sha256": hashlib.sha256(data).hexdigest(),
            "size": len(data),
            "text": text,
            "meta": json.dumps(meta, ensure_ascii=False),
            "created_at": now_iso(),
        }
        self.db.insert("materials", record)
        return record

    def extract(
        self,
        *,
        text: str = "",
        filename: str = "",
        data: bytes | None = None,
        use_llm: bool = True,
    ) -> dict:
        warnings: List[str] = []
        material = None
        if data:
            if not filename:
                raise ServiceError("缺少文件名")
            try:
                extracted = extract_text(filename, data)
            except MaterialError as exc:
                raise ServiceError(str(exc)) from exc
            text = (text or "") + ("\n" if text else "") + extracted
            material = self._store_material(filename, data, extracted, {"kind": "upload"})
        text = (text or "").strip()
        if not text:
            raise ServiceError("材料文本为空")

        engine = "local"
        records: List[dict] = []
        masked_preview = ""
        llm_error = ""
        if use_llm and self.llm.configured():
            if not self.settings.data.get("allow_text_upload", True):
                warnings.append("已关闭原始文本上传，本次使用本地规则抽取。")
            else:
                masker = Masker(entity["name"] for entity in self._entities_raw())
                try:
                    records, masked_preview = llm_extract(
                        self.llm, text, self.settings.as_of_date(), masker if self.settings.data.get("masking", True) else None
                    )
                    engine = "llm"
                except LLMError as exc:
                    llm_error = str(exc)
                    warnings.append(f"线上抽取失败，已回退本地规则抽取：{exc}")
        elif use_llm and not self.llm.configured():
            warnings.append("线上模型未启用或未配置密钥，本次使用本地规则抽取兜底。")

        if not records:
            records = local_extract(text)
            if use_llm and not llm_error and self.llm.configured():
                warnings.append("线上模型未返回有效债务记录，已回退本地规则抽取。")
        if not records:
            warnings.append("未从材料中识别出债务要素，请检查文本是否包含债权人、债务人、金额与到期日。")

        candidates = normalize_candidates(
            records,
            self._entities_raw(),
            self.list_debts(),
            source="ai" if engine == "llm" else "manual",
        )
        if material:
            self.db.update(
                "materials",
                material["id"],
                {"meta": json.dumps({"kind": "upload", "engine": engine, "records": len(records)}, ensure_ascii=False)},
            )
        self.db.audit(
            "material.extract",
            {"engine": engine, "filename": filename or "粘贴文本", "records": len(records), "material_id": material["id"] if material else None},
        )
        return {
            "material_id": material["id"] if material else None,
            "filename": filename or "粘贴文本",
            "engine": engine,
            "engine_label": "线上大模型抽取" if engine == "llm" else "本地规则抽取",
            "text_length": len(text),
            "masked_preview": masked_preview[:1000],
            "records": records,
            "candidates": candidates,
            "warnings": warnings,
            "as_of_date": self.settings.as_of_date(),
        }

    def import_candidates(self, candidates: List[dict], material_id: str | None = None) -> dict:
        if not isinstance(candidates, list) or not candidates:
            raise ServiceError("没有可导入的债务记录")
        created = []
        entities_created = []
        for candidate in candidates:
            creditor_id = candidate.get("creditor_id")
            debtor_id = candidate.get("debtor_id")
            if not creditor_id:
                creditor = self._find_or_create_entity(candidate.get("creditor_name"), created_by="ai")
                creditor_id = creditor["id"]
                if creditor.get("_created"):
                    entities_created.append(creditor_id)
            if not debtor_id:
                debtor = self._find_or_create_entity(candidate.get("debtor_name"), created_by="ai")
                debtor_id = debtor["id"]
                if debtor.get("_created"):
                    entities_created.append(debtor_id)
            amount_cents = candidate.get("amount_cents")
            if amount_cents is None:
                amount_cents = parse_amount_cents(candidate.get("amount"))
            if not amount_cents or amount_cents <= 0:
                raise ServiceError(f"第 {candidate.get('index', '?')} 条记录金额无效")
            due_date = parse_date(candidate.get("due_date")) or ""
            status = "pending" if self.settings.data.get("review_required_for_ai", True) and candidate.get("source") == "ai" else "confirmed"
            debt_id = new_id("debt")
            principal_cents = int(candidate.get("principal_cents") or amount_cents)
            interest_cents = int(candidate.get("interest_cents") or 0)
            self.db.insert(
                "debts",
                {
                    "id": debt_id,
                    "debtor_id": debtor_id,
                    "creditor_id": creditor_id,
                    "principal_cents": principal_cents,
                    "interest_cents": interest_cents,
                    "amount_cents": amount_cents,
                    "due_date": due_date,
                    "disputed": 1 if candidate.get("disputed") else 0,
                    "frozen": 1 if candidate.get("frozen") else 0,
                    "no_setoff_clause": 1 if candidate.get("no_setoff_clause") else 0,
                    "priority_group": candidate.get("priority_group") or "ordinary",
                    "status": status,
                    "source": "ai" if candidate.get("source") == "ai" else "import",
                    "material_id": material_id,
                    "note": str(candidate.get("note") or ""),
                    "created_at": now_iso(),
                    "updated_at": now_iso(),
                },
            )
            created.append(debt_id)
        self.db.audit(
            "material.import",
            {"debts": created, "entities_created": entities_created, "material_id": material_id},
        )
        return {
            "created": len(created),
            "debt_ids": created,
            "entities_created": entities_created,
            "pending": sum(1 for debt_id in created if self.get_debt(debt_id)["status"] == "pending"),
        }

    def import_debts(self, rows: List[dict]) -> dict:
        """批量导入结构化债务（CSV/Excel 转成的行），逐行容错。"""
        if not isinstance(rows, list) or not rows:
            raise ServiceError("没有可导入的债务行")
        if len(rows) > 5000:
            raise ServiceError("单次导入最多 5000 行")

        priority_input = {
            "ordinary": "ordinary", "普通": "ordinary", "普通债权": "ordinary",
            "mortgage": "mortgage", "抵押": "mortgage", "抵押优先": "mortgage", "抵押优先债权": "mortgage",
            "wage": "wage", "工资": "wage", "职工工资": "wage", "职工工资债权": "wage",
            "tax": "tax", "税款": "tax", "税款债权": "tax",
            "custom": "custom", "其他优先": "custom", "其他优先债权": "custom",
        }
        status_input = {
            "confirmed": "confirmed", "已确认": "confirmed", "确认": "confirmed",
            "pending": "pending", "待复核": "pending", "待确认": "pending",
            "rejected": "rejected", "已排除": "rejected",
        }

        def pick(row: dict, *keys: str):
            for key in keys:
                value = row.get(key)
                if value not in (None, ""):
                    return value
            return None

        created: List[str] = []
        errors: List[dict] = []
        entities_created: List[str] = []

        for index, row in enumerate(rows, start=1):
            if not isinstance(row, dict):
                errors.append({"row": index, "error": "行格式不是对象"})
                continue
            try:
                debtor_name = str(pick(row, "debtor_name", "debtor", "债务人", "欠款人") or "").strip()
                creditor_name = str(pick(row, "creditor_name", "creditor", "债权人", "收款人") or "").strip()
                debtor_id = str(pick(row, "debtor_id", "债务人编号") or "").strip()
                creditor_id = str(pick(row, "creditor_id", "债权人编号") or "").strip()

                amount_cents = parse_amount_cents(pick(row, "amount", "金额", "债务金额", "欠款金额"))
                principal_cents = parse_amount_cents(pick(row, "principal", "本金"))
                interest_cents = parse_amount_cents(pick(row, "interest", "利息"))
                if amount_cents is None and (principal_cents is not None or interest_cents is not None):
                    amount_cents = (principal_cents or 0) + (interest_cents or 0)
                if amount_cents is None or amount_cents <= 0:
                    raise ServiceError("金额缺失或不是正数")
                if principal_cents is None:
                    principal_cents = amount_cents - (interest_cents or 0)

                due_date = pick(row, "due_date", "到期日", "到期时间")
                due_date = parse_date(due_date) if due_date else ""
                if pick(row, "due_date", "到期日", "到期时间") and not due_date:
                    raise ServiceError("到期日格式无法识别")

                if not debtor_id:
                    if not debtor_name:
                        raise ServiceError("缺少债务人")
                    debtor = self._find_or_create_entity(debtor_name, created_by="import")
                    debtor_id = debtor["id"]
                    if debtor.get("_created"):
                        entities_created.append(debtor_id)
                else:
                    self._entity_row(debtor_id)
                if not creditor_id:
                    if not creditor_name:
                        raise ServiceError("缺少债权人")
                    creditor = self._find_or_create_entity(creditor_name, created_by="import")
                    creditor_id = creditor["id"]
                    if creditor.get("_created"):
                        entities_created.append(creditor_id)
                else:
                    self._entity_row(creditor_id)
                if debtor_id == creditor_id:
                    raise ServiceError("债务人与债权人是同一主体")

                priority_raw = str(pick(row, "priority_group", "分组", "顺位分组", "债权分组") or "ordinary").strip()
                priority = priority_input.get(priority_raw)
                if not priority:
                    raise ServiceError(f"未知的顺位分组：{priority_raw}")
                status_raw = str(pick(row, "status", "状态") or "confirmed").strip()
                status = status_input.get(status_raw)
                if not status:
                    raise ServiceError(f"未知的确认状态：{status_raw}")

                debt_id = new_id("debt")
                self.db.insert(
                    "debts",
                    {
                        "id": debt_id,
                        "debtor_id": debtor_id,
                        "creditor_id": creditor_id,
                        "principal_cents": int(principal_cents or 0),
                        "interest_cents": int(interest_cents or 0),
                        "amount_cents": int(amount_cents),
                        "due_date": due_date or "",
                        "disputed": 1 if parse_bool(pick(row, "disputed", "争议", "是否存在争议")) else 0,
                        "frozen": 1 if parse_bool(pick(row, "frozen", "查封", "查封冻结", "是否被查封冻结")) else 0,
                        "no_setoff_clause": 1 if parse_bool(
                            pick(row, "no_setoff_clause", "禁止抵销", "是否约定禁止抵销")
                        ) else 0,
                        "priority_group": priority,
                        "status": status,
                        "source": "import",
                        "material_id": None,
                        "note": str(pick(row, "note", "备注", "事由") or ""),
                        "created_at": now_iso(),
                        "updated_at": now_iso(),
                    },
                )
                created.append(debt_id)
            except (ServiceError, ValueError) as exc:
                errors.append({"row": index, "error": str(exc)})

        self.db.audit(
            "debt.batch_import",
            {"created": len(created), "errors": len(errors), "entities_created": len(set(entities_created))},
        )
        return {
            "created": len(created),
            "debt_ids": created,
            "entities_created": len(set(entities_created)),
            "errors": errors,
        }

    def _find_or_create_entity(self, name: str, created_by: str = "manual") -> dict:
        clean = str(name or "").strip()
        if not clean:
            raise ServiceError("主体名称不能为空")
        existing = self.db.query_one(
            "SELECT e.*, e.rowid AS seq FROM entities e WHERE replace(replace(name, ' ', ''), '　', '') = ?",
            (re.sub(r"[\s　]+", "", clean),),
        )
        if existing:
            return self._entity_public(existing)
        row = {
            "id": new_id("ent"),
            "name": clean,
            "credit_code": "",
            "account": "",
            "status": "正常经营",
            "available_cash_cents": 0,
            "litigation": 0,
            "enforced": 0,
            "note": f"由{'材料抽取' if created_by == 'ai' else '录入'}自动创建",
            "created_at": now_iso(),
            "updated_at": now_iso(),
        }
        self.db.insert("entities", row)
        result = self._entity_public(self._entity_row(row["id"]))
        result["_created"] = True
        return result

    def list_materials(self, limit: int = 50) -> List[dict]:
        rows = self.db.query(
            "SELECT id, filename, size, sha256, created_at, meta FROM materials ORDER BY created_at DESC LIMIT ?",
            (limit,),
        )
        for row in rows:
            try:
                row["meta"] = json.loads(row["meta"] or "{}")
            except ValueError:
                row["meta"] = {}
        return rows

    def llm_test(self) -> dict:
        result = self.llm.test()
        self.db.audit("llm.test", {"ok": result.get("ok"), "message": result.get("message")})
        return result

    # ================================================================== 设置
    def update_settings(self, patch: dict) -> dict:
        if not isinstance(patch, dict):
            raise ServiceError("配置格式错误")
        clean: dict[str, Any] = {}
        if "as_of_date" in patch:
            value = patch.get("as_of_date")
            if value and not parse_date(value):
                raise ServiceError("基准日格式无法识别")
            clean["as_of_date"] = parse_date(value) if value else None
        for field in ("masking", "allow_text_upload", "include_priority_groups", "review_required_for_ai"):
            if field in patch:
                clean[field] = bool(patch.get(field))
        if "exact_solver_seconds" in patch:
            try:
                clean["exact_solver_seconds"] = max(0.2, min(30.0, float(patch["exact_solver_seconds"])))
            except (TypeError, ValueError) as exc:
                raise ServiceError("求解时间预算无效") from exc

        if isinstance(patch.get("llm"), dict):
            current = self.settings.data.get("llm", {})
            llm_patch = patch["llm"]
            llm_clean: dict[str, Any] = {}
            for field in ("enabled", "provider", "base_url", "model", "temperature", "timeout"):
                if field in llm_patch:
                    llm_clean[field] = llm_patch[field]
            if "provider" in llm_clean and llm_clean["provider"] not in ("deepseek", "qwen", "wenxin", "custom"):
                raise ServiceError("不支持的模型厂商")
            if "enabled" in llm_clean:
                llm_clean["enabled"] = bool(llm_clean["enabled"])
            if "temperature" in llm_clean:
                try:
                    llm_clean["temperature"] = max(0.0, min(1.0, float(llm_clean["temperature"])))
                except (TypeError, ValueError) as exc:
                    raise ServiceError("temperature 无效") from exc
            if "timeout" in llm_clean:
                try:
                    llm_clean["timeout"] = max(5, min(300, int(llm_clean["timeout"])))
                except (TypeError, ValueError) as exc:
                    raise ServiceError("超时时间无效") from exc
            if llm_patch.get("clear_api_key"):
                llm_clean["api_key"] = ""
            elif llm_patch.get("api_key"):
                key = str(llm_patch["api_key"]).strip()
                if key and "****" not in key:
                    llm_clean["api_key"] = key
            if "base_url" in llm_clean:
                llm_clean["base_url"] = str(llm_clean["base_url"] or "").strip().rstrip("/")
                if llm_clean["base_url"] and not llm_clean["base_url"].startswith(("http://", "https://")):
                    raise ServiceError("接口地址必须以 http:// 或 https:// 开头")
            if "model" in llm_clean:
                llm_clean["model"] = str(llm_clean["model"] or "").strip()
            clean["llm"] = llm_clean

        self.settings.save(clean)
        safe_patch = dict(clean)
        if "llm" in safe_patch:
            safe_patch["llm"] = {k: ("****" if k == "api_key" else v) for k, v in safe_patch["llm"].items()}
        self.db.audit("settings.update", safe_patch)
        return self.settings.public()

    def reload_ontology(self) -> dict:
        self.ontology.load()
        self.db.audit("ontology.reload", self.ontology.health())
        return self.ontology.health()

    def audit_log(self, limit: int = 100) -> List[dict]:
        return self.db.list_audit(limit)

    # ================================================================== 导出
    def export(self, kind: str, plan_id: str | None = None) -> tuple[str, bytes, str]:
        stamp = datetime.now().strftime("%Y%m%d_%H%M")
        if kind == "ledger":
            entities = self.list_entities()
            debts = self.list_debts()
            content = export_ledger_xlsx(entities, debts)
            filename = f"债务台账_{stamp}.xlsx"
            mime = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        elif kind == "plan_xlsx":
            plan = self.get_plan(plan_id)
            content = export_plan_xlsx(plan)
            filename = f"清偿方案_{stamp}.xlsx"
            mime = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        elif kind == "plan_docx":
            plan = self.get_plan(plan_id)
            content = export_plan_docx(plan)
            filename = f"清偿方案报告_{stamp}.docx"
            mime = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        elif kind == "agreement_docx":
            plan = self.get_plan(plan_id)
            if plan.get("mode") == "pure":
                raise ServiceError("纯数学口径方案不能生成抵销协议，请使用法律合规口径方案", 400)
            content = export_agreement_docx(plan)
            filename = f"多方债务抵销及清偿协议_草稿_{stamp}.docx"
            mime = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        elif kind == "plan_json":
            plan = self.get_plan(plan_id)
            content = json.dumps(plan, ensure_ascii=False, indent=2).encode("utf-8")
            filename = f"清偿方案_{stamp}.json"
            mime = "application/json"
        else:
            raise ServiceError("未知的导出类型", 404)
        self.db.audit("export", {"kind": kind, "filename": filename, "plan_id": plan_id})
        return filename, content, mime

    # ================================================================== 示例数据
    def seed_demo(self, force: bool = False) -> dict:
        existing_entities = self.db.query("SELECT COUNT(*) AS n FROM entities")[0]["n"]
        existing_debts = self.db.query("SELECT COUNT(*) AS n FROM debts")[0]["n"]
        if (existing_entities or existing_debts) and not force:
            raise ServiceError("台账已有数据；如需重置并载入示例，请确认后使用强制载入", 409)
        if force:
            self.db.clear_business_data()

        today = date.today()
        def offset(days: int) -> str:
            from datetime import timedelta

            return (today + timedelta(days=days)).isoformat()

        entities = [
            ("华远建设集团有限公司", "91310000MA1K3XXXX1", "正常经营", 1200000, 0, 0, "总承包方，本方案核心枢纽"),
            ("恒通建材有限公司", "91310000MA1K3XXXX2", "正常经营", 800000, 0, 0, "材料供应商"),
            ("中鑫物流有限公司", "91310000MA1K3XXXX3", "正常经营", 600000, 1, 0, "运输服务商，有一起在诉案件"),
            ("安泰设备租赁有限公司", "91310000MA1K3XXXX4", "正常经营", 1500000, 0, 0, "设备出租方"),
            ("工商银行城东支行", "91310000MA1K3XXXX5", "正常经营", 0, 0, 0, "抵押债权人"),
            ("华远建设集团有限公司工会委员会", "81310000MA1K3XXXX6", "正常", 0, 0, 0, "职工工资债权人"),
        ]
        entity_ids = []
        for name, code, status, cash, litigation, enforced, note in entities:
            entity_id = new_id("ent")
            entity_ids.append(entity_id)
            self.db.insert(
                "entities",
                {
                    "id": entity_id,
                    "name": name,
                    "credit_code": code,
                    "account": "",
                    "status": status,
                    "available_cash_cents": int(Decimal(cash) * 100),
                    "litigation": litigation,
                    "enforced": enforced,
                    "note": note,
                    "created_at": now_iso(),
                    "updated_at": now_iso(),
                },
            )
        a, b, c, d, bank, union_ = entity_ids

        debts = [
            (a, b, 5000000, offset(-52), 0, 0, 0, "ordinary", "confirmed", "manual", "工程款，双方已对账"),
            (b, c, 3000000, offset(-37), 0, 0, 0, "ordinary", "confirmed", "manual", "材料款"),
            (c, d, 4000000, offset(-93), 0, 0, 0, "ordinary", "confirmed", "manual", "运输费"),
            (d, a, 1000000, offset(-51), 0, 0, 0, "ordinary", "confirmed", "manual", "设备租赁费"),
            (a, b, 500000, offset(-120), 1, 0, 0, "ordinary", "confirmed", "manual", "金额存在争议，双方对账差异待核"),
            (b, c, 300000, offset(-100), 0, 1, 0, "ordinary", "confirmed", "manual", "已被法院查封，处分受限"),
            (a, bank, 2000000, offset(-80), 0, 0, 0, "mortgage", "confirmed", "manual", "抵押借款，优先受偿"),
            (c, a, 200000, offset(120), 0, 0, 0, "ordinary", "confirmed", "manual", "未到期借款"),
            (d, c, 100000, offset(-130), 0, 0, 1, "ordinary", "confirmed", "manual", "合同约定禁止抵销"),
            (d, b, 800000, offset(-60), 0, 0, 0, "ordinary", "pending", "ai", "由材料抽取，待人工复核"),
            (a, union_, 800000, offset(-45), 0, 0, 0, "wage", "confirmed", "manual", "职工工资，优先顺位"),
        ]
        for debtor, creditor, amount, due, disputed, frozen, no_setoff, group, status, source, note in debts:
            self.db.insert(
                "debts",
                {
                    "id": new_id("debt"),
                    "debtor_id": debtor,
                    "creditor_id": creditor,
                    "principal_cents": int(Decimal(amount) * 100),
                    "interest_cents": 0,
                    "amount_cents": int(Decimal(amount) * 100),
                    "due_date": due,
                    "disputed": disputed,
                    "frozen": frozen,
                    "no_setoff_clause": no_setoff,
                    "priority_group": group,
                    "status": status,
                    "source": source,
                    "material_id": None,
                    "note": note,
                    "created_at": now_iso(),
                    "updated_at": now_iso(),
                },
            )
        self.db.audit("demo.seed", {"entities": len(entity_ids), "debts": len(debts)})
        return {
            "entities": len(entity_ids),
            "debts": len(debts),
            "message": "示例数据已载入：包含方案文档中的四主体闭环、各类不可抵销情形、优先顺位分组与待复核记录。",
        }

    def reset_all(self) -> dict:
        self.db.clear_business_data()
        self.db.audit("system.reset", {})
        return {"ok": True}
