"""Offline calibration, stability, and model comparison over stored judgments.

Reads the same JSONL as replay, one file per model or backend. Performs no
inference. Reports IDs and counts only, never issue text.
"""
from collections import defaultdict

from .policy import Evidence, bounded_number
from .replay import load_replay

CHOICES = {"docs", "build", "runtime", "other"}
LOW_COUNT = 10


def load_judgments(path):
    """Load replay rows and validate the optional comparison fields."""
    rows = load_replay(path)
    ids = {row["issue_id"] for row in rows}
    for line_number, row in enumerate(rows, 1):
        try:
            if row.get("expected_choice") is not None and row["expected_choice"] not in CHOICES:
                raise ValueError
            if row.get("expected_reproduction") is not None and not isinstance(row["expected_reproduction"], bool):
                raise ValueError
            base = row.get("variant_of")
            if base is not None and (base not in ids or base == row["issue_id"]):
                raise ValueError
            if base is not None and next(r for r in rows if r["issue_id"] == base).get("variant_of") is not None:
                raise ValueError
        except ValueError:
            # Count judged records, not file lines: blank lines are skipped on load.
            raise ValueError(f"invalid comparison fields in record {line_number}; see docs/compare.md") from None
    return rows


def bucket_floor(probability, width):
    # 1.0 belongs to the top bucket; integer math avoids 0.7 / 0.1 == 6.999...
    buckets = round(1 / width)
    return min(int(round(probability * 1e9) // round(width * 1e9)), buckets - 1) / buckets


def reliability(pairs, width):
    """pairs: (reported probability, whether it was correct). Returns buckets and ECE."""
    grouped = defaultdict(list)
    for probability, correct in pairs:
        grouped[bucket_floor(probability, width)].append((probability, correct))
    buckets, error = [], 0.0
    for floor in sorted(grouped):
        members = grouped[floor]
        mean = sum(p for p, _ in members) / len(members)
        rate = sum(c for _, c in members) / len(members)
        error += len(members) / len(pairs) * abs(mean - rate)
        buckets.append({
            "from": floor, "to": round(floor + width, 9), "count": len(members),
            "mean_reported": mean, "correct_rate": rate, "gap": mean - rate,
            "low_count": len(members) < LOW_COUNT,
        })
    return buckets, (error if pairs else None)


def calibrate(rows, *, width=0.1):
    bounded_number(width, "width")
    if width <= 0 or abs(round(1 / width) * width - 1) > 1e-9:
        raise ValueError("width must divide 1 evenly, such as 0.1 or 0.2")
    judged = [row for row in rows if row["evidence"] is not None]
    evidence = {row["issue_id"]: Evidence(**row["evidence"]) for row in judged}
    routes = [(evidence[row["issue_id"]].confidence,
               evidence[row["issue_id"]].choice == row["expected_choice"])
              for row in judged if row.get("expected_choice") is not None]
    nouls = [(evidence[row["issue_id"]].reproduction, row["expected_reproduction"])
             for row in judged if row.get("expected_reproduction") is not None]
    route_buckets, route_ece = reliability(routes, width)
    # For a yes/no probability, compare the reported value with how often "yes" was true.
    noul_buckets, noul_ece = reliability(nouls, width)
    return {
        "models": sorted({item.model for item in evidence.values()}),
        "cases": len(rows), "judged": len(judged), "unavailable": len(rows) - len(judged),
        "route": {
            "labeled": len(routes),
            "accuracy": sum(c for _, c in routes) / len(routes) if routes else None,
            "expected_calibration_error": route_ece, "buckets": route_buckets,
        },
        "reproduction": {
            "labeled": len(nouls),
            "brier_score": (sum((p - float(y)) ** 2 for p, y in nouls) / len(nouls)) if nouls else None,
            "expected_calibration_error": noul_ece, "buckets": noul_buckets,
        },
        "stability": stability(rows),
    }


def stability(rows):
    """Compare each variant (a reworded or reordered input) with its base record."""
    by_id = {row["issue_id"]: row for row in rows}
    variants = [row for row in rows if row.get("variant_of") is not None]
    compared, flips, shifts, flipped_ids = 0, 0, [], []
    for row in variants:
        base = by_id[row["variant_of"]]
        if row["evidence"] is None or base["evidence"] is None:
            continue
        compared += 1
        shifts.append(abs(row["evidence"]["confidence"] - base["evidence"]["confidence"]))
        if row["evidence"]["choice"] != base["evidence"]["choice"]:
            flips += 1
            flipped_ids.append(row["issue_id"])
    return {
        "variants": len(variants), "compared": compared, "choice_flips": flips,
        "flip_rate": flips / compared if compared else None,
        "max_confidence_shift": max(shifts) if shifts else None,
        "flipped_ids": flipped_ids,
    }


def compare(named_rows):
    """Pairwise agreement between files on the issue IDs they share."""
    pairs = []
    names = list(named_rows)
    for index, left in enumerate(names):
        for right in names[index + 1:]:
            a = {row["issue_id"]: row for row in named_rows[left]}
            b = {row["issue_id"]: row for row in named_rows[right]}
            shared = [i for i in a if i in b and a[i]["evidence"] is not None and b[i]["evidence"] is not None]
            agree = [i for i in shared if a[i]["evidence"]["choice"] == b[i]["evidence"]["choice"]]
            only_left, only_right = [], []
            for issue_id in shared:
                label = a[issue_id].get("expected_choice")
                if label is None or label != b[issue_id].get("expected_choice"):
                    continue
                left_ok = a[issue_id]["evidence"]["choice"] == label
                right_ok = b[issue_id]["evidence"]["choice"] == label
                if left_ok and not right_ok:
                    only_left.append(issue_id)
                if right_ok and not left_ok:
                    only_right.append(issue_id)
            pairs.append({
                "left": left, "right": right, "shared_judged": len(shared),
                "choice_agreement": len(agree) / len(shared) if shared else None,
                "disagreement_ids": [i for i in shared if i not in set(agree)],
                "correct_only_in_left": only_left, "correct_only_in_right": only_right,
            })
    return pairs


def report(paths, *, width=0.1):
    names = [str(path) for path in paths]
    if len(set(names)) != len(names):
        raise ValueError("each file may be given once")
    named_rows = {name: load_judgments(path) for name, path in zip(names, paths)}
    provenances = {rows[0]["provenance"] for rows in named_rows.values()}
    if len(provenances) != 1:
        raise ValueError("compare synthetic files with synthetic files, and recorded with recorded")
    return {
        "mode": "offline-calibration", "provenance": provenances.pop(), "bucket_width": width,
        "note": ("Reuses stored judgments; no model calls. Synthetic records test this code, "
                 "not any model. Buckets under 10 records are marked low_count."),
        "files": {name: calibrate(rows, width=width) for name, rows in named_rows.items()},
        "comparisons": compare(named_rows),
    }
