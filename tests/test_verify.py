"""Adversarial tampering tests for the independent structural verifier."""
import copy
import unittest

from catledger.model import InputError, parse_problem
from catledger.solver import solve
from catledger.verify import verify_plan


class VerifyTests(unittest.TestCase):
    def setUp(self):
        self.problem = parse_problem({
            "job_id": "audit_job", "kerf_mm": 3, "min_reusable_offcut_mm": 200,
            "demands": [{"id": "A", "length_mm": 350, "quantity": 2}],
            "stock": [{"id": "Board", "length_mm": 800, "quantity": 2, "cost_cents": 200}],
        })
        self.plan = solve(self.problem, mode="exact")

    def test_valid_plan(self):
        out = verify_plan(self.problem, self.plan)
        self.assertEqual(out, self.plan["objective"])

    def assert_tampered_rejected(self, change):
        invalid = copy.deepcopy(self.plan)
        change(invalid)
        with self.assertRaises(InputError):
            verify_plan(self.problem, invalid)

    def test_wrong_hash(self):
        self.assert_tampered_rejected(lambda p: p.update(input_sha256="0"*64))

    def test_wrong_job_id(self):
        self.assert_tampered_rejected(lambda p: p.update(job_id="another"))

    def test_wrong_schema(self):
        self.assert_tampered_rejected(lambda p: p.update(schema_version=2))

    def test_wrong_objective(self):
        self.assert_tampered_rejected(lambda p: p["objective"].update(material_cost_cents=0))

    def test_wrong_physical_leftover(self):
        self.assert_tampered_rejected(lambda p: p["boards"][0].update(leftover_mm=777))

    def test_wrong_physical_kerf(self):
        self.assert_tampered_rejected(lambda p: p["boards"][0].update(kerf_total_mm=0))

    def test_wrong_stock_quantity(self):
        self.assert_tampered_rejected(lambda p: p["boards"].append(copy.deepcopy(p["boards"][0])))

    def test_missing_piece(self):
        self.assert_tampered_rejected(lambda p: p["boards"][0]["pieces"].pop())

    def test_extra_piece(self):
        self.assert_tampered_rejected(lambda p: p["boards"][0]["pieces"].append({"demand_id": "A", "length_mm": 350}))

    def test_wrong_stock_id(self):
        self.assert_tampered_rejected(lambda p: p["boards"][0].update(stock_id="other"))

    def test_wrong_stock_cost(self):
        self.assert_tampered_rejected(lambda p: p["boards"][0].update(cost_cents=0))

    def test_false_optimality_claim(self):
        self.assert_tampered_rejected(lambda p: p.update(proven_optimal=False))

    def test_proven_only_exact_claim(self):
        self.assert_tampered_rejected(lambda p: p.update(planning_method="heuristic"))

    def test_invalid_search_nodes(self):
        self.assert_tampered_rejected(lambda p: p.update(search_nodes=-1))

    def test_invalid_board_id(self):
        self.assert_tampered_rejected(lambda p: p["boards"][0].update(board_id="../escape"))

    def test_boolean_instead_of_integer(self):
        self.assert_tampered_rejected(lambda p: p["boards"][0].update(usable_mm=True))

    def test_unhashable_stock_id_rejected(self):
        self.assert_tampered_rejected(lambda p: p["boards"][0].update(stock_id=["Board"]))

    def test_unhashable_demand_id_rejected(self):
        self.assert_tampered_rejected(lambda p: p["boards"][0]["pieces"][0].update(demand_id={"id": "A"}))

    def test_unhashable_method_rejected(self):
        self.assert_tampered_rejected(lambda p: p.update(planning_method=["exact"]))

    def test_boolean_objective_rejected(self):
        self.assert_tampered_rejected(lambda p: p["objective"].update(boards_used=True))

    def test_boolean_schema_rejected(self):
        self.assert_tampered_rejected(lambda p: p.update(schema_version=True))

    def test_invalid_document_type(self):
        with self.assertRaises(InputError):
            verify_plan(self.problem, [])


if __name__ == "__main__":
    unittest.main()
