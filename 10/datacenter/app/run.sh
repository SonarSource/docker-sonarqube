#!/usr/bin/env bash

set -euxo pipefail

HOSTNAME=$(hostname)
# Get the global IPv4 and IPv6 addresses
IPV4=$(ip -4 -br address show scope global | awk '{print $3}' | cut -d '/' -f 1 | head -n 1)
IPV6=$(ip -6 -br address show scope global | awk '{print $3}' | cut -d '/' -f 1 | head -n 1)

# Check Kubernetes DNS for IPv4 and IPv6
K8S_DNS_IPV4_ANSWER=1
K8S_DNS_IPV6_ANSWER=1

if output=$(dig -4 +short kubernetes.default.svc.cluster.local 2>/dev/null) && [[ -n "$output" ]]; then
    K8S_DNS_IPV4_ANSWER=0
fi

if output=$(dig -6 AAAA +short kubernetes.default.svc.cluster.local 2>/dev/null) && [[ -n "$output" ]]; then
    K8S_DNS_IPV6_ANSWER=0
fi

# Determine the IP address to use
if [[ $K8S_DNS_IPV4_ANSWER -eq 0 || $K8S_DNS_IPV6_ANSWER -eq 0 ]]; then
    # Check if it's IPv6 only
    if [[ $K8S_DNS_IPV6_ANSWER -eq 0 && $K8S_DNS_IPV4_ANSWER -eq 1 ]]; then
        IP=$IPV6
    elif [[ $K8S_DNS_IPV4_ANSWER -eq 0 ]]; then
        IP=$IPV4
    else
        echo "No valid Kubernetes IP addresses found." && exit 1
    fi
else
    # Not running in Kubernetes, decide which IP to use
    if [[ -n "$IPV4" ]]; then
        IP=$IPV4
    elif [[ -n "$IPV6" ]]; then
        IP=$IPV6
    else
        echo "No valid IP addresses found." && exit 1
    fi
fi

echo "Using IP: $IP"

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
