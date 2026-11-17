# Compare decision models on stored judgments

`calibrate` answers three questions about a decision model on **your** cases,
from judgments you already recorded:

1. When it reports 0.9, is it right about nine times in ten?
2. Does a reworded or reordered input change its answer?
3. Where does it disagree with another model, and which one was right?

It performs no inference, needs no packages or keys, and reports issue IDs and
counts only. Source issue text is neither required nor echoed.

```sh
python3 -m jevidence calibrate model-a.jsonl model-b.jsonl --bucket-width 0.1
```

Give one file per model or backend. A single file works; `comparisons` is then empty.

## Input format

The files are [replay records](replay.md) with three optional fields:

```json
{"issue_id":"csv-export","provenance":"synthetic","evidence":{"model":"synthetic-fixture-a-not-model-output","choice":"runtime","confidence":0.94,"reproduction":0.92,"specificity":2.0},"expected_choice":"runtime","expected_reproduction":true}
```

- `expected_choice`: the independently labeled route, one of `docs`, `build`,
  `runtime`, or `other`. Rows without it are counted and left out of accuracy.
- `expected_reproduction`: `true` or `false`, whether the report really gives
  reproduction steps. Used for the yes/no probability.
- `variant_of`: the `issue_id` of the base record this one perturbs: the same
  issue reworded, with options reordered, or with irrelevant text added. A
  variant cannot point at another variant.

Label the inputs yourself, before looking at any model's answer. Do not copy one
model's choice into `expected_choice` and score another against it.

Use the same `issue_id` for the same input in every file, so the files can be compared.
Keep failed attempts as `status: unavailable` rows with `evidence: null`.

## Reading the report

For each file:

| Field | Meaning |
| --- | --- |
| `models` | Model labels found in the file. More than one means mixed versions. |
| `cases`, `judged`, `unavailable` | All rows, usable judgments, stored failures. |
| `route.accuracy` | Chosen route equals `expected_choice`, among labeled judged rows. |
| `route.buckets` | Per confidence band: `count`, `mean_reported`, `correct_rate`, and `gap` (reported minus correct; positive means overconfident). |
| `route.expected_calibration_error` | Count-weighted mean of the absolute gaps. Lower is better; 0 is perfect. |
| `reproduction.brier_score` | Mean squared error of the yes/no probability. Lower is better; always answering 0.5 scores 0.25. |
| `stability.flip_rate` | Variants whose choice differs from their base, among pairs where both were judged. |
| `stability.max_confidence_shift` | Largest change in confidence between a variant and its base. |

`comparisons` lists each pair of files: the share of shared judged IDs where the
choices agree, the IDs where they differ, and the IDs only one of them got right.

A band with fewer than 10 records is marked `low_count`. Treat those as
anecdotes. A few hundred labeled records per model is a reasonable minimum
before moving a threshold on the strength of a band.

A completed report exits 0 whatever it finds. Malformed input exits 2.

## Records from other decision models

`triage --live` writes records for TypeSafe's hosted Jev and for a
[Kev](kev.md) server. No other vendor adapter is bundled, because an adapter
that has never run against a real account is a guess. To compare another
model, call it with your own code and convert each answer:

```python
from jevidence.normalize import from_distribution

row = from_distribution(
    issue_id="csv-export",
    model="exact-model-and-version",
    probabilities={"docs": 0.03, "build": 0.02, "runtime": 0.91, "other": 0.04},
    reproduction=0.88,       # probability the yes/no statement is true
    specificity=1.7,         # 0 to 2, as in the Score rubric
    expected_choice="runtime",
)
```

Ask the other model the same three questions from
[`questions.py`](../jevidence/questions.py), with the same option names and
descriptions, including `other`. Write one `json.dumps(row)` per line.

Two cautions:

- **The confidence is not the same number.** Converted rows hold the top
  option's probability and say so in `confidence_kind`. Jev's `confidence` is
  its own calculation. Each file is calibrated on its own, so the bands stay
  meaningful, but do not carry a threshold from one model to another.
- **Record the exact model.** An alias such as `latest` can change between
  runs, and `models` will then hide a version change.

Tune thresholds on one set of records and confirm them on a held-out set.
Latency and cost are not in these records: measure them from where your code runs.
