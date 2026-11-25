"""净头寸计算与“最小交易笔数”轧差求解。

数学结构
--------
对同一顺位分组内的主体计算净头寸后，净债务人为供给点、净债权人为需求点。
把参与主体按“零和子集”划分为尽可能多的组，各组内部用 n-1 笔交易即可结清
（每笔交易至少使一个主体头寸归零）；因此

    最少交易笔数 = 参与主体数 N - 最大零和划分数 G

最大零和划分是 NP 难问题，本模块采用：
  1) 先剥离金额完全对冲的两两配对（可证明不影响最优性）；
  2) 小规模（默认 ≤ 18 个参与主体）用带记忆化与上界剪枝的精确搜索，
     搜索完成即证明全局最优；
  3) 超时或规模过大时退化为“精确配对 + 3/4 元零和子集”的启发式，
     并在方案中如实标注 optimality。
"""
from __future__ import annotations

import itertools
import time
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

Item = Tuple[str, int]          # (entity_id, signed cents)
Group = List[Item]

EXACT_LIMIT = 18
NODE_BUDGET = 400_000


class SolverTimeout(Exception):
    pass


@dataclass
class PartitionResult:
    groups: List[Group]
    proven: bool


def _now() -> float:
    return time.monotonic()


def compute_positions(debts: Iterable[dict]) -> Dict[str, dict]:
    """按主体汇总应收、应付与净头寸（单位：分）。

    debts 需已带 amount_cents、debtor_id、creditor_id。
    """
    gross: Dict[str, dict] = {}
    for debt in debts:
        amount = int(debt.get("amount_cents") or 0)
        debtor = debt.get("debtor_id")
        creditor = debt.get("creditor_id")
        if not debtor or not creditor or amount <= 0:
            continue
        gross.setdefault(debtor, {"receivable": 0, "payable": 0})
        gross.setdefault(creditor, {"receivable": 0, "payable": 0})
        gross[debtor]["payable"] += amount
        gross[creditor]["receivable"] += amount
    positions: Dict[str, dict] = {}
    for entity_id, item in gross.items():
        receivable = item["receivable"]
        payable = item["payable"]
        net = receivable - payable
        if net > 0:
            role = "creditor"
        elif net < 0:
            role = "debtor"
        else:
            role = "zero"
        positions[entity_id] = {
            "receivable_cents": receivable,
            "payable_cents": payable,
            "net_cents": net,
            "role": role,
        }
    return positions


def partition_zero_sum(
    items: Sequence[Item], seconds: float = 3.0, exact_limit: int = EXACT_LIMIT
) -> PartitionResult:
    """把零和主体集合划分为尽可能多的零和子集。"""
    items = [(entity_id, int(amount)) for entity_id, amount in items if int(amount) != 0]
    total = sum(amount for _, amount in items)
    if total != 0:
        raise ValueError(f"净头寸合计不为零：{total}")
    if not items:
        return PartitionResult([], True)

    groups: List[Group] = []
    remaining = list(items)

    # 1) 金额完全对冲的两两配对：拆出配对不会减少可形成的组数
    by_amount: Dict[int, List[Item]] = {}
    for item in remaining:
        by_amount.setdefault(item[1], []).append(item)
    used: set[str] = set()
    for amount in sorted(by_amount):
        if amount <= 0:
            continue
        positives = by_amount.get(amount, [])
        negatives = by_amount.get(-amount, [])
        while positives and negatives:
            pair = [positives.pop(0), negatives.pop(0)]
            groups.append(pair)
            used.update(item[0] for item in pair)
    remaining = [item for item in remaining if item[0] not in used]
    if not remaining:
        return PartitionResult(groups, True)

    # 2) 精确搜索 / 启发式
    deadline = _now() + max(0.05, float(seconds))
    if len(remaining) <= exact_limit:
        try:
            exact = _exact_partition(remaining, deadline)
            return PartitionResult(groups + exact, True)
        except SolverTimeout:
            pass
    heuristic = _heuristic_partition(remaining, deadline)
    return PartitionResult(groups + heuristic, False)


def _exact_partition(items: Sequence[Item], deadline: float) -> List[Group]:
    memo: Dict[tuple, List[Group]] = {}
    stats = {"nodes": 0}

    def solve(rem: Tuple[Item, ...]) -> List[Group]:
        if not rem:
            return []
        key = tuple(sorted(rem, key=lambda item: (item[1], item[0])))
        cached = memo.get(key)
        if cached is not None:
            return cached
        if _now() > deadline:
            raise SolverTimeout
        stats["nodes"] += 1
        if stats["nodes"] > NODE_BUDGET:
            raise SolverTimeout

        positions = sum(1 for _, amount in rem if amount > 0)
        negatives = sum(1 for _, amount in rem if amount < 0)
        upper_bound = min(positions, negatives)
        if upper_bound <= 1:
            memo[key] = [list(rem)]
            return memo[key]

        pivot = max(rem, key=lambda item: (abs(item[1]), item[1]))
        rest = tuple(item for item in rem if item[0] != pivot[0])
        target = -pivot[1]
        best: Optional[List[Group]] = None
        seen_subsets: set[tuple] = set()

        for subset in _subsets_with_sum(rest, target, deadline, stats):
            signature = tuple(sorted(item[0] for item in subset))
            if signature in seen_subsets:
                continue
            seen_subsets.add(signature)
            subset_ids = {item[0] for item in subset}
            leftover = tuple(item for item in rest if item[0] not in subset_ids)
            remainder = solve(leftover)
            candidate = [list((pivot,) + subset)] + remainder
            if best is None or len(candidate) > len(best):
                best = candidate
                if len(best) >= upper_bound:
                    break
        if best is None:
            best = [list(rem)]
        memo[key] = best
        return best

    result = solve(tuple(items))
    return result


def _subsets_with_sum(
    items: Sequence[Item], target: int, deadline: float, stats: dict
):
    """枚举和为目标值的子集（可剪枝、可超时）。"""
    ordered = sorted(items, key=lambda item: (abs(item[1]), item[1]), reverse=True)
    n = len(ordered)
    suffix_max = [0] * (n + 1)
    suffix_min = [0] * (n + 1)
    for index in range(n - 1, -1, -1):
        amount = ordered[index][1]
        suffix_max[index] = suffix_max[index + 1] + max(0, amount)
        suffix_min[index] = suffix_min[index + 1] + min(0, amount)

    chosen: List[Item] = []

    def walk(index: int, remaining: int):
        if remaining == 0:
            yield tuple(chosen)
            return
        if index >= n:
            return
        if remaining > suffix_max[index] or remaining < suffix_min[index]:
            return
        if _now() > deadline:
            raise SolverTimeout
        stats["nodes"] += 1
        if stats["nodes"] > NODE_BUDGET:
            raise SolverTimeout

        previous = None
        for pos in range(index, n):
            amount = ordered[pos][1]
            if previous is not None and amount == previous:
                continue
            previous = amount
            chosen.append(ordered[pos])
            yield from walk(pos + 1, remaining - amount)
            chosen.pop()

    yield from walk(0, target)


def _heuristic_partition(items: Sequence[Item], deadline: float) -> List[Group]:
    """启发式：反复剥离 3 元、4 元零和子集，剩余整体成组。"""
    remaining = list(items)
    groups: List[Group] = []
    for size in (3, 4):
        if len(remaining) <= size:
            continue
        # 组合爆炸保护：大规模集合只尝试 3 元子集
        if size == 4 and len(remaining) > 45:
            continue
        if size == 3 and len(remaining) > 120:
            continue
        changed = True
        while changed and len(remaining) >= size:
            changed = False
            if _now() > deadline:
                break
            for combo in itertools.combinations(remaining, size):
                if sum(item[1] for item in combo) == 0:
                    groups.append(list(combo))
                    ids = {item[0] for item in combo}
                    remaining = [item for item in remaining if item[0] not in ids]
                    changed = True
                    break
    if remaining:
        if sum(item[1] for item in remaining) != 0:
            raise ValueError("划分剩余集合不是零和集合")
        groups.append(remaining)
    return groups


def settle_group(group: Sequence[Item], order: Dict[str, int] | None = None) -> List[dict]:
    """对一个零和组生成 n-1 笔清偿交易（每笔至少清零一个主体）。"""
    order = order or {}
    debtors = sorted(
        [(entity_id, -amount) for entity_id, amount in group if amount < 0],
        key=lambda item: (order.get(item[0], 10**9), item[0]),
    )
    creditors = sorted(
        [(entity_id, amount) for entity_id, amount in group if amount > 0],
        key=lambda item: (order.get(item[0], 10**9), item[0]),
    )
    transactions: List[dict] = []
    i = j = 0
    while i < len(debtors) and j < len(creditors):
        payer, payable = debtors[i]
        payee, receivable = creditors[j]
        amount = min(payable, receivable)
        if amount > 0:
            transactions.append({"from": payer, "to": payee, "amount_cents": int(amount)})
        debtors[i] = (payer, payable - amount)
        creditors[j] = (payee, receivable - amount)
        if debtors[i][1] == 0:
            i += 1
        if creditors[j][1] == 0:
            j += 1
    if i != len(debtors) or j != len(creditors):
        raise ValueError("零和组清偿未完全结清")
    return transactions


def build_liquidity_schedule(
    transactions: Sequence[dict],
    positions: Dict[str, dict],
    entities: Dict[str, dict],
    period_days: int = 30,
    periods: int = 3,
    base_date: str | None = None,
) -> List[dict]:
    """对可动用资金不足的付款方给出分期执行建议（不改变最小笔数方案）。"""
    payables: Dict[str, int] = {}
    for tx in transactions:
        payables[tx["from"]] = payables.get(tx["from"], 0) + int(tx["amount_cents"])
    constrained = []
    for entity_id, payable in payables.items():
        cash = int((entities.get(entity_id) or {}).get("available_cash_cents") or 0)
        if cash < payable:
            constrained.append((entity_id, payable, cash))

    if not constrained:
        return []

    start = date.fromisoformat(base_date) if base_date else date.today()
    schedule: List[dict] = []
    for entity_id, payable, cash in constrained:
        periods = max(1, int(periods))
        if cash <= 0:
            # 无当期资金时，按协商分期平均摊到各期
            capacities = [payable // periods] * periods
            capacities[-1] += payable - sum(capacities)
        else:
            first_capacity = min(cash, payable)
            remaining = payable - first_capacity
            capacities = [first_capacity]
            if periods > 1:
                share = remaining // (periods - 1)
                capacities += [share] * (periods - 1)
                capacities[-1] += remaining - share * (periods - 1)
            if sum(capacities) < payable:
                capacities[-1] += payable - sum(capacities)

        outgoing = [tx for tx in transactions if tx["from"] == entity_id]
        for tx in outgoing:
            amount = int(tx["amount_cents"])
            for period_index, capacity in enumerate(capacities):
                if amount <= 0:
                    break
                if capacity <= 0:
                    continue
                chunk = min(amount, capacity)
                schedule.append(
                    {
                        "payer": entity_id,
                        "payee": tx["to"],
                        "amount_cents": chunk,
                        "period": period_index + 1,
                        "due_date": (start + timedelta(days=period_days * (period_index + 1))).isoformat(),
                    }
                )
                amount -= chunk
                capacities[period_index] -= chunk
            if amount > 0:  # 兜底，保证金额守恒
                schedule.append(
                    {
                        "payer": entity_id,
                        "payee": tx["to"],
                        "amount_cents": amount,
                        "period": periods,
                        "due_date": (start + timedelta(days=period_days * periods)).isoformat(),
                    }
                )
    return schedule
