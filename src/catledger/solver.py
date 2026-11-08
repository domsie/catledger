"""Deterministic bounded cutting-stock solver; exact search is explicitly certified."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from catledger.model import InputError, Problem, Stock

MAX_EXACT_PIECES = 16
MAX_EXACT_STOCK_UNITS = 32
DEFAULT_NODE_BUDGET = 150_000


@dataclass
class Board:
    stock: Stock
    pieces: list[tuple[str, int]] = field(default_factory=list)
    used_mm: int = 0

    def remaining_mm(self) -> int:
        return self.stock.usable_mm - self.used_mm

    def clone(self) -> "Board":
        return Board(self.stock, self.pieces.copy(), self.used_mm)


def _pieces(problem: Problem) -> list[tuple[str, int]]:
    return sorted(((d.id, d.length_mm) for d in problem.demands for _ in range(d.quantity)),
                  key=lambda p: (-p[1], p[0]))


def _score(problem: Problem, boards: list[Board]) -> tuple[int, int, int, int]:
    cost = sum(b.stock.cost_cents for b in boards)
    unrecoverable = problem.kerf_mm * sum(len(b.pieces) for b in boards)
    unrecoverable += sum(b.stock.trim_start_mm + b.stock.trim_end_mm for b in boards)
    unused = 0
    for board in boards:
        rem = board.remaining_mm()
        unused += rem
        if rem < problem.min_reusable_offcut_mm:
            unrecoverable += rem
    return (cost, unrecoverable, len(boards), unused)


def _to_result(problem: Problem, boards: list[Board], *, strategy: str,
               proven: bool, nodes: int) -> dict[str, Any]:
    ordered = sorted(boards, key=lambda b: (b.stock.id, tuple(b.pieces)))
    counts: dict[str, int] = {}
    rows = []
    for board in ordered:
        counts[board.stock.id] = counts.get(board.stock.id, 0) + 1
        number = counts[board.stock.id]
        remaining = board.remaining_mm()
        rows.append({
            "board_id": f"{board.stock.id}-{number:03d}",
            "stock_id": board.stock.id,
            "stock_kind": board.stock.kind,
            "length_mm": board.stock.length_mm,
            "usable_mm": board.stock.usable_mm,
            "trim_start_mm": board.stock.trim_start_mm,
            "trim_end_mm": board.stock.trim_end_mm,
            "cost_cents": board.stock.cost_cents,
            "pieces": [{"demand_id": pid, "length_mm": length} for pid, length in board.pieces],
            "kerf_total_mm": len(board.pieces) * problem.kerf_mm,
            "used_mm": board.used_mm,
            "leftover_mm": remaining,
            "reusable_offcut_mm": remaining if remaining >= problem.min_reusable_offcut_mm else 0,
        })
    return {
        "schema_version": 1,
        "job_id": problem.job_id,
        "input_sha256": problem.fingerprint,
        "planning_method": strategy,
        "proven_optimal": proven,
        "search_nodes": nodes,
        "objective": {
            "material_cost_cents": _score(problem, boards)[0],
            "unrecoverable_mm": _score(problem, boards)[1],
            "boards_used": _score(problem, boards)[2],
            "total_leftover_mm": _score(problem, boards)[3],
        },
        "kerf_per_cut_mm": problem.kerf_mm,
        "min_reusable_offcut_mm": problem.min_reusable_offcut_mm,
        "boards": rows,
    }


def _heuristic(problem: Problem, variant: str) -> list[Board] | None:
    boards: list[Board] = []
    types = sorted(problem.stock, key=lambda s: s.id)
    supply = {s.id: s.quantity for s in types}
    for piece_id, length in _pieces(problem):
        consumed = length + problem.kerf_mm
        options = []
        for index, board in enumerate(boards):
            if board.remaining_mm() >= consumed:
                residual = board.remaining_mm() - consumed
                if variant == "best_fit":
                    rank = (0, residual, 0, board.stock.id, index)
                elif variant == "offcut_first":
                    rank = (0 if board.stock.kind == "offcut" else 1, 0, residual, board.stock.id, index)
                else:
                    rank = (0, 0, residual, board.stock.id, index)
                options.append((rank, index, None))
        for stock in types:
            if supply[stock.id] > 0 and stock.usable_mm >= consumed:
                residual = stock.usable_mm - consumed
                if variant == "best_fit":
                    rank = (1, residual, stock.cost_cents, stock.id, len(boards))
                elif variant == "offcut_first":
                    rank = (0 if stock.kind == "offcut" else 1, 1, residual, stock.id, len(boards))
                else:
                    rank = (stock.cost_cents, 1, residual, stock.id, len(boards))
                options.append((rank, None, stock))
        if not options:
            return None
        _, index, new_stock = min(options, key=lambda item: item[0])
        if new_stock is not None:
            supply[new_stock.id] -= 1
            boards.append(Board(new_stock))
            index = len(boards) - 1
        assert index is not None
        boards[index].pieces.append((piece_id, length))
        boards[index].used_mm += consumed
    return boards


def solve(problem: Problem, *, mode: str = "auto", node_budget: int = DEFAULT_NODE_BUDGET) -> dict[str, Any]:
    if mode not in {"auto", "heuristic", "exact"}:
        raise InputError("mode must be auto, heuristic or exact")
    if isinstance(node_budget, bool) or not isinstance(node_budget, int) or not 1 <= node_budget <= 1_000_000:
        raise InputError("node_budget must be an integer in [1, 1000000]")
    supply_count = sum(s.quantity for s in problem.stock)
    can_exact = problem.piece_count <= MAX_EXACT_PIECES and supply_count <= MAX_EXACT_STOCK_UNITS
    if mode == "exact" and not can_exact:
        raise InputError(f"exact mode requires <= {MAX_EXACT_PIECES} pieces and <= {MAX_EXACT_STOCK_UNITS} stock units")
    seeds = [_heuristic(problem, v) for v in ("cost", "best_fit", "offcut_first")]
    feasible = [p for p in seeds if p is not None]
    best = min(feasible, key=lambda b: _score(problem, b)) if feasible else None
    if mode == "heuristic" or (mode == "auto" and not can_exact):
        if best is None:
            raise InputError("heuristic could not find a feasible cutting plan; try changing stock or using exact mode")
        return _to_result(problem, best, strategy="heuristic", proven=False, nodes=0)

    pieces = _pieces(problem)
    types = sorted(problem.stock, key=lambda s: s.id)
    by_id = {s.id: s for s in types}
    stock_limits = {s.id: s.quantity for s in types}
    boards: list[Board] = []
    visited: set[tuple[int, tuple[tuple[str, int], ...]]] = set()
    nodes = 0
    exhausted = False

    def visit(index: int) -> None:
        nonlocal best, nodes, exhausted
        if exhausted:
            return
        nodes += 1
        if nodes > node_budget:
            exhausted = True
            return
        if best is not None and sum(b.stock.cost_cents for b in boards) > _score(problem, best)[0]:
            return
        state = (index, tuple(sorted((b.stock.id, b.used_mm) for b in boards)))
        if state in visited:
            return
        visited.add(state)
        if index == len(pieces):
            if best is None or _score(problem, boards) < _score(problem, best):
                best = [b.clone() for b in boards]
            return
        piece_id, length = pieces[index]
        consumed = length + problem.kerf_mm
        seen_existing: set[tuple[str, int]] = set()
        for board in boards:
            marker = (board.stock.id, board.used_mm)
            if marker in seen_existing:
                continue
            seen_existing.add(marker)
            if board.remaining_mm() < consumed:
                continue
            board.used_mm += consumed
            board.pieces.append((piece_id, length))
            visit(index + 1)
            board.pieces.pop()
            board.used_mm -= consumed
            if exhausted:
                return
        used_supply: dict[str, int] = {}
        for board in boards:
            used_supply[board.stock.id] = used_supply.get(board.stock.id, 0) + 1
        for stock in types:
            if used_supply.get(stock.id, 0) >= stock_limits[stock.id] or stock.usable_mm < consumed:
                continue
            new_board = Board(by_id[stock.id], [(piece_id, length)], consumed)
            boards.append(new_board)
            visit(index + 1)
            boards.pop()
            if exhausted:
                return

    visit(0)
    if best is None:
        if exhausted:
            raise InputError("exact search exhausted its node budget before finding a feasible plan")
        raise InputError("no feasible cutting plan exists with the supplied stock")
    if exhausted and mode == "exact":
        raise InputError("exact search exhausted its node budget; optimality cannot be certified")
    return _to_result(problem, best, strategy="exact" if not exhausted else "search_limited",
                      proven=not exhausted, nodes=min(nodes, node_budget))
