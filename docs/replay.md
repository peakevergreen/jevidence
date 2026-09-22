# Replay stored judgments

Replay separates **model evaluation** from **policy evaluation**: ask the model
once, label the input independently, and compare code-owned thresholds over the
same evidence. It performs no inference and never applies an assignment.

## Input format

One JSON object per line (JSONL). Each row has a unique, nonempty `issue_id`,
`provenance` (`synthetic` or `recorded`), and normalized `evidence`:

```json
{"issue_id":"example-001","provenance":"synthetic","evidence":{"model":"synthetic-fixture-not-model-output","choice":"runtime","confidence":0.72,"reproduction":0.95,"specificity":2.0},"expected_queue":"general-triage"}
```

The example above is constructed, not a recorded model answer. Evidence uses
Choice confidence, Noul reproduction probability, and the 0–2 specificity Score.
Malformed/nonfinite values and duplicate IDs are rejected. Keep synthetic and
recorded evidence in separate files; provenance is a declaration, not proof of
origin. Keep raw dated captures and model/question versions alongside real data.
Replay uses the current policy version, recorded in every result.

Optional fields:

- `question_version`: source question version; absent/null means unknown. Replay
  preserves it instead of claiming the current questions produced the evidence.
- `current_queue`: known existing queue; absent/null means unknown.
- `expected_queue`: required on every row with `--labels`; independently labeled
  as `documentation-review`, `build-investigation`, `runtime-investigation`,
  `general-triage`, or `reproduction-review`.
- `status`: `judged` for valid evidence. A failed attempt has
  `status: unavailable` and `evidence: null`. Retain these rows to avoid hiding failures.

A normal `triage` output already supplies the required normalized fields. Add
`expected_queue` yourself before using `--labels`. Do not copy a model proposal
into that field and call it independent ground truth. Unlabeled runs ignore labels.

## Compare thresholds

```sh
python3 -m jevidence replay examples/replay-synthetic.jsonl --labels \
  --compare-route-floor 0.7 --compare-route-floor 0.95
```

The first run uses `--route-floor` and `--reproduction-floor` (default `0.8` and
`0.85`). Each repeatable comparison changes only the route threshold. For a
reproduction-gate experiment, rerun with a different `--reproduction-floor`.

Every run contains individual `results` and these metrics:

| Field | Meaning / denominator |
| --- | --- |
| `cases` | All input rows, including failures. |
| `judged`, `unavailable` | Usable judgments and stored failures. |
| `specialist_proposals` | Documentation, build, or runtime investigation proposals. |
| `review_count` | General-triage and reproduction-review proposals. |
| `review_rate_among_judged` | Review proposals / usable judgments; null if none are usable. |
| `specialist_coverage` | Specialist proposals / all input rows, including failures. |
| `label_mismatches` | Any judged proposal disagreeing with its label, including review proposals. |
| `wrong_routes` | Specialist proposals disagreeing with their label. |
| `wrong_route_rate_among_specialists` | Wrong specialist routes / specialist proposals; null without labels or proposals. |

Without `--labels`, label metrics are null. Unavailable rows get no prediction or
label agreement and are not scored as correct fallbacks. A completed replay exits
0 even when there are disagreements; inspect its report for your own CI criteria.
Malformed input exits 2. Source issue text is neither required nor echoed.

## Record and label real judgments

Install the optional SDK with `make setup-live` and configure `TYPESAFE_API_KEY`
in your private environment. This next command makes **one billable request**
using the synthetic issue, with retries disabled:

```sh
.venv/bin/python -m jevidence triage --live --input examples/issue.json \
  --record-response capture.json > judgment.jsonl
```

`capture.json` contains the UTC capture time, endpoint, backend, requested model,
question version, supplied issue, and the full SDK response including usage and
typed answer distributions. It refuses to overwrite an existing file. The
returned `model` in the response is the provider's model label. A custom Kev
server may return an alias; separately record its checkpoint/server settings.

`judgment.jsonl` is pretty-printed CLI JSON for one attempt. To make a one-line
record after adding your independent label, use Python or your dataset tooling:

```sh
python3 -c 'import json; print(json.dumps(json.load(open("judgment.jsonl"))))' > issues.jsonl
python3 -m jevidence replay issues.jsonl --labels --compare-route-floor 0.7
```

Add `expected_queue` before that replay. For multiple attempts, serialize each
normalized record on one line; do not concatenate pretty-printed JSON documents.
Keep failed attempts too. Do not publish captures containing private issue text.
A saved raw response is useful provenance, not an accuracy claim.

Tune on one dataset and evaluate on a separate held-out set. Review disagreements
by category, preserve failures, and measure real latency/cost separately. This
command cannot establish production readiness or calibrate a new model for you.
