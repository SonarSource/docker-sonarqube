#!/bin/bash

PUBLIC_IMAGE_NAME=${1}
tag=${2}
WS_PRODUCTNAME=${3}
WS_WSS_URL=${4}
MEND_API_KEY=${5}

IMAGE_PULLED=1
SCANNED=1

echo "Scan the ${PUBLIC_IMAGE_NAME}:${tag} image"

for i in $(seq 1 3); do
    if docker pull "${PUBLIC_IMAGE_NAME}:${tag}"; then
        IMAGE_PULLED=0
        break
    fi
    echo "[${i}/3] Retrying to pull image ${PUBLIC_IMAGE_NAME}:${tag}..."
    sleep 5
done

if [[ ${IMAGE_PULLED} -ne 0 ]]; then
    echo "Failed to pull image ${PUBLIC_IMAGE_NAME}:${tag}"
    exit 1
fi

for i in $(seq 1 3); do
    if java -jar wss-unified-agent.jar -c .cirrus/wss-unified-agent.config -apiKey $MEND_API_KEY -product ${WS_PRODUCTNAME} -project ${PUBLIC_IMAGE_NAME}:${tag} -wss.url ${WS_WSS_URL} -docker.scanImages true; then
        SCANNED=0
        break
    fi
    echo "[${i}/3] Retrying to scan image ${PUBLIC_IMAGE_NAME}:${tag}..."
    sleep 5
done

if [[ ${SCANNED} -ne 0 ]]; then
    echo "Failed to scan image ${PUBLIC_IMAGE_NAME}:${tag}"
    exit 2
fi

exit 0
