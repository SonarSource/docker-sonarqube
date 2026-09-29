#!/bin/sh
# Renders the egress allowlist into squid.conf, then execs Squid on it in the foreground. Runs as
# the image's proxy user on a read-only root, so the config goes to the /tmp tmpfs; the base image's
# own entrypoint needs root to set up its log tails and cache dirs, and neither is used here.
set -eu

TEMPLATE=/etc/squid/squid.conf.template
TARGET=/tmp/squid.conf
LLM_DOMAINS="${AGENTIC_LLM_ALLOWED_DOMAINS:-}"
STORAGE_DOMAIN="${AGENTIC_STORAGE_ALLOWED_DOMAIN:-}"
SQS_HOST="${AGENTIC_SQS_PROXY_HOST:-sonarqube}"
SQS_PORT="${AGENTIC_SQS_PROXY_PORT:-9000}"
SQS_SCHEME="${AGENTIC_SQS_PROXY_SCHEME:-http}"
STORAGE_PORT="${AGENTIC_STORAGE_ALLOWED_PORT:-}"
ORCHESTRATOR_HOST="${AGENTIC_ORCHESTRATOR_PROXY_HOST:-orchestrator}"
ORCHESTRATOR_PORT="${AGENTIC_ORCHESTRATOR_PROXY_PORT:-8080}"

if [ -z "$LLM_DOMAINS" ]; then
  echo "egress-proxy: AGENTIC_LLM_ALLOWED_DOMAINS is empty — every outbound request would be denied," \
    "which surfaces as an unexplained LLM failure inside the agent. Set it in .env." >&2
  exit 1
fi

# Same charset as the domain check below, plus digits-only for the port — an unvalidated value
# here would otherwise reach awk's gsub as the replacement text, breaking squid.conf and taking
# down ALL egress, not just this leg.
case "$SQS_HOST" in
  *[!A-Za-z0-9.-]*)
    echo "egress-proxy: refusing malformed AGENTIC_SQS_PROXY_HOST '$SQS_HOST'" >&2
    exit 1
    ;;
  *) ;;
esac
case "$SQS_PORT" in
  *[!0-9]*|"")
    echo "egress-proxy: refusing malformed AGENTIC_SQS_PROXY_PORT '$SQS_PORT'" >&2
    exit 1
    ;;
  *) ;;
esac
case "$SQS_SCHEME" in
  http|https) ;;
  *)
    echo "egress-proxy: refusing AGENTIC_SQS_PROXY_SCHEME '$SQS_SCHEME' (expected http or https)" >&2
    exit 1
    ;;
esac
# Optional, like the storage domain: blank when the stack has no S3 endpoint.
case "$STORAGE_PORT" in
  *[!0-9]*)
    echo "egress-proxy: refusing malformed AGENTIC_STORAGE_ALLOWED_PORT '$STORAGE_PORT'" >&2
    exit 1
    ;;
  *) ;;
esac
# Same validation for the orchestrator leg, and for the same reason: an unvalidated value reaches
# awk's gsub as replacement text and would break squid.conf, taking down ALL egress.
case "$ORCHESTRATOR_HOST" in
  *[!A-Za-z0-9.-]*)
    echo "egress-proxy: refusing malformed AGENTIC_ORCHESTRATOR_PROXY_HOST '$ORCHESTRATOR_HOST'" >&2
    exit 1
    ;;
  *) ;;
esac
case "$ORCHESTRATOR_PORT" in
  *[!0-9]*|"")
    echo "egress-proxy: refusing malformed AGENTIC_ORCHESTRATOR_PROXY_PORT '$ORCHESTRATOR_PORT'" >&2
    exit 1
    ;;
  *) ;;
esac

# Storage is optional (blank while the stack still uses the local volume) but comes as a pair: its
# rules below are scoped to the storage port, so a domain without one could never be reached.
if [ -n "$STORAGE_DOMAIN" ] && [ -z "$STORAGE_PORT" ]; then
  echo "egress-proxy: AGENTIC_STORAGE_ALLOWED_DOMAIN is set but AGENTIC_STORAGE_ALLOWED_PORT is empty" >&2
  exit 1
fi

# One `acl <name> dstdomain -n <host>` line per entry — repeating the ACL name unions the values.
# A leading dot makes Squid's dstdomain match every subdomain, e.g. `.amazonaws.com` would allow any
# bucket on AWS — refuse it, since the whole point is an exact-host allowlist, not a wildcard.
# -n, here and on every other dstdomain ACL: without it, a request by bare IP makes Squid look up
# the address's name, and a reverse lookup of an address the client picks is a DNS channel out.
domain_acls() {
  acl=$1
  domains=$2
  for domain in $(printf '%s' "$domains" | tr ',' ' '); do
    [ -n "$domain" ] || continue
    case "$domain" in
      .*)
        echo "egress-proxy: refusing wildcard domain '$domain' — a leading '.' matches every subdomain" >&2
        exit 1
        ;;
      *[!A-Za-z0-9.-]*)
        echo "egress-proxy: refusing malformed domain '$domain' (from AGENTIC_LLM_ALLOWED_DOMAINS or AGENTIC_STORAGE_ALLOWED_DOMAIN)" >&2
        exit 1
        ;;
      *) ;;
    esac
    printf 'acl %s dstdomain -n %s\n' "$acl" "$domain"
  done
}
acl_lines=$(domain_acls allowed_host "$LLM_DOMAINS")

# The storage host gets its own ACL so each allowlist is reachable on its own ports only: the LLM
# hosts on 80/443, the storage host on the port its endpoint names. Without a storage domain, no
# rule renders at all — a valueless ACL would make Squid warn on every start. The tunnel rule takes
# no SSL_ports: an https endpoint may sit on any port (MinIO's 9000, say), and storage_port alone
# already holds it to that one; the rule precedes `deny CONNECT !SSL_ports`, so it still applies.
storage_acl_lines="# No storage host: the stack keeps job artifacts on a local volume."
storage_tunnel_rule=""
storage_http_rule=""
if [ -n "$STORAGE_DOMAIN" ]; then
  storage_acl_lines="$(domain_acls storage_host "$STORAGE_DOMAIN")
acl storage_port port ${STORAGE_PORT}"
  storage_tunnel_rule="http_access allow CONNECT storage_host storage_port !link_local"
  storage_http_rule="http_access allow storage_host storage_port !link_local"
fi

# One line per distinct port: the same port twice (SonarQube on 443, say) would only be noise.
safe_port_lines=""
for port in $(printf '%s\n' 80 443 "$SQS_PORT" "$ORCHESTRATOR_PORT" ${STORAGE_PORT:+"$STORAGE_PORT"} | sort -un); do
  safe_port_lines="${safe_port_lines}acl Safe_ports port ${port}
"
done

# An https SonarQube is a CONNECT tunnel, so Squid can't see the path and can hold it only to its
# host and port. A plain-http one gets no tunnel rule at all: its path-restricted rule is the only
# way in.
if [ "$SQS_SCHEME" = https ]; then
  sqs_tunnel_rule="http_access allow CONNECT remediation_listener remediation_client sqs_host sqs_port
"
else
  sqs_tunnel_rule="# No CONNECT rule for SonarQube: it is plain http, reached only via sqs_endpoints below.
"
fi

awk -v repl="$acl_lines" -v safe_ports="$safe_port_lines" -v sqs_tunnel="$sqs_tunnel_rule" \
  -v storage_acls="$storage_acl_lines" -v storage_tunnel="$storage_tunnel_rule" -v storage_http="$storage_http_rule" \
  -v sqs_host="$SQS_HOST" -v sqs_port="$SQS_PORT" \
  -v orch_host="$ORCHESTRATOR_HOST" -v orch_port="$ORCHESTRATOR_PORT" '
  { if ($0 == "@@LLM_ACL_LINES@@") { print repl; next }
    if ($0 == "@@STORAGE_ACL_LINES@@") { print storage_acls; next }
    if ($0 == "@@STORAGE_TUNNEL_RULE@@") { if (storage_tunnel != "") print storage_tunnel; next }
    if ($0 == "@@STORAGE_HTTP_RULE@@") { if (storage_http != "") print storage_http; next }
    if ($0 == "@@SAFE_PORT_LINES@@") { printf "%s", safe_ports; next }
    if ($0 == "@@SQS_TUNNEL_RULE@@") { printf "%s", sqs_tunnel; next }
    gsub(/@@SQS_HOST@@/, sqs_host); gsub(/@@SQS_PORT@@/, sqs_port);
    gsub(/@@ORCHESTRATOR_HOST@@/, orch_host); gsub(/@@ORCHESTRATOR_PORT@@/, orch_port); print }' \
  "$TEMPLATE" > "$TARGET"

echo "egress-proxy: allowlisting $(printf '%s' "$LLM_DOMAINS" | tr ',' ' ') on 80/443${STORAGE_DOMAIN:+, $STORAGE_DOMAIN on $STORAGE_PORT}"

exec squid -N -f "$TARGET" "$@"
