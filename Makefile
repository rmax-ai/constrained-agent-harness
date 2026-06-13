.PHONY: install format lint typecheck test security docs build clean doctor demo

# Install
install:
	uv sync --frozen

install-dev:
	uv sync --frozen --all-extras

# Formatting
format:
	uv run ruff format .

# Linting
lint:
	uv run ruff check .
	uv run ruff format --check .

# Type checking
typecheck:
	uv run mypy src

# Testing
test:
	uv run pytest

test-unit:
	uv run pytest tests/unit -v

test-integration:
	uv run pytest tests/integration -v

test-e2e:
	uv run pytest tests/end_to_end -v

test-coverage:
	uv run pytest --cov --cov-report=term --cov-report=html

test-live:
	uv run pytest -m live_model -v

# Security
security:
	uv run bandit -r src/
	uv run semgrep --config=auto --error

# Documentation
docs:
	uv run mkdocs serve

docs-build:
	uv run mkdocs build --strict

# CI checks (runs everything CI does)
ci-check: format lint typecheck test security docs-build

# Demo
doctor:
	uv run cah doctor

demo-scripted:
	uv run cah run \
		benchmarks/payment_webhook/goal.yaml \
		--repo benchmarks/payment_webhook/source_repo \
		--agent scripted

# Build
build:
	uv build

# Cleanup
clean:
	rm -rf .cah/ .pytest_cache/ .mypy_cache/ .ruff_cache/ htmlcov/ site/ dist/ build/ *.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
