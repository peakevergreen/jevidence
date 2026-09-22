"""Normalize judgments and produce advisory records. Never assign an issue."""
from dataclasses import asdict
from datetime import datetime, timezone
import json
from importlib.resources import files
from urllib.parse import urlsplit

from .policy import Evidence, Thresholds, POLICY_VERSION, QUEUES, decide
from .questions import QUESTION_VERSION


def load_cases():
    return json.loads(files("jevidence").joinpath("data/cases.json").read_text())


def validate_issue(value):
    if not isinstance(value, dict):
        raise ValueError("issue must be a JSON object")
    # Only these fields cross the API boundary. Extra fields are not forwarded.
    result = {}
    for key, limit in (("id", 128), ("title", 500), ("body", 20000)):
        field = value.get(key)
        if not isinstance(field, str) or not field.strip() or len(field) > limit:
            raise ValueError(f"issue.{key} must be nonempty text, at most {limit} characters")
        result[key] = field
    return result


TYPESAFE_URL = "https://api.typesafe.ai"


class JudgmentUnavailable(Exception):
    """Expected provider failure; retain no provider body or credentials."""


KEV_URL = "http://127.0.0.1:8009"


def validate_kev_url(value):
    url = urlsplit(value)
    if (url.scheme not in {"http", "https"} or not url.hostname or url.username
            or url.password or url.query or url.fragment or url.path not in {"", "/"}):
        raise ValueError("--kev-url must be an HTTP(S) server origin, without credentials, path, query, or fragment")
    return value.rstrip("/")


def judge_live(issue, *, model, timeout, backend="typesafe", kev_url=KEV_URL, record_response=None):
    from typesafe_sdk import RetryPolicy, TypeSafeClient, TypeSafeError
    from .questions import issue_questions

    # A single request, with SDK retries disabled. This timeout is per HTTP
    # operation, not an end-to-end deadline for a production workflow.
    if backend not in {"typesafe", "kev"}:
        raise ValueError("unknown backend")
    options = {"base_url": TYPESAFE_URL}
    if backend == "kev":
        # Kev's local server has no authentication. Satisfy SDK key validation
        # without sending a real TYPESAFE_API_KEY to another server.
        options = {"api_key": "local", "base_url": validate_kev_url(kev_url)}
    try:
        with TypeSafeClient(model=model, timeout=timeout, retry=RetryPolicy(max_retries=0), **options) as client:
            response = client.system_one(state={"issue": issue}, questions=issue_questions())
    except TypeSafeError as error:
        raise JudgmentUnavailable(type(error).__name__) from None
    if record_response is not None:
        # Explicit opt-in: contains supplied issue text and raw answers, never the key.
        # Exclusive creation prevents accidental replacement of a previous capture.
        with record_response.open("x", encoding="utf-8") as target:
            json.dump({
                "recorded_at": datetime.now(timezone.utc).isoformat(),
                "provenance": "recorded", "backend": backend,
                "endpoint": options["base_url"], "requested_model": model,
                "question_version": QUESTION_VERSION, "issue": issue,
                "response": response.model_dump(mode="json"),
            }, target, indent=2, allow_nan=False)
            target.write("\n")
    evidence = Evidence(
        model=response.model,
        choice=response.choices["route"].choice,
        confidence=response.choices["route"].confidence,
        reproduction=response.nouls["reproduction"].noul,
        specificity=response.scores["specificity"].score,
    )
    return evidence


def run_case(issue, judge, *, current_queue=None, mode="fixture", thresholds=None):
    issue = validate_issue(issue)
    thresholds = thresholds or Thresholds()
    record = {
        "issue_id": issue["id"], "mode": mode,
        "question_version": QUESTION_VERSION, "policy_version": POLICY_VERSION,
        "thresholds": asdict(thresholds), "current_queue": current_queue,
        "applied": False, "change_proposed": None,
    }
    try:
        evidence = judge(issue)
        if not isinstance(evidence, Evidence):
            raise ValueError("judge did not return validated evidence")
    except (JudgmentUnavailable, TimeoutError, ConnectionError, KeyError, ValueError) as error:
        # Keep input, secrets, and provider error bodies out of stdout/stderr.
        # An unavailable model is not a model vote for a fallback category.
        return dict(record, status="unavailable", evidence=None, proposed_queue=None,
                    reason="judgment_unavailable_keep_current_queue", error_type=type(error).__name__)
    except Exception as error:
        # Unexpected defects are distinguishable from outages without dumping private inputs.
        return dict(record, status="error", evidence=None, proposed_queue=None,
                    reason="unexpected_error_keep_current_queue", error_type=type(error).__name__)
    decision = decide(evidence, thresholds)
    record["change_proposed"] = (decision.proposed_queue != current_queue
                                 if current_queue is not None else None)
    return dict(record, status="judged", evidence=asdict(evidence),
                hints=["needs_more_detail"] if evidence.specificity < 1.0 else [],
                **asdict(decision))


def evaluate_cases(cases, thresholds):
    results = []
    for case in cases:
        evidence = Evidence(**case["evidence"])
        result = run_case(case["issue"], lambda issue, e=evidence: e, thresholds=thresholds)
        result["expected_queue"] = case["expected_queue"]
        result["matches_expected"] = result["proposed_queue"] == case["expected_queue"]
        results.append(result)
    return {
        "mode": "synthetic-fixture-policy-check",
        "note": "Constructed judgments test code behavior, not Jev accuracy or calibration.",
        "cases": len(results),
        "matches_expected": sum(row["matches_expected"] for row in results),
        "specialist_proposals": sum(row["proposed_queue"] in set(QUEUES.values()) for row in results),
        "results": results,
    }
