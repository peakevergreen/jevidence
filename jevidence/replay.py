"""Offline replay of stored evidence, with optional independent queue labels."""
from dataclasses import asdict
import json

from .policy import Evidence, QUEUES
from .runner import JudgmentUnavailable, run_case

REVIEW_QUEUES = {"general-triage", "reproduction-review"}
ALLOWED_LABELS = set(QUEUES.values()) | REVIEW_QUEUES


def load_replay(path, *, labels=False):
    rows, ids, provenances = [], set(), set()
    with path.open(encoding="utf-8") as source:
        for line_number, line in enumerate(source, 1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
                if not isinstance(row, dict):
                    raise ValueError
                issue_id = row["issue_id"]
                if not isinstance(issue_id, str) or not issue_id.strip() or len(issue_id) > 128 or issue_id in ids:
                    raise ValueError
                provenance = row["provenance"]
                if provenance not in {"synthetic", "recorded"}:
                    raise ValueError
                evidence = row["evidence"]
                if evidence is None:
                    if row.get("status") != "unavailable":
                        raise ValueError
                else:
                    Evidence(**evidence)
                    if row.get("status", "judged") != "judged":
                        raise ValueError
                if labels and row.get("expected_queue") not in ALLOWED_LABELS:
                    raise ValueError
                if row.get("current_queue") is not None and (
                    not isinstance(row["current_queue"], str) or not row["current_queue"].strip()
                ):
                    raise ValueError
            except (ValueError, KeyError, TypeError):
                # Never include input excerpts (which could contain private data).
                raise ValueError(f"invalid replay record at line {line_number}; see docs/replay.md") from None
            ids.add(issue_id)
            provenances.add(provenance)
            rows.append(row)
    if not rows:
        raise ValueError("replay input must contain at least one record")
    if len(provenances) != 1:
        raise ValueError("keep synthetic and recorded judgments in separate replay files")
    return rows


def unavailable(_issue):
    raise JudgmentUnavailable("stored unavailable judgment")


def replay(rows, thresholds, *, labels=False):
    runs = []
    for threshold in thresholds:
        results = []
        for row in rows:
            evidence = Evidence(**row["evidence"]) if row["evidence"] is not None else None
            judge = (lambda _issue, e=evidence: e) if evidence is not None else unavailable
            result = run_case(
                {"id": row["issue_id"], "title": "Stored judgment", "body": "Offline replay"},
                judge, current_queue=row.get("current_queue"), mode="replay", thresholds=threshold,
            )
            # Replay runs today's policy over yesterday's evidence. Do not claim
            # the current question version generated an older stored judgment.
            result["question_version"] = row.get("question_version")
            if labels:
                result["expected_queue"] = row["expected_queue"]
                result["matches_expected"] = (result["proposed_queue"] == row["expected_queue"]
                                               if result["status"] == "judged" else None)
            results.append(result)
        judged = [r for r in results if r["status"] == "judged"]
        specialists = [r for r in judged if r["proposed_queue"] in set(QUEUES.values())]
        reviews = sum(r["proposed_queue"] in REVIEW_QUEUES for r in judged)
        wrong = [r for r in specialists if not r["matches_expected"]] if labels else None
        runs.append({
            "thresholds": asdict(threshold), "cases": len(results), "judged": len(judged),
            "unavailable": len(results) - len(judged),
            "specialist_proposals": len(specialists), "review_count": reviews,
            "review_rate_among_judged": reviews / len(judged) if judged else None,
            "specialist_coverage": len(specialists) / len(results),
            "label_mismatches": sum(not r["matches_expected"] for r in judged) if labels else None,
            "wrong_routes": len(wrong) if labels else None,
            "wrong_route_rate_among_specialists": (len(wrong) / len(specialists)
                                                   if labels and specialists else None),
            "results": results,
        })
    return {"mode": "offline-replay", "provenance": rows[0]["provenance"], "labels": labels,
            "note": "Reuses stored judgments; no model calls. Synthetic replay tests policy, not model quality.",
            "runs": runs}
