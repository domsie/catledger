"""Safe deterministic text, CSV and SVG presentation of verified plans."""

from __future__ import annotations

import csv
from html import escape
from io import StringIO
from typing import Any


def as_text(plan: dict[str, Any]) -> str:
    obj = plan["objective"]
    lines = [
        f"CatLedger plan: {plan['job_id']}",
        f"Method: {plan['planning_method']} (optimality proven: {str(plan['proven_optimal']).lower()})",
        f"Material cost: {obj['material_cost_cents']} cents | Boards: {obj['boards_used']}",
        f"Unrecoverable: {obj['unrecoverable_mm']} mm | Leftover: {obj['total_leftover_mm']} mm",
    ]
    for board in plan["boards"]:
        names = ", ".join(f"{p['demand_id']} ({p['length_mm']} mm)" for p in board["pieces"])
        lines.append(f"  {board['board_id']}: {names}; kerf {board['kerf_total_mm']} mm; "
                     f"left {board['leftover_mm']} mm (reusable {board['reusable_offcut_mm']} mm)")
    return "\n".join(lines) + "\n"


def as_csv(plan: dict[str, Any]) -> str:
    output = StringIO(newline="")
    columns = ["job_id", "board_id", "stock_id", "stock_kind", "demand_id", "length_mm",
               "kerf_mm", "board_leftover_mm", "board_reusable_offcut_mm", "board_cost_cents"]
    writer = csv.DictWriter(output, fieldnames=columns, lineterminator="\n")
    writer.writeheader()
    for board in plan["boards"]:
        for piece in board["pieces"]:
            writer.writerow({"job_id": plan["job_id"], "board_id": board["board_id"],
                             "stock_id": board["stock_id"], "stock_kind": board["stock_kind"],
                             "demand_id": piece["demand_id"], "length_mm": piece["length_mm"],
                             "kerf_mm": plan["kerf_per_cut_mm"],
                             "board_leftover_mm": board["leftover_mm"],
                             "board_reusable_offcut_mm": board["reusable_offcut_mm"],
                             "board_cost_cents": board["cost_cents"]})
    return output.getvalue()


def as_svg(plan: dict[str, Any]) -> str:
    """Generate static SVG with no scripts, external resources or embedded URLs."""
    width = 1050
    height = 80 + 105 * len(plan["boards"])
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
           '<rect width="100%" height="100%" fill="#ffffff"/>',
           f'<text x="24" y="34" font-size="18" font-family="sans-serif" fill="#111827">CatLedger: {escape(plan["job_id"])}</text>']
    for i, board in enumerate(plan["boards"]):
        top = 75 + i * 105
        usable = board["usable_mm"]
        scale = 990 / usable
        x = 24.0
        out.append(f'<text x="24" y="{top - 9}" font-family="sans-serif" font-size="13" fill="#374151">{escape(board["board_id"])} (usable {usable} mm)</text>')
        palette = ["#60a5fa", "#34d399", "#fbbf24", "#a78bfa", "#f472b6"]
        for j, piece in enumerate(board["pieces"]):
            w = piece["length_mm"] * scale
            out.append(f'<rect x="{x:.3f}" y="{top}" width="{w:.3f}" height="36" fill="{palette[j % len(palette)]}" stroke="#1f2937" stroke-width="0.5"/>')
            if w >= 50:
                out.append(f'<text x="{x + 4:.3f}" y="{top+22}" font-family="sans-serif" font-size="11" fill="#111827">{escape(piece["demand_id"])}</text>')
            x += w
            kerf = plan["kerf_per_cut_mm"] * scale
            if kerf:
                out.append(f'<rect x="{x:.3f}" y="{top}" width="{kerf:.3f}" height="36" fill="#374151"/>')
                x += kerf
        rem = board["leftover_mm"] * scale
        if rem:
            color = "#bbf7d0" if board["reusable_offcut_mm"] else "#e5e7eb"
            out.append(f'<rect x="{x:.3f}" y="{top}" width="{rem:.3f}" height="36" fill="{color}" stroke="#1f2937" stroke-width="0.5"/>')
        out.append(f'<text x="24" y="{top+57}" font-family="sans-serif" font-size="12" fill="#4b5563">Leftover {board["leftover_mm"]} mm; reusable {board["reusable_offcut_mm"]} mm</text>')
    out.append('</svg>')
    return "\n".join(out) + "\n"
