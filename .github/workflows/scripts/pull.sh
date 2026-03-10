#!/bin/bash

IMAGE_NAME="${1}"
tag="${2}"
platform="${3}"

for i in $(seq 1 3); do
    if docker pull --platform "linux/${platform}" "${IMAGE_NAME}:${tag}"; then
        exit 0
    fi
    echo "[${i}/3] Retrying to pull image ${IMAGE_NAME}:${tag}..."
    sleep 5
done
echo "[Error]: Failed to pull image ${IMAGE_NAME}:${tag}"
exit 1
