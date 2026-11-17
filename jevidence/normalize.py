"""Turn another decision model's answer into a replay record. No network."""
from .policy import Evidence, bounded_number


def from_distribution(*, issue_id, model, probabilities, reproduction, specificity,
                      provenance="recorded", **optional):
    """Build one replay row from per-option probabilities.

    `probabilities` maps each option name to the probability the model reported
    for it. The row's confidence is the top probability. That is not the same
    calculation as Jev's confidence field, so the row says which one it holds.
    """
    if not isinstance(probabilities, dict) or not probabilities:
        raise ValueError("probabilities must be a nonempty object")
    cleaned = {}
    for option, value in probabilities.items():
        if not isinstance(option, str) or not option.strip():
            raise ValueError("option names must be nonempty text")
        cleaned[option] = bounded_number(value, "probability")
    total = sum(cleaned.values())
    if abs(total - 1) > 0.02:
        raise ValueError("probabilities must sum to 1 within 0.02")
    ranked = sorted(cleaned.items(), key=lambda item: (-item[1], item[0]))
    if len(ranked) > 1 and ranked[0][1] == ranked[1][1]:
        raise ValueError("top probability is tied; record this attempt as unavailable")
    choice, confidence = ranked[0]
    evidence = Evidence(model=model, choice=choice, confidence=confidence,
                        reproduction=reproduction, specificity=specificity)
    unknown = set(optional) - {"expected_choice", "expected_reproduction", "expected_queue",
                                "variant_of", "question_version", "current_queue"}
    if unknown:
        raise ValueError("unsupported optional field")
    row = {
        "issue_id": issue_id, "provenance": provenance, "confidence_kind": "top_probability",
        "evidence": {"model": evidence.model, "choice": evidence.choice,
                     "confidence": evidence.confidence, "reproduction": evidence.reproduction,
                     "specificity": evidence.specificity},
    }
    row.update({key: value for key, value in optional.items() if value is not None})
    return row
