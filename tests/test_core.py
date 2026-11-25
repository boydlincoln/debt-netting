"""核心逻辑测试：本体规则、净额求解、服务编排、图谱与导出。"""
from __future__ import annotations

import itertools
import random
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.config import ONTOLOGY_PATH, Settings
from app.extract import local_extract, normalize_candidates
from app.netting import build_liquidity_schedule, partition_zero_sum, settle_group
from app.ontology import DebtOntology
from app.service import AppService, ServiceError


def make_debt(**overrides):
    base = {
        "id": "debt_test",
        "debtor_id": "ent_a",
        "creditor_id": "ent_b",
        "principal_cents": 1_000_000,
        "interest_cents": 0,
        "amount_cents": 1_000_000,
        "due_date": "2026-01-01",
        "disputed": 0,
        "frozen": 0,
        "no_setoff_clause": 0,
        "priority_group": "ordinary",
        "status": "confirmed",
        "source": "manual",
    }
    base.update(overrides)
    return base


def brute_force_groups(items):
    if not items:
        return 0
    best = 0
    rest = list(range(1, len(items)))
    for size in range(len(rest) + 1):
        for combo in itertools.combinations(rest, size):
            indexes = (0,) + combo
            if sum(items[i][1] for i in indexes) == 0:
                remaining = [items[i] for i in range(len(items)) if i not in indexes]
                best = max(best, 1 + brute_force_groups(remaining))
    return best


class OntologyRulesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ontology = DebtOntology(ONTOLOGY_PATH)

    def test_rules_loaded(self):
        self.assertGreaterEqual(len(self.ontology.rules), 7)
        self.assertEqual([rule.rule_id for rule in self.ontology.rules][:4], ["R1", "R2", "R3", "R4"])

    def test_normal_debt_eligible(self):
        evaluation = self.ontology.evaluate(make_debt(), "2026-11-21")
        self.assertTrue(evaluation["eligible"])
        self.assertEqual(evaluation["group_code"], "ordinary")
        self.assertFalse(evaluation["blocking"])

    def test_disputed_blocked(self):
        evaluation = self.ontology.evaluate(make_debt(disputed=1), "2026-11-21")
        self.assertFalse(evaluation["eligible"])
        self.assertEqual(evaluation["blocking"][0]["rule_id"], "R1")

    def test_frozen_blocked(self):
        evaluation = self.ontology.evaluate(make_debt(frozen=1), "2026-11-21")
        self.assertFalse(evaluation["eligible"])
        self.assertIn("R2", [item["rule_id"] for item in evaluation["blocking"]])

    def test_unmatured_blocked(self):
        evaluation = self.ontology.evaluate(make_debt(due_date="2027-01-01"), "2026-11-21")
        self.assertFalse(evaluation["eligible"])
        self.assertIn("R3", [item["rule_id"] for item in evaluation["blocking"]])

    def test_no_setoff_blocked(self):
        evaluation = self.ontology.evaluate(make_debt(no_setoff_clause=1), "2026-11-21")
        self.assertFalse(evaluation["eligible"])
        self.assertIn("R4", [item["rule_id"] for item in evaluation["blocking"]])

    def test_priority_is_info_not_block(self):
        evaluation = self.ontology.evaluate(make_debt(priority_group="mortgage"), "2026-11-21")
        self.assertTrue(evaluation["eligible"])
        self.assertEqual(evaluation["group_code"], "mortgage")
        self.assertEqual(evaluation["notes"][0]["rule_id"], "R5")

    def test_amount_not_positive_review(self):
        evaluation = self.ontology.evaluate(make_debt(amount_cents=0, principal_cents=0), "2026-11-21")
        self.assertFalse(evaluation["eligible"])
        self.assertIn("R6", [item["rule_id"] for item in evaluation["review"]])

    def test_self_dealing_blocked(self):
        evaluation = self.ontology.evaluate(make_debt(creditor_id="ent_a"), "2026-11-21")
        self.assertFalse(evaluation["eligible"])
        self.assertIn("R7", [item["rule_id"] for item in evaluation["blocking"]])

    def test_missing_due_date_review(self):
        evaluation = self.ontology.evaluate(make_debt(due_date=""), "2026-11-21")
        self.assertFalse(evaluation["eligible"])
        self.assertIn("DQ2", [item["rule_id"] for item in evaluation["review"]])

    def test_amount_inconsistency_review(self):
        evaluation = self.ontology.evaluate(
            make_debt(principal_cents=1_000_000, interest_cents=200_000, amount_cents=1_000_000),
            "2026-11-21",
        )
        self.assertFalse(evaluation["eligible"])
        self.assertIn("DQ3", [item["rule_id"] for item in evaluation["review"]])


class NettingSolverTest(unittest.TestCase):
    def test_doc_example(self):
        items = [("A", -40_000_000), ("B", 20_000_000), ("C", -10_000_000), ("D", 30_000_000)]
        result = partition_zero_sum(items)
        self.assertTrue(result.proven)
        self.assertEqual(len(result.groups), 1)
        transactions = settle_group(result.groups[0], {"A": 1, "B": 2, "C": 3, "D": 4})
        self.assertEqual(len(transactions), 3)
        pairs = [(tx["from"], tx["to"], tx["amount_cents"]) for tx in transactions]
        self.assertEqual(
            pairs,
            [
                ("A", "B", 20_000_000),
                ("A", "D", 20_000_000),
                ("C", "D", 10_000_000),
            ],
        )

    def test_exact_pairs_reduce_transactions(self):
        items = [("A", -10_000_000), ("B", 10_000_000), ("C", -25_000_000), ("D", 25_000_000)]
        result = partition_zero_sum(items)
        self.assertEqual(len(result.groups), 2)
        transactions = settle_group(result.groups[0]) + settle_group(result.groups[1])
        self.assertEqual(len(transactions), 2)

    def test_bruteforce_optimality(self):
        random.seed(17)
        for _ in range(120):
            count = random.choice([2, 4, 6, 8])
            values = [random.randint(1, 30) for _ in range(count)]
            if sum(values) % 2:
                values[0] += 1
            half = sum(values) // 2
            chosen = None
            for size in range(1, count):
                for combo in itertools.combinations(range(count), size):
                    if sum(values[index] for index in combo) == half:
                        chosen = set(combo)
                        break
                if chosen:
                    break
            if not chosen:
                continue
            items = [(f"e{index}", -value if index in chosen else value) for index, value in enumerate(values)]
            result = partition_zero_sum(items)
            self.assertTrue(result.proven)
            self.assertEqual(len(result.groups), brute_force_groups(items))

    def test_settlement_conserves_amounts(self):
        items = [("A", -30_000_000), ("B", -20_000_000), ("C", 15_000_000), ("D", 35_000_000)]
        result = partition_zero_sum(items)
        self.assertTrue(result.proven)
        transactions = []
        for group in result.groups:
            transactions.extend(settle_group(group))
        outflow = {}
        inflow = {}
        for tx in transactions:
            outflow[tx["from"]] = outflow.get(tx["from"], 0) + tx["amount_cents"]
            inflow[tx["to"]] = inflow.get(tx["to"], 0) + tx["amount_cents"]
        self.assertEqual(outflow, {"A": 30_000_000, "B": 20_000_000})
        self.assertEqual(inflow, {"C": 15_000_000, "D": 35_000_000})
        self.assertLessEqual(len(transactions), len(items) - 1)

    def test_liquidity_schedule_conserves_amounts(self):
        transactions = [
            {"from": "A", "to": "B", "amount_cents": 20_000_000},
            {"from": "A", "to": "C", "amount_cents": 30_000_000},
            {"from": "D", "to": "C", "amount_cents": 10_000_000},
        ]
        entities = {
            "A": {"available_cash_cents": 25_000_000},
            "D": {"available_cash_cents": 0},
        }
        schedule = build_liquidity_schedule(
            transactions, {}, entities, period_days=30, periods=3, base_date="2026-11-21"
        )
        totals = {}
        for item in schedule:
            totals[item["payer"]] = totals.get(item["payer"], 0) + item["amount_cents"]
        self.assertEqual(totals, {"A": 50_000_000, "D": 10_000_000})
        self.assertTrue(all(item["due_date"] >= "2026-12-21" for item in schedule))


class ServiceEndToEndTest(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        base = Path(self.tempdir.name)
        self.settings = Settings(base / "settings.json")
        self.ontology = DebtOntology(ONTOLOGY_PATH)
        self.service = AppService(base / "test.db", self.settings, self.ontology)
        self.service.seed_demo()

    def tearDown(self):
        self.tempdir.cleanup()

    def test_seed_and_doc_example_plan(self):
        plan = self.service.run_netting()
        ordinary = next(group for group in plan["groups"] if group["code"] == "ordinary")
        self.assertEqual(len(ordinary["transactions"]), 3)
        self.assertEqual(ordinary["optimality"], "proven")
        pairs = [
            (tx["from_name"], tx["to_name"], tx["amount_cents"])
            for tx in ordinary["transactions"]
        ]
        self.assertIn(("华远建设集团有限公司", "恒通建材有限公司", 200_000_000), pairs)
        self.assertIn(("华远建设集团有限公司", "安泰设备租赁有限公司", 200_000_000), pairs)
        self.assertIn(("中鑫物流有限公司", "安泰设备租赁有限公司", 100_000_000), pairs)
        self.assertEqual(plan["summary"]["transaction_count"], 5)
        self.assertEqual(plan["summary"]["excluded_count"], 5)
        self.assertEqual(plan["summary"]["debtor_count"], 2)
        self.assertEqual(plan["summary"]["creditor_count"], 4)
        self.assertTrue(all(check["ok"] for check in plan["checks"]))

    def test_pending_confirmation_changes_plan(self):
        pending = [debt for debt in self.service.list_debts() if debt["status"] == "pending"]
        self.assertEqual(len(pending), 1)
        self.service.set_debt_status(pending[0]["id"], "confirmed")
        plan = self.service.run_netting()
        self.assertEqual(plan["summary"]["included_count"], 7)
        self.assertEqual(plan["summary"]["pending_count"], 0)

    def test_priority_group_switch(self):
        self.service.update_settings({"include_priority_groups": False})
        plan = self.service.run_netting()
        self.assertEqual([group["code"] for group in plan["groups"]], ["ordinary"])
        self.assertEqual(plan["summary"]["transaction_count"], 3)
        self.assertTrue(any("优先顺位" in " ".join(item["reasons"]) for item in plan["excluded"]))

    def test_material_extraction_and_import(self):
        text = """债权人：恒通建材有限公司
债务人：华远建设集团有限公司
债务金额：人民币 180 万元
到期日：2020年10月31日
是否存在争议：否
是否被查封冻结：否
是否约定禁止抵销：否
备注：补充材料款"""
        result = self.service.extract(text=text, use_llm=False)
        self.assertEqual(result["engine"], "local")
        candidate = result["candidates"][0]
        self.assertEqual(candidate["amount_cents"], 180_000_000)
        self.assertFalse(candidate["disputed"])
        imported = self.service.import_candidates([candidate], result["material_id"])
        self.assertEqual(imported["created"], 1)
        debt = self.service.get_debt(imported["debt_ids"][0])
        self.assertEqual(debt["amount_cents"], 180_000_000)
        self.assertTrue(debt["eligibility"]["eligible"])

    def test_material_file_upload_is_archived(self):
        content = (
            "债权人：恒通建材有限公司\n"
            "债务人：华远建设集团有限公司\n"
            "债务金额：人民币 66 万元\n"
            "到期日：2020年1月1日\n"
        ).encode("utf-8")
        result = self.service.extract(filename="contract.txt", data=content, use_llm=False)
        self.assertIsNotNone(result["material_id"])
        self.assertEqual(result["candidates"][0]["amount_cents"], 66_000_000)
        materials = self.service.list_materials()
        self.assertTrue(any(item["id"] == result["material_id"] for item in materials))

    def test_crud_and_validation(self):
        entity = self.service.create_entity({"name": "测试主体", "available_cash": 1000})
        debt = self.service.create_debt(
            {
                "debtor_id": entity["id"],
                "creditor_id": self.service.list_entities()[0]["id"],
                "principal": 5000,
                "interest": 100,
                "due_date": "2026-10-01",
                "priority_group": "ordinary",
            }
        )
        self.assertEqual(debt["amount"], 5100.0)
        updated = self.service.update_debt(debt["id"], {"note": "备注更新"})
        self.assertEqual(updated["note"], "备注更新")
        self.service.delete_debt(debt["id"])
        with self.assertRaises(ServiceError):
            self.service.get_debt(debt["id"])

    def test_graph(self):
        graph = self.service.graph()
        self.assertGreaterEqual(graph["stats"]["node_count"], 6)
        self.assertGreaterEqual(graph["stats"]["cycle_count"], 1)
        self.assertTrue(graph["hubs"])
        self.assertTrue(all("eligible_net_cents" in node for node in graph["nodes"]))

    def test_exports_open(self):
        from docx import Document
        from io import BytesIO
        from openpyxl import load_workbook

        plan = self.service.run_netting()
        for kind in ("ledger", "plan_xlsx", "plan_docx", "agreement_docx"):
            filename, content, mime = self.service.export(kind, plan["id"])
            self.assertTrue(filename)
            self.assertGreater(len(content), 1000)
            if filename.endswith(".xlsx"):
                workbook = load_workbook(BytesIO(content))
                self.assertGreaterEqual(len(workbook.sheetnames), 2)
            else:
                document = Document(BytesIO(content))
                self.assertGreater(len(document.paragraphs), 5)

    def test_as_of_date_affects_maturity(self):
        self.service.update_settings({"as_of_date": "2025-01-01"})
        plan = self.service.run_netting()
        self.assertEqual(plan["summary"]["included_count"], 0)
        self.assertEqual(plan["summary"]["transaction_count"], 0)

    def test_narrative_requires_configured_llm(self):
        plan = self.service.run_netting()
        with self.assertRaises(ServiceError):
            self.service.generate_narrative(plan["id"])

    def test_pure_math_mode_includes_everything(self):
        plan = self.service.run_netting("pure")
        self.assertEqual(plan["mode"], "pure")
        self.assertEqual(plan["summary"]["included_count"], 11)
        self.assertEqual(plan["summary"]["excluded_count"], 0)
        self.assertEqual(plan["summary"]["transaction_count"], 4)
        self.assertEqual(plan["summary"]["transaction_amount_cents"], 790_000_000)
        self.assertEqual([group["code"] for group in plan["groups"]], ["all"])
        self.assertTrue(plan["summary"]["optimality"] == "proven")
        with self.assertRaises(ServiceError):
            self.service.export("agreement_docx", plan["id"])

    def test_compare_modes(self):
        result = self.service.compare_netting()
        self.assertEqual(result["legal"]["summary"]["transaction_count"], 5)
        self.assertEqual(result["pure"]["summary"]["transaction_count"], 4)
        self.assertEqual(result["comparison"]["transaction_count"]["difference"], -1)
        self.assertEqual(len(result["comparison"]["adjusted_debts"]), 5)
        self.assertEqual(result["comparison"]["amount_cents"]["difference"], 10_000_000)

    def test_plan_sequence_and_debt_snapshot(self):
        first = self.service.run_netting("legal")
        second = self.service.run_netting("pure")
        self.assertEqual(second["seq"], first["seq"] + 1)
        self.assertTrue(first["name"].startswith("核算 #"))
        self.assertEqual(len(first["debt_snapshot"]), 11)
        included = [item for item in first["debt_snapshot"] if item["included"]]
        excluded = [item for item in first["debt_snapshot"] if not item["included"]]
        self.assertEqual(len(included), 6)
        self.assertEqual(len(excluded), 5)
        plans = self.service.list_plans()
        self.assertEqual(plans[0]["seq"], second["seq"])
        self.assertTrue(plans[0]["name"].startswith("核算 #"))
        loaded = self.service.get_plan(first["id"])
        self.assertEqual(loaded["seq"], first["seq"])
        self.assertEqual(len(loaded["debt_snapshot"]), 11)

    def test_work_record_isolation(self):
        first = self.service.active_case()
        second = self.service.create_case("隔离测试工作记录", with_demo=False)
        self.assertEqual(second["seq"], 2)
        self.assertEqual(self.service.dashboard()["debts"]["total"], 0)
        self.service.import_debts(
            [
                {
                    "debtor_name": "隔离测试甲",
                    "creditor_name": "隔离测试乙",
                    "amount": 12345,
                    "due_date": "2020-01-01",
                    "priority_group": "ordinary",
                }
            ]
        )
        self.assertEqual(self.service.dashboard()["debts"]["total"], 1)
        self.service.switch_case(first["id"])
        self.assertEqual(self.service.dashboard()["debts"]["total"], 11)
        cases = self.service.list_cases()
        self.assertEqual(len(cases), 2)
        self.assertTrue(next(item for item in cases if item["id"] == first["id"])["active"])

    def test_batch_import(self):
        rows = [            {
                "debtor_name": "批量测试甲",
                "creditor_name": "批量测试乙",
                "amount": 1000,
                "due_date": "2020-01-01",
                "disputed": "否",
                "frozen": "否",
                "no_setoff_clause": "否",
                "priority_group": "ordinary",
                "note": "批量导入测试一",
            },
            {
                "debtor_name": "批量测试乙",
                "creditor_name": "批量测试甲",
                "amount": 500,
                "due_date": "2020-01-01",
                "priority_group": "ordinary",
                "note": "批量导入测试二",
            },
            {
                "debtor_name": "批量测试甲",
                "creditor_name": "批量测试乙",
                "amount": "",
                "due_date": "2020-01-01",
            },
        ]
        result = self.service.import_debts(rows)
        self.assertEqual(result["created"], 2)
        self.assertEqual(len(result["errors"]), 1)
        self.assertEqual(result["errors"][0]["row"], 3)
        self.assertGreaterEqual(len(self.service.list_entities()), 8)
        debts = self.service.list_debts()
        self.assertTrue(any(debt["note"] == "批量导入测试一" for debt in debts))


class ExtractionTest(unittest.TestCase):
    def test_flags_and_interest(self):
        text = """债权人：安泰设备租赁有限公司
债务人：中鑫物流有限公司
本金：人民币 95 万元
利息：人民币 5 万元
到期日：2026年9月15日
是否存在争议：是
是否被查封冻结：否
是否约定禁止抵销：否"""
        records = local_extract(text)
        self.assertEqual(len(records), 1)
        self.assertTrue(records[0]["disputed"])
        self.assertFalse(records[0]["frozen"])
        candidates = normalize_candidates(records, [], [], source="manual")
        self.assertEqual(candidates[0]["amount_cents"], 100_000_000)


if __name__ == "__main__":
    unittest.main()
