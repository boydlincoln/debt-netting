"""债务图谱：主体为节点、债务为有向加权边，检索环路、枢纽与强连通分量。

图谱仅用于展示原始债务链条与风险传导路径；最终清偿方案以净头寸为依据，
是否识别出具体环路不影响轧差结果（与方案 5.3 一致）。
"""
from __future__ import annotations

from collections import defaultdict
from typing import Dict, Iterable, List, Sequence


def _tarjan(nodes: Sequence[str], adjacency: Dict[str, List[str]]) -> List[List[str]]:
    index_counter = 0
    stack: List[str] = []
    lowlink: Dict[str, int] = {}
    index: Dict[str, int] = {}
    on_stack: Dict[str, bool] = {}
    components: List[List[str]] = []

    def strongconnect(node: str) -> None:
        nonlocal index_counter
        index[node] = index_counter
        lowlink[node] = index_counter
        index_counter += 1
        stack.append(node)
        on_stack[node] = True
        for target in adjacency.get(node, []):
            if target not in index:
                strongconnect(target)
                lowlink[node] = min(lowlink[node], lowlink[target])
            elif on_stack.get(target):
                lowlink[node] = min(lowlink[node], index[target])
        if lowlink[node] == index[node]:
            component = []
            while True:
                member = stack.pop()
                on_stack[member] = False
                component.append(member)
                if member == node:
                    break
            components.append(component)

    for node in nodes:
        if node not in index:
            strongconnect(node)
    return components


def _simple_cycles(
    nodes: Sequence[str],
    adjacency: Dict[str, List[str]],
    max_cycles: int = 30,
    max_length: int = 6,
) -> List[List[str]]:
    """枚举有向简单环路（每个环只从最小序号节点出发一次）。"""
    order = {node: i for i, node in enumerate(nodes)}
    cycles: List[List[str]] = []

    for start in nodes:
        start_index = order[start]
        path = [start]
        visited = {start}

        def dfs(node: str) -> None:
            if len(cycles) >= max_cycles or len(path) > max_length:
                return
            for target in adjacency.get(node, []):
                if target == start and len(path) >= 2:
                    cycles.append(path.copy())
                    if len(cycles) >= max_cycles:
                        return
                    continue
                if target in visited:
                    continue
                if order.get(target, -1) < start_index:
                    continue
                visited.add(target)
                path.append(target)
                dfs(target)
                path.pop()
                visited.remove(target)

        dfs(start)
    return cycles


def build_graph(
    entities: Iterable[dict],
    debts: Iterable[dict],
    evaluations: Dict[str, dict],
    *,
    include_ineligible: bool = True,
    max_cycles: int = 30,
    max_length: int = 6,
) -> dict:
    entity_list = list(entities)
    debt_list = list(debts)
    entity_map = {entity["id"]: entity for entity in entity_list}
    names = {entity["id"]: entity["name"] for entity in entity_list}

    nodes: Dict[str, dict] = {}
    for entity in entity_list:
        nodes[entity["id"]] = {
            "id": entity["id"],
            "name": entity["name"],
            "receivable_cents": 0,
            "payable_cents": 0,
            "net_cents": 0,
            "eligible_receivable_cents": 0,
            "eligible_payable_cents": 0,
            "eligible_net_cents": 0,
            "edge_count": 0,
            "group_breakdown": defaultdict(int),
        }

    edges: List[dict] = []
    adjacency: Dict[str, List[str]] = defaultdict(list)
    for debt in debt_list:
        evaluation = evaluations.get(debt["id"], {})
        eligible = bool(evaluation.get("eligible")) and (debt.get("status") or "confirmed") == "confirmed"
        if not eligible and not include_ineligible:
            continue
        debtor = debt["debtor_id"]
        creditor = debt["creditor_id"]
        if debtor not in nodes:
            nodes[debtor] = {
                "id": debtor,
                "name": debt.get("debtor_name") or debtor,
                "receivable_cents": 0,
                "payable_cents": 0,
                "net_cents": 0,
                "eligible_receivable_cents": 0,
                "eligible_payable_cents": 0,
                "eligible_net_cents": 0,
                "edge_count": 0,
                "group_breakdown": defaultdict(int),
            }
        if creditor not in nodes:
            nodes[creditor] = {
                "id": creditor,
                "name": debt.get("creditor_name") or creditor,
                "receivable_cents": 0,
                "payable_cents": 0,
                "net_cents": 0,
                "eligible_receivable_cents": 0,
                "eligible_payable_cents": 0,
                "eligible_net_cents": 0,
                "edge_count": 0,
                "group_breakdown": defaultdict(int),
            }
        amount = int(debt.get("amount_cents") or 0)
        group = debt.get("priority_group") or "ordinary"
        edges.append(
            {
                "id": debt["id"],
                "from": debtor,
                "to": creditor,
                "amount_cents": amount,
                "due_date": debt.get("due_date") or "",
                "group": group,
                "eligible": eligible,
                "status": debt.get("status") or "confirmed",
                "blocking": evaluation.get("blocking", []),
                "review": evaluation.get("review", []),
                "disputed": bool(debt.get("disputed")),
                "frozen": bool(debt.get("frozen")),
                "source": debt.get("source") or "manual",
            }
        )
        nodes[debtor]["payable_cents"] += amount
        nodes[creditor]["receivable_cents"] += amount
        if eligible:
            nodes[debtor]["eligible_payable_cents"] += amount
            nodes[creditor]["eligible_receivable_cents"] += amount
        nodes[debtor]["edge_count"] += 1
        nodes[creditor]["edge_count"] += 1
        nodes[debtor]["group_breakdown"][group] += amount
        nodes[creditor]["group_breakdown"][group] += amount
        if creditor not in adjacency[debtor]:
            adjacency[debtor].append(creditor)

    node_ids = list(nodes.keys())
    cycles = _simple_cycles(node_ids, adjacency, max_cycles=max_cycles, max_length=max_length)
    components = _tarjan(node_ids, adjacency)

    cycle_membership: Dict[str, int] = defaultdict(int)
    for cycle in cycles:
        for node in cycle:
            cycle_membership[node] += 1

    adjacency_sets = {node: set(adjacency.get(node, [])) for node in node_ids}
    for node in nodes.values():
        inbound = sum(1 for source in node_ids if node["id"] in adjacency_sets.get(source, set()))
        node["in_degree"] = inbound
        node["out_degree"] = len(adjacency_sets.get(node["id"], set()))
        node["cycle_count"] = cycle_membership.get(node["id"], 0)
        node["net_cents"] = node["receivable_cents"] - node["payable_cents"]
        node["eligible_net_cents"] = node["eligible_receivable_cents"] - node["eligible_payable_cents"]
        node["in_cycles"] = cycle_membership.get(node["id"], 0) > 0
        node["is_hub"] = node["cycle_count"] >= 2 or (node["in_degree"] + node["out_degree"]) >= 4
        node["group_breakdown"] = dict(node["group_breakdown"])

    hubs = sorted(
        [node for node in nodes.values() if node["is_hub"]],
        key=lambda item: (-item["cycle_count"], -item["out_degree"], item["name"]),
    )

    return {
        "nodes": list(nodes.values()),
        "edges": edges,
        "cycles": cycles,
        "hubs": hubs,
        "components": [component for component in components if len(component) > 1],
        "stats": {
            "node_count": len(nodes),
            "edge_count": len(edges),
            "eligible_edge_count": sum(1 for edge in edges if edge["eligible"]),
            "cycle_count": len(cycles),
            "hub_count": len(hubs),
            "scc_count": sum(1 for component in components if len(component) > 1),
            "total_amount_cents": sum(edge["amount_cents"] for edge in edges),
        },
    }
