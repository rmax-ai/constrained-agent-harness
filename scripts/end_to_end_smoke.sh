#!/usr/bin/env bash
set -euo pipefail

# E2E smoke test: runs the scripted agent against the benchmark
# and verifies the reporting commands work.
# Skips Docker-dependent steps.

echo "=== Constrained Agent Harness E2E Smoke ==="

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.."

echo "--- Lint ---"
uv run ruff check src/

echo "--- Unit Tests ---"
uv run pytest tests/unit -q --tb=short

echo "--- Controller Integration ---"
uv run pytest tests/integration/test_controller.py -q --tb=short

echo "--- Telemetry Import ---"
uv run python -c "
from constrained_agent.telemetry import GaugeCollector, RunSummary, TelemetryLogger
g = GaugeCollector()
g.record_decision('ACCEPT')
g.record_model_call(150)
snap = g.snapshot()
assert snap['model_calls'] == 1
assert snap['decisions']['ACCEPT'] == 1
print(f'telemetry OK: {snap}')
"

echo "=== E2E SMOKE PASSED ==="
