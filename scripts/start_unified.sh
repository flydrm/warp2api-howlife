#!/usr/bin/env bash
set -euo pipefail

export HOST=${HOST:-0.0.0.0}
export PORT=${PORT:-8080}

# Defaults for MoeMail (can be overridden by env)
export MOEMAIL_BASE_URL=${MOEMAIL_BASE_URL:-https://email.959585.xyz}
export MOEMAIL_API_KEY=${MOEMAIL_API_KEY:-}

python -m unified_server

#!/usr/bin/env bash
set -euo pipefail

export PORT=${PORT:-8080}

python -m unified_server

