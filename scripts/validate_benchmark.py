from __future__ import annotations

import sys
from pathlib import Path

from constrained_agent.cli.benchmark import validate_benchmark_path


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: uv run python scripts/validate_benchmark.py benchmarks/payment_webhook")
        return 2
    benchmark_path = Path(sys.argv[1])
    errors = validate_benchmark_path(benchmark_path)
    if errors:
        for error in errors:
            print(error)
        return 1
    print(f"benchmark valid: {benchmark_path.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
