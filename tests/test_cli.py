from contextlib import redirect_stdout, redirect_stderr
from io import StringIO
import json
import unittest
from unittest.mock import patch

from jevidence.cli import main
from jevidence.policy import Evidence


class CliTests(unittest.TestCase):
    def test_kev_uses_explicit_backend_without_a_typesafe_key(self):
        output = StringIO()
        with patch.dict("os.environ", {}, clear=True), \
                patch("jevidence.cli.judge_live", return_value=Evidence("kev-latest", "runtime", .72, .9, 1.8)) as live, \
                redirect_stdout(output):
            self.assertEqual(main(["triage", "--live", "--backend", "kev", "--input", "examples/issue.json"]), 0)
        self.assertEqual(live.call_args.kwargs["backend"], "kev")
        self.assertEqual(live.call_args.kwargs["model"], "kev-latest")
        self.assertEqual(live.call_args.kwargs["kev_url"], "http://127.0.0.1:8009")
        result = json.loads(output.getvalue())
        self.assertEqual(result["backend"], "kev")
        self.assertEqual(result["requested_model"], "kev-latest")
        self.assertEqual(result["proposed_queue"], "general-triage")

    def test_kev_requires_opt_in_and_valid_server_configuration(self):
        for extra in ([], ["--live", "--kev-url", "file:///tmp/kev"],
                      ["--live", "--kev-url", "http://localhost:8009/v1/systemone"],
                      ["--live", "--kev-url", "http://secret@localhost:8009"]):
            with self.subTest(extra=extra), patch("jevidence.cli.judge_live") as live, \
                    redirect_stderr(StringIO()), self.assertRaises(SystemExit) as caught:
                main(["triage", "--backend", "kev", "--input", "examples/issue.json", *extra])
            self.assertEqual(caught.exception.code, 2)
            live.assert_not_called()

    def test_typesafe_does_not_accept_a_kev_url(self):
        with redirect_stderr(StringIO()), self.assertRaises(SystemExit) as caught:
            main(["triage", "--live", "--kev-url", "http://localhost:8009", "--input", "examples/issue.json"])
        self.assertEqual(caught.exception.code, 2)

    def test_demo_never_calls_live_adapter(self):
        output = StringIO()
        with patch("jevidence.cli.judge_live") as live, redirect_stdout(output):
            self.assertEqual(main(["demo"]), 0)
        live.assert_not_called()
        result = json.loads(output.getvalue())
        self.assertEqual(result["evidence"]["confidence"], .72)
        self.assertEqual(result["proposed_queue"], "general-triage")
        self.assertEqual(result["mode"], "fixture")

    def test_live_requires_opt_in_and_key(self):
        for args in (["triage", "--input", "examples/issue.json"],
                     ["triage", "--live", "--input", "examples/issue.json"]):
            with self.subTest(args=args), patch.dict("os.environ", {}, clear=True), \
                    patch("jevidence.cli.judge_live") as live, redirect_stderr(StringIO()):
                with self.assertRaises(SystemExit) as caught:
                    main(args)
                self.assertEqual(caught.exception.code, 2)
                live.assert_not_called()

    def test_live_failure_has_nonzero_exit_and_keeps_queue(self):
        output, errors = StringIO(), StringIO()
        with patch.dict("os.environ", {"TYPESAFE_API_KEY": "test-key"}), \
                patch("jevidence.cli.judge_live", side_effect=TimeoutError("secret-body")), \
                redirect_stdout(output), redirect_stderr(errors):
            code = main(["triage", "--live", "--input", "examples/issue.json",
                         "--current-queue", "existing-review"])
        self.assertEqual(code, 1)
        self.assertEqual(json.loads(output.getvalue())["current_queue"], "existing-review")
        self.assertNotIn("secret-body", output.getvalue() + errors.getvalue())

    def test_invalid_threshold_is_an_argument_error(self):
        with redirect_stderr(StringIO()), self.assertRaises(SystemExit) as caught:
            main(["demo", "--route-floor", "nan"])
        self.assertEqual(caught.exception.code, 2)

    def test_unexpected_defects_have_distinct_exit_and_no_private_trace(self):
        output = StringIO()
        with patch.dict("os.environ", {"TYPESAFE_API_KEY": "test-key"}), \
                patch("jevidence.cli.judge_live", side_effect=AttributeError("secret-input")), \
                redirect_stdout(output):
            code = main(["triage", "--live", "--input", "examples/issue.json"])
        self.assertEqual(code, 3)
        result = json.loads(output.getvalue())
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["error_type"], "AttributeError")
        self.assertIsNone(result["current_queue"])
        self.assertNotIn("secret-input", output.getvalue())

    def test_replay_is_offline_and_bad_input_has_stable_program_name(self):
        output = StringIO()
        with patch("jevidence.cli.judge_live") as live, redirect_stdout(output):
            self.assertEqual(main(["replay", "examples/replay-synthetic.jsonl", "--labels", "--compare-route-floor", "0.7"]), 0)
        live.assert_not_called()
        self.assertEqual(len(json.loads(output.getvalue())["runs"]), 2)
        errors = StringIO()
        with redirect_stderr(errors), self.assertRaises(SystemExit):
            main(["replay", "examples/replay-synthetic.jsonl", "--route-floor", "nan"])
        self.assertIn("jevidence: error:", errors.getvalue())
