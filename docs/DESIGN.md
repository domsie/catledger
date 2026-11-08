# Architecture and algorithm

## Domain and units

The input describes demanded parts (ID, length in whole millimetres, count) and stock *types* (ID, full length, available count, unit cost in integer cents, optional end trims and new/offcut classification). Every stock unit is assumed physically interchangeable within its type. A piece consumes `length_mm + kerf_mm`. Usable capacity is `stock.length_mm - trim_start_mm - trim_end_mm`.

Using integer arithmetic avoids binary floating-point mistakes. No real customers or personal data are expected in input. The tool has no network, server or persistence layer; users control any JSON plans written to disk.

## Objective

Plans are ranked lexicographically by:

1. **Total material cost** in cents, including the configured cost of each used stock unit.
2. **Unrecoverable length** in millimetres: per-piece kerf + end trims of used units + leftover lengths smaller than the configured reuse threshold.
3. **Number of used stock units**.
4. **Total leftover length** in millimetres (a deterministic tie-breaker).

An uncut stock unit does not incur cost or waste. If a remainder meets the reusable threshold, its length is recorded as recoverable and is not penalised in the second objective. The ranking expresses one particular interpretation of 'use offcuts first'; alternative priorities are future work.

## Search

Part instances are sorted by descending length and then by demand ID, ensuring deterministic traversal. The exact solver explores placing the next part into any fitting opened unit or opening any permissible new stock type. It prunes symmetric open units of the same stock type and fill level, memoizes equivalent states (processed part prefix and sorted stock/fill pairs), and bounds branches exceeding the best already observed material cost. A deterministic greedy plan seeds the upper bound when available.

The search returns `proven_optimal=true` **only when all branches have been exhausted without hitting the node budget**. Its default budget is 150,000 nodes; explicit exact mode fails rather than misrepresenting a budget-limited result as exact. `auto` may fall back to a search-limited plan, flagged nonoptimal. Jobs above the small-instance boundaries use three greedy heuristics and return the best feasible result. A greedy failure is **not** a proof that the job is infeasible.

**Worst-case complexity is exponential.** The search cap is a resource protection, not a performance guarantee.

## Independent verifier

`catledger verify JOB PLAN` checks that a saved plan has a matching canonical input hash, the correct job ID, valid physical stock counts, the exact required set of parts, calculated kerf, trims, per-board remnants and recomputed objective values. It checks the *plan's consistency*; it neither independently audits the solver's optimality proof nor certifies machine-tool safety. A malicious JSON object could copy a false 'optimality' flag along with 'exact'; use test evidence or independent optimisation verification for high-stakes applications.

## Synthetic acceptance scenarios

- With one 1,300 mm board costing 200 cents and two 700 mm boards costing 120 cents each, cutting two 600 mm pieces must choose the cheaper single board.
- A 3 mm per-piece kerf prevents two 500 mm pieces fitting in 1,005 mm, but fits them in 1,006 mm.
- If a leftover meets the configured reuse threshold exactly, it counts as reusable.
- A tampered saved plan fails verification.
- A strict exact solve either completes and proves optimality or reports a search limit; it never silently downgrades certainty.
- Independently enumerated small random assignments agree with the exact solver's lexicographic scores.
