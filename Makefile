PYTHON ?= python3
VENV ?= .venv
PY := $(VENV)/bin/python
IMAGE ?= peakevergreen/jevidence:local
KEV_URL ?= http://127.0.0.1:8009
.DEFAULT_GOAL := help

.PHONY: help setup setup-live demo evaluate test live kev docker-build docker-test docker-demo docker-live
help:
	@printf '%s\n' 'make kev           Run against your existing Kev server (no TypeSafe key)'
	@printf '%s\n' 'make demo          Offline example (Python 3.10+; no install or key)' 'make evaluate      Synthetic policy checks, not model benchmarks' 'make replay        Compare thresholds on stored synthetic judgments' 'make lint          Run Ruff from the virtual environment' 'make test          Offline policy/CLI tests' 'make setup-live    Create venv and install pinned live dependencies' 'make live          One billable request using TYPESAFE_API_KEY' 'make docker-build  Build the runtime image' 'make docker-test   Build the test stage and run its tests' 'make docker-demo   Run the image offline' 'make docker-live   One billable request; pass key from environment'

setup:
	$(PYTHON) -m venv $(VENV)
	$(PY) -m pip install -e .

setup-live: setup
	$(PY) -m pip install -r requirements-live.txt

demo:
	$(PYTHON) -m jevidence demo

evaluate:
	$(PYTHON) -m jevidence evaluate

test:
	$(PYTHON) -m unittest discover -s tests -v

live:
	$(PY) -m jevidence triage --live --input examples/issue.json

kev:
	$(PY) -m jevidence triage --live --backend kev --kev-url "$(KEV_URL)" --timeout 120 --input examples/issue.json

docker-build:
	docker build --target runtime -t $(IMAGE) .

docker-test:
	docker build --target test -t $(IMAGE)-test .
	docker run --rm --network none $(IMAGE)-test

docker-demo:
	docker run --rm --network none --read-only --cap-drop ALL --security-opt no-new-privileges $(IMAGE) demo

docker-live:
	docker run --rm --read-only --cap-drop ALL --security-opt no-new-privileges -e TYPESAFE_API_KEY $(IMAGE) triage --live --input examples/issue.json

.PHONY: replay lint
replay:
	$(PYTHON) -m jevidence replay examples/replay-synthetic.jsonl --labels --compare-route-floor 0.7

lint:
	$(VENV)/bin/ruff check .
