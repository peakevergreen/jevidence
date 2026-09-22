# Contributing

Start with the offline demo and tests. Changes should keep model judgment separate
from application policy, make fallbacks explicit, and avoid hidden side effects.

- Add synthetic fixtures for new policy branches and tests around threshold boundaries.
- Label synthetic evidence clearly. Do not describe fixture pass rates as model accuracy.
- Never add API keys, real customer records, or private logs to fixtures or issues.
- Keep live calls explicitly opted in. Tests and CI must not need a paid account.
- Bump question/policy version identifiers when their behavior changes.
- Run `make test`, `make replay`, `make lint`, and the SDK transport tests described in the README.
- For container changes, also run `make docker-test docker-build docker-demo`.
- When updating the SDK, review its changelog, refresh dependency pins in a clean
  Python 3.12 environment, and rerun the mocked transport tests.

Submit a focused pull request explaining the behavior change and how it was checked.
