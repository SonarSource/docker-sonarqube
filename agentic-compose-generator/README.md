# SonarQube agentic pack: Docker Compose bundle generator

`generate.py` builds a ready-to-run Docker Compose bundle for the SonarQube agentic pack (Agent
Orchestrator, Hunter Agent, Remediation Agent and Vortex) from the options you choose. The bundle
is a single `docker-compose.yaml` plus an `.env` and a few support files: you start it with
`docker compose up -d` and never need to edit it by hand.

The bundle can run in front of:

- a new SonarQube Server that it runs for you: Developer, Enterprise or Data Center Edition;
- your existing SonarQube install (`--edition none`). In that case it only runs the agentic
  services, and writes a `ZIP-INSTRUCTIONS.md` listing the changes to make in your `sonar.properties`.

## Prerequisites

- **SonarQube Server 2026.5 or later.** It is the first release that ships the agentic pack; this
  applies both to the image the bundle runs and to your own install with `--edition none`.
- **Python 3.9 or later** to run the generator. It uses the standard library only; there is
  nothing to install. Without a local Python, run it in a container instead:

  ```bash
  docker run --rm -u "$(id -u):$(id -g)" -v "$PWD":/work -w /work python:3.9-slim \
    python generate.py --edition developer --out my-bundle
  ```

  The image also has the `openssl` that `--edition none --tls on` needs. `-u` keeps the bundle
  owned by you rather than root. `--out` and a relative `--custom-ca-dir` must be under the mounted
  directory.
- **Docker Engine with Docker Compose v2.23 or later** (`docker compose`, not `docker-compose`) on
  the host that runs the bundle: with `--storage local` or `nfs`, each agent runtime mounts only its
  own subdirectory of the storage volume, through Compose's `volume.subpath`.
- **A sandboxing container runtime** registered with Docker. The agent runtimes execute
  LLM-driven code, so they run under a runtime that isolates it from the host kernel. The default
  is gVisor (`runsc`), which must be registered with `--network=host`. To use another runtime you
  already operate, such as Kata Containers, pass its Docker runtime name with `--sandbox`; see
  [Sandboxing](#sandboxing).
- **`openssl`** on the host that runs the generator, only for `--edition none` with `--tls on`,
  where the generator issues the bundle's certificates; see [TLS](#tls).
- **Outbound access** from the Docker host to your LLM provider (`api.anthropic.com` by default)
  and to GitHub (or your GitHub Enterprise instance).

## Quick start

```bash
python3 generate.py --edition developer --out my-bundle
cd my-bundle
docker compose up -d
docker compose ps
```

With the defaults this runs:

- SonarQube Server Developer Edition;
- a bundled PostgreSQL;
- all three agentic components;
- local storage;
- TLS with a self-signed certificate.

Open `https://localhost:9443` once `docker compose ps` shows the long-running services as
healthy. The first start can take several minutes. The init services (`storage-init`,
`truststore-init`, and the like) never report healthy, and that is expected: they prepare a volume
and exit with code 0. `docker compose ps -a` lists them as exited.

The bundle's own `README.md` covers running, stopping and securing it, and what to do after the
first start: logging in, the licence, connecting GitHub and your LLM provider, and checking that the
agents are connected. Read it before going further.

## Choosing your options

Pass options as flags, or collect them in a JSON profile and pass `--profile <file>`.

- **Profile keys** are the flag names with underscores, so `--db-host` becomes `db_host`. The
  exception is `--db`, whose key is `db_mode`.
- **The full list** of keys is printed by `python3 generate.py --print-inputs-schema`, and
  `profiles/` holds examples.
- **Flags on the command line** override the profile.

```bash
python3 generate.py --profile profiles/enterprise-local-external-db.json --db-host db.example.com \
  --db-password '…' --out my-bundle
```

`--out -` prints only the compose file to stdout, to review it before generating a full bundle.
Without `--out`, the bundle goes to `out/<edition>`.

### Edition and components

| Flag | Values | Default | Effect |
|---|---|---|---|
| `--edition` | `developer` \| `enterprise` \| `datacenter` \| `none` | *required* | The SonarQube Server edition to run, or `none` to use your existing install |
| `--components` | comma-separated subset of `hunter,remediation,vortex` | all three | Services to run. `remediation` needs `vortex` and adds it if missing |
| `--sonarqube-tag` | SonarQube version, 2026.5 or later, e.g. `2026.5.0` | see `default-images.json` | SonarQube image version; the edition suffix is added for you |
| `--image-tag` | agentic pack version | see `default-images.json` | Version of all four agentic images |
| `--sonarqube-registry`, `--image-registry` | registry host, optionally with a port and a path, e.g. `mirror.example.com:5000/sonar` | Docker Hub | Pull from a mirror of the official images instead |
| `--project-name` | lowercase letters, digits, `_`, `-` | `agentic-<edition>` | Compose project name, the prefix of every container, network and volume. Give two bundles of the same edition on one host different names |

### Database

| Flag | Values | Default | Effect |
|---|---|---|---|
| `--db` | `local` \| `external` | `local` | `local` runs PostgreSQL in the bundle; `external` connects SonarQube and the orchestrator to yours |
| `--db-host`, `--db-password` | — | — | Required with `--db external` |
| `--db-port`, `--db-name`, `--db-user` | — | `5432`, `sonarqube`, `sonarqube` | |

The orchestrator stores its state in the same database as SonarQube.

The bundled database is meant for evaluation; for production, use `--db external`. The
connection to an external database is always encrypted and its certificate verified; see
[TLS](#tls).

### Storage

The orchestrator, the agent runtimes and SonarQube exchange job files through shared storage.
With `local`, `hostpath` and `nfs`, the orchestrator writes each job under a `hunter/` or
`remediation/` subdirectory, and each agent runtime mounts only its own, so neither sees the
other's jobs.

| `--storage` | Required flags | Use it for |
|---|---|---|
| `local` | — | Evaluation: a Docker volume on this host, removed by `docker compose down -v` |
| `hostpath` | `--storage-path` (absolute path) | A directory you already provision on the host, e.g. an EFS or NFS mount |
| `nfs` | `--nfs-server`, `--nfs-export`; with `--edition none`, also `--storage-path` (where your SonarQube host mounts the export) | An NFS export that Docker mounts for you |
| `s3` | `--s3-bucket`, `--s3-region`, `--s3-access-key`, `--s3-secret-key` | An S3 bucket. Add `--s3-endpoint` for an S3-compatible service. Addressing is virtual-hosted on AWS and path-style with `--s3-endpoint`; `--s3-path-style` overrides it |

Per-job LLM provider keys are stored in plaintext in this storage: restrict access to it as you
would a credential store.

### Network and security

| Flag | Values | Default | Effect |
|---|---|---|---|
| `--tls` | `on` \| `off` | `on` | `on` serves SonarQube over https on port 9443. With `--edition none`, it serves the orchestrator on 8443 and Vortex on 8444, and adds a TLS proxy for your SonarQube; see [TLS](#tls). `off` serves plain http on 9000 (orchestrator and Vortex on 9091 and 9092) |
| `--tls-server-name` | host name | `localhost` | The host name users reach the bundle by. Used for the bundle's certificate and for SonarQube's server base URL |
| `--sandbox` | a Docker runtime name | `runsc` | Container runtime of the two agent runtime services; see [Sandboxing](#sandboxing) |
| `--llm-domains` | comma-separated host names | `api.anthropic.com` | The only LLM hosts the agent runtimes may reach |
| `--github-api-base-url` | URL | public GitHub | Set for GitHub Enterprise, e.g. `https://github.example.com/api/v3` |
| `--custom-ca-dir` | directory | unset (`./custom-ca` with `--edition none --tls on`) | PEM CA certificates (`*.crt`, `*.pem`) to trust for outbound TLS; see [TLS](#tls) |
| `--sonar-secret-key-file` | file | unset | SonarQube's settings encryption key (`sonar-secret.txt`), mounted into SonarQube (as `sonar.secretKeyPath`) and the orchestrator, so both decrypt the same `{aes-gcm}` values. With `--edition none`, point it at the key your SonarQube already uses |

### Using your existing SonarQube (`--edition none`)

| Flag | Values | Default | Effect |
|---|---|---|---|
| `--sonarqube-external-host` | host name | `host.docker.internal` | Where the containers reach your SonarQube; the default is the Docker host. With `--tls on`, also the name on the certificate of the TLS proxy for your SonarQube |
| `--sonarqube-external-port` | port | `9000` | |
| `--sonarqube-external-scheme` | `http` \| `https` | `http` | Use `https` if your SonarQube already serves TLS; the containers then call it directly |
| `--host-gateway` | `on` \| `off` | `on` | Makes `host.docker.internal` resolve on Linux. Set `off` on Docker Desktop, Rancher Desktop or colima, which provide it themselves |

This mode has two requirements:

- **`--db external`**, pointed at your SonarQube's database.
- **Storage other than `local`**, reachable from both your SonarQube host and the containers.
  With `--storage hostpath`, mount it at the same path on both.

Then follow the bundle's `ZIP-INSTRUCTIONS.md`.

## TLS

- **Into the bundle** (`--tls on`, bundled SonarQube): an nginx proxy terminates https in front of
  SonarQube, and SonarQube publishes no plain port. The orchestrator, Vortex and the agent runtimes
  reach SonarQube on the bundle's internal networks.

  On first start the proxy generates a self-signed certificate for `--tls-server-name` and keeps
  it across restarts. To serve your own certificate, copy it in before the first start, from the
  bundle directory:

  ```bash
  # certs/ holds tls.crt (the full chain) and tls.key
  docker compose run --rm --no-deps -v "$PWD/certs:/src:ro" --entrypoint sh tls-proxy \
    -c 'cp /src/tls.crt /src/tls.key /tls/'
  ```
- **Between your SonarQube and the agentic services** (`--edition none`, `--tls on`): every
  connection between them is encrypted and verified, in both directions.
  - **From SonarQube to the orchestrator and Vortex:** `agentic-proxy` serves https on port 8443
    for the orchestrator and 8444 for Vortex (only when Vortex is deployed), and the services behind
    it publish no plain port.
  - **From the containers to SonarQube:** the bundle includes `sonarqube-tls-proxy/`, a small TLS
    proxy that you run on your SonarQube machine. It serves https on port 9443 and forwards to
    SonarQube's own port. Only the agentic services use it: your users and scanners keep reaching
    SonarQube as they do today. If your SonarQube already serves https, pass
    `--sonarqube-external-scheme https` and the containers call it directly, with no proxy.
  - **Certificates:** the generator creates a CA for the bundle, `tls/ca.crt`, and uses it to issue
    the certificates of both proxies: `agentic-proxy` for `--tls-server-name`, and
    `sonarqube-tls-proxy` for `--sonarqube-external-host`. The containers trust that CA
    automatically; you import it once into your SonarQube's JVM truststore. The CA's private key
    isn't kept, so nothing can issue further certificates from it. The certificates are valid for
    825 days.

  `ZIP-INSTRUCTIONS.md` and `sonarqube-tls-proxy/README.md` in the bundle walk through the setup,
  including serving certificates of your own.
- **To your database** (`--db external`): always TLS with `sslmode=verify-full`. The database must
  serve a certificate that is valid for `--db-host`, and SonarQube must trust the CA that issued it:
  - **Bundled SonarQube:** only public CAs are trusted, so a database whose certificate comes from
    a private CA can't be used yet. This includes Amazon RDS and Google Cloud SQL.
  - **`--edition none`:** add the database's CA certificate to your SonarQube's JVM truststore,
    and pass it with `--custom-ca-dir` for the orchestrator. `ZIP-INSTRUCTIONS.md` has the details.
- **To your SonarQube over its own https** (`--edition none`, `--sonarqube-external-scheme https`):
  the containers trust public CAs only. If your SonarQube's certificate comes from a private CA,
  pass that CA's certificate with `--custom-ca-dir`.

  Each CA certificate needs a `keyUsage` extension that includes `keyCertSign`; without it, the
  remediation runtime rejects the certificate.

## Sandboxing

The Hunter and Remediation agent runtimes run code chosen by an LLM against your repositories.
`--sandbox` sets the Docker runtime they run under (the `runtime:` of those two services); nothing
else in the bundle uses it.

- **`runsc` (default)**: [gVisor](https://gvisor.dev/docs/user_guide/install/), which intercepts the
  containers' system calls in a user-space kernel. Register it with `--network=host`, so that the
  containers use the host's network stack under gVisor. With gVisor's own network stack, Docker's
  embedded DNS server (127.0.0.11) is unreachable from inside the sandbox and the agent runtimes
  can't resolve `egress-proxy`. Also pass `--overlay2=root:self,size=50g`: by default gVisor keeps
  the containers' writable layer in memory, where the repositories an agent job checks out count
  against the runtime's memory limit. In `/etc/docker/daemon.json`:

  ```json
  {
    "runtimes": {
      "runsc": {
        "path": "/usr/local/bin/runsc",
        "runtimeArgs": ["--network=host", "--overlay2=root:self,size=50g"]
      }
    }
  }
  ```

  Then restart Docker (`sudo systemctl restart docker`). The containers still get their own network
  namespace from Docker; the flag only changes which network stack gVisor uses inside it.
- **Any other runtime registered with your Docker daemon**, for example `kata-runtime` for Kata
  Containers. Pass the name it is registered under; `docker info --format '{{json .Runtimes}}'` lists
  them. Choose one that isolates the workload from the host kernel at least as well as gVisor.
- **`runc`**: Docker's default runtime, with no isolation beyond a regular container. Use it only
  for evaluation where you can't install a sandbox runtime, for example on Docker Desktop.

The generator checks only that the value is a valid runtime name. Docker reports a runtime that
isn't registered when you start the bundle.

## Secrets

The generator creates the secret that signs requests between SonarQube, the orchestrator and
Vortex, and writes it to the bundle's `.env`. The secret is never an input, so it can't end up in
a script or CI log.

The bundle also contains the database password (in `docker-compose.yaml`) and the S3 credentials
(in `.env`) when you pass them. Keep the bundle directory private and out of version control.

The first run creates the signing secret, and for Data Center Edition the secret that signs
users' sessions. Later runs into the same directory reuse both from the existing `.env`, so
regenerating doesn't break jobs in flight or log users out. To replace them, pass
`--rotate-secrets`, then restart the whole stack.

The generator writes `.env` readable by its owner only (mode 600).

## Data Center Edition

`--edition datacenter` runs a cluster of two application nodes and three search nodes behind a
load balancer.

- **Memory.** The cluster alone needs about 18 GB.
- **Kernel setting.** Set `vm.max_map_count` to at least 262144 on the Docker host.
- **Licence.** The cluster starts unlicensed; apply a Data Center Edition licence in SonarQube
  (Administration → Configuration → License Manager). The agentic features also need a licence
  that includes them.
- **First start.** One application node may restart during the first start. This is expected.

The bundle's `README.md` has the details.

## Upgrading and regenerating

1. Regenerate the bundle into the same directory, reusing your profile, with the new
   `--sonarqube-tag` or `--image-tag`, or with any other option you want to change.
2. Run `docker compose up -d`.

Regenerating into an existing bundle directory is safe:

- **Secrets are kept**: the signing secret and the Data Center session secret are read from the
  existing `.env`; see [Secrets](#secrets).
- **Your edits are protected.** The generator records a checksum of every file it writes in
  `.generator-manifest.json`. If a file it is about to replace was edited since, or was never
  written by the generator, it stops and names the file. Move your change into a
  `docker-compose.override.yaml`, which `docker compose` loads automatically and the generator
  never writes, or rerun with `--force` to overwrite it. A bundle generated before the manifest
  existed has none, so its first regeneration stops too; rerun with `--force` once, nothing is lost.
- **Your ports and cluster addresses in `.env` are kept**, like the secrets, even with `--force`.
  Change a published port there, not in an override: `docker compose` adds an override's `ports`
  to the ones in `docker-compose.yaml` instead of replacing them. The keys are
  `SONARQUBE_PUBLISH_PORT` (`--tls off`, default 9000), `SONARQUBE_TLS_PUBLISH_PORT` (`--tls on`,
  default 9443), and `ORCHESTRATOR_PUBLISH_PORT` and `VORTEX_PUBLISH_PORT` (`--tls off`, defaults
  9091 and 9092). For Data Center, the cluster addresses are `SONARQUBE_CLUSTER_SUBNET` and the
  application node addresses.
- **It reports what changed**: every file it updated, and every file it removed because the new
  options no longer need it. A removed file that you edited is left in place.
- **Certificates are kept** with `--edition none --tls on`, so SonarQube keeps trusting the bundle,
  as long as they still match `--tls-server-name` and `--sonarqube-external-host`. If you changed
  either, the generator stops; rerun with `--force` to issue a new CA and certificates, then
  re-import the new `tls/ca.crt` wherever you trusted the old one.

Your data stays in the named volumes and your database. Don't run `docker compose down -v`: it
deletes the named volumes, including the bundled database, SonarQube's data and `local` storage.

## When the generator refuses your options

The generator writes nothing and exits with an error in these cases:

- a required flag is missing for the chosen mode, e.g. `--storage nfs` without `--nfs-server`, or
  `--db external` without `--db-host` or `--db-password`;
- `--edition none` is combined with `--storage local`;
- `--sonarqube-external-scheme https` is used without `--edition none`;
- `--sandbox` isn't a valid Docker runtime name;
- the profile isn't a JSON object, has a key that isn't in `--print-inputs-schema`, e.g.
  `"tls_server_nmae"`, or a value that isn't one of those its flag accepts, e.g.
  `"edition": "datacentre"`;
- a host name (`--db-host`, `--nfs-server`, `--tls-server-name`, `--sonarqube-external-host`, each
  `--llm-domains` entry, the S3 host) isn't a valid host name or IPv4 address (IPv6 literals
  aren't supported), a port isn't a number between 1 and 65535, or `--db-name` has characters
  other than letters, digits, `_` and `-`;
- `--s3-bucket` isn't a valid bucket name: 3 to 63 lowercase letters, digits, `.` and `-`;
- `--image-registry` or `--sonarqube-registry` isn't a registry host with an optional port and
  path, `--image-tag` or `--sonarqube-tag` isn't a valid image tag, or `--project-name` isn't a
  valid compose project name;
- a path or URL (`--storage-path`, `--nfs-export`, `--custom-ca-dir`, `--sonar-secret-key-file`,
  `--s3-endpoint`, `--github-api-base-url`) contains whitespace, a quote, `$`, `#` or `\`, or a
  relative `--custom-ca-dir` climbs out of the bundle with `..`;
- an S3 key contains a single quote or a newline;
- with `--edition none --tls on`, `openssl` is missing from the host that runs the generator;
- regenerating would overwrite a file you edited, or certificates that no longer match your
  options, and `--force` isn't set; see [Upgrading and regenerating](#upgrading-and-regenerating);
- the output directory can't be written to.

Database credentials may contain any character: the generator quotes them.

## Troubleshooting

- **The orchestrator stays unhealthy right after the first start.** It waits for SonarQube to
  create the database schema. With `--edition none`, start your SonarQube first.
- **The agent runtimes can't resolve `egress-proxy` under gVisor**, and their logs show a DNS
  error such as `connection refused` from 127.0.0.11. `runsc` isn't registered with
  `--network=host`; see [Sandboxing](#sandboxing).
- **`docker compose up` fails with "unknown or invalid runtime name".** The `--sandbox` runtime
  isn't registered with Docker. Install and register it, or regenerate with the name of a runtime
  that `docker info` lists.
- **Agent jobs fail to reach the LLM.** The agent runtimes reach the internet only through the
  bundle's egress proxy. It allows `--llm-domains` on ports 80 and 443, and the S3 bucket's host on
  its endpoint's port only, never at a link-local address (169.254.0.0/16, where cloud metadata
  services live). The remediation runtime can also reach your SonarQube's rule-info and analysis
  endpoints, through a listener of its own. Wildcard domains are refused.
  Denied requests are logged by the proxy: `docker compose logs -f egress-proxy`.
- **A Data Center Edition start fails with "Pool overlaps with other one".** Change the cluster
  subnet in `.env`, as explained in the bundle's `README.md`.

## Testing the generator

`tests/lint.sh` generates every profile under `profiles/`, validates each bundle with
`docker compose config`, and checks the refusals and the regeneration behaviour. It needs Docker
and Python 3, but no image.

`tests/egress-proxy.sh` starts `egress-proxy/` on its pinned image with stand-ins for SonarQube,
the orchestrator, an LLM host and a storage host, and checks what each agent runtime may and may not reach through
it, with SonarQube over http and over https. It needs Docker and the `egress-proxy` image.

`tests/e2e.sh <out-dir> [flags...]` generates one bundle, starts it, waits until every service is
healthy, and checks that the sandboxed agent runtimes can reach `egress-proxy`. Every image must
already be present locally. It configures no licence, LLM provider or GitHub App, so no agent job
runs.
