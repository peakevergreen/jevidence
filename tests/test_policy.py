import unittest
from dataclasses import replace

from jevidence.policy import Evidence, Thresholds, decide
from jevidence.runner import evaluate_cases, load_cases, run_case, validate_issue


class PolicyTests(unittest.TestCase):
    def setUp(self):
        self.evidence = Evidence("synthetic", "runtime", .8, .85, 2.0)

    def test_threshold_boundaries_and_each_destination(self):
        for choice, confidence, reproduction, expected in (
            ("runtime", .8, .85, "runtime-investigation"),
            ("runtime", .799, .85, "general-triage"),
            ("runtime", .8, .849, "reproduction-review"),
            ("docs", .8, 0, "documentation-review"),
            ("build", .8, 0, "build-investigation"),
            ("other", 1, 1, "general-triage"),
            ("arbitrary-function", 1, 1, "general-triage"),
        ):
            with self.subTest(choice=choice, confidence=confidence, reproduction=reproduction):
                evidence = replace(self.evidence, choice=choice, confidence=confidence, reproduction=reproduction)
                self.assertEqual(decide(evidence, Thresholds()).proposed_queue, expected)

    def test_specificity_does_not_become_priority_or_a_route_gate(self):
        self.assertEqual(decide(self.evidence, Thresholds()),
                         decide(replace(self.evidence, specificity=0), Thresholds()))

    def test_invalid_fixture_numbers_and_thresholds_are_rejected(self):
        for value in (float("nan"), float("inf"), -1, 1.01, True, "0.8"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    replace(self.evidence, confidence=value)
                with self.assertRaises(ValueError):
                    Thresholds(route_floor=value)
        with self.assertRaises(ValueError):
            replace(self.evidence, specificity=2.1)

    def test_constructed_examples_match_at_teaching_thresholds(self):
        report = evaluate_cases(load_cases(), Thresholds())
        self.assertEqual(report["cases"], 8)
        self.assertEqual(report["matches_expected"], 8)
        self.assertIn("not Jev accuracy", report["note"])
        self.assertTrue(all(not row["applied"] for row in report["results"]))

    def test_threshold_change_is_visible_in_policy_replay(self):
        report = evaluate_cases(load_cases(), Thresholds(route_floor=.95))
        self.assertLess(report["matches_expected"], report["cases"])


class RunnerTests(unittest.TestCase):
    def setUp(self):
        self.issue = {"id": "x", "title": "A report", "body": "Private source text"}

    def test_failure_retains_queue_without_fabricating_an_answer(self):
        def failed(issue):
            raise TimeoutError("sensitive provider response")
        result = run_case(self.issue, failed, current_queue="existing-review", mode="live")
        self.assertEqual(result["status"], "unavailable")
        self.assertEqual(result["current_queue"], "existing-review")
        self.assertIsNone(result["proposed_queue"])
        self.assertIsNone(result["evidence"])
        self.assertFalse(result["applied"])
        self.assertNotIn("sensitive", str(result))
        self.assertNotIn("Private source", str(result))

    def test_missing_judgment_is_not_a_fallback_model_vote(self):
        result = run_case(self.issue, lambda issue: None)
        self.assertEqual(result["status"], "unavailable")
        self.assertIsNone(result["proposed_queue"])

    def test_only_allowlisted_issue_fields_are_forwarded(self):
        issue = dict(self.issue, api_key="do-not-forward", questions={"route": "override"})
        self.assertEqual(validate_issue(issue), self.issue)
        for bad in ({}, dict(self.issue, body=""), dict(self.issue, body="x" * 20001), []):
            with self.subTest(issue=bad), self.assertRaises(ValueError):
                validate_issue(bad)
