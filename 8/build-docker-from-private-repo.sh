#!/usr/bin/env bash

set -euo pipefail

##
# Wrapper around 'docker build' command to easily build a docker 8 image from an SQ artifact hosted on a private server
# 
# Usage:
# $0 EDITION [any number of docker run options]
#
#    EDITION: name of the directory of the edition to build
#
# Required env variables:
#    SQ_VERSION: version of SQ
#    ZIP_SERVER: name of private server
#    ZIP_URL: full URL to the SQ archive on the private server
#    ZIP_USERNAME: username to authenticate on the private server
#    ZIP_PASSWORD: password to authenticate on the private server
#
# Sample usage:
# BUILD_NUMBER="8.0.0.42" SQ_VERSION="${BUILD_NUMBER}" ZIP_SERVER="repox.jfrog.io" ZIP_URL="https://repox.jfrog.io/repox/sonarsource-builds/org/sonarsource/sonarqube/sonar-application/${BUILD_NUMBER}/sonar-application-${BUILD_NUMBER}.zip" ZIP_USERNAME="foo" ZIP_PASSWORD="bar" $0 community --tag sonarqube:8
#
##

info() {
  echo "[info] $@"
}

fatal() {
  echo "[error] $@" >&2
  exit 1
}

download_artifact_to() {
  local available=no
  local netrc="machine ${ZIP_SERVER} login ${ZIP_USERNAME} password ${ZIP_PASSWORD}"
  local output="${1}"

  for ((i = 0; i < 10; i++)); do
    info "Waiting for artifact to be available in repox..."

    # repox may require some time to index the artifact freshly uploaded
    if curl --silent --head --show-error --netrc-file <(cat <<<"${netrc}") "$ZIP_URL" | grep '^HTTP/.* 200'; then
      available=yes
      info "Downloading artifact..."
      curl --silent --show-error --netrc-file <(cat <<<"${netrc}") --output "${output}" "$ZIP_URL" \
         || fatal "Failed to download artifact"
      break
    fi
    sleep 5s
  done

  [[ ${available} = yes ]]
}

# name of edition to build is mandatory
if [ "${1:-}" ]; then
  edition="${1}"
else
  fatal "Name of the edition is required"
fi
shift

cd "$(dirname "$0")"
docker_file="${PWD}/${edition}/Dockerfile"
if [ ! -f "$docker_file" ]; then
  fatal "Can not find DockerFile ${docker_file}"
fi

mkdir -p "${PWD}/${edition}/zip"
zip_file="${edition}/zip/sonarqube-${SQ_VERSION}.zip"
info "Docker image will be built from artifact $ZIP_URL"
download_artifact_to "${zip_file}" || fatal "Timeout waiting for artifact to be available"

docker build "$edition" \
  --build-arg SONARQUBE_VERSION="${SQ_VERSION}" \
  "$@"

rm "${zip_file}" || fatal "Failed to delete downloaded artifact ${zip_file}"

