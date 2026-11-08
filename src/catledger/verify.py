"""Independent structural verification of a saved plan (not an optimality proof)."""

from __future__ import annotations

from collections import Counter
from typing import Any

from catledger.model import InputError, Problem


def _positive_int(value: Any, label: str, *, zero_ok: bool = False) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < (0 if zero_ok else 1):
        raise InputError(f"invalid {label}")
    return value


def verify_plan(problem: Problem, plan: Any) -> dict[str, int]:
    if not isinstance(plan, dict):
        raise InputError("plan must be a JSON object")
    if type(plan.get("schema_version")) is not int or plan.get("schema_version") != 1 or plan.get("job_id") != problem.job_id:
        raise InputError("plan schema version or job id does not match")
    if plan.get("input_sha256") != problem.fingerprint:
        raise InputError("plan does not match the supplied input (SHA-256 mismatch)")
    if plan.get("kerf_per_cut_mm") != problem.kerf_mm:
        raise InputError("plan kerf does not match the input")
    if plan.get("min_reusable_offcut_mm") != problem.min_reusable_offcut_mm:
        raise InputError("plan offcut threshold does not match the input")
    if not isinstance(plan.get("planning_method"), str) or plan.get("planning_method") not in {"heuristic", "exact", "search_limited"}:
        raise InputError("invalid planning_method")
    if not isinstance(plan.get("proven_optimal"), bool):
        raise InputError("invalid proven_optimal flag")
    if plan["proven_optimal"] != (plan["planning_method"] == "exact"):
        raise InputError("planning_method and proven_optimal flag disagree")
    _positive_int(plan.get("search_nodes"), "search_nodes", zero_ok=True)
    rows = plan.get("boards")
    if not isinstance(rows, list) or not rows or len(rows) > sum(s.quantity for s in problem.stock):
        raise InputError("invalid boards list")
    demand_map = {d.id: d for d in problem.demands}
    stock_map = {s.id: s for s in problem.stock}
    stock_seen: Counter[str] = Counter()
    demand_seen: Counter[str] = Counter()
    board_ids: set[str] = set()
    totals = {"material_cost_cents": 0, "unrecoverable_mm": 0,
              "boards_used": 0, "total_leftover_mm": 0}
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            raise InputError(f"boards[{index}] is not an object")
        if not isinstance(row.get("stock_id"), str):
            raise InputError(f"board {index}: stock_id must be a string")
        stock = stock_map.get(row.get("stock_id"))
        if stock is None:
            raise InputError(f"unknown stock in board {index}")
        stock_seen[stock.id] += 1
        if stock_seen[stock.id] > stock.quantity:
            raise InputError(f"stock {stock.id} used more than available quantity")
        board_id = f"{stock.id}-{stock_seen[stock.id]:03d}"
        if row.get("board_id") != board_id or board_id in board_ids:
            raise InputError(f"invalid/duplicate board id: {row.get('board_id')}")
        board_ids.add(board_id)
        expected = {"stock_kind": stock.kind, "length_mm": stock.length_mm,
                    "usable_mm": stock.usable_mm,
                    "trim_start_mm": stock.trim_start_mm, "trim_end_mm": stock.trim_end_mm,
                    "cost_cents": stock.cost_cents}
        for key, value in expected.items():
            if row.get(key) != value or isinstance(row.get(key), bool):
                raise InputError(f"board {board_id}: {key} is inconsistent")
        pieces = row.get("pieces")
        if not isinstance(pieces, list) or not pieces:
            raise InputError(f"board {board_id}: empty/invalid pieces")
        length_sum = 0
        for piece in pieces:
            if not isinstance(piece, dict):
                raise InputError(f"board {board_id}: piece must be an object")
            if not isinstance(piece.get("demand_id"), str):
                raise InputError(f"board {board_id}: demand_id must be a string")
            demand = demand_map.get(piece.get("demand_id"))
            if demand is None or piece.get("length_mm") != demand.length_mm or isinstance(piece.get("length_mm"), bool):
                raise InputError(f"board {board_id}: invalid piece")
            demand_seen[demand.id] += 1
            if demand_seen[demand.id] > demand.quantity:
                raise InputError(f"demand {demand.id} occurs too often")
            length_sum += demand.length_mm
        kerf_total = len(pieces) * problem.kerf_mm
        used = length_sum + kerf_total
        rem = stock.usable_mm - used
        if rem < 0:
            raise InputError(f"board {board_id}: pieces overrun usable stock")
        reuse = rem if rem >= problem.min_reusable_offcut_mm else 0
        for key, value in {"kerf_total_mm": kerf_total, "used_mm": used,
                           "leftover_mm": rem, "reusable_offcut_mm": reuse}.items():
            if row.get(key) != value or isinstance(row.get(key), bool):
                raise InputError(f"board {board_id}: {key} is inconsistent")
        totals["material_cost_cents"] += stock.cost_cents
        totals["unrecoverable_mm"] += kerf_total + stock.trim_start_mm + stock.trim_end_mm
        if not reuse:
            totals["unrecoverable_mm"] += rem
        totals["boards_used"] += 1
        totals["total_leftover_mm"] += rem
    if demand_seen != Counter({d.id: d.quantity for d in problem.demands}):
        raise InputError("plan does not fulfill exactly all requested pieces")
    if not isinstance(plan.get("objective"), dict) or any(
        type(plan["objective"].get(key)) is not int for key in totals
    ) or plan.get("objective") != totals:
        raise InputError("plan objective does not match the physical allocations")
    return totals
