#!/usr/bin/env bash
set -euo pipefail

IMAGE_NAME=${IMAGE_NAME:-warp2api-unified}
IMAGE_TAG=${IMAGE_TAG:-latest}

docker build -t ${IMAGE_NAME}:${IMAGE_TAG} .

echo "Built ${IMAGE_NAME}:${IMAGE_TAG}"

#!/usr/bin/env bash
set -euo pipefail

IMAGE_NAME=${IMAGE_NAME:-warp2api-unified}
IMAGE_TAG=${IMAGE_TAG:-latest}

docker build -t ${IMAGE_NAME}:${IMAGE_TAG} .

echo "Built ${IMAGE_NAME}:${IMAGE_TAG}"

