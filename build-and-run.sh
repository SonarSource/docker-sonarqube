#!/usr/bin/env bash

set -euo pipefail

cd "$(dirname "$0")"

port=9000

print_usage() {
    cat << EOF
usage: $0 [IMAGE...]

examples:
       $0
       $0 7.4-community
       $0 7.4-community-alpine
EOF
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

require docker

for arg; do
    if [[ $arg == "-h" ]] || [[ $arg == "--help" ]]; then
        print_usage
        exit
    fi
done

if [[ $# = 0 ]]; then
    print_usage
    exit 1
fi

image=$1
image=${image%/}
if ! [[ -d "$image" ]]; then
    warn "not a valid image, directory does not exist: $image"
    exit 1
fi
name=sqtest:$image
docker build -t "$name" -f "$image/Dockerfile" "$PWD/$image"
docker run -p $port:9000 "$name"
