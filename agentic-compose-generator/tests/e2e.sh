#!/usr/bin/env bash
# End-to-end check of one generated bundle: generate it, bring it up, wait until every service is
# healthy (or, for the init services, exited 0), then confirm the gVisor-sandboxed agent runtimes
# can resolve and reach egress-proxy — the path that breaks when runsc runs without
# --network=host. Does not configure a licence, an LLM provider or GitHub, so no agent job runs.
#
# Every image the bundle references must already be present locally (`docker compose pull` in the
# bundle, or your own builds retagged); `docker compose up` is run with --pull never so a missing
# one fails fast instead of silently testing a different image.
#
# Usage: tests/e2e.sh <out-dir> [generate.py flags...]
set -euo pipefail

cd "$(dirname "$0")/.."

out=${1:?usage: tests/e2e.sh <out-dir> [generate.py flags...]}
shift
timeout_s=${E2E_TIMEOUT_SECONDS:-900}

python3 generate.py --out "$out" --force "$@"
cd "$out"

on_exit() {
  local status=$?
  if [ "$status" -ne 0 ]; then
    docker compose ps -a || true
    docker compose logs --no-color --tail 200 || true
  fi
  exit "$status"
}
trap on_exit EXIT

docker compose up -d --pull never

# One line per container: service, state, health (empty without a healthcheck), exit code.
states() {
  docker compose ps -a --format '{{.Service}} {{.State}} {{.Health}} {{.ExitCode}}'
}

deadline=$(( $(date +%s) + timeout_s ))
while :; do
  pending=0
  while read -r service state health code; do
    # `{{.Health}}` renders empty when there is no healthcheck, which shifts the exit code left.
    if [ -z "$code" ]; then code=$health; health=""; fi
    case "$state:$health" in
      running:healthy | running:) ;;
      exited:*)
        if [ "$code" != "0" ]; then
          echo "error: $service exited with code $code" >&2
          exit 1
        fi
        ;;
      *) pending=$((pending + 1)) ;;
    esac
  done < <(states)
  [ "$pending" -eq 0 ] && break
  if [ "$(date +%s)" -ge "$deadline" ]; then
    echo "error: services not healthy after ${timeout_s}s" >&2
    exit 1
  fi
  sleep 10
done
echo "all services healthy"

# Any HTTP status proves name resolution and a TCP connection; squid answers a direct,
# non-proxy request with an error page, which is fine here.
for service in $(docker compose config --services); do
  case "$service" in
    hunter-runtime | remediation-agent-runtime)
      code=$(docker compose exec -T "$service" \
        curl -sS --noproxy '*' -o /dev/null -w '%{http_code}' --max-time 10 http://egress-proxy:3128/)
      echo "$service -> egress-proxy: HTTP $code"
      [ "$code" != "000" ] || { echo "error: $service cannot reach egress-proxy" >&2; exit 1; }
      ;;
  esac
done

echo "e2e passed"
