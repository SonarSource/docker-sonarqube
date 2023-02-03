#!/usr/bin/env bash

set -euo pipefail

HOSTNAME=$(hostname)
IP=$(ip -4 address show scope global | grep inet | awk '{ print $2 }' | head -n 1 | cut -d \/ -f 1)

declare -a sq_opts=()
set_prop() {
  if [ "$2" ]; then
    sq_opts+=("-D$1=$2")
  fi
}

# if nothing is passed, assume we want to run sonarqube server
if [ "$#" == 0 ]; then
  set -- /opt/sonarqube/docker/sonar.sh
fi

# if first arg looks like a flag, assume we want to run sonarqube server with flags
if [ "${1:0:1}" = '-' ]; then
    set -- /opt/sonarqube/docker/sonar.sh "$@"
fi

if [[ "$1" = '/opt/sonarqube/docker/sonar.sh' ]]; then

    #
    # Change log path to ensure every app node can write in their own directory
    # This resolves a cluttered log on docker-compose with scale > 1
    #
    if [ -z "${SONAR_PATH_LOGS:-}" ]
    then
        SONAR_CLUSTER_PATH_LOGS="logs/${HOSTNAME}"
        mkdir -p ${SONARQUBE_HOME}/${SONAR_CLUSTER_PATH_LOGS}
    else
        SONAR_CLUSTER_PATH_LOGS="${SONAR_PATH_LOGS}/${HOSTNAME}"
        mkdir -p ${SONAR_CLUSTER_PATH_LOGS}}
    fi

    #
    # Set mandatory properties
    #
    set_prop "sonar.cluster.node.host" "${IP:-}"
    set_prop "sonar.path.logs" "${SONAR_CLUSTER_PATH_LOGS:-}"
    if [ ${#sq_opts[@]} -ne 0 ]; then
        set -- "$@" "${sq_opts[@]}"
    fi
fi

exec "$@"
