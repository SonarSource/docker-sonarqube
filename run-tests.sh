#!/usr/bin/env bash

set -euo pipefail

cd "$(dirname "$0")"

port=9000

print_usage() {
    cat << EOF
usage: ${0} [IMAGE...]

examples:
       ${0} 7.6-community
EOF
}

info() {
    echo "[info] $*"
}

warn() {
    echo "[warn] $*" >&2
}

fatal() {
    echo "[error] $*" >&2
    exit 1
}

require() {
    local prog missing=()
    for prog; do
        if ! type "${prog}" &>/dev/null; then
            missing+=("${prog}")
        fi
    done

    [[ ${#missing[@]} = 0 ]] || fatal "could not find required programs on the path: ${missing[*]}"
}

wait_for_sonarqube() {
    local image="${1}" i web_up=no sonarqube_up=no

    for ((i = 0; i < 15; i++)); do
        info "${image}: waiting for web server to start ..."
        if curl -sI "localhost:${port}" | grep '^HTTP/.* 200'; then
            web_up=yes
            break
        fi
        sleep 5
    done

    [[ "${web_up}" = yes ]] || return 1

    for ((i = 0; i < 30; i++)); do
        info "${image}: waiting for sonarqube to be ready ..."
        if curl -s "localhost:${port}/api/system/status" | grep '"status":"UP"'; then
            sonarqube_up=yes
            break
        fi
        sleep 10
    done

    [[ "${sonarqube_up}" = yes ]]
}

wait_for_sonarqube_dce() {
    local image="${1}-app" i web_up=no sonarqube_up=no

    for ((i = 0; i < 90; i++)); do
        info "${image}: waiting for web server to start ..."
        if curl -sI "localhost:${port}" | grep '^HTTP/.* 200'; then
            web_up=yes
            break
        fi
        sleep 5
    done

    [[ "${web_up}" = yes ]] || return 1

    for ((i = 0; i < 90; i++)); do
        info "${image}: waiting for sonarqube to be ready ..."
        if curl -s "localhost:${port}/api/system/status" | grep '"status":"UP"'; then
            sonarqube_up=yes
            break
        fi
        sleep 10
    done

    [[ "${sonarqube_up}" = yes ]]
}

sanity_check_image() {
    local image="${1}" id result
    local test_case="${2}"

    if [[ "${test_case}" == docker ]]; then
        id=$(docker run -d -p "${port}:9000" "${image}")
        info "${image}: container started: ${id}"

        if wait_for_sonarqube "${image}"; then
            info "${image}: OK !"
            result=ok
        else
            warn "${image}: could not confirm service started"
            result=failure
        fi

        info "${image}: stopping container: ${id}"
        docker container stop "${id}"

        [[ "${result}" == ok ]]
    elif [[ "${test_case}" == docker-compose ]]; then
        local test_compose_path="tests/dce-compose-test"
        cd "${test_compose_path}"
        export PORT="${port}"
        export IMAGE="${1}"
        docker compose up -d sonarqube
        if wait_for_sonarqube_dce "${image}"; then
            info "${image}-app: OK !"
            result=ok
        else
            warn "${image}-app: could not confirm service started"
            result=failure
        fi

        info "${image}-app: stopping container stack"
        docker compose stop

        [[ "${result}" == ok ]]
    fi
    
}

require curl docker

for arg; do
    if [[ "${arg}" == "-h" ]] || [[ "${arg}" == "--help" ]]; then
        print_usage
        exit
    fi
done

if [[ $# = 0 ]]; then
    warn "at least one image as parameter is required"
    exit 1
fi

image="${1}"
test_case="${2:-docker}"
results=()

if sanity_check_image "${image}" "${test_case}"; then
    results+=("success")
else
    results+=("failure")
fi

failures=0
echo "${image} => ${results[*]}"
if [[ "${results[0]}" != success ]]; then
    ((failures++))
fi

[[ "${failures}" = 0 ]]
