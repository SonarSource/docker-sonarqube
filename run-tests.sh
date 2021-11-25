#!/usr/bin/env bash

set -euo pipefail

cd "$(dirname "$0")"

port=9000

print_usage() {
    cat << EOF
usage: $0 [IMAGE...]

examples:
       $0 7.6-community
EOF
}

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

    for ((i = 0; i < 20; i++)); do
        info "$image: waiting for sonarqube to be ready ..."
        if curl -s localhost:$port/api/system/status | grep '"status":"UP"'; then
            sonarqube_up=yes
            break
        fi
        sleep 10
    done

    [[ "$sonarqube_up" = yes ]]
}

wait_for_sonarqube_dce() {
    local image=$1 i web_up=no sonarqube_up=no

    for ((i = 0; i < 80; i++)); do
        info "$image: waiting for web server to start ..."
        if curl -sI localhost:$port | grep '^HTTP/.* 200'; then
            web_up=yes
            break
        fi
        sleep 5
    done

    [[ $web_up = yes ]] || return 1

    for ((i = 0; i < 80; i++)); do
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
    local test_case=$2

    if [[ $2 == docker ]]; then
        id=$(docker run -d -p $port:9000 "$image")
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
    elif [ $2 == docker-compose ]; then
        if [[ $1 =~ "8" ]]; then
            _test_compose_path="tests/8/dce-compose-test"
        elif [[ $1 =~ "9" ]]; then
            _test_compose_path="tests/9/dce-compose-test"
        fi
        cd $_test_compose_path
        export PORT=$port
        docker-compose up -d --scale sonarqube=0
        sleep 60
        docker-compose up -d --scale sonarqube=1
        if wait_for_sonarqube_dce "$image"; then
            info "$image: OK !"
            result=ok
        else
            warn "$image: could not confirm service started"
            result=failure
        fi

        info "$image: stopping container stack"
        docker-compose stop

        [[ $result == ok ]]
    fi
    
}

require curl docker

for arg; do
    if [[ $arg == "-h" ]] || [[ $arg == "--help" ]]; then
        print_usage
        exit
    fi
done

if [[ $# = 0 ]]; then
    warn "at least one image as parameter is required"
    exit
fi

image=($1)
test_case=($2)
results=()

if sanity_check_image "$image" "$test_case"; then
    results+=("success")
else
    results+=("failure")
fi

failures=0
echo "${image} => ${results}"
if [[ ${results} != success ]]; then
    ((failures++))
fi

[[ $failures = 0 ]]
