# Agentic Docker Compose generator: maintainer notes

Notes for whoever changes this generator. The customer-facing guide is
`README.md`; keep anything internal out of it, and out of the templates under `templates/docs/`,
which end up in every bundle.

The output of this generator is a single flattened `docker-compose.yaml` a customer can run
as-is: no overlays, no `!override`/`!reset`.

`egress-proxy/` and `tls-proxy/` are copied as-is into every bundle, so keep their comments
customer-facing. The `egress-proxy` rules follow the
[Helm chart's](https://github.com/SonarSource/helm-chart-sonarqube): a remediation-only listener on 3129, SonarQube limited to its two
endpoints when it is plain http, `deny !Safe_ports`, no `Via`/`X-Forwarded-For`, and small
`cache_mem`/`max_filedescriptors`. Two deliberate differences from Helm: wildcard domains stay
refused, and the orchestrator rule requires a `jobId`. Compose can't keep hunter-runtime off 3129
the way Helm's NetworkPolicy does, so the SonarQube rules also match the client's name.
`tls-proxy/entrypoint.sh` runs against the vanilla nginx image, so it installs `openssl` itself when it needs to self-sign.

`AGENTIC_SIGNING_SECRET` is deliberately **not** an input. The generator always mints its own
(`secrets.token_hex(32)`) and writes it into the bundle's `.env`: accepting it as a flag would risk
a weak or reused secret ending up in a script or CI log.

## Data Center Edition internals

`--edition datacenter` replaces the single `sonarqube` service with three search nodes
(`sonarqube-search-1/2/3`), two application nodes (`sonarqube-app-1/2`) and an nginx load
balancer (`sonarqube-lb/nginx.conf`) that takes over the `sonarqube` service name, so `tls-proxy`
and the agentic services are wired exactly as for a single node, and `--tls on|off` behaves the
same. The layout:

- the nodes talk over an internal `cluster` network; the application nodes discover each other
  through Hazelcast's DNS joiner (`SONAR_CLUSTER_KUBERNETES=true`) on a shared
  `sonarqube-cluster` alias, and pin a static address (`SONARQUBE_APP_1_IP`/`_2_IP` in `.env`,
  inside `SONARQUBE_CLUSTER_SUBNET`) so `SONAR_CLUSTER_NODE_HOST` is known up front;
- the application nodes share a generated `SONARQUBE_JWT_SECRET` (in `.env`, minted like the
  signing secret), and both mount the agentic storage and signing key;
- both application nodes use `restart: unless-stopped` to recover from the schema-creation race
  on a fresh database.

Its images come from `default-images.json`'s `sonarqube` entry (`-datacenter-app`/
`-datacenter-search` suffixes) and `sonarqube-lb`; `--sonarqube-registry`/`--sonarqube-tag`
override the former. The bundle's own `README.md` covers resources (~18 GB of `mem_limit`s,
`vm.max_map_count`), licensing and the cluster-subnet override.

By default the bundle pulls the official, multi-arch (amd64 and arm64) Docker Hub images
`sonarqube:<tag>-datacenter-app` and `sonarqube:<tag>-datacenter-search`; pick another published
version with `--sonarqube-tag`.

**Unreleased amd64-only builds:** if you point `--sonarqube-registry`/`--sonarqube-tag` at an
image published only for `linux/amd64`, note that under amd64
emulation on an arm64 host (qemu or Rosetta, e.g. Rancher Desktop on Apple Silicon) Elasticsearch 9
cannot probe seccomp and every search node exits with "seccomp unavailable: CONFIG_SECCOMP not
compiled into kernel" — ES always installs its syscall filter, so there is no setting to skip it.
The published multi-arch images don't hit this. To test an unreleased build on such a host, build
native images from a Data Center zip with the
[docker-sonarqube `commercial-editions/datacenter`](https://github.com/SonarSource/docker-sonarqube/tree/master/commercial-editions/datacenter)
Dockerfiles (swapping the download/GPG step for a `COPY` of the zip), tag them
`<registry>/sonarqube:<tag>-datacenter-app|search`, and pass
`--sonarqube-registry <registry> --sonarqube-tag <tag>`.

## TLS internals

`--tls` covers the hops *into* the bundle. For a bundled edition, `tls-proxy` fronts SonarQube only
and self-signs into the `tls_certs` volume on first start (`tls-proxy/entrypoint.sh`,
`TLS_TEMPLATE=sonarqube`).

`--edition none --tls on` works differently, because the containers' calls to a zip SonarQube
would otherwise be the one plain hop:

- **Bundle CA** (`write_bundle_certs`): the generator shells out to `openssl` (OpenSSL 3 or
  LibreSSL; validation refuses the mode when it's missing, except for `--out -`) in a temp dir,
  issues a CA and two leaf certificates, and throws the CA key away. Output: `tls/ca.crt`,
  `tls/agentic-proxy/tls.{crt,key}` and `sonarqube-tls-proxy/tls/tls.{crt,key}`, leaves written as
  full chains, keys `0600`. The extensions are what Python 3.13's strict verification needs: CA with
  critical `basicConstraints` and `keyUsage keyCertSign`; leaves with SAN, `serverAuth`, SKI and AKI.
  When all five files exist, a regeneration keeps them, so customers import the CA into SonarQube
  once.
- **Trust inside the bundle**: `validate_and_normalize` defaults `--custom-ca-dir` to `./custom-ca`,
  and the CA is copied there as `agentic-bundle-ca.crt`, so the existing `/custom-ca` import paths
  (orchestrator, runtimes, `truststore-init` for Vortex) pick it up with no new mount. A nested file
  mount into the read-only `/custom-ca` bind isn't possible, which is why it goes through the
  directory. With an absolute `--custom-ca-dir` the generator can't write there and prints a note.
- **`agentic-proxy`** mounts `tls/agentic-proxy` read-only with `TLS_SELF_SIGN=0`; it no longer uses
  the `tls_certs` volume, which isn't declared for edition none. Without Vortex in `--components`
  it gets `TLS_VORTEX=0` and no 8444 port: the entrypoint drops the lines between
  `# @@VORTEX_BEGIN@@` and `# @@VORTEX_END@@` in `nginx.agentic.conf.template`, since nginx fails
  to start on an upstream host it can't resolve. Keep those markers on lines of their own.
- **The kit** (`uses_kit`: edition none, tls on, scheme `http`): `sonarqube-tls-proxy/` is a
  standalone compose project customers run on their SonarQube machine, the same `tls-proxy` image
  with `TLS_TEMPLATE=kit` (`tls-proxy/nginx.kit.conf.template`, an 8443 listener and no http
  redirect), plus a bare `nginx/sonarqube-tls.conf` for customers with their own nginx. Every
  SonarQube URL in the bundle becomes `https://<--sonarqube-external-host>:9443`
  (`SONARQUBE_KIT_PORT`); egress-proxy's SQS host and port follow because `build_egress_proxy`
  parses that URL. Users and scanners keep the plain port: the kit serves only the containers. With
  scheme `https` the kit is still emitted, but nothing points at it.

The hops out of the bundle are configured separately:

- **SonarQube (`--edition none`)**: `--sonarqube-external-scheme https` switches every URL the
  containers use for your SonarQube to https. The remediation runtime reaches it through
  `egress-proxy` as a CONNECT tunnel, so Squid never sees the plaintext, and can hold it only to
  SonarQube's host and port, not to the two endpoints it enforces over plain http.
- **Database (`--db external`)**: always `sslmode=verify-full`, on SonarQube's `SONAR_JDBC_URL` (or
  the `sonar.jdbc.url` in `ZIP-INSTRUCTIONS.md`) and on the orchestrator's `SPRING_DATASOURCE_URL`,
  which replaces its built-in datasource URL. The database must serve TLS with a certificate valid
  for `--db-host`. `sslfactory=org.postgresql.ssl.DefaultJavaSSLFactory` makes pgjdbc validate it
  against the JVM truststore, i.e. public CAs; the bundled Postgres stays plain on the internal
  `data` network.
- **Private CAs**: `--custom-ca-dir` mounts the directory at `/custom-ca` in the orchestrator and
  both runtimes, whose entrypoints import it. Vortex can't import at startup, so a one-shot
  `truststore-init` (`eclipse-temurin`, from `default-images.json`) builds the JDK's `cacerts` plus
  those certs into the `custom_truststore` volume, and Vortex points `javax.net.ssl.trustStore` at
  it through `JAVA_TOOL_OPTIONS`. Without it, only
  public CAs are trusted. The runtimes' Python 3.13 verifies strictly: a CA certificate without a
  `keyUsage` extension (`keyCertSign`) is rejected there even though the JVMs accept it.

## Default image registry/tags

`default-images.json` is the single canonical place holding the default registry, image name, and
tag for every image this generator can emit: the agentic components (`agent-orchestrator`,
`hunter-agent`, `remediation-agent`, `vortex`), `sonarqube`, and the third-party images used by
supporting services (`postgres`; the `alpine`-based `storage-init`/`storage-probe` one-shot
helpers; the `eclipse-temurin`-based `truststore-init`; and the `egress-proxy`/`tls-proxy` base
images, which also back `agentic-proxy`). Every third-party image is pinned by `digest` as well as
tag, so a re-pushed tag can't change a customer's bundle; bump both together. `sonarqube` and the
agentic components are ours and pinned by tag only (the `sonarqube` tag gets an edition suffix, so
one digest can't cover it). `image_ref()` and `build_sonarqube()` in `generate.py` read from it; nothing else
in this generator hardcodes an image coordinate.

Bump it with a small, direct edit to the file, referencing the ticket in the commit. Renovate
proposes digest bumps for the third-party images.

All defaults are public Docker Hub coordinates: the official `sonarqube` image
(`sonarqube:<tag>-<edition>`, e.g. `sonarqube:2026.5.0-datacenter-app`), and for the four agentic
components `sonarsource/sonarqube-agent-orchestrator`, `sonarqube-hunter-agent`,
`sonarqube-remediation-agent` and `sonar-vortex`, tagged with the SonarQube Server release they
ship with (e.g. `2026.5.0`). `--image-registry`/`--image-tag`
apply uniformly to the four agentic components only (`AGENTIC_IMAGES` in `generate.py`); the
third-party images (`postgres`, `storage-init`/`storage-probe`, `truststore-init`, `egress-proxy`,
`tls-proxy`, `sonarqube-lb`) always
use their `default-images.json` coordinates, since a customer's agentic tag means nothing for
them. `--sonarqube-registry`/`--sonarqube-tag` override `sonarqube` the same way. There is no per-component CLI override, only
per-component *defaults* — changing an image's `name` (or a pinned `digest`) means editing
`default-images.json` directly.

## Supported combinations

All four editions × all four storage backends × both DB modes × both TLS states × all five legal
component sets (`hunter`; `vortex`; `hunter,vortex`; `remediation,vortex`; `hunter,remediation,vortex`)
are supported, subject to the two `--edition none` constraints above. `profiles/*.json` exercises a
representative slice of this matrix and is what CI lints against.

## Validation

The generator fails closed (`exit 1`, no files written) if:

- a storage/DB requirement is missing for the chosen mode (e.g. `--storage nfs` without
  `--nfs-server`/`--nfs-export`);
- `--edition none` is combined with `--storage local`;
- `--db external` is missing `--db-host` or `--db-password`;
- `--sonarqube-external-scheme https` is set without `--edition none`;
- `--sandbox` isn't a valid Docker runtime name (`SANDBOX_RUNTIME_RE`; whether it is registered
  is only known to the daemon, at `docker compose up`);
- the rendered output still contains an unresolved `${...}` placeholder, or any of the
  comma-separated strings in the `AGENTIC_GEN_FORBIDDEN` environment variable. CI sets it to the
  build-time and registry references that must never reach a bundle; `tests/lint.sh` runs the same
  scan.

## Testing

```bash
tests/lint.sh
```

Generates every profile under `profiles/`, validates each with
`docker compose config -q`, and re-runs the forbidden-string/leftover-placeholder scan against the
generated files. Needs Docker and Python 3; no images are pulled and no secrets are required.

```bash
tests/egress-proxy.sh
```

Probes the egress-proxy allowlist on the pinned Squid image (see `README.md`). Extend its matrix
whenever `egress-proxy/` changes.

```bash
python3 -m unittest discover -s tests -v
```

Unit tests for input validation and regeneration. Together with the two scripts above, they run
on every PR touching this directory (`.github/workflows/agentic-compose-generator.yml`).
`tests/e2e.sh` needs a registered gVisor runtime and pulls every image, so it isn't part of the PR
checks; run it locally before changing the templates or `default-images.json`.

```bash
python3 generate.py --print-inputs-schema
```

Prints the JSON Schema a web form (or any other caller) can build inputs against — property names
match the flag-derived attribute names used in `profiles/*.json`.

## Programmatic use

A caller (e.g. a configurator form) should:

1. Render a form from `--print-inputs-schema`.
2. POST the collected values as a JSON profile matching that schema.
3. Invoke `generate.py --profile <that JSON> --out <bundle dir>` server-side.
4. Zip and serve the bundle directory to the customer, along with the `README.md` and (for
   `--edition none`) `ZIP-INSTRUCTIONS.md` this tool writes into it.

## What's not here yet

- `AZURE`/`GCS` storage providers (both fully supported product-side; not yet wired into this
  generator).
