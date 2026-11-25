"""HTTP 接口集成测试：启动真实本地服务并验证主要端点。"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.config import ONTOLOGY_PATH, Settings
from app.ontology import DebtOntology
from app.server import DebtServer
from app.service import AppService


class ServerIntegrationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tempdir = tempfile.TemporaryDirectory()
        base = Path(cls.tempdir.name)
        cls.settings = Settings(base / "settings.json")
        cls.service = AppService(base / "api.db", cls.settings, DebtOntology(ONTOLOGY_PATH))
        cls.service.seed_demo()
        cls.server = DebtServer(cls.service, port=0)
        cls.server.start(background=True)
        cls.port = cls.server.httpd.server_address[1]

    @classmethod
    def tearDownClass(cls):
        cls.server.stop()
        cls.tempdir.cleanup()

    def request(self, path, method="GET", payload=None):
        data = None
        headers = {}
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(
            f"http://127.0.0.1:{self.port}{path}", data=data, headers=headers, method=method
        )
        with urllib.request.urlopen(request, timeout=20) as response:
            return response.status, response.headers, response.read()

    def request_json(self, path, method="GET", payload=None):
        status, headers, body = self.request(path, method, payload)
        return status, json.loads(body.decode("utf-8"))

    def test_index_page(self):
        status, headers, body = self.request("/")
        self.assertEqual(status, 200)
        self.assertIn("text/html", headers.get("Content-Type", ""))
        self.assertIn("三角债".encode("utf-8"), body)

    def test_bootstrap(self):
        status, data = self.request_json("/api/bootstrap")
        self.assertEqual(status, 200)
        self.assertEqual(data["entities"], 6)
        self.assertEqual(data["debts"]["total"], 11)
        self.assertEqual(data["ontology"]["rules"], 7)

    def test_netting_and_exports(self):
        status, plan = self.request_json("/api/netting/run", "POST", {})
        self.assertEqual(status, 200)
        self.assertEqual(plan["summary"]["transaction_count"], 5)
        self.assertTrue(plan["summary"]["optimality"] == "proven")
        status, headers, body = self.request(f"/api/export/plan_xlsx?plan_id={plan['id']}")
        self.assertEqual(status, 200)
        self.assertIn("spreadsheetml", headers.get("Content-Type", ""))
        self.assertGreater(len(body), 5000)

    def test_debt_crud(self):
        status, entities = self.request_json("/api/entities")
        self.assertEqual(status, 200)
        entities = entities["items"]
        status, debt = self.request_json(
            "/api/debts",
            "POST",
            {
                "debtor_id": entities[0]["id"],
                "creditor_id": entities[1]["id"],
                "principal": 1234.56,
                "interest": 0,
                "due_date": "2020-01-01",
                "priority_group": "ordinary",
                "note": "接口测试",
            },
        )
        self.assertEqual(status, 201)
        self.assertEqual(debt["amount_cents"], 123456)
        status, updated = self.request_json(
            f"/api/debts/{debt['id']}", "PUT", {"note": "接口测试更新"}
        )
        self.assertEqual(status, 200)
        self.assertEqual(updated["note"], "接口测试更新")
        status, deleted = self.request_json(f"/api/debts/{debt['id']}", "DELETE")
        self.assertEqual(status, 200)
        self.assertEqual(deleted["deleted"], debt["id"])

    def test_invalid_payload_returns_error(self):
        request = urllib.request.Request(
            f"http://127.0.0.1:{self.port}/api/debts",
            data=b"{}",
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with self.assertRaises(urllib.error.HTTPError) as context:
            urllib.request.urlopen(request, timeout=10)
        self.assertEqual(context.exception.code, 400)
        payload = json.loads(context.exception.read().decode("utf-8"))
        self.assertIn("error", payload)

    def test_extract_and_graph(self):
        text = "债权人：恒通建材有限公司\n债务人：华远建设集团有限公司\n债务金额：人民币 180 万元\n到期日：2020年10月31日\n"
        status, result = self.request_json("/api/materials/extract", "POST", {"text": text, "use_llm": False})
        self.assertEqual(status, 200)
        self.assertEqual(result["engine"], "local")
        self.assertGreaterEqual(len(result["candidates"]), 1)
        status, graph = self.request_json("/api/graph")
        self.assertEqual(status, 200)
        self.assertGreaterEqual(graph["stats"]["cycle_count"], 1)


if __name__ == "__main__":
    unittest.main()
