"""Pure application policy. No SDK, network, persistence, or side effects."""
from dataclasses import dataclass
import math

POLICY_VERSION = "issue-routing-v1"
QUEUES = {
    "docs": "documentation-review",
    "build": "build-investigation",
    "runtime": "runtime-investigation",
}


def bounded_number(value, name, upper=1.0):
    # Recorded fixtures are untrusted JSON, unlike SDK-validated responses.
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a number")
    if not math.isfinite(value) or not 0 <= value <= upper:
        raise ValueError(f"{name} must be finite and between 0 and {upper}")
    return float(value)


@dataclass(frozen=True)
class Evidence:
    model: str
    choice: str
    confidence: float
    reproduction: float
    specificity: float

    def __post_init__(self):
        if not isinstance(self.model, str) or not self.model.strip():
            raise ValueError("model must be a nonempty string")
        if not isinstance(self.choice, str) or not self.choice.strip():
            raise ValueError("choice must be a nonempty string")
        bounded_number(self.confidence, "confidence")
        bounded_number(self.reproduction, "reproduction")
        bounded_number(self.specificity, "specificity", upper=2.0)


@dataclass(frozen=True)
class Thresholds:
    # Teaching values, not calibrated production defaults.
    route_floor: float = 0.8
    reproduction_floor: float = 0.85

    def __post_init__(self):
        bounded_number(self.route_floor, "route_floor")
        bounded_number(self.reproduction_floor, "reproduction_floor")


@dataclass(frozen=True)
class Decision:
    proposed_queue: str
    reason: str


def decide(evidence: Evidence, thresholds: Thresholds) -> Decision:
    if evidence.choice not in QUEUES:
        return Decision("general-triage", "unknown_or_fallback_category")
    if evidence.confidence < thresholds.route_floor:
        return Decision("general-triage", "route_confidence_below_floor")
    if evidence.choice == "runtime" and evidence.reproduction < thresholds.reproduction_floor:
        return Decision("reproduction-review", "reproduction_below_floor")
    return Decision(QUEUES[evidence.choice], "route_passed_policy")
