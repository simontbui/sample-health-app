#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
export BENCH_RESULTS_DIR="${BENCH_RESULTS_DIR:-results-5m}"
python3 scripts/setup-large.py "$@"
python3 scripts/benchmark.py "${BENCH_REPEATS:-10}"
