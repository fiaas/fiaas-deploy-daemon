# CLAUDE.md

## Prerequisites

- Python 3.12
- Install dependencies: `pip install -r requirements.txt`

## Running tests

Always use tox to run tests. Do not use `pytest`, `python -m pytest`, or try to find/invoke pytest binaries directly.

```sh
# Run unit tests (optionally pass specific test files/args after --)
tox -e test
tox -e test -- tests/fiaas_deploy_daemon/specs/v3/test_v3factory.py -x -q

# Check code style
tox -e codestyle

# Run integration tests (requires docker and kind v0.18.0+) - OK to run
tox -e integration_test
```
