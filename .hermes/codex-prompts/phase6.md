# Phase 6: CI/CD, Security, Final Polish

## 6.1 GitHub Actions CI

Create `.github/workflows/ci.yml` on the main branch:

```yaml
name: CI
on: [push, pull_request]

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v3
      - run: uv sync
      - run: uv run ruff check src/

  type-check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v3
      - run: uv sync
      - run: uv run mypy src/

  security:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v3
      - run: uv sync
      - run: uv run bandit -r src/ -c pyproject.toml
      - run: uv run semgrep --config=auto --error src/

  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v3
      - run: uv sync
      - run: uv run pytest tests/unit tests/integration/test_controller.py -q --tb=short

  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v3
      - run: uv build
```

- Use `astral-sh/setup-uv@v3` with `enable-cache: true`
- Skip docker-dependent e2e tests in CI (mark them with @pytest.mark.docker and exclude via `-m "not docker"` in the test job)

## 6.2 Security Configuration

Update `pyproject.toml` with:

- `[tool.bandit]` — exclude test directories, set `skips: ["B101"]` (allow assert in tests)
- `[tool.semgrep]` — rules section if needed
- Add semgrep to `[project.optional-dependencies]` with `dev` group
- `[tool.safety]` — known vulnerability ignores if needed

## 6.3 Ruff & Mypy Config (if not already set)

Ensure `pyproject.toml` has:

- `[tool.ruff]` — line-length 100, target-version py313
- `[tool.ruff.lint]` — select ALL and ignore specific rules that don't fit
- `[tool.mypy]` — strict mode, python-version 3.13, ignore_missing_imports = true

## 6.4 Docker Test Marker

- Add `docker` to pytest markers in `pyproject.toml` (`[tool.pytest.ini_options]`)
- Mark existing Docker sandbox tests in `tests/unit/test_sandbox.py` with `@pytest.mark.docker`
- Mark e2e tests that use Docker with `@pytest.mark.docker`

## 6.5 Final E2E Smoke

Create `scripts/end_to_end_smoke.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail
# End-to-end smoke test: runs scripted agent on the benchmark
# Skips Docker-dependent steps

echo "=== Constrained Agent Harness E2E Smoke ==="
uv run cah run --agent scripted --benchmark benchmarks/payment_webhook --iterations 3 2>&1
uv run cah report run latest
echo "=== SMOKE PASSED ==="
```

Make it executable. Test it.

## 6.6 README Update

Update README.md to include:
- Badges (CI, Python version, license) — use placeholder URLs
- Quick-start: `uv sync`, `cah run --help`
- Full example: `cah run --agent scripted --benchmark benchmarks/payment_webhook`
- CLI overview
- Project status note

## Verification

1. `uv run ruff check src/` — clean
2. `uv run mypy src/` — clean (or minimal known issues)
3. `pip install bandit semgrep 2>/dev/null; uv run bandit -r src/ -c pyproject.toml` — no high-severity issues
4. `uv run pytest tests/unit tests/integration/test_controller.py -q --tb=short` — all pass
5. `bash scripts/end_to_end_smoke.sh` — runs the scripted agent against the benchmark
6. `uv run mkdocs build --strict` (if mkdocs-material is installed)
