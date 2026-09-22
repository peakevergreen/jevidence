"""JSON on stdout; explicit live calls; no credentials needed for the demo."""
import argparse
import json
import math
import os
from pathlib import Path
import sys

from .policy import Evidence, Thresholds
from .questions import MODEL
from .runner import evaluate_cases, judge_live, load_cases, run_case, validate_issue


def positive_timeout(value):
    number = float(value)
    if not math.isfinite(number) or number <= 0:
        raise argparse.ArgumentTypeError("timeout must be finite and positive")
    return number


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name, help_text in (
        ("demo", "Replay one synthetic judgment without an API call"),
        ("evaluate", "Check the policy against synthetic expected queues"),
        ("triage", "Judge a JSON issue using an explicit live API call"),
    ):
        command = commands.add_parser(name, help=help_text)
        command.add_argument("--route-floor", type=float, default=0.8)
        command.add_argument("--reproduction-floor", type=float, default=0.85)
        if name == "demo":
            command.add_argument("--case", default="runtime-low-confidence")
        if name == "triage":
            command.add_argument("--input", type=Path, required=True)
            command.add_argument("--live", action="store_true", help="Send this issue to TypeSafe (billable)")
            command.add_argument("--model", default=MODEL)
            command.add_argument("--timeout", type=positive_timeout, default=15.0)
            command.add_argument("--current-queue", default="general-triage")
    args = parser.parse_args(argv)
    try:
        thresholds = Thresholds(args.route_floor, args.reproduction_floor)
        if args.command == "evaluate":
            result = evaluate_cases(load_cases(), thresholds)
        elif args.command == "demo":
            case = next((case for case in load_cases() if case["id"] == args.case), None)
            if case is None:
                raise ValueError("unknown case; see jevidence/data/cases.json")
            evidence = Evidence(**case["evidence"])
            result = run_case(case["issue"], lambda issue: evidence, thresholds=thresholds)
        else:
            if not args.live:
                raise ValueError("triage requires --live; use demo for an offline run")
            if not os.environ.get("TYPESAFE_API_KEY", "").strip():
                raise ValueError("set TYPESAFE_API_KEY in the environment before using --live")
            # Parse and validate before making a request. Never print the body.
            issue = validate_issue(json.loads(args.input.read_text()))
            result = run_case(issue, lambda item: judge_live(item, model=args.model, timeout=args.timeout),
                              current_queue=args.current_queue, mode="live", thresholds=thresholds)
    except (ValueError, OSError) as error:
        # JSONDecodeError can contain document excerpts in other decoders.
        message = "invalid input JSON" if isinstance(error, json.JSONDecodeError) else str(error)
        parser.error(message)
    print(json.dumps(result, indent=2, allow_nan=False))
    return 1 if result.get("status") == "unavailable" else 0
