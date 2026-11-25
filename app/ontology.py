"""OWL/SWRL 本体加载与本地规则推理。

- 规则定义在 ontology/debt_ontology.owl（Protégé 可直接打开维护）；
- 本模块解析 OWL 中的类、属性与 SWRL Imp，对每笔债务实例化并前向推理；
- 金额、日期等派生属性由本地引擎计算，推理结论与命中的规则、法条一并留痕。
"""
from __future__ import annotations

import re
import threading
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from .config import ONTOLOGY_PATH

RDF = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"
RDFS = "http://www.w3.org/2000/01/rdf-schema#"
OWL = "http://www.w3.org/2002/07/owl#"
SWRL = "http://www.w3.org/2003/11/swrl#"
DEBT = "http://example.org/debt#"
XSD = "http://www.w3.org/2001/XMLSchema#"

GROUP_LABELS = {
    "ordinary": "普通债权",
    "mortgage": "抵押优先债权",
    "wage": "职工工资债权",
    "tax": "税款债权",
    "custom": "其他优先债权",
}
PRIORITY_GROUPS = ("mortgage", "wage", "tax", "custom")

MISSING = object()


def _q(ns: str, tag: str) -> str:
    return f"{{{ns}}}{tag}"


def _local(name: str) -> str:
    if not name:
        return ""
    if "}" in name:            # ElementTree 的 {namespace}local 形式
        name = name.rsplit("}", 1)[-1]
    return name.rsplit("#", 1)[-1].rsplit("/", 1)[-1]


def _text(el: Optional[ET.Element]) -> str:
    return (el.text or "").strip() if el is not None else ""


@dataclass
class Atom:
    kind: str                      # class | datatype | object
    predicate: str
    args: List[dict] = field(default_factory=list)

    def describe(self, labels: Dict[str, str]) -> str:
        if self.kind == "class":
            return f"个体属于「{labels.get(self.predicate, self.predicate)}」"
        values = []
        for arg in self.args:
            if arg["kind"] == "var":
                values.append(f"?{arg['name']}")
            else:
                value = arg["value"]
                if isinstance(value, bool):
                    value = "真" if value else "假"
                values.append(str(value))
        predicate = labels.get(self.predicate, self.predicate)
        return f"{values[0] if values else '?'} 的「{predicate}」为 {values[1] if len(values) > 1 else ''}".strip()


@dataclass
class Rule:
    uri: str
    rule_id: str
    name: str
    severity: str
    message: str
    legal_basis: str
    order: int
    body: List[Atom]
    head: List[Atom]

    def body_text(self, labels: Dict[str, str]) -> str:
        return " 且 ".join(atom.describe(labels) for atom in self.body)

    def head_text(self, labels: Dict[str, str]) -> str:
        return " 且 ".join(atom.describe(labels) for atom in self.head)

    def to_dict(self, labels: Dict[str, str]) -> dict:
        return {
            "uri": self.uri,
            "id": self.rule_id,
            "name": self.name,
            "severity": self.severity,
            "message": self.message,
            "legal_basis": self.legal_basis,
            "order": self.order,
            "body": self.body_text(labels),
            "head": self.head_text(labels),
        }


class OntologyError(RuntimeError):
    pass


class DebtOntology:
    def __init__(self, path: str | Path = ONTOLOGY_PATH):
        self.path = Path(path)
        self._lock = threading.RLock()
        self._stamp: tuple | None = None
        self.title = "债务抵销本体"
        self.version = ""
        self.comment = ""
        self.classes: Dict[str, str] = {}
        self.object_properties: Dict[str, str] = {}
        self.datatype_properties: Dict[str, str] = {}
        self.labels: Dict[str, str] = {}
        self.rules: List[Rule] = []
        self.load()

    # ------------------------------------------------------------------ 加载
    def load(self) -> None:
        with self._lock:
            if not self.path.exists():
                raise OntologyError(f"未找到本体文件：{self.path}")
            try:
                root = ET.parse(str(self.path)).getroot()
            except ET.ParseError as exc:
                raise OntologyError(f"本体文件解析失败：{exc}") from exc

            classes: Dict[str, str] = {}
            object_props: Dict[str, str] = {}
            datatype_props: Dict[str, str] = {}
            labels: Dict[str, str] = {}

            for el in root.iter():
                tag = el.tag
                if tag in (_q(OWL, "Class"), _q(OWL, "ObjectProperty"), _q(OWL, "DatatypeProperty")):
                    name = _local(el.get(_q(RDF, "about"), ""))
                    if not name:
                        continue
                    label = _text(el.find(_q(RDFS, "label"))) or name
                    labels[name] = label
                    if tag == _q(OWL, "Class"):
                        classes[name] = label
                    elif tag == _q(OWL, "ObjectProperty"):
                        object_props[name] = label
                    else:
                        datatype_props[name] = label

            title = "债务抵销本体"
            version = ""
            comment = ""
            for el in root.iter(_q(OWL, "Ontology")):
                title = _text(el.find(_q(RDFS, "label"))) or title
                version = _text(el.find(_q(OWL, "versionInfo")))
                comment = _text(el.find(_q(RDFS, "comment")))
                break

            rules = []
            for el in root.iter(_q(SWRL, "Imp")):
                rules.append(self._parse_rule(el))
            rules.sort(key=lambda item: (item.order, item.rule_id))

            self.classes = classes
            self.object_properties = object_props
            self.datatype_properties = datatype_props
            self.labels = labels
            self.rules = rules
            self.title = title
            self.version = version
            self.comment = comment
            stat = self.path.stat()
            self._stamp = (stat.st_mtime_ns, stat.st_size)

    def _parse_rule(self, el: ET.Element) -> Rule:
        def meta(tag: str) -> str:
            return _text(el.find(_q(DEBT, tag)))

        uri = el.get(_q(RDF, "about"), "")
        rule_id = meta("ruleId") or _local(uri)
        name = meta("ruleName") or rule_id
        severity = meta("severity") or "info"
        if severity not in ("blocking", "review", "info"):
            severity = "info"
        try:
            order = int(meta("order") or 0)
        except ValueError:
            order = 0

        body_el = el.find(_q(SWRL, "body"))
        head_el = el.find(_q(SWRL, "head"))
        body_children = list(body_el) if body_el is not None else []
        head_children = list(head_el) if head_el is not None else []
        body = [atom for atom in (self._parse_atom(child) for child in body_children) if atom]
        head = [atom for atom in (self._parse_atom(child) for child in head_children) if atom]
        if not body:
            raise OntologyError(f"规则 {rule_id} 的 SWRL body 为空")
        return Rule(
            uri=uri,
            rule_id=rule_id,
            name=name,
            severity=severity,
            message=meta("message"),
            legal_basis=meta("legalBasis"),
            order=order,
            body=body,
            head=head,
        )

    def _parse_atom(self, el: ET.Element) -> Optional[Atom]:
        types = [
            _local(child.get(_q(RDF, "resource"), ""))
            for child in el.findall(_q(RDF, "type"))
        ]
        if "ClassAtom" in types:
            predicate = self._resource(el.find(_q(SWRL, "classPredicate")))
            arg = self._argument(el.find(_q(SWRL, "argument1")))
            if not predicate or not arg:
                return None
            return Atom("class", predicate, [arg])
        if "DatatypePropertyAtom" in types:
            predicate = self._resource(el.find(_q(SWRL, "propertyPredicate")))
            arg1 = self._argument(el.find(_q(SWRL, "argument1")))
            arg2 = self._argument(el.find(_q(SWRL, "argument2")))
            if not predicate or not arg1 or not arg2:
                return None
            return Atom("datatype", predicate, [arg1, arg2])
        if "ObjectPropertyAtom" in types:
            predicate = self._resource(el.find(_q(SWRL, "propertyPredicate")))
            arg1 = self._argument(el.find(_q(SWRL, "argument1")))
            arg2 = self._argument(el.find(_q(SWRL, "argument2")))
            if not predicate or not arg1 or not arg2:
                return None
            return Atom("object", predicate, [arg1, arg2])
        return None

    @staticmethod
    def _resource(el: Optional[ET.Element]) -> str:
        if el is None:
            return ""
        return _local(el.get(_q(RDF, "resource"), ""))

    @staticmethod
    def _argument(el: Optional[ET.Element]) -> Optional[dict]:
        if el is None:
            return None
        for child in el.iter():
            if _local(child.tag) == "Variable":
                name = _local(child.get(_q(RDF, "about"), ""))
                if name:
                    return {"kind": "var", "name": name}
        literal = (el.text or "").strip()
        if literal:
            datatype = _local(el.get(_q(RDF, "datatype"), ""))
            return {"kind": "literal", "value": _cast_literal(literal, datatype), "datatype": datatype}
        return None

    # ------------------------------------------------------------------ 状态
    def reload(self) -> None:
        self.load()

    def is_stale(self) -> bool:
        try:
            stat = self.path.stat()
        except OSError:
            return False
        return self._stamp != (stat.st_mtime_ns, stat.st_size)

    def health(self) -> dict:
        return {
            "loaded": bool(self.rules),
            "title": self.title,
            "version": self.version,
            "comment": self.comment,
            "path": str(self.path),
            "classes": len(self.classes),
            "object_properties": len(self.object_properties),
            "datatype_properties": len(self.datatype_properties),
            "rules": len(self.rules),
            "rule_ids": [rule.rule_id for rule in self.rules],
            "stale": self.is_stale(),
        }

    def rules_catalog(self) -> List[dict]:
        return [rule.to_dict(self.labels) for rule in self.rules]

    # ------------------------------------------------------------------ 推理
    def _derived(self, debt: dict, as_of: str) -> Dict[str, Any]:
        due = (debt.get("due_date") or "").strip()
        amount_cents = int(debt.get("amount_cents") or 0)
        group = (debt.get("priority_group") or "ordinary").strip() or "ordinary"
        debtor = debt.get("debtor_id") or ""
        creditor = debt.get("creditor_id") or ""
        matured = None
        if due:
            try:
                matured = date.fromisoformat(due) <= date.fromisoformat(as_of)
            except ValueError:
                matured = None
        return {
            "hasAmount": amount_cents / 100.0,
            "hasPrincipal": int(debt.get("principal_cents") or 0) / 100.0,
            "hasInterest": int(debt.get("interest_cents") or 0) / 100.0,
            "hasDueDate": due,
            "hasDisputed": bool(debt.get("disputed")),
            "hasFrozen": bool(debt.get("frozen")),
            "hasNoSetoffClause": bool(debt.get("no_setoff_clause")),
            "hasPriorityGroup": group,
            "hasStatus": debt.get("status") or "confirmed",
            "hasSource": debt.get("source") or "manual",
            "hasMatured": matured,
            "hasPriority": group in PRIORITY_GROUPS,
            "hasSelfDealing": bool(debtor) and debtor == creditor,
            "hasAmountPositive": amount_cents > 0,
        }

    def evaluate(self, debt: dict, as_of: str) -> dict:
        """对单笔债务执行本体推理，返回抵销资格、分组、命中规则与理由。"""
        if self.is_stale():
            try:
                self.reload()
            except OntologyError:
                pass

        props = self._derived(debt, as_of)
        blocking: List[dict] = []
        review: List[dict] = []
        notes: List[dict] = []
        trace: List[dict] = []

        for rule in self.rules:
            fired = all(self._atom_true(atom, props) for atom in rule.body)
            trace.append(
                {
                    "rule_id": rule.rule_id,
                    "name": rule.name,
                    "severity": rule.severity,
                    "fired": fired,
                    "message": rule.message,
                    "legal_basis": rule.legal_basis,
                }
            )
            if not fired:
                continue
            entry = {
                "rule_id": rule.rule_id,
                "name": rule.name,
                "message": rule.message,
                "legal_basis": rule.legal_basis,
            }
            if rule.severity == "blocking":
                blocking.append(entry)
            elif rule.severity == "review":
                review.append(entry)
            else:
                notes.append(entry)

        # 数据质量兜底：本体规则之外的结构性校验
        if not debt.get("debtor_id") or not debt.get("creditor_id"):
            blocking.append(
                {
                    "rule_id": "DQ1",
                    "name": "债权债务主体不完整",
                    "message": "缺少债务人或债权人，无法参与抵销。",
                    "legal_basis": "",
                }
            )
        if not (debt.get("due_date") or "").strip():
            review.append(
                {
                    "rule_id": "DQ2",
                    "name": "缺少到期日",
                    "message": "无法判断是否已到期，转人工复核。",
                    "legal_basis": "",
                }
            )
        elif props["hasMatured"] is None:
            review.append(
                {
                    "rule_id": "DQ2",
                    "name": "到期日无法解析",
                    "message": "到期日格式异常，无法判断是否已到期，转人工复核。",
                    "legal_basis": "",
                }
            )
        principal = int(debt.get("principal_cents") or 0)
        interest = int(debt.get("interest_cents") or 0)
        amount = int(debt.get("amount_cents") or 0)
        if principal or interest:
            if abs(principal + interest - amount) > 1:
                review.append(
                    {
                        "rule_id": "DQ3",
                        "name": "金额与本金、利息之和不一致",
                        "message": "债务金额与本息合计存在差异，转人工复核。",
                        "legal_basis": "",
                    }
                )

        group = (debt.get("priority_group") or "ordinary").strip() or "ordinary"
        eligible = not blocking and not review
        return {
            "eligible": eligible,
            "group_code": group,
            "group_label": GROUP_LABELS.get(group, group),
            "blocking": blocking,
            "review": review,
            "notes": notes,
            "trace": trace,
            "derived": {
                "hasMatured": props["hasMatured"],
                "hasPriority": props["hasPriority"],
                "hasSelfDealing": props["hasSelfDealing"],
                "hasAmountPositive": props["hasAmountPositive"],
                "priority_group": group,
            },
            "reasons": [item["message"] for item in blocking + review],
        }

    def _atom_true(self, atom: Atom, props: Dict[str, Any]) -> bool:
        if atom.kind == "class":
            return atom.predicate == "DebtObligation"
        if atom.kind == "datatype":
            arg1, arg2 = atom.args
            if arg1.get("kind") != "var" or arg1.get("name") != "d":
                return False
            value = props.get(atom.predicate, MISSING)
            if value is MISSING or value is None:
                return False
            return _value_equals(value, arg2.get("value"))
        if atom.kind == "object":
            return False
        return False


def _cast_literal(text: str, datatype: str) -> Any:
    lowered = text.strip().lower()
    if datatype in ("boolean", "bool") or lowered in ("true", "false"):
        return lowered == "true"
    if datatype in ("int", "integer", "long", "short", "byte"):
        try:
            return int(text)
        except ValueError:
            return text
    if datatype in ("decimal", "double", "float"):
        try:
            return float(text)
        except ValueError:
            return text
    return text


def _value_equals(value: Any, literal: Any) -> bool:
    if isinstance(value, bool) or isinstance(literal, bool):
        return bool(value) == bool(literal)
    if isinstance(literal, (int, float)) and not isinstance(literal, bool):
        try:
            return abs(float(value) - float(literal)) < 1e-9
        except (TypeError, ValueError):
            return False
    return str(value) == str(literal)


def evaluate_all(debts: Iterable[dict], as_of: str, ontology: DebtOntology | None = None) -> Dict[str, dict]:
    engine = ontology or get_ontology()
    return {debt["id"]: engine.evaluate(debt, as_of) for debt in debts}


_ENGINE: DebtOntology | None = None
_ENGINE_LOCK = threading.Lock()


def get_ontology() -> DebtOntology:
    global _ENGINE
    with _ENGINE_LOCK:
        if _ENGINE is None:
            _ENGINE = DebtOntology()
        return _ENGINE
