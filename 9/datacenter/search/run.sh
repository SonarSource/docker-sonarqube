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
  set -- /opt/sonarqube/bin/sonar.sh
fi

# if first arg looks like a flag, assume we want to run sonarqube server with flags
if [ "${1:0:1}" = '-' ]; then
    set -- /opt/sonarqube/bin/sonar.sh "$@"
fi

if [[ "$1" = '/opt/sonarqube/bin/sonar.sh' ]]; then

    #
    # Set mandatory properties
    #
    set_prop "sonar.cluster.node.search.host" "${IP:-}"
    set_prop "sonar.cluster.node.es.host" "${IP:-}"

    if [ ${#sq_opts[@]} -ne 0 ]; then
        set -- "$@" "${sq_opts[@]}"
    fi
fi

exec "$@"
