"""Normalize judgments and produce advisory records. Never assign an issue."""
from dataclasses import asdict
import json
from importlib.resources import files

from .policy import Evidence, Thresholds, POLICY_VERSION, decide
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


def judge_live(issue, *, model, timeout):
    from typesafe_sdk import RetryPolicy, TypeSafeClient
    from .questions import issue_questions

    # A single request, with SDK retries disabled. This timeout is per HTTP
    # operation, not an end-to-end deadline for a production workflow.
    with TypeSafeClient(model=model, timeout=timeout, retry=RetryPolicy(max_retries=0)) as client:
        response = client.system_one(state={"issue": issue}, questions=issue_questions())
    evidence = Evidence(
        model=response.model,
        choice=response.choices["route"].choice,
        confidence=response.choices["route"].confidence,
        reproduction=response.nouls["reproduction"].noul,
        specificity=response.scores["specificity"].score,
    )
    return evidence


def run_case(issue, judge, *, current_queue="general-triage", mode="fixture", thresholds=None):
    issue = validate_issue(issue)
    thresholds = thresholds or Thresholds()
    record = {
        "issue_id": issue["id"], "mode": mode,
        "question_version": QUESTION_VERSION, "policy_version": POLICY_VERSION,
        "thresholds": asdict(thresholds), "current_queue": current_queue,
        "applied": False,
    }
    try:
        evidence = judge(issue)
        if not isinstance(evidence, Evidence):
            raise ValueError("judge did not return validated evidence")
    except Exception as error:
        # Keep input, secrets, and provider error bodies out of stdout/stderr.
        # An unavailable model is not a model vote for a fallback category.
        return dict(record, status="unavailable", evidence=None, proposed_queue=None,
                    reason="judgment_unavailable_keep_current_queue", error_type=type(error).__name__)
    decision = decide(evidence, thresholds)
    return dict(record, status="judged", evidence=asdict(evidence), **asdict(decision))


def evaluate_cases(cases, thresholds):
    results = []
    for case in cases:
        evidence = Evidence(**case["evidence"])
        result = run_case(case["issue"], lambda issue: evidence, thresholds=thresholds)
        result["expected_queue"] = case["expected_queue"]
        result["matches_expected"] = result["proposed_queue"] == case["expected_queue"]
        results.append(result)
    return {
        "mode": "synthetic-fixture-policy-check",
        "note": "Constructed judgments test code behavior, not Jev accuracy or calibration.",
        "cases": len(results),
        "matches_expected": sum(row["matches_expected"] for row in results),
        "specialist_proposals": sum(row["proposed_queue"] in {
            "documentation-review", "build-investigation", "runtime-investigation"
        } for row in results),
        "results": results,
    }
