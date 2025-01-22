#!/bin/bash

export DOCKER_BUILDKIT=1
for i in $(seq 1 3); do
  if docker buildx build --platform linux/amd64,linux/arm64 --tag "$1:$2" --label "com.googleapis.cloudmarketplace.product.service.name=services/sonarqube-dce" --push $3; then
    echo "[Success]: Buildx, attempt ${i}"
    exit 0
  fi
  sleep 3
done
echo "[Error]: Context Deadline Exceeded - Buildx"
exit 1