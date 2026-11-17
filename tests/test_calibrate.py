import json
from pathlib import Path
import tempfile
import unittest

from jevidence.calibrate import bucket_floor, calibrate, compare, load_judgments, reliability, report, stability
from jevidence.cli import main
from jevidence.normalize import from_distribution
from jevidence.replay import load_replay

ROOT = Path(__file__).resolve().parents[1]
A = ROOT / "examples" / "compare-synthetic-a.jsonl"
B = ROOT / "examples" / "compare-synthetic-b.jsonl"


def row(issue_id="one", choice="runtime", confidence=.9, **extra):
    return dict({"issue_id": issue_id, "provenance": "recorded",
                 "evidence": {"model": "model-x", "choice": choice, "confidence": confidence,
                              "reproduction": .5, "specificity": 1}}, **extra)


class CalibrateTests(unittest.TestCase):
    def load(self, rows):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "rows.jsonl"
            path.write_text("\n".join(json.dumps(r) for r in rows))
            return load_judgments(path)

    def test_bucket_boundaries(self):
        self.assertEqual(bucket_floor(0.7, 0.1), 0.7)
        self.assertEqual(bucket_floor(0.3, 0.1), 0.3)
        self.assertEqual(bucket_floor(0.999, 0.1), 0.9)
        self.assertEqual(bucket_floor(1.0, 0.1), 0.9)
        self.assertEqual(bucket_floor(0.0, 0.1), 0.0)
        self.assertEqual(bucket_floor(0.5, 0.5), 0.5)

    def test_reliability_counts_gap_and_low_count(self):
        buckets, error = reliability([(.9, True), (.9, True), (.9, False), (.9, False)], 0.1)
        self.assertEqual(len(buckets), 1)
        self.assertEqual(buckets[0]["count"], 4)
        self.assertAlmostEqual(buckets[0]["correct_rate"], .5)
        self.assertAlmostEqual(buckets[0]["gap"], .4)
        self.assertAlmostEqual(error, .4)
        self.assertTrue(buckets[0]["low_count"])
        self.assertEqual(reliability([], 0.1), ([], None))

    def test_unlabeled_rows_do_not_claim_accuracy(self):
        result = calibrate(self.load([row()]))
        self.assertIsNone(result["route"]["accuracy"])
        self.assertIsNone(result["route"]["expected_calibration_error"])
        self.assertIsNone(result["reproduction"]["brier_score"])
        self.assertEqual(result["route"]["labeled"], 0)

    def test_unavailable_rows_are_counted_and_not_scored(self):
        rows = self.load([row(expected_choice="runtime"),
                          row("two", expected_choice="docs") | {"evidence": None, "status": "unavailable"}])
        result = calibrate(rows)
        self.assertEqual((result["cases"], result["judged"], result["unavailable"]), (2, 1, 1))
        self.assertEqual(result["route"]["labeled"], 1)
        self.assertEqual(result["route"]["accuracy"], 1)

    def test_brier_score(self):
        rows = self.load([row(expected_reproduction=True), row("two", expected_reproduction=False)])
        self.assertAlmostEqual(calibrate(rows)["reproduction"]["brier_score"], .25)

    def test_stability_counts_flips_against_the_base(self):
        rows = self.load([row(), row("two", "docs", .6, variant_of="one"), row("three", variant_of="one"),
                          row("four", variant_of="one") | {"evidence": None, "status": "unavailable"}])
        result = stability(rows)
        self.assertEqual((result["variants"], result["compared"], result["choice_flips"]), (3, 2, 1))
        self.assertAlmostEqual(result["flip_rate"], .5)
        self.assertAlmostEqual(result["max_confidence_shift"], .3)
        self.assertEqual(result["flipped_ids"], ["two"])
        self.assertIsNone(stability(self.load([row()]))["flip_rate"])

    def test_rejects_bad_comparison_fields(self):
        for rows in ([row(expected_choice="security")], [row(expected_reproduction="yes")],
                     [row(variant_of="missing")], [row(variant_of="one")],
                     [row(), row("two", variant_of="one"), row("three", variant_of="two")]):
            with self.subTest(rows=rows), self.assertRaises(ValueError) as caught:
                self.load(rows)
            self.assertIn("docs/compare.md", str(caught.exception))

    def test_width_must_divide_one(self):
        for width in (0, 0.3, 1.5, float("nan")):
            with self.subTest(width=width), self.assertRaises(ValueError):
                calibrate(self.load([row()]), width=width)

    def test_compare_reports_ids_only(self):
        left = [row(expected_choice="runtime"), row("two", "docs", expected_choice="docs"), row("left-only")]
        right = [row(choice="docs", expected_choice="runtime"), row("two", "docs", expected_choice="docs")]
        pair = compare({"left": left, "right": right})[0]
        self.assertEqual(pair["shared_judged"], 2)
        self.assertAlmostEqual(pair["choice_agreement"], .5)
        self.assertEqual(pair["disagreement_ids"], ["one"])
        self.assertEqual(pair["correct_only_in_left"], ["one"])
        self.assertEqual(pair["correct_only_in_right"], [])

    def test_bundled_examples_and_cli(self):
        result = report([A, B])
        self.assertEqual(result["provenance"], "synthetic")
        a, b = result["files"][str(A)], result["files"][str(B)]
        self.assertAlmostEqual(a["route"]["accuracy"], .9)
        self.assertAlmostEqual(b["route"]["accuracy"], .8)
        self.assertEqual(a["stability"]["choice_flips"], 0)
        self.assertEqual(b["stability"]["flipped_ids"], ["csv-export-reworded"])
        self.assertEqual(result["comparisons"][0]["correct_only_in_right"], ["docs-or-bug"])
        self.assertEqual(main(["calibrate", str(A), str(B)]), 0)
        with self.assertRaises(ValueError):
            report([A, A])
        # The examples stay valid replay input too.
        self.assertEqual(len(load_replay(A)), 10)

    def test_mixed_provenance_across_files_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "recorded.jsonl"
            path.write_text(json.dumps(row()))
            with self.assertRaises(ValueError):
                report([A, path])


class NormalizeTests(unittest.TestCase):
    def build(self, **changes):
        return from_distribution(**dict({"issue_id": "one", "model": "other-model-1",
                                         "probabilities": {"docs": .1, "runtime": .85, "other": .05},
                                         "reproduction": .7, "specificity": 2}, **changes))

    def test_top_probability_becomes_confidence_and_is_labeled(self):
        built = self.build(expected_choice="runtime", variant_of=None)
        self.assertEqual(built["evidence"]["choice"], "runtime")
        self.assertEqual(built["evidence"]["confidence"], .85)
        self.assertEqual(built["confidence_kind"], "top_probability")
        self.assertEqual(built["expected_choice"], "runtime")
        self.assertNotIn("variant_of", built)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "rows.jsonl"
            path.write_text(json.dumps(built))
            self.assertEqual(calibrate(load_judgments(path))["route"]["accuracy"], 1)

    def test_rejects_bad_distributions(self):
        for changes in ({"probabilities": {}}, {"probabilities": {"docs": .5, "runtime": .5}},
                        {"probabilities": {"docs": .2, "runtime": .2}}, {"probabilities": {"docs": 1.2}},
                        {"probabilities": {"": 1.0}}, {"probabilities": {"docs": True}},
                        {"model": ""}, {"reproduction": 2}, {"note": "private text"}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.build(**changes)
