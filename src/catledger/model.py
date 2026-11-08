"""Strict, dependency-free JSON input model with integer millimetre arithmetic."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
from typing import Any

MAX_JSON_BYTES = 1_000_000
ID_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{0,39}$")


class InputError(ValueError):
    """User-correctable invalid input or infeasible planning request."""


@dataclass(frozen=True)
class Demand:
    id: str
    length_mm: int
    quantity: int


@dataclass(frozen=True)
class Stock:
    id: str
    length_mm: int
    quantity: int
    cost_cents: int
    kind: str
    trim_start_mm: int
    trim_end_mm: int

    @property
    def usable_mm(self) -> int:
        return self.length_mm - self.trim_start_mm - self.trim_end_mm


@dataclass(frozen=True)
class Problem:
    job_id: str
    kerf_mm: int
    min_reusable_offcut_mm: int
    demands: tuple[Demand, ...]
    stock: tuple[Stock, ...]

    @property
    def piece_count(self) -> int:
        return sum(d.quantity for d in self.demands)

    @property
    def canonical(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "kerf_mm": self.kerf_mm,
            "min_reusable_offcut_mm": self.min_reusable_offcut_mm,
            "demands": [{"id": d.id, "length_mm": d.length_mm, "quantity": d.quantity} for d in self.demands],
            "stock": [{"id": s.id, "length_mm": s.length_mm, "quantity": s.quantity,
                       "cost_cents": s.cost_cents, "kind": s.kind,
                       "trim_start_mm": s.trim_start_mm, "trim_end_mm": s.trim_end_mm} for s in self.stock],
        }

    @property
    def fingerprint(self) -> str:
        value = json.dumps(self.canonical, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _object(value: Any, name: str, allowed: set[str], required: set[str]) -> dict:
    if not isinstance(value, dict):
        raise InputError(f"{name} must be a JSON object")
    extra = set(value) - allowed
    missing = required - set(value)
    if extra or missing:
        raise InputError(f"{name}: unknown keys {sorted(extra)}; missing keys {sorted(missing)}")
    return value


def _integer(value: Any, name: str, low: int, high: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
        raise InputError(f"{name} must be an integer in [{low}, {high}]")
    return value


def _id(value: Any, name: str) -> str:
    if not isinstance(value, str) or not ID_PATTERN.fullmatch(value):
        raise InputError(f"{name} must start with a letter and contain only letters, digits, _ or - (max 40 chars)")
    return value


def parse_problem(data: Any) -> Problem:
    root = _object(data, "job", {"job_id", "kerf_mm", "min_reusable_offcut_mm", "demands", "stock"},
                   {"job_id", "kerf_mm", "demands", "stock"})
    job_id = _id(root["job_id"], "job_id")
    kerf = _integer(root["kerf_mm"], "kerf_mm", 0, 20)
    threshold = _integer(root.get("min_reusable_offcut_mm", 250), "min_reusable_offcut_mm", 0, 100_000)
    raw_demands = root["demands"]
    raw_stock = root["stock"]
    if not isinstance(raw_demands, list) or not 1 <= len(raw_demands) <= 100:
        raise InputError("demands must be a nonempty list of at most 100 types")
    if not isinstance(raw_stock, list) or not 1 <= len(raw_stock) <= 32:
        raise InputError("stock must be a nonempty list of at most 32 types")
    demands = []
    seen: set[str] = set()
    for index, value in enumerate(raw_demands):
        d = _object(value, f"demands[{index}]", {"id", "length_mm", "quantity"}, {"id", "length_mm", "quantity"})
        name = _id(d["id"], "demand id")
        if name in seen:
            raise InputError(f"duplicate demand id: {name}")
        seen.add(name)
        demands.append(Demand(name, _integer(d["length_mm"], "length_mm", 1, 100_000),
                              _integer(d["quantity"], "quantity", 1, 200)))
    if sum(d.quantity for d in demands) > 300:
        raise InputError("total requested pieces must not exceed 300")
    stocks = []
    seen.clear()
    for index, value in enumerate(raw_stock):
        s = _object(value, f"stock[{index}]",
                    {"id", "length_mm", "quantity", "cost_cents", "kind", "trim_start_mm", "trim_end_mm"},
                    {"id", "length_mm", "quantity", "cost_cents"})
        name = _id(s["id"], "stock id")
        if name in seen:
            raise InputError(f"duplicate stock id: {name}")
        seen.add(name)
        kind = s.get("kind", "new")
        if kind not in ("new", "offcut"):
            raise InputError("stock kind must be new or offcut")
        length = _integer(s["length_mm"], "length_mm", 1, 100_000)
        start = _integer(s.get("trim_start_mm", 0), "trim_start_mm", 0, 10_000)
        end = _integer(s.get("trim_end_mm", 0), "trim_end_mm", 0, 10_000)
        if start + end >= length:
            raise InputError(f"stock {name}: trims consume the entire stock")
        stocks.append(Stock(name, length, _integer(s["quantity"], "quantity", 1, 200),
                            _integer(s["cost_cents"], "cost_cents", 0, 100_000_000),
                            kind, start, end))
    if sum(s.quantity for s in stocks) > 500:
        raise InputError("total stock units must not exceed 500")
    if max(d.length_mm + kerf for d in demands) > max(s.usable_mm for s in stocks):
        raise InputError("at least one requested piece is longer than every usable stock length")
    return Problem(job_id, kerf, threshold, tuple(demands), tuple(stocks))


def load_json(path: str | Path) -> Any:
    p = Path(path)
    try:
        if p.stat().st_size > MAX_JSON_BYTES:
            raise InputError("JSON input exceeds the 1 MB safety limit")
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise InputError(f"cannot read valid JSON from {p}: {exc}") from exc


def load_problem(path: str | Path) -> Problem:
    return parse_problem(load_json(path))
