from contextlib import redirect_stdout, redirect_stderr
from io import StringIO
import json
import unittest
from unittest.mock import patch

from jevidence.cli import main


class CliTests(unittest.TestCase):
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
