#!/usr/bin/env bash
set -euo pipefail

export UV_CACHE_DIR="${UV_CACHE_DIR:-$PWD/.uv-cache}"
uv run ruff check ml tests/ml
uv run pytest tests/ml --cov=ml --cov-branch --cov-report=term-missing
