#!/bin/bash

STAGING_IMAGE_NAME=${1}
tag=${2}
platform=${3}
WS_PRODUCTNAME=${4}
WS_WSS_URL=${5}
MEND_API_KEY=${6}

IMAGE_PULLED=1
SCANNED=1

echo "Scan the ${STAGING_IMAGE_NAME}:${tag} image supporting linux/${platform}"

for i in $(seq 1 3); do
    if docker pull --platform linux/"${platform}" "${STAGING_IMAGE_NAME}:${tag}"; then
        IMAGE_PULLED=0
        break
    fi
    echo "[${i}/3] Retrying to pull image ${STAGING_IMAGE_NAME}:${tag}..."
    sleep 5
done

if [[ ${IMAGE_PULLED} -ne 0 ]]; then
    echo "Failed to pull image ${STAGING_IMAGE_NAME}:${tag}"
    exit 1
fi

for i in $(seq 1 3); do
    if java -jar wss-unified-agent.jar -c .cirrus/wss-unified-agent.config -apiKey "${MEND_API_KEY}" -product "${WS_PRODUCTNAME}" -project "${STAGING_IMAGE_NAME}:${tag}" -wss.url ${WS_WSS_URL} -docker.scanImages true; then
        SCANNED=0
        break
    fi
    echo "[${i}/3] Retrying to scan image ${STAGING_IMAGE_NAME}:${tag}..."
    sleep 5
done

if [[ ${SCANNED} -ne 0 ]]; then
    echo "Failed to scan image ${STAGING_IMAGE_NAME}:${tag}"
    exit 2
fi

exit 0
