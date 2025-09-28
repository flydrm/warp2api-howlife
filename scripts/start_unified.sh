#!/usr/bin/env bash
set -euo pipefail

export PORT=${PORT:-8080}

python -m unified_server

