#!/usr/bin/env bash
# Runs egress-proxy/ as shipped, on the pinned Squid image, and probes its allowlist: stand-ins for
# SonarQube, the orchestrator and an LLM host answer every request they receive, and two clients
# named like the runtimes (Squid tells them apart by reverse DNS) try each rule. A 403 is Squid's
# denial; anything the stand-ins answer means the proxy let the request through.
#
# Needs only Docker and the egress-proxy image from default-images.json. The image has no curl, so
# the stand-ins and clients are Perl one-liners on that same image.
#
# Usage: tests/egress-proxy.sh
set -euo pipefail

cd "$(dirname "$0")/.."
image=$(python3 -c "import json; i = json.load(open('default-images.json'))['egress-proxy']; print(i['name'] + '@' + i['digest'])")
docker image inspect "$image" >/dev/null 2>&1 || docker pull -q "$image" >/dev/null
net=egress-proxy-test-$$
containers=(egress-proxy sonarqube orchestrator llm storage remediation-agent-runtime hunter-runtime)

cleanup() {
  docker rm -f "${containers[@]/#/$net-}" >/dev/null 2>&1 || true
  docker network rm "$net" >/dev/null 2>&1 || true
}
trap cleanup EXIT
docker network create "$net" >/dev/null

# Answers 204, or 222 when the request reveals the proxy or the client (Via / X-Forwarded-For).
serve() {
  local name=$1 port=$2
  docker run -d --name "$net-$name" --network "$net" --network-alias "$name" --entrypoint perl "$image" \
    -MIO::Socket::INET -e '
      my $s = IO::Socket::INET->new(LocalPort => $ARGV[0], Listen => 16, ReuseAddr => 1) or die $!;
      while (my $c = $s->accept) {
        my $revealed = 0;
        while (<$c>) { last if /^\r?\n$/; $revealed = 1 if /^(via|x-forwarded-for):/i }
        print $c ($revealed ? "HTTP/1.1 222 Revealed" : "HTTP/1.1 204 No Content"), "\r\nConnection: close\r\n\r\n";
        close $c;
      }' "$port" >/dev/null
}

# The container name, not an alias, is what Docker's reverse DNS answers with, and what the
# proxy's srcdom_regex rules match.
client() {
  local name=$1
  docker run -d --name "$name" --network "$net" --entrypoint sleep "$image" infinity >/dev/null
}

proxy() {
  local sqs_scheme=$1
  docker rm -f "$net-egress-proxy" >/dev/null 2>&1 || true
  # The same user, read-only root and dropped capabilities as the bundle's egress-proxy service.
  # "metadata" stands in for an allowlisted name that resolves into the link-local range.
  docker run -d --name "$net-egress-proxy" --network "$net" --network-alias egress-proxy \
    --add-host metadata:169.254.169.254 \
    --user 13:13 --read-only --tmpfs /tmp --cap-drop ALL --security-opt no-new-privileges:true \
    -e AGENTIC_LLM_ALLOWED_DOMAINS="llm,$net-llm.$net,metadata" \
    -e AGENTIC_STORAGE_ALLOWED_DOMAIN=storage -e AGENTIC_STORAGE_ALLOWED_PORT=9002 \
    -e AGENTIC_SQS_PROXY_HOST=sonarqube -e AGENTIC_SQS_PROXY_PORT=9000 -e AGENTIC_SQS_PROXY_SCHEME="$sqs_scheme" \
    -e AGENTIC_ORCHESTRATOR_PROXY_HOST=orchestrator -e AGENTIC_ORCHESTRATOR_PROXY_PORT=8080 \
    -v "$PWD/egress-proxy/squid.conf.template:/etc/squid/squid.conf.template:ro" \
    -v "$PWD/egress-proxy/entrypoint.sh:/usr/local/bin/render-and-run.sh:ro" \
    --entrypoint /bin/sh "$image" /usr/local/bin/render-and-run.sh >/dev/null
  for _ in $(seq 30); do
    [[ "$(status hunter-runtime 3128 "GET http://llm/ HTTP/1.1")" != 000 ]] && return
    sleep 1
  done
  docker logs "$net-egress-proxy" >&2
  echo "error: egress-proxy did not start" >&2
  exit 1
}

# Prints the status code the proxy (or, through it, a stand-in) answers the request line with.
status() {
  local client=$1 port=$2 request=$3
  docker exec "$net-$client" perl -MIO::Socket::INET -e '
    my $s = IO::Socket::INET->new(PeerAddr => "egress-proxy", PeerPort => $ARGV[0], Timeout => 5)
      or do { print "000"; exit };
    print $s "$ARGV[1]\r\nHost: x\r\n\r\n";
    my ($code) = (<$s> // "") =~ m{^HTTP/\S+ (\d+)};
    print $code // "000";' "$port" "$request"
}

fail=0
expect() {
  local want=$1 client=$2 port=$3 request=$4 got
  got=$(status "$client" "$port" "$request")
  if [[ "$got" = "$want" ]]; then
    echo "ok   $got  $client :$port $request"
  else
    echo "FAIL $got (want $want)  $client :$port $request"
    fail=1
  fi
}

serve sonarqube 9000
serve orchestrator 8080
serve llm 80
serve storage 9002
client "$net-remediation-agent-runtime"
client "$net-hunter-runtime"
# Reverse DNS answers "<container>.<network>", so prefixing the names keeps them matching the
# unanchored srcdom_regex, as Compose's project prefix does.
r=remediation-agent-runtime h=hunter-runtime
connect_sqs="CONNECT sonarqube:9000 HTTP/1.1"
llm_ip=$(docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' "$net-llm")

echo "=== SonarQube over http"
proxy http
expect 204 $r 3129 "GET http://sonarqube:9000/api/rules/show?key=java:S1 HTTP/1.1"
expect 204 $r 3129 "GET http://sonarqube:9000/api/v2/a3s/private/analyses HTTP/1.1"
expect 204 $r 3129 "GET http://sonarqube:9000/api/v2/a3s/private/analyses/abc HTTP/1.1"
expect 204 $r 3129 "GET http://sonarqube:9000/sonarqube/api/rules/show HTTP/1.1"
expect 403 $r 3129 "GET http://sonarqube:9000/api/system/info HTTP/1.1"
expect 403 $r 3129 "GET http://sonarqube:9000/api/x?y=/rules/show HTTP/1.1"
expect 403 $r 3129 "$connect_sqs"
expect 403 $r 3128 "GET http://sonarqube:9000/api/rules/show HTTP/1.1"
expect 403 $h 3129 "GET http://sonarqube:9000/api/rules/show HTTP/1.1"
expect 403 $h 3128 "GET http://sonarqube:9000/api/rules/show HTTP/1.1"
echo "=== orchestrator: locator renewal only"
expect 204 $h 3128 "GET http://orchestrator:8080/artifact-locators?jobId=j1 HTTP/1.1"
expect 204 $r 3129 "GET http://orchestrator:8080/artifact-locators?jobId=j1 HTTP/1.1"
expect 403 $h 3128 "GET http://orchestrator:8080/artifact-locators HTTP/1.1"
expect 403 $h 3128 "GET http://orchestrator:8080/actuator/health HTTP/1.1"
echo "=== allowlisted host: allowed ports only, proxy not revealed"
expect 204 $h 3128 "GET http://llm/ HTTP/1.1"
expect 204 $r 3129 "GET http://llm/ HTTP/1.1"
expect 403 $h 3128 "GET http://llm:8081/ HTTP/1.1"
expect 403 $h 3128 "CONNECT llm:8080 HTTP/1.1"
expect 403 $h 3128 "GET http://example.com/ HTTP/1.1"
# "$net-llm.$net" is also allowlisted: it is what reverse DNS answers for llm's address. A request
# by bare IP must still be denied, as Squid would otherwise look that name up, and a reverse lookup
# of an address the client picks is a DNS channel out of the sandbox.
expect 403 $h 3128 "GET http://$llm_ip/ HTTP/1.1"
# Safe_ports also holds SonarQube's, the orchestrator's and the storage port, but an LLM host is
# reachable on 80/443 only.
expect 403 $h 3128 "GET http://llm:8080/ HTTP/1.1"
expect 403 $h 3128 "GET http://llm:9002/ HTTP/1.1"
echo "=== storage host: its own port only"
expect 204 $h 3128 "GET http://storage:9002/bucket/key HTTP/1.1"
expect 204 $r 3129 "GET http://storage:9002/bucket/key HTTP/1.1"
expect 403 $h 3128 "GET http://storage/bucket/key HTTP/1.1"
expect 403 $h 3128 "GET http://storage:8080/bucket/key HTTP/1.1"
# An https endpoint is a tunnel to its own port, which needn't be 443.
expect 200 $h 3128 "CONNECT storage:9002 HTTP/1.1"
expect 200 $r 3129 "CONNECT storage:9002 HTTP/1.1"
expect 403 $h 3128 "CONNECT storage:8080 HTTP/1.1"
echo "=== allowlisted name resolving to link-local: denied"
expect 403 $h 3128 "GET http://metadata/latest/meta-data/ HTTP/1.1"
expect 403 $h 3128 "CONNECT metadata:443 HTTP/1.1"

echo "=== SonarQube over https"
proxy https
expect 200 $r 3129 "$connect_sqs"
expect 403 $r 3128 "$connect_sqs"
expect 403 $h 3129 "$connect_sqs"

if [[ "$fail" -ne 0 ]]; then
  docker logs --tail 30 "$net-egress-proxy" 2>&1 || true
  echo
  echo "egress-proxy.sh: one or more checks failed"
  exit 1
fi
echo
echo "egress-proxy.sh: all checks passed"
