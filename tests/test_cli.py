"""End-to-end CLI and file safety tests."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from catledger.model import load_problem, parse_problem
from catledger.render import as_csv, as_svg, as_text
from catledger.solver import solve
from catledger.verify import verify_plan

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples" / "offcut_first.json"


def run_cli(*args):
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    return subprocess.run([sys.executable, "-m", "catledger", *map(str, args)],
                          cwd=ROOT, env=env, text=True, capture_output=True, check=False)


class CliTests(unittest.TestCase):
    def test_version(self):
        p = run_cli("--version")
        self.assertEqual(p.returncode, 0)
        self.assertIn("catledger 0.1.0", p.stdout)

    def test_json_roundtrip(self):
        result = run_cli("plan", EXAMPLE)
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual(data["job_id"], "offcut_reuse_demo")
        self.assertTrue(data["proven_optimal"])

    def test_golden_workshop_plan_still_verifies(self):
        job = load_problem(ROOT / "examples" / "workshop.json")
        saved = json.loads((ROOT / "examples" / "expected-workshop.plan.json").read_text(encoding="utf-8"))
        objective = verify_plan(job, saved)
        self.assertEqual(objective["material_cost_cents"], 1180)
        self.assertEqual(objective["boards_used"], 4)

    def test_text_output(self):
        p = run_cli("plan", EXAMPLE, "--format", "text")
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn("CatLedger plan", p.stdout)
        self.assertIn("reusable", p.stdout)

    def test_csv_output(self):
        p = run_cli("plan", EXAMPLE, "--format", "csv")
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn("job_id,board_id,stock_id", p.stdout)

    def test_plan_verify_compare_file_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            a, b = Path(tmp) / "a.json", Path(tmp) / "b.json"
            p = run_cli("plan", EXAMPLE, "--output", a, "--svg", Path(tmp) / "plan.svg")
            self.assertEqual(p.returncode, 0, p.stderr)
            self.assertTrue(a.exists())
            self.assertTrue((Path(tmp) / "plan.svg").read_text().startswith("<svg"))
            self.assertEqual(run_cli("verify", EXAMPLE, a).returncode, 0)
            self.assertEqual(run_cli("plan", EXAMPLE, "--mode", "heuristic", "--output", b).returncode, 0)
            cmp = run_cli("compare", EXAMPLE, a, b)
            self.assertEqual(cmp.returncode, 0, cmp.stderr)
            self.assertIn(json.loads(cmp.stdout)["winner"], ("first", "second", "tie"))

    def test_output_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "plan.json"
            out.write_text("preserve", encoding="utf-8")
            p = run_cli("plan", EXAMPLE, "--output", out)
            self.assertEqual(p.returncode, 2)
            self.assertEqual(out.read_text(), "preserve")
            p = run_cli("plan", EXAMPLE, "--output", out, "--overwrite")
            self.assertEqual(p.returncode, 0, p.stderr)
            self.assertIn("schema_version", out.read_text())

    def test_output_and_svg_cannot_be_same_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "both.json"
            p = run_cli("plan", EXAMPLE, "--output", path, "--svg", path)
            self.assertEqual(p.returncode, 2)
            self.assertFalse(path.exists())

    def test_missing_input_is_controlled_error(self):
        p = run_cli("plan", "/does/not/exist.json")
        self.assertEqual(p.returncode, 2)
        self.assertIn("catledger:", p.stderr)

    def test_invalid_node_budget(self):
        p = run_cli("plan", EXAMPLE, "--node-budget", "0")
        self.assertEqual(p.returncode, 2)

    def test_tampered_plan_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "invalid.json"
            r = json.loads(run_cli("plan", EXAMPLE).stdout)
            r["objective"]["material_cost_cents"] = 999
            path.write_text(json.dumps(r), encoding="utf-8")
            p = run_cli("verify", EXAMPLE, path)
            self.assertEqual(p.returncode, 2)
            self.assertIn("objective", p.stderr)

    def test_svg_is_static_and_escapes_id(self):
        raw = json.loads(EXAMPLE.read_text(encoding="utf-8"))
        raw["job_id"] = "Test_Job"
        plan = solve(parse_problem(raw))
        svg = as_svg(plan)
        self.assertIn("<svg", svg)
        self.assertNotIn("<script", svg)
        self.assertNotIn("href=", svg)
        self.assertNotIn("javascript:", svg)

    def test_renderers_do_not_mutate_plan(self):
        p = run_cli("plan", EXAMPLE)
        data = json.loads(p.stdout)
        old = json.dumps(data, sort_keys=True)
        as_csv(data); as_svg(data); as_text(data)
        self.assertEqual(json.dumps(data, sort_keys=True), old)


if __name__ == "__main__":
    unittest.main()
