#!/usr/bin/env bash
set -euo pipefail

export UV_CACHE_DIR="${UV_CACHE_DIR:-$PWD/.uv-cache}"
uv run ruff check backend ml tests
uv run pytest tests --cov=backend --cov=ml --cov-branch --cov-report=term-missing
coverage_json="${TMPDIR:-/tmp}/wind-coverage.json"
uv run coverage json -o "$coverage_json"
uv run python -c 'import json,sys; totals=json.load(open(sys.argv[1]))["totals"]; assert totals["percent_statements_covered"] >= 85; assert totals["percent_branches_covered"] >= 80' "$coverage_json"
npm test --prefix frontend
npm run typecheck --prefix frontend
npm run build --prefix frontend
