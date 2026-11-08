# CatLedger

**A local cutting-stock optimiser and reusable-offcut ledger for small workshops and DIY projects.**

CatLedger turns a list of required one-dimensional cuts and a finite supply of boards, strips or offcuts into a checkable cutting plan. It takes saw kerf, end trimming, material prices and a reusable-offcut threshold into account. The output includes machine-readable plans, a human-readable cut list, CSV and optional static SVG diagrams.

This is a **new, early-stage, AI-assisted personal open-source project**, begun on **8 November 2026**. The repository contains synthetic examples, not evidence of actual workshop use, an established user base, or an older development history. See [provenance](docs/PROVENANCE.md).

## What works now

- Strict JSON input validation using integer millimetres and integer cents (no floating-point rounding of cuts or prices).
- Cost-aware use of finite new-stock and offcut supplies, with start/end trim allowances and configurable saw kerf.
- A deterministic **exact branch-and-bound solver** for bounded small jobs. A plan is flagged `proven_optimal` only when the search finishes without exhausting its budget.
- Three deterministic greedy strategies and a clearly labelled heuristic fallback for larger jobs.
- A lexicographic objective: **material cost**, **unrecoverable length**, **boards used**, **total leftover length**.
- An **independent physical-consistency verifier** that checks material availability, requested piece counts, dimensions, kerf and recorded totals. It does **not** independently prove optimality.
- JSON, text, CSV and standalone SVG exports; no network requests or external runtime dependencies.
- Regression and adversarial tests, plus a randomized cross-check against an independent exhaustive oracle on small synthetic jobs.

## Quick start

Requires **Python 3.11 or newer**. No runtime packages or database needed.

```bash
python -m pip install -e .
catledger plan examples/workshop.json --format text
catledger plan examples/workshop.json --output plan.json --svg layout.svg
catledger verify examples/workshop.json plan.json
catledger verify examples/workshop.json examples/expected-workshop.plan.json
catledger plan examples/offcut_first.json --mode heuristic --output alternative.json
catledger compare examples/workshop.json plan.json plan.json
```

Use the same input job in both arguments to `compare` (the last command shows a self-comparison). For two distinct approaches, generate exact and heuristic plans from the **same input** and compare them.

You can also run without installing the package, from the project directory:

```bash
PYTHONPATH=src python -m catledger plan examples/workshop.json --format text
PYTHONPATH=src python -m unittest discover -s tests -p 'test_*.py' -v
```

On Windows PowerShell after installing, use the `catledger` entry point directly. `--output` and `--svg` refuse to overwrite existing files unless `--overwrite` is explicitly set.

## Job schema

```json
{
  "job_id": "shelf_job",
  "kerf_mm": 3,
  "min_reusable_offcut_mm": 250,
  "demands": [
    {"id": "shelf", "length_mm": 600, "quantity": 2}
  ],
  "stock": [
    {"id": "scrap", "length_mm": 800, "quantity": 1, "cost_cents": 0, "kind": "offcut"},
    {"id": "new", "length_mm": 1800, "quantity": 1, "cost_cents": 950, "kind": "new", "trim_start_mm": 5, "trim_end_mm": 5}
  ]
}
```

- `kind` defaults to `new`; the kind is descriptive, **not** an automatic pricing rule: use `cost_cents: 0` if an offcut is already owned and should carry no incremental cost.
- `trim_start_mm` and `trim_end_mm` default to zero.
- `min_reusable_offcut_mm` defaults to 250.
- Each requested part is assumed to need **one full kerf**, even when an exact physical layout might allow the final part to be kept without an additional cut. This conservative convention is applied consistently to every solver and the verifier.
- All stock dimensions refer to **one-dimensional lengths**, not sheet cutting, mixed widths, material grain or blade safety constraints.
- Rejects nonpositive sizes, invalid identities, duplicate IDs, oversized inputs and impossible individual cuts.

## Correctness and limitations

The exact mode is an exhaustive, memoized branch-and-bound search limited to **16 pieces** and **32 available stock units**. It has a finite node budget and **will not claim optimality if that budget is exhausted**. The larger `auto` jobs use a heuristic, which can fail to find a solution even when one exists. Read the [algorithm/design notes](docs/DESIGN.md) and the [limitations](docs/LIMITATIONS.md) before cutting real material.

Generated SVGs are **visual aids**, not scale-certified machine instructions. Verify measurements and safe cutting practices independently before operating any tools.

## Development

Run the test suite:

```bash
python -m unittest discover -s tests -p 'test_*.py' -v
```

The CI workflow targets Linux and Windows across Python 3.11–3.13. The mere presence of that workflow is **not** evidence that hosted CI has already passed. A successful CI result must be checked after the repository is published.

See [ROADMAP.md](ROADMAP.md) for proposed multi-session development milestones with over 20 hours of nontrivial work ahead and [docs/PROVENANCE.md](docs/PROVENANCE.md) for the project's creation context.

## License

MIT, copyright 2026 Dominik Siefert. See [LICENSE](LICENSE).
