"""Exercise the real SDK over a mocked transport. No network or account used."""
import importlib.util
import json
import unittest
from unittest.mock import patch

from jevidence.runner import TYPESAFE_URL, judge_live, run_case
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

    def invoke(self, handler, backend="typesafe", record_response=None):
        import httpx2
        from typesafe_sdk import TypeSafeClient
        def client_factory(**kwargs):
            self.assertEqual(kwargs["model"], "kev-latest" if backend == "kev" else MODEL)
            self.assertEqual(kwargs["timeout"], 3.0)
            self.assertEqual(kwargs["retry"].max_retries, 0)
            if backend == "kev":
                self.assertEqual(kwargs["api_key"], "local")
                self.assertEqual(kwargs["base_url"], "http://127.0.0.1:8009")
            else:
                self.assertEqual(kwargs["base_url"], TYPESAFE_URL)
                kwargs.update(api_key="test-key")
            return TypeSafeClient(transport=httpx2.MockTransport(handler), **kwargs)
        with patch("typesafe_sdk.TypeSafeClient", side_effect=client_factory):
            return run_case(self.issue, lambda issue: judge_live(issue, model="kev-latest" if backend == "kev" else MODEL,
                            timeout=3.0, backend=backend, record_response=record_response),
                            mode="live", current_queue="existing-review")

    def test_kev_wire_format_and_paid_key_isolation(self):
        import httpx2
        requests = []
        self.response.update(model="kev-latest", latency_ms=495)
        def handler(request):
            requests.append(request)
            return httpx2.Response(200, json=self.response)
        with patch.dict("os.environ", {"TYPESAFE_API_KEY": "paid-key-not-for-kev", "TYPESAFE_BASE_URL": "https://not-kev.invalid"}):
            result = self.invoke(handler, backend="kev")
        self.assertEqual(len(requests), 1)
        self.assertEqual(str(requests[0].url), "http://127.0.0.1:8009/v1/systemone")
        self.assertNotIn("paid-key-not-for-kev", str(requests[0].headers))
        self.assertEqual(json.loads(requests[0].content)["model"], "kev-latest")
        self.assertEqual(result["status"], "judged")
        self.assertEqual(result["evidence"]["model"], "kev-latest")
        self.assertEqual(result["proposed_queue"], "runtime-investigation")

    def test_kev_connection_failure_retains_queue(self):
        import httpx2
        def handler(request):
            raise httpx2.ConnectError("local server is unavailable", request=request)
        result = self.invoke(handler, backend="kev")
        self.assertEqual(result["status"], "unavailable")
        self.assertEqual(result["current_queue"], "existing-review")
        self.assertIsNone(result["proposed_queue"])

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

    def test_typesafe_origin_is_pinned_despite_environment_override(self):
        import httpx2
        requests = []
        def handler(request):
            requests.append(request)
            return httpx2.Response(200, json=self.response)
        with patch.dict("os.environ", {"TYPESAFE_BASE_URL": "http://untrusted.invalid:8009"}):
            result = self.invoke(handler)
        self.assertEqual(result["status"], "judged")
        self.assertEqual(str(requests[0].url), "https://api.typesafe.ai/v1/systemone")

    def test_recording_saves_raw_response_without_credentials_and_never_overwrites(self):
        import httpx2
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "capture.json"
            result = self.invoke(lambda request: httpx2.Response(200, json=self.response), record_response=path)
            self.assertEqual(result["status"], "judged")
            captured = json.loads(path.read_text())
            self.assertEqual(captured["response"]["answers"]["route"]["choice"], "runtime")
            self.assertEqual(captured["endpoint"], TYPESAFE_URL)
            self.assertIn("recorded_at", captured)
            self.assertNotIn("test-key", path.read_text())
            original = path.read_bytes()
            result = self.invoke(lambda request: httpx2.Response(200, json=self.response), record_response=path)
            self.assertEqual(result["status"], "error")
            self.assertEqual(path.read_bytes(), original)
