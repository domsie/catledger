"""Correctness, determinism, edge cases, exact/heuristic mode distinction."""
import copy
import unittest

from catledger.model import InputError, parse_problem
from catledger.solver import solve
from catledger.verify import verify_plan


def data(demands, stock, kerf=0, threshold=250):
    return parse_problem({"job_id": "j", "kerf_mm": kerf,
                          "min_reusable_offcut_mm": threshold, "demands": demands, "stock": stock})


def demand(name, length, n=1):
    return {"id": name, "length_mm": length, "quantity": n}


def stock(name, length, n=1, cost=0, kind="new", **kwargs):
    return {"id": name, "length_mm": length, "quantity": n,
            "cost_cents": cost, "kind": kind, **kwargs}


class SolverTests(unittest.TestCase):
    def test_exact_finds_single_board_over_two_cheaper_than_per_piece(self):
        p = data([demand("a", 600, 2)],
                 [stock("big", 1300, 1, 200), stock("small", 700, 2, 120)])
        result = solve(p, mode="exact")
        self.assertEqual(result["objective"]["material_cost_cents"], 200)
        self.assertEqual(result["objective"]["boards_used"], 1)
        self.assertTrue(result["proven_optimal"])
        verify_plan(p, result)

    def test_cost_objective_dominates_waste(self):
        p = data([demand("a", 600, 2)],
                 [stock("big", 1300, 1, 170), stock("small", 700, 2, 80)])
        r = solve(p, mode="exact")
        self.assertEqual(r["objective"]["material_cost_cents"], 160)
        self.assertEqual(r["objective"]["boards_used"], 2)

    def test_offcut_beats_new_stock(self):
        p = data([demand("a", 600, 2)],
                 [stock("scrap", 700, 2, 0, "offcut"), stock("new", 1300, 1, 500)])
        r = solve(p, mode="exact")
        self.assertEqual(r["objective"]["material_cost_cents"], 0)
        self.assertEqual(len(r["boards"]), 2)

    def test_kerf_is_one_cut_per_part(self):
        p = data([demand("a", 500, 2)], [stock("board", 1005, 2, 50)], kerf=3)
        r = solve(p, mode="exact")
        self.assertEqual(r["objective"]["boards_used"], 2)
        self.assertEqual(sum(b["kerf_total_mm"] for b in r["boards"]), 6)

    def test_exact_fit_with_kerf(self):
        p = data([demand("a", 500, 2)], [stock("board", 1006, 1, 50)], kerf=3)
        r = solve(p, mode="exact")
        self.assertEqual(r["boards"][0]["leftover_mm"], 0)

    def test_unrecoverable_includes_kerf_and_trim(self):
        p = data([demand("a", 400)],
                 [stock("board", 600, 1, 50, trim_start_mm=12, trim_end_mm=8)],
                 kerf=3, threshold=250)
        r = solve(p, mode="exact")
        self.assertEqual(r["objective"]["unrecoverable_mm"], 3 + 20 + 177)

    def test_reusable_offcut_not_unrecoverable(self):
        p = data([demand("a", 400)], [stock("board", 800, 1, 0)], kerf=3, threshold=250)
        r = solve(p, mode="exact")
        self.assertEqual(r["boards"][0]["reusable_offcut_mm"], 397)
        self.assertEqual(r["objective"]["unrecoverable_mm"], 3)

    def test_threshold_exactly_met_is_reusable(self):
        p = data([demand("a", 500)], [stock("board", 750, 1, 0)], threshold=250)
        r = solve(p, mode="exact")
        self.assertEqual(r["boards"][0]["reusable_offcut_mm"], 250)

    def test_tie_break_reduces_unrecoverable(self):
        p = data([demand("a", 500)], [stock("a", 650, 1, 100), stock("b", 800, 1, 100)], threshold=250)
        r = solve(p, mode="exact")
        self.assertEqual(r["boards"][0]["stock_id"], "b")
        self.assertEqual(r["objective"]["unrecoverable_mm"], 0)

    def test_tie_break_reduces_board_count(self):
        p = data([demand("a", 500, 2)],
                 [stock("big", 1100, 1, 0), stock("small", 550, 2, 0)], threshold=2000)
        r = solve(p, mode="exact")
        self.assertEqual(r["objective"]["boards_used"], 1)

    def test_infeasible_sufficient_total_capacity_but_packing_impossible(self):
        p = data([demand("a", 600, 3)], [stock("board", 1000, 2)])
        with self.assertRaisesRegex(InputError, "no feasible"):
            solve(p, mode="exact")

    def test_demand_exceeds_number_of_boards(self):
        p = data([demand("a", 600, 5)], [stock("board", 800, 2)])
        with self.assertRaises(InputError):
            solve(p, mode="exact")

    def test_heuristic_and_exact_marked_correctly(self):
        p = data([demand("a", 500)], [stock("board", 1000, 1)])
        h = solve(p, mode="heuristic")
        e = solve(p, mode="exact")
        self.assertFalse(h["proven_optimal"])
        self.assertEqual(h["search_nodes"], 0)
        self.assertTrue(e["proven_optimal"])
        self.assertGreater(e["search_nodes"], 0)

    def test_auto_uses_exact_for_small_job(self):
        p = data([demand("a", 500, 2)], [stock("board", 1100, 2)])
        self.assertTrue(solve(p)["proven_optimal"])

    def test_auto_uses_heuristic_for_many_pieces(self):
        p = data([demand("a", 100, 17)], [stock("board", 10000, 3)])
        r = solve(p)
        self.assertFalse(r["proven_optimal"])
        verify_plan(p, r)

    def test_explicit_exact_limit(self):
        p = data([demand("a", 100, 17)], [stock("board", 10000, 3)])
        with self.assertRaisesRegex(InputError, "exact mode requires"):
            solve(p, mode="exact")

    def test_search_budget_avoids_false_optimality(self):
        p = data([demand("a", 400, 3)], [stock("board", 1500, 3)])
        with self.assertRaisesRegex(InputError, "node budget"):
            solve(p, mode="exact", node_budget=1)
        r = solve(p, mode="auto", node_budget=1)
        self.assertFalse(r["proven_optimal"])
        self.assertEqual(r["planning_method"], "search_limited")
        verify_plan(p, r)

    def test_refuses_invalid_mode_or_budget(self):
        p = data([demand("a", 500)], [stock("board", 1000)])
        for kw in ({"mode": "unsafe"}, {"node_budget": 0}, {"node_budget": True}):
            with self.subTest(kw=kw), self.assertRaises(InputError):
                solve(p, **kw)

    def test_same_input_same_output(self):
        p = data([demand("a", 550, 2), demand("b", 300, 3)],
                 [stock("big", 1500, 2, 90), stock("small", 800, 2, 40)])
        self.assertEqual(solve(p), solve(p))

    def test_does_not_mutate_input(self):
        raw = {"job_id": "j", "kerf_mm": 0,
               "demands": [demand("a", 600)], "stock": [stock("board", 700)]}
        original = copy.deepcopy(raw)
        solve(parse_problem(raw))
        self.assertEqual(raw, original)

    def test_leftover_not_negative(self):
        p = data([demand("a", 600, 3), demand("b", 200, 5)],
                 [stock("a", 1300, 4, 100), stock("b", 900, 4, 75)], kerf=4)
        r = solve(p)
        self.assertTrue(all(b["leftover_mm"] >= 0 for b in r["boards"]))


if __name__ == "__main__":
    unittest.main()
