#!/usr/bin/env bash

set -euo pipefail

HOSTNAME=$(hostname)

log() { printf '[run.sh] %s\n' "$*" >&2; }

discover_ip() {
    if [[ "${1}" == "6" ]]; then
        ip -6 address show scope global | grep inet6 | awk '{ print $2 }' | head -n 1 | cut -d \/ -f 1 || true
    else
        ip -4 address show scope global | grep inet | awk '{ print $2 }' | head -n 1 | cut -d \/ -f 1 || true
    fi
}

# This search node's Elasticsearch address (sonar.cluster.node.search.host / .es.host): prefer the
# explicit SONAR_CLUSTER_NODE_IP, else autodiscover, preferring IPv6 when USE_IPV6=true and IPv4 otherwise.
resolve_node_ip() {
    if [[ -n "${SONAR_CLUSTER_NODE_IP:-}" ]]; then
        log "Cluster node IP set via SONAR_CLUSTER_NODE_IP=${SONAR_CLUSTER_NODE_IP}"
        printf '%s' "${SONAR_CLUSTER_NODE_IP}"
        return
    fi

    local primary=4 secondary=6
    [[ "${USE_IPV6:-false}" == "true" ]] && { primary=6; secondary=4; }
    log "SONAR_CLUSTER_NODE_IP not set; autodiscovering node IP (IPv${primary} then IPv${secondary})."
    local discovered
    discovered=$(discover_ip "${primary}")
    [[ -z "${discovered}" ]] && discovered=$(discover_ip "${secondary}")
    log "Autodiscovered cluster node IP: ${discovered:-<none found>}"
    printf '%s' "${discovered}"
}

IP=$(resolve_node_ip)

if [[ -z "${IP}" ]]; then
    log "WARNING: no search node IP found; sonar.cluster.node.search.host will be unset and startup may fail."
fi

# When USE_IPV6 is enabled, tell the JVM to prefer IPv6 for SonarQube's own sockets.
if [[ "${USE_IPV6:-false}" == "true" ]]; then
    ipv6_jvm_opts="-Djava.net.preferIPv4Stack=false -Djava.net.preferIPv6Addresses=true"
    export JAVA_TOOL_OPTIONS="${JAVA_TOOL_OPTIONS:-} ${ipv6_jvm_opts}"
    export SONAR_SEARCH_JAVAADDITIONALOPTS="${SONAR_SEARCH_JAVAADDITIONALOPTS:-} ${ipv6_jvm_opts}"
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
