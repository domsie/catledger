"""Cross-check exact search against a deliberately independent exhaustive oracle."""

from itertools import product
import random
import unittest

from catledger.model import InputError, parse_problem
from catledger.solver import solve
from catledger.verify import verify_plan


def brute_force(problem):
    """Assign every piece to physical stock units, excluding unused units at scoring."""
    units = [stock for s in problem.stock for stock in [s] * s.quantity]
    pieces = [(d.id, d.length_mm) for d in problem.demands for _ in range(d.quantity)]
    best = None
    for assignment in product(range(len(units)), repeat=len(pieces)):
        used = [0] * len(units)
        cuts = [0] * len(units)
        for index, (_, length) in enumerate(pieces):
            slot = assignment[index]
            used[slot] += length + problem.kerf_mm
            cuts[slot] += 1
        if any(used[i] > units[i].usable_mm for i in range(len(units))):
            continue
        cost = wasted = boards = remaining = 0
        for i, unit in enumerate(units):
            if cuts[i] == 0:
                continue
            boards += 1
            cost += unit.cost_cents
            rem = unit.usable_mm - used[i]
            remaining += rem
            wasted += cuts[i] * problem.kerf_mm + unit.trim_start_mm + unit.trim_end_mm
            if rem < problem.min_reusable_offcut_mm:
                wasted += rem
        score = (cost, wasted, boards, remaining)
        if best is None or score < best:
            best = score
    return best


class RandomizedOracleTests(unittest.TestCase):
    def test_exact_matches_independent_exhaustive_oracle_100_cases(self):
        rng = random.Random(20261108)
        feasible_count = 0
        infeasible_count = 0
        for case in range(100):
            lengths = [rng.randint(30, 120) for _ in range(rng.randint(1, 4))]
            demands = [{"id": f"P{i}", "length_mm": length, "quantity": 1}
                       for i, length in enumerate(lengths)]
            stock = [{"id": f"S{i}", "length_mm": rng.randint(max(lengths) + 14, 240),
                      "quantity": rng.randint(1, 2), "cost_cents": rng.randint(0, 12),
                      "trim_start_mm": rng.randint(0, 5), "trim_end_mm": rng.randint(0, 5)}
                     for i in range(rng.randint(1, 3))]
            kerf = rng.randint(0, 4)
            threshold = rng.randint(0, 120)
            p = parse_problem({"job_id": f"case_{case}", "kerf_mm": kerf,
                               "min_reusable_offcut_mm": threshold,
                               "demands": demands, "stock": stock})
            target = brute_force(p)
            if target is None:
                infeasible_count += 1
                with self.subTest(case=case), self.assertRaises(InputError):
                    solve(p, mode="exact")
            else:
                feasible_count += 1
                with self.subTest(case=case):
                    actual = solve(p, mode="exact")
                    verify_plan(p, actual)
                    self.assertEqual(tuple(actual["objective"][k] for k in (
                        "material_cost_cents", "unrecoverable_mm", "boards_used", "total_leftover_mm")), target)
                    self.assertTrue(actual["proven_optimal"])
        self.assertGreater(feasible_count, 20)
        self.assertGreater(infeasible_count, 5)
        self.assertEqual(feasible_count + infeasible_count, 100)


if __name__ == "__main__":
    unittest.main()
