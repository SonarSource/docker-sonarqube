#!/usr/bin/env bash

set -euo pipefail

cd "$(dirname "$0")"

port=9000

info() {
    echo "[info] $@"
}

warn() {
    echo "[warn] $@" >&2
}

fatal() {
    echo "[error] $@" >&2
    exit 1
}

require() {
    local prog missing=()
    for prog; do
        if ! type "$prog" &>/dev/null; then
            missing+=("$prog")
        fi
    done

    [[ ${#missing[@]} = 0 ]] || fatal "could not find reqired programs on the path: ${missing[@]}"
}

wait_for_sonarqube() {
    local image=$1 i web_up=no sonarqube_up=no

    for ((i = 0; i < 10; i++)); do
        info "$image: waiting for web server to start ..."
        if curl -sI localhost:$port | grep '^HTTP/.* 200'; then
            web_up=yes
            break
        fi
        sleep 5
    done

    [[ $web_up = yes ]] || return 1

    for ((i = 0; i < 10; i++)); do
        info "$image: waiting for sonarqube to be ready ..."
        if curl -s localhost:$port/api/system/status | grep '"status":"UP"'; then
            sonarqube_up=yes
            break
        fi
        sleep 10
    done

    [[ "$sonarqube_up" = yes ]]
}

sanity_check_image() {
    local image=$1 id result

    docker system prune -fa
    docker pull ${image}
    id=$(docker run -d -p ${port}:9000 "$image")
    info "$image: container started: $id"

    if wait_for_sonarqube "$image"; then
        info "$image: OK !"
        result=ok
    else
        warn "$image: could not confirm service started"
        result=failure
    fi

    info "$image: stopping container: $id"
    docker container stop "$id"

    [[ $result == ok ]]
}

require curl docker


results=()

if sanity_check_image "sonarqube"; then
    results+=("success")
else
    results+=("failure")
fi


echo

failures=0

echo "sonarqube => ${results[0]}"
if [[ ${results[0]} != success ]]; then
    ((failures++)) || :
fi


[[ ${failures} = 0 ]]
