"""Exercise the real SDK over a mocked transport. No network or account used."""
import importlib.util
import json
import unittest
from unittest.mock import patch

from jevidence.runner import judge_live, run_case
from jevidence.questions import MODEL

SDK_AVAILABLE = importlib.util.find_spec("typesafe_sdk") is not None


@unittest.skipUnless(SDK_AVAILABLE, "install requirements-live.txt for SDK transport tests")
class SdkContractTests(unittest.TestCase):
    def setUp(self):
        self.issue = {"id": "issue-x", "title": "Export stuck", "body": "Click Export; no download."}
        self.response = {
            "model": MODEL, "usage": {"input_tokens": 120, "output_tokens": 0},
            "answers": {
                "route": {"type": "choice", "choice": "runtime", "confidence": .9,
                          "probabilities": {"runtime": .95, "docs": .02, "build": .02, "other": .01}},
                "reproduction": {"type": "noul", "noul": .9},
                "specificity": {"type": "score", "score": 1.8, "confidence": .8,
                                "legend": {"0": "general", "1": "identifiable", "2": "expected vs actual"},
                                "probabilities": {"0": 0., "1": .2, "2": .8}},
            },
        }

    def invoke(self, handler):
        import httpx2
        from typesafe_sdk import TypeSafeClient
        def client_factory(**kwargs):
            self.assertEqual(kwargs["model"], MODEL)
            self.assertEqual(kwargs["timeout"], 3.0)
            self.assertEqual(kwargs["retry"].max_retries, 0)
            return TypeSafeClient(api_key="test-key", base_url="https://mock.invalid/",
                                  transport=httpx2.MockTransport(handler), **kwargs)
        with patch("typesafe_sdk.TypeSafeClient", side_effect=client_factory):
            return run_case(self.issue, lambda issue: judge_live(issue, model=MODEL, timeout=3.0),
                            mode="live", current_queue="existing-review")

    def test_request_and_answer_shapes(self):
        import httpx2
        requests = []
        def handler(request):
            requests.append(json.loads(request.content))
            return httpx2.Response(200, json=self.response)
        result = self.invoke(handler)
        self.assertEqual(len(requests), 1)
        self.assertEqual(requests[0]["state"], {"issue": self.issue})
        self.assertEqual(set(requests[0]["questions"]), {"route", "reproduction", "specificity"})
        self.assertEqual(requests[0]["model"], MODEL)
        self.assertEqual(result["proposed_queue"], "runtime-investigation")
        self.assertEqual(result["evidence"]["specificity"], 1.8)

    def test_server_failure_is_not_retried_or_treated_as_a_judgment(self):
        import httpx2
        requests = []
        def handler(request):
            requests.append(request)
            return httpx2.Response(503, json={"error": "private-provider-body"})
        result = self.invoke(handler)
        self.assertEqual(len(requests), 1)
        self.assertEqual(result["status"], "unavailable")
        self.assertIsNone(result["proposed_queue"])
        self.assertEqual(result["current_queue"], "existing-review")
        self.assertNotIn("private-provider-body", str(result))

    def test_missing_required_answer_preserves_current_queue(self):
        import httpx2
        del self.response["answers"]["reproduction"]
        result = self.invoke(lambda request: httpx2.Response(200, json=self.response))
        self.assertEqual(result["status"], "unavailable")
        self.assertIsNone(result["proposed_queue"])
