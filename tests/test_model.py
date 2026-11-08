"""Input boundaries, semantic constraints and stable fingerprints."""
import copy
import json
import tempfile
import unittest
from pathlib import Path

from catledger.model import InputError, load_problem, parse_problem


BASE = {
    "job_id": "job_one", "kerf_mm": 3, "min_reusable_offcut_mm": 250,
    "demands": [{"id": "piece_a", "length_mm": 500, "quantity": 2}],
    "stock": [{"id": "stock_a", "length_mm": 1200, "quantity": 2, "cost_cents": 300}],
}


class ModelTests(unittest.TestCase):
    def test_parse_valid_defaults(self):
        x = parse_problem(BASE)
        self.assertEqual(x.piece_count, 2)
        self.assertEqual(x.stock[0].kind, "new")
        self.assertEqual(x.stock[0].usable_mm, 1200)

    def test_defaults_equivalent_to_explicit_values(self):
        x = copy.deepcopy(BASE)
        x["stock"][0].update({"kind": "new", "trim_start_mm": 0, "trim_end_mm": 0})
        self.assertEqual(parse_problem(BASE).fingerprint, parse_problem(x).fingerprint)

    def test_job_order_does_not_change_fingerprint(self):
        x = dict(reversed(list(BASE.items())))
        self.assertEqual(parse_problem(BASE).fingerprint, parse_problem(x).fingerprint)

    def test_kerf_must_be_integer_not_bool(self):
        for value in [True, 1.5, "2", -1, 21]:
            x = copy.deepcopy(BASE)
            x["kerf_mm"] = value
            with self.subTest(value=value), self.assertRaises(InputError):
                parse_problem(x)

    def test_zero_demand_and_negative_stock_quantity(self):
        for location, value in [("demands", 0), ("stock", -1)]:
            x = copy.deepcopy(BASE)
            x[location][0]["quantity"] = value
            with self.subTest(location=location), self.assertRaises(InputError):
                parse_problem(x)

    def test_duplicate_demand(self):
        x = copy.deepcopy(BASE)
        x["demands"].append(x["demands"][0].copy())
        with self.assertRaisesRegex(InputError, "duplicate demand"):
            parse_problem(x)

    def test_duplicate_stock(self):
        x = copy.deepcopy(BASE)
        x["stock"].append(x["stock"][0].copy())
        with self.assertRaisesRegex(InputError, "duplicate stock"):
            parse_problem(x)

    def test_non_ascii_csv_formula_ids_not_allowed(self):
        for value in ["=1+1", "<script>", "with space", "", "../secret", "A" * 41]:
            x = copy.deepcopy(BASE)
            x["demands"][0]["id"] = value
            with self.subTest(value=value), self.assertRaises(InputError):
                parse_problem(x)

    def test_unknown_input_field_rejected(self):
        x = copy.deepcopy(BASE)
        x["token"] = "do-not-store"
        with self.assertRaisesRegex(InputError, "unknown keys"):
            parse_problem(x)

    def test_missing_required_field_rejected(self):
        x = copy.deepcopy(BASE)
        del x["stock"][0]["cost_cents"]
        with self.assertRaisesRegex(InputError, "missing keys"):
            parse_problem(x)

    def test_trim_reduces_capacity(self):
        x = copy.deepcopy(BASE)
        x["stock"][0].update({"trim_start_mm": 10, "trim_end_mm": 20})
        self.assertEqual(parse_problem(x).stock[0].usable_mm, 1170)

    def test_trim_cannot_consume_whole_stock(self):
        x = copy.deepcopy(BASE)
        x["stock"][0].update({"trim_start_mm": 900, "trim_end_mm": 300})
        with self.assertRaisesRegex(InputError, "entire stock"):
            parse_problem(x)

    def test_too_long_demand(self):
        x = copy.deepcopy(BASE)
        x["demands"][0]["length_mm"] = 1200
        with self.assertRaisesRegex(InputError, "longer than"):
            parse_problem(x)

    def test_allows_total_stock_length_insufficient_for_demand(self):
        x = copy.deepcopy(BASE)
        x["demands"][0]["quantity"] = 4
        parsed = parse_problem(x)
        self.assertEqual(parsed.piece_count, 4)

    def test_too_many_pieces(self):
        x = copy.deepcopy(BASE)
        x["demands"] = [{"id": "A", "length_mm": 100, "quantity": 200},
                         {"id": "B", "length_mm": 100, "quantity": 101}]
        with self.assertRaisesRegex(InputError, "300"):
            parse_problem(x)

    def test_file_read_and_overlarge_file(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "input.json"
            path.write_text(json.dumps(BASE), encoding="utf-8")
            self.assertEqual(load_problem(path).job_id, "job_one")
            path.write_bytes(b" " * 1_000_001)
            with self.assertRaisesRegex(InputError, "1 MB"):
                load_problem(path)

    def test_missing_file(self):
        with self.assertRaises(InputError):
            load_problem("/definitely-not-a-real-path/catledger.json")

    def test_invalid_json_file(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "input.json"
            path.write_text("{ invalid", encoding="utf-8")
            with self.assertRaises(InputError):
                load_problem(path)


if __name__ == "__main__":
    unittest.main()
