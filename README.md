![Jevidence: Let Jev judge. Let your code decide.](assets/jevidence-social-preview.png)

# Jevidence

**Let Jev judge. Let your code decide.**

A Python sandbox for turning TypeSafe Jev judgments into testable issue-routing
proposals. Inspect the evidence, change a threshold, and replay labeled records
without another model call.

```text
Issue → Jev judgment → your policy → proposed queue + review hints
                            failure → keep the existing queue
```

A companion to [Jev for developers](https://peakevergreen.com/blog/jev-for-developers/)
by [Peak Evergreen](https://peakevergreen.com/). Substantially built with Codex;
independent of TypeSafe.

## Watch the 50-second demo

https://github.com/user-attachments/assets/2502886a-ce3c-46c9-b118-edf8bd8bae9e

[Video download](assets/jevidence-demo.mp4) · [Transcript](docs/demo.md)

The silent, captioned demo shows the same synthetic judgment falling back at
`0.8` and proposing runtime investigation at `0.7`, followed by policy tests.
It captures an earlier revision; its test counts and output fields are historical.

## Start in 30 seconds

Python **3.10+**. The offline commands need no packages, API key, or network after cloning.

```sh
git clone https://github.com/peakevergreen/jevidence.git
cd jevidence
python3 -m jevidence demo
python3 -m jevidence demo --route-floor 0.7
python3 -m jevidence evaluate
```

Or use `make demo`, `make evaluate`, and `make test`.

## Replay your labeled judgments

```sh
python3 -m jevidence replay examples/replay-synthetic.jsonl \
  --labels --compare-route-floor 0.7 --compare-route-floor 0.95
```

Supply one JSON object per line with an `issue_id`, `provenance`, stored
`evidence`, and an independent `expected_queue` label. Replay reports wrong
specialist routes, review volume, unavailable judgments, coverage, and individual
disagreements for each threshold. Omit `--labels` to inspect unlabeled evidence
without implying accuracy. **Replay never contacts a model.**

See [the replay guide](docs/replay.md) for the schema, denominators, and a workflow
for recording, labeling, and comparing real judgments.

## What the code decides

| Jev judgment | Application behavior |
| --- | --- |
| Choice: investigation area | Allowlist and confidence gate choose a specialist or general triage. |
| Noul: explicit reproduction steps | Runtime reports below the reproduction gate go to reproduction review. |
| Score: observation specificity, 0–2 | Below `1.0`, emit a `needs_more_detail` hint; never change the queue or priority. |

Reproduction gates **runtime only** in this teaching policy: a sequence of user
actions is useful for reproducing application behavior; build and documentation
reports can begin investigation from error output or a specific document reference.
A build-specific completeness check would need different questions and labels.

The Score hint is an illustrative review signal from an averaged rubric, not
proof that a report lacks detail. See [the policy](jevidence/policy.py) and
[runner](jevidence/runner.py).

Output includes evidence, thresholds, versions, proposed queue, hints, and
`applied: false`. An omitted current queue is `null` (unknown). When supplied,
`change_proposed` distinguishes a new suggestion from the existing queue.

## Make one live request

Hosted TypeSafe calls send the validated issue ID, title, and body to TypeSafe
and may incur charges. Configure `TYPESAFE_API_KEY` privately, then:

```sh
make setup-live
.venv/bin/python -m jevidence triage --live --input examples/issue.json \
  --current-queue existing-review
```

The TypeSafe endpoint is pinned to `https://api.typesafe.ai`; a
`TYPESAFE_BASE_URL` override cannot redirect this backend. Output names the actual
endpoint. The SDK is pinned to `0.7.1`, the default model to `jev-1.13.0`, and
SDK retries are disabled. The HTTP timeout is not an end-to-end job deadline.

To save a dated **real** raw response and its input, add
`--record-response capture.json`. This is opt-in, refuses an existing filename,
and includes issue text but not the API key. No real response is bundled yet.
See [recording instructions](docs/replay.md#record-and-label-real-judgments).

To use an existing [Kev](https://github.com/jaredpalmer/kev) server, run `make kev`
after setup. Its endpoint is explicit and receives a placeholder key, never your
TypeSafe key. See [the Kev guide](docs/kev.md); use Kev's own playground to explore
its models.

| Exit | Meaning |
| --- | --- |
| `0` | Judgment or replay completed; may include review proposals or label mismatches. |
| `1` | Provider unavailable or required answer invalid/missing; retain the current queue. |
| `2` | Invalid input or configuration. |
| `3` | Unexpected application/SDK integration defect; `status: error` and sanitized `error_type`. |

## Install, test, and build

```sh
python3 -m pip install .
jevidence demo
make test
# Include SDK transport tests without making live requests:
make setup-live
.venv/bin/python -m unittest discover -s tests -v
# Lint:
.venv/bin/python -m pip install ruff==0.16.8
make lint
# Containers (running Docker daemon required):
make docker-test docker-build docker-demo
```

CI runs Ruff, Python 3.10/3.12/3.13 tests, mocked SDK transport checks, replay,
and Docker builds. The Docker runtime is non-root and defaults to the offline
demo. `make docker-demo` disables networking. The package version comes from
`jevidence.__version__`; release wheels can be installed without a source checkout.
This project is not currently published on PyPI.

## Limitations

- Bundled judgments are **synthetic**. Fixture agreement measures code behavior,
  not model accuracy or calibration. Real evaluation needs independently labeled,
  representative inputs and a held-out set. Confidence is not a correctness probability.
- Thresholds and the specificity hint are teaching choices. Jev and Kev require
  separate evaluation; API compatibility does not imply equivalent judgments.
- This is advisory issue triage. It never assigns issues, changes records, or
  executes actions. Production use also needs access checks, durable/idempotent
  writes, deadlines, and observability. Prompt wording is not an authorization boundary.
- Live calls transmit issue text to the selected backend. Captures contain that
  text, and ordinary output includes issue IDs. Use synthetic/public inputs for
  shared examples and protect private records and SDK debug logs.
- Replay reuses existing judgments; it cannot assess new prompts/models, recover
  missing answers, or estimate inference cost or latency from synthetic records.

See [CONTRIBUTING.md](CONTRIBUTING.md), [MIT license](LICENSE),
[SDK documentation](https://docs.typesafe.ai/sdk/python), and
[confidence documentation](https://docs.typesafe.ai/confidence).
