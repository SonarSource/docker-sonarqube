#!/usr/bin/env bash

set -euo pipefail

HOSTNAME=$(hostname)
USE_IPV6="${USE_IPV6:-false}"
if [[ "${USE_IPV6}" == "true" ]]; then
    IP=$(ip -6 address show scope global | grep inet6 | awk '{ print $2 }' | head -n 1 | cut -d \/ -f 1)
    export JAVA_TOOL_OPTIONS="-Djava.net.preferIPv4Stack=false -Djava.net.preferIPv6Addresses=true"
    export SONAR_WEB_JAVAADDITIONALOPTS="-Djava.net.preferIPv4Stack=false -Djava.net.preferIPv6Addresses=true"
else
    IP=$(ip -4 address show scope global | grep inet | awk '{ print $2 }' | head -n 1 | cut -d \/ -f 1)
fi

declare -a sq_opts=()
set_prop() {
  if [[ "${2}" ]]; then
    sq_opts+=("-D${1}=${2}")
  fi
}

# if nothing is passed, assume we want to run sonarqube server
if [[ $# == 0 ]]; then
  set -- /opt/sonarqube/docker/sonar.sh
fi

# if first arg looks like a flag, assume we want to run sonarqube server with flags
if [[ "${1:0:1}" = '-' ]]; then
    set -- /opt/sonarqube/docker/sonar.sh "$@"
fi

if [[ "${1}" = '/opt/sonarqube/docker/sonar.sh' ]]; then

    #
    # Change log path to ensure every app node can write in their own directory
    # This resolves a cluttered log on docker-compose with scale > 1
    #
    if [[ -z "${SONAR_PATH_LOGS:-}" ]]
    then
        SONAR_CLUSTER_PATH_LOGS="logs/${HOSTNAME}"
        mkdir -p "${SONARQUBE_HOME}/${SONAR_CLUSTER_PATH_LOGS}"
    else
        SONAR_CLUSTER_PATH_LOGS="${SONAR_PATH_LOGS}/${HOSTNAME}"
        mkdir -p "${SONAR_CLUSTER_PATH_LOGS}"
    fi

    #
    # Set mandatory properties
    #
    set_prop "sonar.cluster.node.host" "${IP:-}"
    set_prop "sonar.path.logs" "${SONAR_CLUSTER_PATH_LOGS:-}"
    if [[ "${#sq_opts[@]}" -ne 0 ]]; then
        set -- "$@" "${sq_opts[@]}"
    fi
fi

exec "$@"
