#!/bin/bash

export DOCKER_BUILDKIT=1
EXTRA_DOCKER_BUILD_ARGS=${EXTRA_DOCKER_BUILD_ARGS:-""}

echo "Using the following extra args: ${EXTRA_DOCKER_BUILD_ARGS}"

for i in $(seq 1 3); do
  if docker buildx build --platform linux/amd64,linux/arm64 ${EXTRA_DOCKER_BUILD_ARGS} --tag "$1:$2" --push $3; then
    echo "[Success]: Buildx, attempt ${i}"
    exit 0
  fi
  sleep 3
done
echo "[Error]: Context Deadline Exceeded - Buildx"
exit 1
