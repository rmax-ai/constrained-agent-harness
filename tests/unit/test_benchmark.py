from __future__ import annotations

import stat
import subprocess
import sys
from pathlib import Path

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[2]
BENCHMARK_ROOT = PROJECT_ROOT / "benchmarks" / "payment_webhook"
SOURCE_REPO = BENCHMARK_ROOT / "source_repo"
PROTECTED_TESTS = BENCHMARK_ROOT / "protected_tests"


def test_benchmark_visible_tests_fail_initially() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "tests/test_webhook.py"],
        cwd=SOURCE_REPO,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0
    combined_output = f"{result.stdout}\n{result.stderr}"
    assert "test_duplicate_sequential_delivery" in combined_output


def test_hidden_tests_not_writable() -> None:
    assert PROTECTED_TESTS.is_dir()

    for path in [PROTECTED_TESTS, *PROTECTED_TESTS.rglob("*")]:
        mode = path.stat().st_mode
        assert (mode & stat.S_IWUSR) == 0, f"{path} should not be owner-writable"
        assert (mode & stat.S_IWGRP) == 0, f"{path} should not be group-writable"
        assert (mode & stat.S_IWOTH) == 0, f"{path} should not be world-writable"


def test_benchmark_validates_correctly() -> None:
    manifest = yaml.safe_load((BENCHMARK_ROOT / "benchmark_manifest.yaml").read_text())
    assert manifest == {
        "name": "payment-webhook",
        "title": "Payment Webhook Idempotency",
        "description": "Fix duplicate payment creation from duplicate webhook deliveries.\n",
        "language": "python",
        "framework": "fastapi",
        "default_goal": "goal.yaml",
    }

    goal = yaml.safe_load((BENCHMARK_ROOT / "goal.yaml").read_text())
    assert goal["task"]["id"] == "payment-webhook-idempotency"
    assert goal["acceptance"]["hidden_checks"]["directory"] == "../protected_tests"
    assert goal["acceptance"]["hidden_checks"]["writable"] is False
    assert goal["constraints"]["writable_paths"] == ["src/"]
    assert goal["constraints"]["protected_paths"] == ["tests/", "pyproject.toml"]

    assert (SOURCE_REPO / "src" / "app.py").is_file()
    assert (SOURCE_REPO / "tests" / "test_webhook.py").is_file()
    assert (BENCHMARK_ROOT / "reference_solution" / "src" / "app.py").is_file()
