#!/usr/bin/env bash
set -euo pipefail

IMAGE_NAME=${IMAGE_NAME:-warp2api-unified}
IMAGE_TAG=${IMAGE_TAG:-latest}
CONTAINER_NAME=${CONTAINER_NAME:-warp2api-unified}
PORT=${PORT:-8080}

# Optional: mount local accounts.db for persistence
DB_PATH_HOST=${DB_PATH_HOST:-}
DB_PATH_CONT=${DB_PATH_CONT:-/app/account-pool-service/accounts.db}

RUN_ARGS=( -d --rm --name "$CONTAINER_NAME" -p ${PORT}:8080 )

if [[ -n "$DB_PATH_HOST" ]]; then
  RUN_ARGS+=( -v "$DB_PATH_HOST":"$DB_PATH_CONT" )
fi

docker run "${RUN_ARGS[@]}" ${IMAGE_NAME}:${IMAGE_TAG}

echo "Container ${CONTAINER_NAME} running on :${PORT}"

