# Connect Jevidence to Kev

[Kev by Jared Palmer](https://github.com/jaredpalmer/kev) supplies independently
developed decision models and a TypeSafe-compatible server. Its own
[playground](https://github.com/jaredpalmer/kev#playground) and
[hosted Hugging Face demo](https://huggingface.co/spaces/jaredpalmer/kev) are the
places to explore questions and option-order sensitivity interactively.

Jevidence connects that server to its existing Python routing policy. It does
not bundle Kev, its weights, training code, or a second playground.

## Run the connection

1. Follow [Kev's current quick start](https://github.com/jaredpalmer/kev#quick-start)
   in a separate checkout. That project manages model downloads, hardware
   requirements, and serving. Wait until its server is ready.
2. From Jevidence, install the client dependencies with `make setup-live`.
3. Run `make kev`. It sends the synthetic `examples/issue.json` to
   `http://127.0.0.1:8009` using `kev-latest` and a 120-second HTTP timeout.

The equivalent command is:

```sh
.venv/bin/python -m jevidence triage \
  --live --backend kev \
  --kev-url http://127.0.0.1:8009 \
  --model kev-latest --timeout 120 \
  --input examples/issue.json \
  --current-queue existing-review
```

Use the server origin, without `/v1` or `/v1/systemone`; the SDK supplies the
endpoint path. `--live` means an actual server request, including for local Kev.
The offline demo remains entirely offline. No TypeSafe account or key is needed
for this backend. The adapter explicitly supplies `api_key="local"` rather than
inheriting a paid TypeSafe key from the environment.

If the server is unavailable or its answer cannot be used, Jevidence keeps the
current queue and exits with status 1. Unexpected implementation errors instead use
`status: error` and exit 3. It never switches providers automatically.

## Compare evidence, then review the policy

Use the same issue, question definitions, and policy versions for a first
comparison. Save the two JSON outputs with distinct filenames. A TypeSafe run
still requires your key and is billable; a Kev run uses your configured server.
The result includes `backend`, `requested_model`, and the returned model label.

Kev's [server implementation](https://github.com/jaredpalmer/kev/blob/main/kev/serve.py)
echoes the request's model label. `kev-latest` is therefore not proof of which
immutable checkpoint produced a judgment. Record the checkpoint revision and
startup settings yourself; `/v1/models` also exposes loaded-server metadata.

The API shape is compatible, but the judgments are not interchangeable. Kev's
[API notes](https://github.com/jaredpalmer/kev#api) describe its confidence
calculation and the approximation used for Score confidence. Tune each backend
on representative labeled data, then verify on a held-out set. Fixture replay
only tests application code; it cannot choose a model or calibrate thresholds.

## Local serving and Docker

Run this connection from the host Python environment alongside Kev. Jevidence's
Docker image includes the SDK, not Kev's serving stack or model weights.
`127.0.0.1` inside a container refers to that container, while Kev's documented
server binds to the host's loopback interface. The project deliberately provides
no command that exposes that unauthenticated server on your network.

The integration tests use the real SDK with mocked Kev-shaped HTTP responses,
including its extra `latency_ms` field. They test the request path, response
parsing, failure handling, and key isolation. They do not download weights or
measure inference quality, throughput, or hardware compatibility.
