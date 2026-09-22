FROM python:3.12-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
COPY requirements-live.txt ./
RUN python -m pip install -r requirements-live.txt
COPY pyproject.toml README.md LICENSE ./
COPY jevidence ./jevidence
COPY examples ./examples
RUN python -m pip install --no-deps . \
    && useradd --uid 10001 --create-home sandbox
USER 10001:10001

FROM base AS test
COPY tests ./tests
ENTRYPOINT ["python", "-m", "unittest", "discover", "-s", "tests", "-v"]

FROM base AS runtime
ENTRYPOINT ["python", "-m", "jevidence"]
CMD ["demo"]
