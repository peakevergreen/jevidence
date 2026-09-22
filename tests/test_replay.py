import json
from pathlib import Path
import tempfile
import unittest

from jevidence.policy import Thresholds
from jevidence.replay import load_replay, replay


class ReplayTests(unittest.TestCase):
    def row(self, **changes):
        return dict({"issue_id": "one", "provenance": "recorded",
                     "evidence": {"model": "jev-1.13.0", "choice": "runtime", "confidence": .72,
                                  "reproduction": .95, "specificity": 2},
                     "expected_queue": "general-triage"}, **changes)

    def load(self, rows, **options):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "issues.jsonl"
            path.write_text("\n".join(json.dumps(r) for r in rows))
            return load_replay(path, **options)

    def test_threshold_comparison_counts_wrong_specialists_and_review(self):
        rows = self.load([self.row()], labels=True)
        report = replay(rows, [Thresholds(), Thresholds(.7)], labels=True)
        high, low = report["runs"]
        self.assertEqual(high["review_count"], 1)
        self.assertEqual(high["wrong_routes"], 0)
        self.assertIsNone(high["wrong_route_rate_among_specialists"])
        self.assertEqual(low["review_count"], 0)
        self.assertEqual(low["wrong_routes"], 1)
        self.assertEqual(low["wrong_route_rate_among_specialists"], 1)
        self.assertFalse(low["results"][0]["applied"])
        self.assertIsNone(low["results"][0]["question_version"])
        rows[0]["question_version"] = "older-questions"
        preserved = replay(rows, [Thresholds()])["runs"][0]["results"][0]
        self.assertEqual(preserved["question_version"], "older-questions")

    def test_unavailable_is_not_a_prediction_or_correct_fallback(self):
        rows = self.load([self.row(evidence=None, status="unavailable", current_queue="existing")], labels=True)
        report = replay(rows, [Thresholds()], labels=True)["runs"][0]
        self.assertEqual(report["unavailable"], 1)
        self.assertEqual(report["label_mismatches"], 0)
        self.assertEqual(report["specialist_coverage"], 0)
        self.assertIsNone(report["review_rate_among_judged"])
        self.assertIsNone(report["results"][0]["matches_expected"])
        self.assertEqual(report["results"][0]["current_queue"], "existing")

    def test_unlabeled_run_does_not_claim_accuracy(self):
        row = self.row()
        del row["expected_queue"]
        report = replay(self.load([row]), [Thresholds()])["runs"][0]
        self.assertIsNone(report["wrong_routes"])
        self.assertIsNone(report["label_mismatches"])
        with self.assertRaises(ValueError):
            self.load([row], labels=True)

    def test_rejects_duplicates_bad_labels_and_mixed_provenance(self):
        for rows in ([self.row(), self.row()], [self.row(expected_queue="invented")],
                     [self.row(), self.row(issue_id="two", provenance="synthetic")],
                     [self.row(evidence={})], [self.row(evidence=None)], [], [None]):
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                self.load(rows, labels=True)

    def test_malformed_json_does_not_echo_private_input(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "input.jsonl"
            path.write_text('{"private":"customer-secret",broken}')
            with self.assertRaises(ValueError) as caught:
                load_replay(path)
            self.assertNotIn("customer-secret", str(caught.exception))
            self.assertIn("line 1", str(caught.exception))

    def test_reproduction_and_unknown_routes_stay_in_review(self):
        a, b = self.row(), self.row(issue_id="two")
        a["evidence"].update(confidence=.99, reproduction=.1)
        b["evidence"].update(choice="arbitrary-queue", confidence=.99)
        report = replay(self.load([a, b]), [Thresholds()])["runs"][0]
        self.assertEqual(report["review_count"], 2)
        self.assertEqual(report["specialist_proposals"], 0)
