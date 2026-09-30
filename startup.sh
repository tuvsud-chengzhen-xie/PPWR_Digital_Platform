#!/bin/sh
set -eu

cd "$(dirname "$0")"
export PPWR_DATA_DIR="${PPWR_DATA_DIR:-/home/ppwr-data}"

exec python -m uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"