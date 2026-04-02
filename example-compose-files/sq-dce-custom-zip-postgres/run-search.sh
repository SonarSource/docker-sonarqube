#!/usr/bin/env bash

set -euo pipefail

HOSTNAME=$(hostname)
USE_IPV6="${USE_IPV6:-false}"
if [[ "${USE_IPV6}" == "true" ]]; then
    IP=$(ip -6 address show scope global | grep inet6 | awk '{ print $2 }' | head -n 1 | cut -d \/ -f 1)
    export JAVA_TOOL_OPTIONS="-Djava.net.preferIPv4Stack=false -Djava.net.preferIPv6Addresses=true"
    export SONAR_SEARCH_JAVAADDITIONALOPTS="-Djava.net.preferIPv4Stack=false -Djava.net.preferIPv6Addresses=true"
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
    # Set mandatory properties
    #
    set_prop "sonar.cluster.node.search.host" "${IP:-}"
    set_prop "sonar.cluster.node.es.host" "${IP:-}"

    if [[ "${#sq_opts[@]}" -ne 0 ]]; then
        set -- "$@" "${sq_opts[@]}"
    fi
fi

exec "$@"
