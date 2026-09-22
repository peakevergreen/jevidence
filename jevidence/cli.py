"""JSON on stdout; explicit live calls; no credentials needed for the demo."""
import argparse
import json
import math
import os
from pathlib import Path

from .policy import Evidence, Thresholds
from .questions import MODEL
from .runner import KEV_URL, evaluate_cases, judge_live, load_cases, run_case, validate_issue, validate_kev_url


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
            command.add_argument("--live", action="store_true", help="Send this issue to the selected server (TypeSafe calls are billable)")
            command.add_argument("--backend", choices=("typesafe", "kev"), default="typesafe")
            command.add_argument("--kev-url", help=f"Kev server origin; defaults to {KEV_URL}")
            command.add_argument("--model", help=f"Defaults to {MODEL} for TypeSafe or kev-latest for Kev")
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
            if args.backend == "typesafe" and args.kev_url:
                raise ValueError("--kev-url requires --backend kev")
            if args.backend == "typesafe" and not os.environ.get("TYPESAFE_API_KEY", "").strip():
                raise ValueError("set TYPESAFE_API_KEY in the environment before using --live")
            kev_url = validate_kev_url(args.kev_url or KEV_URL) if args.backend == "kev" else KEV_URL
            model = args.model or ("kev-latest" if args.backend == "kev" else MODEL)
            # Parse and validate before making a request. Never print the body.
            issue = validate_issue(json.loads(args.input.read_text()))
            result = run_case(issue, lambda item: judge_live(item, model=model, timeout=args.timeout,
                              backend=args.backend, kev_url=kev_url),
                              current_queue=args.current_queue, mode="live", thresholds=thresholds)
            result.update(backend=args.backend, requested_model=model)
    except (ValueError, OSError) as error:
        # JSONDecodeError can contain document excerpts in other decoders.
        message = "invalid input JSON" if isinstance(error, json.JSONDecodeError) else str(error)
        parser.error(message)
    print(json.dumps(result, indent=2, allow_nan=False))
    return 1 if result.get("status") == "unavailable" else 0
