# Contributing to lazylake

Thank you! All contributions are welcome: code, docs, ideas, bug reports.

## Setup

```bash
uv venv && source .venv/bin/activate
uv pip install -e ".[dev]"
pytest
ruff check . && ruff format .
lazylake --demo
```

## Adding an AWS service

1. Create `src/lazylake/providers/<service>.py` with a class that reads the data through boto3.
2. Add models to `models.py` if needed.
3. Add a demo version (fake data) so the tool stays usable without AWS.
4. Test with **moto**: no real AWS account should be needed to run the tests.
5. Add the screen to `app.py`.

## Rules

- **Read-only by default.** Any action that modifies AWS (rerunning a job, deleting…)
  must ask for explicit confirmation.
- No stored secrets: rely only on the standard AWS credential chain.
- One PR = one topic, with tests.
