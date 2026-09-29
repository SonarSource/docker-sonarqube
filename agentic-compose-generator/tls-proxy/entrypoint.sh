#!/bin/sh
# Runs unmodified against the vanilla nginx:1.27-alpine image (no custom build), so it installs the
# one package that image is missing itself, lazily, only on the path that actually needs it.
#
# Ensures a TLS keypair exists, renders it plus the upstream into nginx.conf, then hands off to the
# base image's own entrypoint. Three shapes, chosen by TLS_TEMPLATE: the default one fronts SonarQube
# (tls-proxy), `agentic` fronts Agent Orchestrator and Vortex under `--edition none`
# (agentic-proxy), and `kit` fronts the customer's own SonarQube from the standalone
# sonarqube-tls-proxy kit.
set -eu

TARGET=/etc/nginx/nginx.conf
CERT_DIR=/tls

TEMPLATE_NAME="${TLS_TEMPLATE:-sonarqube}"
case "$TEMPLATE_NAME" in
  sonarqube) TEMPLATE=/etc/nginx/nginx.conf.template ;;
  agentic)   TEMPLATE=/etc/nginx/nginx.agentic.conf.template ;;
  kit)       TEMPLATE=/etc/nginx/nginx.kit.conf.template ;;
  *) echo "tls-proxy: unknown TLS_TEMPLATE '$TEMPLATE_NAME' (sonarqube|agentic|kit)" >&2; exit 1 ;;
esac

# Filenames within /tls, not paths: tls-proxy and agentic-proxy would otherwise collide if they
# ever shared the volume.
CERT_FILE="${TLS_CERT_FILE:-tls.crt}"
KEY_FILE="${TLS_KEY_FILE:-tls.key}"
CERT="$CERT_DIR/$CERT_FILE"
KEY="$CERT_DIR/$KEY_FILE"

UPSTREAM_HOST="${TLS_UPSTREAM_HOST:-sonarqube}"
UPSTREAM_PORT="${TLS_UPSTREAM_PORT:-9000}"
SERVER_NAME="${TLS_SERVER_NAME:-localhost}"
HTTPS_PUBLIC_PORT="${TLS_HTTPS_PUBLIC_PORT:-9443}"
# 0 turns off self-signing: the certificate must already be there or startup fails. Set by
# agentic-proxy and the sonarqube-tls-proxy kit, whose certificates the generator signs with the
# bundle's CA: a self-signed one there would fail every handshake instead of failing startup.
SELF_SIGN="${TLS_SELF_SIGN:-1}"
# 0 drops Vortex's server block from the agentic template, for bundles deployed without Vortex.
VORTEX="${TLS_VORTEX:-1}"

# Same strict validation ../egress-proxy/entrypoint.sh applies to its own substitutions: every value
# below is fed to awk as replacement text, so an unvalidated one (a mistyped TLS_SERVER_NAME, say)
# would corrupt nginx.conf and take the whole front door down rather than fail on one setting.
for pair in "TLS_UPSTREAM_HOST=$UPSTREAM_HOST" "TLS_SERVER_NAME=$SERVER_NAME" \
            "TLS_CERT_FILE=$CERT_FILE" "TLS_KEY_FILE=$KEY_FILE"; do
  name="${pair%%=*}"
  value="${pair#*=}"
  case "$value" in
    ""|*[!A-Za-z0-9._-]*)
      echo "tls-proxy: refusing malformed $name '$value'" >&2
      exit 1
      ;;
  esac
done
for pair in "TLS_UPSTREAM_PORT=$UPSTREAM_PORT" "TLS_HTTPS_PUBLIC_PORT=$HTTPS_PUBLIC_PORT"; do
  name="${pair%%=*}"
  value="${pair#*=}"
  case "$value" in
    ""|*[!0-9]*)
      echo "tls-proxy: refusing malformed $name '$value'" >&2
      exit 1
      ;;
  esac
done

# Half a keypair means someone dropped in their own cert and forgot the key (or vice versa).
# Generating the missing half would silently serve a self-signed cert instead of theirs.
if [ -f "$CERT" ] && [ ! -f "$KEY" ]; then
  echo "tls-proxy: $CERT exists but $KEY does not — supply both, or neither to self-sign" >&2
  exit 1
fi
if [ -f "$KEY" ] && [ ! -f "$CERT" ]; then
  echo "tls-proxy: $KEY exists but $CERT does not — supply both, or neither to self-sign" >&2
  exit 1
fi

if [ -f "$CERT" ]; then
  echo "tls-proxy: using the certificate already in $CERT_DIR"
elif [ "$SELF_SIGN" != "1" ]; then
  echo "tls-proxy: $CERT is missing and TLS_SELF_SIGN=$SELF_SIGN — generate it first" >&2
  exit 1
else
  # The vanilla nginx:1.27-alpine image ships libssl but not the openssl CLI. Installed here,
  # once, only when self-signing is actually needed — the "customer supplies their own cert" path
  # never touches the package manager or the network.
  command -v openssl >/dev/null 2>&1 || apk add --no-cache openssl
  # localhost and the loopback IPs are always in the SAN: the published port is reached as
  # https://localhost:<port> regardless of what TLS_SERVER_NAME is set to.
  san="DNS:localhost,IP:127.0.0.1,IP:0:0:0:0:0:0:0:1"
  [ "$SERVER_NAME" = "localhost" ] || san="DNS:$SERVER_NAME,$san"
  # 825 days: the longest lifetime Safari and Chrome still accept for a leaf certificate.
  openssl req -x509 -newkey rsa:2048 -nodes -days 825 -sha256 \
    -subj "/CN=$SERVER_NAME" -addext "subjectAltName=$san" \
    -keyout "$KEY" -out "$CERT" >/dev/null 2>&1
  chmod 0644 "$CERT"
  chmod 0600 "$KEY"
  echo "tls-proxy: generated a self-signed certificate for $san in $CERT_DIR — kept across restarts," \
    "so trusting it once is enough. Replace $CERT_FILE/$KEY_FILE there to use your own."
fi

# :443 is the scheme default, so a redirect must not spell it out or every URL grows a stray port.
if [ "$HTTPS_PUBLIC_PORT" = "443" ]; then
  redirect_port=""
else
  redirect_port=":$HTTPS_PUBLIC_PORT"
fi

awk -v upstream="$UPSTREAM_HOST:$UPSTREAM_PORT" -v server_name="$SERVER_NAME" \
    -v redirect_port="$redirect_port" -v cert_file="$CERT_FILE" -v key_file="$KEY_FILE" \
    -v vortex="$VORTEX" '
  /^[[:space:]]*# @@VORTEX_BEGIN@@$/ { skip = (vortex == "0"); next }
  /^[[:space:]]*# @@VORTEX_END@@$/ { skip = 0; next }
  skip { next }
  { gsub(/@@UPSTREAM@@/, upstream)
    gsub(/@@SERVER_NAME@@/, server_name)
    gsub(/@@REDIRECT_PORT@@/, redirect_port)
    gsub(/@@CERT_FILE@@/, cert_file)
    gsub(/@@KEY_FILE@@/, key_file)
    print }' "$TEMPLATE" > "$TARGET"

if [ "$TEMPLATE_NAME" = "agentic" ]; then
  if [ "$VORTEX" = "0" ]; then
    echo "tls-proxy: terminating TLS for $SERVER_NAME, forwarding to orchestrator:8080"
  else
    echo "tls-proxy: terminating TLS for $SERVER_NAME, forwarding to orchestrator:8080 and vortex:8080"
  fi
else
  echo "tls-proxy: terminating TLS for $SERVER_NAME, forwarding to http://$UPSTREAM_HOST:$UPSTREAM_PORT"
fi

exec /docker-entrypoint.sh "$@"
