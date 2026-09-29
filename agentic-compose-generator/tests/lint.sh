#!/usr/bin/env bash
# Generates every profile in profiles/ and validates the emitted bundle:
#   1. `docker compose config -q` — structural validity of the flattened compose file.
#   2. Forbidden-string / leftover-${} scan — same rules as generate.py's scan_forbidden().
#   3. Runtime isolation — each agent runtime is only on internal networks, none shared with the
#      other runtime, so its only way out is egress-proxy.
# Then checks that invalid inputs are refused and that regenerating over a bundle is safe.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT_DIR="$(mktemp -d)"
trap 'rm -rf "$OUT_DIR"' EXIT

# Same source as generate.py: comma-separated extra strings that must never reach a bundle.
IFS=',' read -r -a FORBIDDEN_STRINGS <<< "${AGENTIC_GEN_FORBIDDEN:-}"

fail=0

for profile in "$ROOT"/profiles/*.json; do
  name="$(basename "$profile" .json)"
  bundle="$OUT_DIR/$name"
  echo "=== $name ==="

  if ! python3 "$ROOT/generate.py" --profile "$profile" --out "$bundle"; then
    echo "FAIL: $name: generate.py exited non-zero"
    fail=1
    continue
  fi

  if ! docker compose -f "$bundle/docker-compose.yaml" --env-file "$bundle/.env" config -q; then
    echo "FAIL: $name: docker compose config rejected the bundle"
    fail=1
    continue
  fi

  for needle in ${FORBIDDEN_STRINGS[@]+"${FORBIDDEN_STRINGS[@]}"}; do
    [ -n "$needle" ] || continue
    if grep -rq -- "$needle" "$bundle"; then
      echo "FAIL: $name: forbidden string leaked into output: $needle"
      fail=1
    fi
  done

  for f in "$bundle/docker-compose.yaml" "$bundle/.env"; do
    leftover="$(grep -oE '\$\{[A-Za-z_][A-Za-z0-9_]*\}' "$f" || true)"
    if [ -n "$leftover" ]; then
      echo "FAIL: $name: leftover unresolved placeholder(s) in $(basename "$f"):"
      echo "$leftover"
      fail=1
    fi
  done

  if ! docker compose -f "$bundle/docker-compose.yaml" --env-file "$bundle/.env" config --format json |
    python3 -c '
import json, sys
config = json.load(sys.stdin)
runtimes = {s: set(config["services"][s].get("networks", {}))
            for s in ("hunter-runtime", "remediation-agent-runtime") if s in config["services"]}
errors = [f"{s} is on non-internal network {n}" for s, nets in runtimes.items() for n in sorted(nets)
          if not config["networks"][n].get("internal")]
if len(runtimes) == 2 and set.intersection(*runtimes.values()):
    errors.append(f"the runtimes share {sorted(set.intersection(*runtimes.values()))}")
print("\n".join(errors), file=sys.stderr)
sys.exit(bool(errors))'; then
    echo "FAIL: $name: an agent runtime is not isolated"
    fail=1
  fi

  echo "OK: $name"
done

# Refusals: each of these must exit non-zero and write nothing.
echo "=== refusals ==="
fail_before=$fail
refuse() {
  local label="$1"; shift
  if python3 "$ROOT/generate.py" "$@" --out "$OUT_DIR/refused" >/dev/null 2>&1 || [ -e "$OUT_DIR/refused" ]; then
    echo "FAIL: refusals: accepted $label"
    fail=1
  fi
  rm -rf "$OUT_DIR/refused"
}
printf '{"edition": "developer", "tls_server_nmae": "x"}' > "$OUT_DIR/typo.json"
refuse "an unknown profile key" --profile "$OUT_DIR/typo.json"
refuse "a newline in --image-tag" --edition developer --image-tag "$(printf '1.0\nx: y')"
refuse "a space in --sonarqube-registry" --edition developer --sonarqube-registry "a b"
refuse "an invalid --s3-bucket with --s3-endpoint" --edition developer --storage s3 \
  --s3-endpoint http://minio:9000 --s3-bucket 'Bad$Bucket'
refuse "a port above 65535" --edition developer --db external --db-host db --db-password p --db-port 70000
refuse "an invalid --project-name" --edition developer --project-name "Agentic Dev"
refuse "an IPv6 --tls-server-name" --edition developer --tls-server-name fe80::1
refuse "a --custom-ca-dir outside the bundle" --edition none --tls on --storage s3 --db-host db \
  --db-password p --custom-ca-dir ../escaped
if [[ -e "$OUT_DIR/escaped" ]]; then
  echo "FAIL: refusals: wrote outside the bundle through --custom-ca-dir"
  fail=1
fi
refuse "--storage nfs --edition none without --storage-path" --edition none --storage nfs \
  --nfs-server 10.0.0.5 --nfs-export /export/agentic --db-host db --db-password p
[ "$fail" = "$fail_before" ] && echo "OK: refusals"

# Regeneration: secrets survive, user edits and stale certificates are only overwritten with --force.
echo "=== regeneration ==="
fail_before=$fail
regen="$OUT_DIR/regen"
gen() { python3 "$ROOT/generate.py" --profile "$ROOT/profiles/none-nfs-tls.json" --out "$regen" "$@" >/dev/null 2>&1; }
gen
secret="$(grep '^AGENTIC_SIGNING_SECRET=' "$regen/.env")"
if [ "$(stat -c %a "$regen/.env" 2>/dev/null || stat -f %Lp "$regen/.env")" != "600" ]; then
  echo "FAIL: regeneration: .env is not mode 600"; fail=1
fi
gen
[ "$secret" = "$(grep '^AGENTIC_SIGNING_SECRET=' "$regen/.env")" ] || { echo "FAIL: regeneration: signing secret changed"; fail=1; }
echo "# edited" >> "$regen/docker-compose.yaml"
gen && { echo "FAIL: regeneration: overwrote an edited file without --force"; fail=1; }
gen --force || { echo "FAIL: regeneration: --force did not overwrite an edited file"; fail=1; }
gen --tls-server-name agentic.example.com && { echo "FAIL: regeneration: kept certificates with stale names"; fail=1; }
gen --tls-server-name agentic.example.com --force || { echo "FAIL: regeneration: --force did not reissue certificates"; fail=1; }
gen --tls-server-name agentic.example.com --rotate-secrets
[ "$secret" != "$(grep '^AGENTIC_SIGNING_SECRET=' "$regen/.env")" ] || { echo "FAIL: regeneration: --rotate-secrets kept the secret"; fail=1; }
# The Data Center cluster addresses are the documented .env edit: kept, and not an edit that blocks
# a regeneration that changes other .env keys.
dc="$OUT_DIR/regen-dc"
gen_dc() { python3 "$ROOT/generate.py" --profile "$ROOT/profiles/datacenter-local-tls.json" --out "$dc" "$@" >/dev/null 2>&1; }
gen_dc
sed -i.bak 's|^SONARQUBE_CLUSTER_SUBNET=.*|SONARQUBE_CLUSTER_SUBNET=10.99.0.0/24|' "$dc/.env" && rm -f "$dc/.env.bak"
gen_dc --rotate-secrets || { echo "FAIL: regeneration: an edited cluster subnet blocked regeneration"; fail=1; }
grep -q '^SONARQUBE_CLUSTER_SUBNET=10.99.0.0/24$' "$dc/.env" || { echo "FAIL: regeneration: the edited cluster subnet was not kept"; fail=1; }
# So is a published port, which an override can't change: compose appends override `ports`.
echo "SONARQUBE_PUBLISH_PORT=29000" >> "$dc/.env"
gen_dc --rotate-secrets || { echo "FAIL: regeneration: a published port set in .env blocked regeneration"; fail=1; }
gen_dc --force
grep -q '^SONARQUBE_PUBLISH_PORT=29000$' "$dc/.env" || { echo "FAIL: regeneration: the published port set in .env was not kept"; fail=1; }
echo "EDITED=1" >> "$dc/.env"
gen_dc --rotate-secrets && { echo "FAIL: regeneration: overwrote another .env edit without --force"; fail=1; }
[ "$fail" = "$fail_before" ] && echo "OK: regeneration"

if [ "$fail" -ne 0 ]; then
  echo
  echo "lint.sh: one or more checks failed"
  exit 1
fi

echo
echo "lint.sh: all checks passed"
