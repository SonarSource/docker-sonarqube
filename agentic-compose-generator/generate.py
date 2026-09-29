#!/usr/bin/env python3
"""Generate a self-contained docker-compose bundle for the agentic pack.

Stdlib only. See README.md for the input matrix and profiles/*.json for examples.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import ipaddress
import json
import os
import re
import secrets
import shutil
import string
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
TEMPLATES = HERE / "templates"
DEFAULT_IMAGES_FILE = HERE / "default-images.json"
DEFAULT_IMAGES: dict = json.loads(DEFAULT_IMAGES_FILE.read_text())

EDITIONS = ("developer", "enterprise", "datacenter", "none")
ALL_COMPONENTS = ("hunter", "remediation", "vortex")
DB_MODES = ("local", "external")
STORAGE_MODES = ("local", "nfs", "hostpath", "s3")
# Any runtime registered with the Docker daemon (`docker info --format '{{json .Runtimes}}'`), e.g.
# runsc (gVisor), kata-runtime or runc; rendered unquoted into `runtime:` and into .env.
SANDBOX_RUNTIME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
AGENTIC_IMAGES = ("agent-orchestrator", "hunter-agent", "remediation-agent", "vortex")

# --edition none --tls on: the generator mints a CA per bundle and issues agentic-proxy's certificate
# and the standalone sonarqube-tls-proxy kit's from it, then discards the CA key. The kit runs next
# to the customer's SonarQube; its port is fixed because it is baked into the containers' URLs.
SONARQUBE_KIT_DIR = "sonarqube-tls-proxy"
SONARQUBE_KIT_PORT = "9443"
BUNDLE_CA_FILE = "agentic-bundle-ca.crt"
# sha256 of every file the last run wrote, so a later run can tell its own output from user edits.
MANIFEST_FILE = ".generator-manifest.json"
# The name Docker Desktop, and the host-gateway mapping, resolve to the host.
HOST_GATEWAY_NAME = "host.docker.internal"
# File names in the bundle CA's working directory and in the proxies' tls/ directories.
CA_CERT_FILE = "ca.crt"
LEAF_CERT_FILE = "tls.crt"
LEAF_CONFIG_FILE = "leaf.cnf"
# Written into an openssl config file and a SAN, so no spaces, commas or brackets. No `:` either:
# IPv6 literals aren't supported — tls-proxy/entrypoint.sh refuses them and the URLs built from
# these names don't bracket them.
TLS_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9.-]*$")
# Everything the generator writes into compose YAML or .env unquoted must match one of these: a `$`
# there is interpolated by compose, ` #` starts a comment and `: ` breaks the YAML.
PORT_RE = re.compile(r"^\d{1,5}$", re.ASCII)
DB_NAME_RE = re.compile(r"^[A-Za-z0-9_-]+$")
# Docker's own reference grammar, narrowed: a registry host[:port][/namespace...], and a tag.
IMAGE_REGISTRY_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9.-]*(:\d+)?(/[a-z0-9][a-z0-9._-]*)*$", re.ASCII)
IMAGE_TAG_RE = re.compile(r"^\w[\w.-]{0,127}$", re.ASCII)
S3_BUCKET_RE = re.compile(r"^[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]$")
# `docker compose -p` rules; also becomes the prefix of every container, network and volume.
PROJECT_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*$")
PLAIN_VALUE_RE = re.compile(r"""^[^\s$#'"\\]+$""")

# --edition datacenter topology: application nodes behind a load balancer named `sonarqube`, so
# every other service addresses the cluster exactly like a single node. Each application node gets
# a static address on the `cluster` network -- see templates/compose/networks-datacenter.tmpl.
# Outside Docker's default address pools (172.17-31.0.0/16, 192.168.0.0/16), which a fixed subnet
# would otherwise race against; overridable from .env.
DATACENTER_CLUSTER_SUBNET = "10.203.64.0/24"
DATACENTER_APP_NODES = ("sonarqube-app-1", "sonarqube-app-2")
DATACENTER_APP_NODE_IPS = ("10.203.64.11", "10.203.64.12")
DATACENTER_SEARCH_NODES = ("sonarqube-search-1", "sonarqube-search-2", "sonarqube-search-3")

# Extra strings that must never reach a bundle, comma-separated in AGENTIC_GEN_FORBIDDEN. CI uses it
# to make sure no build-time or registry reference leaks into the output; unset, only the
# placeholder scan runs.
FORBIDDEN_STRINGS = tuple(s for s in os.environ.get("AGENTIC_GEN_FORBIDDEN", "").split(",") if s)


def render(template_name: str, **substitutions: str) -> str:
    text = (TEMPLATES / template_name).read_text()
    return string.Template(text).safe_substitute(**substitutions)


def indent_block(text: str, spaces: int) -> str:
    prefix = " " * spaces
    return "\n".join((prefix + line if line.strip() else "") for line in text.splitlines())


# --------------------------------------------------------------------------------------------------
# Config
# --------------------------------------------------------------------------------------------------


class ConfigError(ValueError):
    pass


def build_argparser() -> argparse.ArgumentParser:
    # No prefix matching: load_config spots CLI flags by their exact text, so an abbreviated flag
    # would go unnoticed and the profile would override it.
    p = argparse.ArgumentParser(
        allow_abbrev=False,
        description="Generate a docker-compose bundle for the agentic pack (Hunter Agent, "
        "Remediation Agent, Vortex, Agent Orchestrator) in front of SonarQube Server.",
    )
    p.add_argument("--profile", help="JSON file with any of the flags below as keys")
    p.add_argument("--print-inputs-schema", action="store_true", help="print the JSON Schema for a profile and exit")
    p.add_argument("--edition", choices=EDITIONS, help="SonarQube edition ('datacenter' runs a 2-app/3-search cluster behind a load "
                         "balancer), or 'none' to target an existing zip install")
    p.add_argument("--components", default="hunter,remediation,vortex", help="csv subset of hunter,remediation,vortex")
    p.add_argument("--db", dest="db_mode", choices=DB_MODES, default="local")
    p.add_argument("--db-host")
    p.add_argument("--db-port", default="5432")
    p.add_argument("--db-name", default="sonarqube")
    p.add_argument("--db-user", default="sonarqube")
    p.add_argument("--db-password")
    p.add_argument("--storage", choices=STORAGE_MODES, default="local")
    p.add_argument("--storage-path", help="absolute host path, --storage hostpath; with --storage nfs "
                                           "--edition none, where your SonarQube host mounts the export")
    p.add_argument("--nfs-server", help="--storage nfs only")
    p.add_argument("--nfs-export", help="--storage nfs only, e.g. /export/agentic")
    p.add_argument("--s3-bucket", default="agentic-jobs")
    p.add_argument("--s3-region", default="us-east-1")
    p.add_argument("--s3-endpoint", default="")
    p.add_argument("--s3-access-key", default="")
    p.add_argument("--s3-secret-key", default="")
    p.add_argument("--s3-path-style", choices=("true", "false"), default=None,
                   help="default: true with --s3-endpoint, false on AWS, whose bucket host is what egress-proxy allowlists")
    p.add_argument("--s3-presign-ttl", default="21600")
    p.add_argument("--sandbox", default="runsc",
                   help="Docker runtime for the agent runtimes: runsc (gVisor, default), another registered "
                        "sandbox runtime such as kata-runtime, or runc for no extra isolation")
    p.add_argument("--tls", choices=("on", "off"), default="on")
    p.add_argument("--tls-server-name", default="localhost")
    p.add_argument("--image-registry", default=None,
                    help="overrides the registry for every agentic component image, blank for "
                         "the official Docker Hub image; per-component defaults come from "
                         "default-images.json")
    p.add_argument("--image-tag", default=None,
                    help="overrides the tag for every agentic component image; "
                         "per-component defaults come from default-images.json")
    p.add_argument("--sonarqube-registry", default=None,
                    help="SonarQube image registry, blank for the official Docker Hub image; "
                         "defaults to default-images.json's sonarqube.registry")
    p.add_argument("--sonarqube-tag", default=None,
                    help="SonarQube image tag; defaults to default-images.json's sonarqube.tag")
    p.add_argument("--llm-domains", default="api.anthropic.com")
    p.add_argument("--github-api-base-url", default="")
    p.add_argument("--sonarqube-external-host", default=HOST_GATEWAY_NAME, help="--edition none only")
    p.add_argument("--sonarqube-external-port", default="9000", help="--edition none only")
    p.add_argument("--sonarqube-external-scheme", choices=("http", "https"), default="http",
                    help="--edition none only: how the containers call your SonarQube")
    p.add_argument("--custom-ca-dir", default="",
                    help="host directory of PEM CA certs (*.crt/*.pem) every container trusts, e.g. "
                         "for an https SonarQube; relative to the bundle")
    p.add_argument("--sonar-secret-key-file", default="",
                    help="host file holding SonarQube's settings encryption key (sonar-secret.txt), "
                         "shared by SonarQube and the orchestrator so both decrypt the same "
                         "{aes-gcm} values; relative to the bundle. Under --edition none, point it "
                         "at the key your SonarQube already uses")
    p.add_argument("--host-gateway", choices=("on", "off"), default="on",
                    help="--edition none only: map host.docker.internal to Docker's host-gateway; "
                         "needed on native Linux Docker, turn off on Docker Desktop, Rancher "
                         "Desktop, or colima, which already resolve host.docker.internal to the host")
    p.add_argument("--project-name", default=None,
                   help="compose project name, the prefix of every container, network and volume; "
                        "defaults to agentic-<edition>. Set it to run two bundles side by side")
    p.add_argument("--out", default=None, help="output directory, or '-' for compose-only to stdout")
    p.add_argument("--force", action="store_true",
                   help="regenerate over files edited since the last run, and reissue certificates "
                        "whose names no longer match the inputs")
    p.add_argument("--rotate-secrets", action="store_true",
                   help="mint new signing (and Data Center JWT) secrets instead of reusing the ones "
                        "in the existing bundle's .env")
    return p


def load_config(argv: list[str]) -> tuple[argparse.Namespace, argparse.ArgumentParser]:
    parser = build_argparser()
    args = parser.parse_args(argv)

    if args.print_inputs_schema:
        return args, parser

    if args.profile:
        try:
            profile = json.loads(Path(args.profile).read_text())
        except OSError as exc:
            raise ConfigError(f"--profile: cannot read {args.profile}: {exc.strerror}") from exc
        except json.JSONDecodeError as exc:
            raise ConfigError(f"--profile: {args.profile} is not valid JSON: {exc}") from exc
        if not isinstance(profile, dict):
            raise ConfigError(f"--profile: {args.profile} must hold a JSON object")
        # Profile values are defaults; explicit CLI flags (present in argv) win. Flags map to their
        # dest, so `--db` guards `db_mode`. argparse only checks `choices` on argv, so profile values
        # are checked here.
        dests = {opt: action.dest for action in parser._actions for opt in action.option_strings}
        choices = {action.dest: action.choices for action in parser._actions if action.choices}
        passed = {dests.get(a.split("=", 1)[0]) for a in argv if a.startswith("--")}
        # A misspelt key would otherwise be set on args and silently ignored, leaving the default.
        unknown = sorted(set(profile) - set(INPUTS_SCHEMA["properties"]))
        if unknown:
            raise ConfigError(f"--profile: unknown key(s) {', '.join(unknown)}; see --print-inputs-schema")
        for key, value in profile.items():
            if key in passed:
                continue
            if key in choices and value not in choices[key]:
                raise ConfigError(f"profile key '{key}': '{value}' is not one of {', '.join(choices[key])}")
            setattr(args, key, value)

    if not args.edition:
        raise ConfigError("--edition is required (developer|enterprise|datacenter|none), or set it in --profile")

    args.components = {c.strip() for c in str(args.components).split(",") if c.strip()}
    unknown = args.components - set(ALL_COMPONENTS)
    if unknown:
        raise ConfigError(f"unknown --components entries: {sorted(unknown)}")

    args.llm_domains = [d.strip() for d in str(args.llm_domains).split(",") if d.strip()]
    # Replaced by the existing bundle's values, if any (see reuse_env_values).
    args.cluster_subnet = DATACENTER_CLUSTER_SUBNET
    args.app_node_ips = list(DATACENTER_APP_NODE_IPS)
    args.publish_ports = {}

    return args, parser


# --------------------------------------------------------------------------------------------------
# Validation (see README "Validation rules" — each of these fails silently at runtime otherwise)
# --------------------------------------------------------------------------------------------------


def resolve_s3_egress(args: argparse.Namespace) -> list[str]:
    """Defaults the S3 addressing style and derives the host and port egress-proxy allowlists.

    The runtimes fetch presigned URLs through egress-proxy, so the allowlisted host must be the one
    the addressing style puts in those URLs: the bucket host for virtual-hosted style, the endpoint
    itself for path style.
    """
    if args.s3_endpoint:
        if args.s3_path_style is None:
            args.s3_path_style = "true"
        authority = re.sub(r"^https?://", "", args.s3_endpoint).split("/")[0]
        host, _, port = authority.partition(":")
        # egress-proxy denies every port it isn't told about, so pass the endpoint's own.
        args.s3_allowed_port = port or ("443" if args.s3_endpoint.startswith("https://") else "80")
        args.s3_allowed_domain = host if args.s3_path_style == "true" else f"{args.s3_bucket}.{host}"
        return []
    args.s3_allowed_port = "443"
    # AWS's wildcard certificate covers a single label, so a dotted bucket host fails TLS
    # verification: such buckets need path style.
    dotted = "." in args.s3_bucket
    if args.s3_path_style is None:
        args.s3_path_style = "true" if dotted else "false"
    if args.s3_path_style == "false":
        args.s3_allowed_domain = f"{args.s3_bucket}.s3.{args.s3_region}.amazonaws.com"
        return []
    args.s3_allowed_domain = f"s3.{args.s3_region}.amazonaws.com"
    reason = ("the bucket name has dots, which AWS's certificate doesn't cover in a bucket host, so path style is used"
              if dotted else "--s3-path-style true on AWS")
    return [f"{reason}: egress-proxy allowlists {args.s3_allowed_domain}, which reaches every bucket in the "
            "region, not only yours" + ("" if dotted else "; drop it to allowlist the bucket host alone")]


def validate_and_normalize(args: argparse.Namespace) -> list[str]:
    notes: list[str] = []

    # 1. remediation implies vortex.
    if "remediation" in args.components and "vortex" not in args.components:
        args.components.add("vortex")
        notes.append("--components: 'remediation' requires 'vortex' — added it automatically.")

    if not args.components:
        raise ConfigError("--components must not be empty")

    # 3. s3 requires bucket + region; derive the egress allowlist host.
    if args.storage == "s3":
        if not args.s3_bucket or not args.s3_region:
            raise ConfigError("--storage s3 requires --s3-bucket and --s3-region")
        notes.extend(resolve_s3_egress(args))

    # 4. nfs requires server + export; hostpath requires an absolute path.
    if args.storage == "nfs":
        if not args.nfs_server or not args.nfs_export:
            raise ConfigError("--storage nfs requires --nfs-server and --nfs-export")
        if not args.nfs_export.startswith("/"):
            raise ConfigError("--nfs-export must be an absolute export path, e.g. /export/agentic")
        # The host SonarQube and the containers exchange absolute file paths, so the containers
        # must mount the export where the host has it mounted.
        if args.edition == "none" and (not args.storage_path or not args.storage_path.startswith("/")):
            raise ConfigError("--storage nfs --edition none requires an absolute --storage-path: where "
                              "your SonarQube host mounts the export, e.g. /mnt/agentic")
    if args.storage == "hostpath":
        if not args.storage_path or not args.storage_path.startswith("/"):
            raise ConfigError("--storage hostpath requires an absolute --storage-path")

    # 5. --edition none forces external DB and rejects local storage.
    if args.edition == "none":
        if args.db_mode != "external":
            args.db_mode = "external"
            notes.append("--edition none: forced --db external — a Docker named volume database is "
                         "not the customer's own SonarQube install.")
        if args.storage == "local":
            raise ConfigError("--edition none needs --storage hostpath, nfs or s3: --storage defaults to "
                              "local, a Docker named volume, which a host-installed SonarQube can't reach.")

    if not SANDBOX_RUNTIME_RE.match(args.sandbox):
        raise ConfigError(f"--sandbox '{args.sandbox}' is not a valid Docker runtime name")

    if args.db_mode == "external" and not args.db_host:
        raise ConfigError("--db external requires --db-host")
    if args.db_mode == "external" and not args.db_password:
        raise ConfigError("--db external requires --db-password")
    if args.sonarqube_external_scheme == "https" and args.edition != "none":
        raise ConfigError("--sonarqube-external-scheme https requires --edition none: a bundled "
                           "SonarQube is reached over the compose network")

    args.tls_on = args.tls == "on"
    validate_plain_values(args)
    if uses_bundle_ca(args):
        if args.out != "-" and not shutil.which("openssl"):
            raise ConfigError("--edition none --tls on needs the openssl command to issue the bundle's "
                               "certificates; install it, or use --tls off")
        if not args.custom_ca_dir:
            # The containers only trust extra CAs through /custom-ca, so the bundle CA needs one.
            args.custom_ca_dir = "./custom-ca"

    # 2. the signing secret is never a generator input — always minted internally, then carried
    # over by later runs over the same bundle (see reuse_env_values).
    args.signing_secret = secrets.token_hex(32)
    # Shared by every Data Center application node so a session survives landing on another node;
    # minted here for the same reason as the signing secret.
    args.jwt_secret = base64.b64encode(secrets.token_bytes(32)).decode() if args.edition == "datacenter" else ""

    args.compose_project_name = args.project_name or f"agentic-{args.edition}"
    if not PROJECT_NAME_RE.match(str(args.compose_project_name)):
        raise ConfigError(f"--project-name '{args.compose_project_name}' may only contain lowercase "
                          f"letters, digits, '_' and '-', and must start with a letter or digit")

    return notes


def validate_plain_values(args: argparse.Namespace) -> None:
    """Rejects values the templates can't carry unquoted; free-form credentials go through yaml_str
    or env_str instead."""
    names = [("--llm-domains", d) for d in args.llm_domains]
    ports = [("--s3-presign-ttl", args.s3_presign_ttl)]
    plain = [("--custom-ca-dir", args.custom_ca_dir), ("--github-api-base-url", args.github_api_base_url),
             ("--sonar-secret-key-file", args.sonar_secret_key_file)]
    if args.tls_on:
        names.append(("--tls-server-name", args.tls_server_name))
    if args.edition == "none":
        names.append(("--sonarqube-external-host", args.sonarqube_external_host))
        ports.append(("--sonarqube-external-port", args.sonarqube_external_port))
    if args.db_mode == "external":
        names.append(("--db-host", args.db_host))
        ports.append(("--db-port", args.db_port))
        if not DB_NAME_RE.match(str(args.db_name)):
            raise ConfigError(f"--db-name '{args.db_name}' may only contain letters, digits, '_' and '-'")
    if args.storage == "nfs":
        names.append(("--nfs-server", args.nfs_server))
        plain.append(("--nfs-export", args.nfs_export))
    if args.storage == "hostpath" or (args.storage == "nfs" and args.edition == "none"):
        plain.append(("--storage-path", args.storage_path))
    if args.storage == "s3":
        # Checked even with --s3-endpoint, where it isn't part of the allowlisted host: it is still
        # written to .env and sonar.properties unquoted.
        if not S3_BUCKET_RE.match(str(args.s3_bucket)):
            raise ConfigError(f"--s3-bucket '{args.s3_bucket}' is not a valid bucket name: 3-63 lowercase "
                              f"letters, digits, '.' and '-'")
        names.append(("--s3-bucket/--s3-endpoint host", args.s3_allowed_domain))
        ports.append(("--s3-endpoint port", args.s3_allowed_port))
        plain += [("--s3-endpoint", args.s3_endpoint), ("--s3-region", args.s3_region)]
        for flag, value in (("--s3-access-key", args.s3_access_key), ("--s3-secret-key", args.s3_secret_key)):
            if "'" in value or "\n" in value:
                raise ConfigError(f"{flag} must not contain a single quote or a newline")
    for flag, pattern, value in (("--image-registry", IMAGE_REGISTRY_RE, args.image_registry),
                                 ("--sonarqube-registry", IMAGE_REGISTRY_RE, args.sonarqube_registry),
                                 ("--image-tag", IMAGE_TAG_RE, args.image_tag),
                                 ("--sonarqube-tag", IMAGE_TAG_RE, args.sonarqube_tag)):
        # None means "use default-images.json", blank means "Docker Hub" (registry) or "no tag".
        if value and not pattern.match(str(value)):
            raise ConfigError(f"{flag} '{value}' is not a valid image {flag.rsplit('-', 1)[1]}")
    for flag, value in names:
        if not TLS_NAME_RE.match(str(value)):
            raise ConfigError(f"{flag} '{value}' is not a valid host name or IPv4 address")
    for flag, value in ports:
        if not PORT_RE.match(str(value)):
            raise ConfigError(f"{flag} '{value}' must be a number")
        # --s3-presign-ttl is seconds, not a port.
        if flag != "--s3-presign-ttl" and not 1 <= int(value) <= 65535:
            raise ConfigError(f"{flag} '{value}' must be a port between 1 and 65535")
    for flag, value in plain:
        if value and not PLAIN_VALUE_RE.match(str(value)):
            raise ConfigError(f"{flag} '{value}' must not contain whitespace, quotes, '$', '#' or '\\'")
    # The generator creates a relative --custom-ca-dir and writes the bundle CA into it, so it must
    # not climb out of the bundle; a directory elsewhere is passed as an absolute path.
    if args.custom_ca_dir and not Path(args.custom_ca_dir).is_absolute() and ".." in Path(args.custom_ca_dir).parts:
        raise ConfigError(f"--custom-ca-dir '{args.custom_ca_dir}' must stay inside the bundle directory; "
                          f"pass an absolute path for a directory outside it")


def yaml_str(value: str) -> str:
    """A free-form value as a double-quoted YAML scalar that compose won't interpolate."""
    return json.dumps(str(value).replace("$", "$$"))


def env_str(value: str) -> str:
    """A free-form value for .env: single-quoted, which compose reads literally. Single quotes and
    newlines are rejected up front by validate_plain_values."""
    return f"'{value}'" if value else ""


# --------------------------------------------------------------------------------------------------
# Compose assembly
# --------------------------------------------------------------------------------------------------


def image_ref(args: argparse.Namespace, component: str) -> str:
    defaults = DEFAULT_IMAGES.get(component, {})
    # --image-registry/--image-tag target the agentic components only: applying a customer's
    # agentic tag to postgres/alpine/squid/nginx would point at images that don't exist.
    overridable = component in AGENTIC_IMAGES
    registry = args.image_registry if overridable and args.image_registry is not None else \
        defaults.get("registry", "REPLACE_WITH_YOUR_REGISTRY")
    name = defaults.get("name", component)
    tag = args.image_tag if overridable and args.image_tag is not None else defaults.get("tag", "latest")
    digest = defaults.get("digest")
    image = f"{registry}/{name}" if registry else name
    ref = f"{image}:{tag}" if tag else image
    return f"{ref}@{digest}" if digest else ref


def build_networks_block(args: argparse.Namespace) -> str:
    # Declared unconditionally — an unused declared network costs nothing, and it keeps every
    # service fragment free of conditional network-declaration logic. The comments in
    # templates/compose/networks.tmpl give the rationale behind each one. The Data Center networks are the
    # exception: `cluster` pins a fixed subnet, which could collide with a network on the host.
    text = render("compose/networks.tmpl")
    if args.edition == "datacenter":
        text += "\n" + render("compose/networks-datacenter.tmpl",
                              cluster_subnet=f"${{SONARQUBE_CLUSTER_SUBNET:-{DATACENTER_CLUSTER_SUBNET}}}")
    return text


def build_volumes_block(args: argparse.Namespace) -> str:
    lines = []
    if args.db_mode == "local":
        lines.append("  pgdata:")
    if args.storage in ("local", "hostpath"):
        lines.append("  agentic-storage:")
    if args.storage == "nfs":
        lines.append(render("compose/volume-nfs.tmpl", nfs_server=args.nfs_server, nfs_export=args.nfs_export))
    if args.edition == "datacenter":
        # Per node, never shared: a data/logs volume mounted by two nodes would corrupt both.
        for node in DATACENTER_SEARCH_NODES:
            lines += [f"  {volume_prefix(node)}_data:", f"  {volume_prefix(node)}_logs:"]
        for node in DATACENTER_APP_NODES:
            lines += [f"  {volume_prefix(node)}_{suffix}:" for suffix in ("data", "extensions", "logs")]
    elif args.edition != "none":
        lines.extend(["  sonarqube_data:", "  sonarqube_extensions:", "  sonarqube_logs:"])
    if args.edition != "none":
        lines.append("  agentic_signing_sqs:")
    lines.append("  agentic_signing_orchestrator:")
    if "hunter" in args.components:
        lines.append("  agentic_signing_hunter:")
    if "remediation" in args.components:
        lines.append("  agentic_signing_remediation:")
    if "vortex" in args.components:
        lines.append("  agentic_signing_vortex:")
    if args.tls_on and args.edition != "none":
        lines.append("  tls_certs:")
    if needs_truststore(args):
        lines.append("  custom_truststore:")
    return "volumes:\n" + "\n".join(lines)


def ip_var(node: str) -> str:
    return f"{volume_prefix(node).upper()}_IP"


def volume_prefix(node: str) -> str:
    return node.replace("-", "_")


def storage_volume_line(args: argparse.Namespace, runtime: str = "", read_only: bool = False) -> str:
    """The shared storage mount; a runtime mounts only its own <runtime>/ subdirectory of it, at the
    same absolute path, so it can't see the other runtime's jobs (the orchestrator writes each job
    under <runtime>/YYYY/MM/DD/<jobId>). `read_only` applies to the whole-volume mount only."""
    if args.storage == "s3":
        return ""
    if not runtime:
        suffix = ":ro" if read_only else ""
        return f"      - ${{AGENTIC_STORAGE_SOURCE:-agentic-storage}}:${{AGENTIC_STORAGE_MOUNT:-/agentic-storage}}{suffix}"
    target = f"${{AGENTIC_STORAGE_MOUNT:-/agentic-storage}}/{runtime}"
    if args.storage == "hostpath":
        return f"      - ${{AGENTIC_STORAGE_SOURCE:?set AGENTIC_STORAGE_SOURCE in .env}}/{runtime}:{target}"
    # A named (or NFS) volume has no path to append to; volume.subpath needs Compose 2.23+.
    return ("      - type: volume\n"
            "        source: agentic-storage\n"
            f"        target: {target}\n"
            "        volume:\n"
            f"          subpath: {runtime}")


def build_sonarqube_properties(args: argparse.Namespace) -> str:
    if args.edition == "none":
        return ""
    if "vortex" in args.components:
        vortex_lines = "sonar.vortex.enabled=true\nsonar.vortex.analysis.url=http://vortex:8080"
    else:
        vortex_lines = "# No Vortex in this bundle.\nsonar.vortex.enabled=false"
    secret_key_line = ""
    if args.sonar_secret_key_file:
        secret_key_line = ("\n\n# Settings encryption key, shared with the orchestrator so both decrypt the same values.\n"
                           f"sonar.secretKeyPath={SONAR_SECRET_KEY_MOUNT}")
    return render("compose/sonar-properties.tmpl", vortex_lines=vortex_lines, secret_key_line=secret_key_line)


def build_storage_anchors(args: argparse.Namespace) -> str:
    provider = {"nfs": "NFS", "s3": "S3"}.get(args.storage, "FILESYSTEM")
    return render("compose/storage-anchors.tmpl", storage_provider=provider)


def build_storage_services(args: argparse.Namespace) -> tuple[str, list[str]]:
    """Returns (compose fragment, list of one-shot service names other services should depend on)."""
    if args.storage == "nfs":
        text = render("compose/storage-nfs.tmpl", nfs_server=args.nfs_server, nfs_export=args.nfs_export,
                       image=image_ref(args, "storage-probe"))
        return text, ["storage-probe"]
    if args.storage == "s3":
        return "", []
    # local | hostpath
    return render("compose/storage-init.tmpl", image=image_ref(args, "storage-init")), ["storage-init"]


def build_signing_init(args: argparse.Namespace) -> str:
    # The orchestrator refuses to start with only one of the two inbound verification keys, so it
    # gets both whichever runtimes are selected.
    labels = ["agentic-shared=/run/agentic-signing/orchestrator/agentic-shared.key",
              "orchestrator-job-capability=/run/agentic-signing/orchestrator/orchestrator-job-capability.key",
              "hunter-to-orchestrator=/run/agentic-signing/orchestrator/hunter-to-orchestrator.key",
              "remediation-to-orchestrator=/run/agentic-signing/orchestrator/remediation-to-orchestrator.key"]
    volumes = ["agentic_signing_orchestrator:/run/agentic-signing/orchestrator"]
    if args.edition != "none":
        labels.insert(0, "agentic-shared=/run/agentic-signing/sqs/agentic-shared.key")
        volumes.insert(0, "agentic_signing_sqs:/run/agentic-signing/sqs")
    if "hunter" in args.components:
        labels += [
            "orchestrator-to-hunter=/run/agentic-signing/orchestrator/orchestrator-to-hunter.key",
            "orchestrator-to-hunter=/run/agentic-signing/hunter/orchestrator-to-hunter.key",
            "hunter-to-orchestrator=/run/agentic-signing/hunter/hunter-to-orchestrator.key",
        ]
        volumes.append("agentic_signing_hunter:/run/agentic-signing/hunter")
    if "remediation" in args.components:
        labels += [
            "orchestrator-to-remediation=/run/agentic-signing/orchestrator/orchestrator-to-remediation.key",
            "orchestrator-to-remediation=/run/agentic-signing/remediation/orchestrator-to-remediation.key",
            "remediation-to-orchestrator=/run/agentic-signing/remediation/remediation-to-orchestrator.key",
            "remediation-to-sqs=/run/agentic-signing/remediation/remediation-to-sqs.key",
        ]
        volumes.append("agentic_signing_remediation:/run/agentic-signing/remediation")
    if "vortex" in args.components:
        labels.append("agentic-shared=/run/agentic-signing/vortex/agentic-shared.key")
        volumes.append("agentic_signing_vortex:/run/agentic-signing/vortex")

    label_args = " \\\n          ".join(f"--label {label}" for label in labels)
    volume_lines = "\n".join(f"      - {v}" for v in volumes)
    # SonarQube reads the raw secret from the sqs-mounted path; that volume isn't mounted here at
    # all under --edition none, since there's no SonarQube container to read it.
    secret_copy_line = "cp /tmp/instance-secret /run/agentic-signing/sqs/instance-secret" \
        if args.edition != "none" else "true"
    return render(
        "compose/signing-init.tmpl",
        orchestrator_image=image_ref(args, "agent-orchestrator"),
        label_args=label_args,
        volume_lines=volume_lines,
        secret_copy_line=secret_copy_line,
    )


def build_postgres(args: argparse.Namespace) -> str:
    if args.db_mode != "local":
        return ""
    return render("compose/postgres.tmpl", image=image_ref(args, "postgres"))


def db_env_lines(args: argparse.Namespace) -> tuple[str, str, str, str]:
    if args.db_mode == "local":
        return "postgres:5432", "sonarqube", "sonarqube", "sonarqube"
    # Credentials are free-form, so quoted; host, port and name are validated as plain tokens.
    return f"{args.db_host}:{args.db_port}", args.db_name, yaml_str(args.db_user), yaml_str(args.db_password)


# An external database is always reached over TLS with its certificate and host name verified.
# pgjdbc's default factory would look for ~/.postgresql/root.crt, which no image here has;
# DefaultJavaSSLFactory validates against the JVM truststore (public CAs, plus --custom-ca-dir in
# the orchestrator) instead.
EXTERNAL_DB_SSL_PARAMS = "sslmode=verify-full&sslfactory=org.postgresql.ssl.DefaultJavaSSLFactory"


def db_url_params(args: argparse.Namespace) -> str:
    return f"?{EXTERNAL_DB_SSL_PARAMS}" if args.db_mode == "external" else ""


def uses_bundle_ca(args: argparse.Namespace) -> bool:
    return args.edition == "none" and args.tls == "on"


def uses_kit(args: argparse.Namespace) -> bool:
    """Whether the containers call the customer's SonarQube through the sonarqube-tls-proxy kit.

    The kit is emitted whenever the bundle CA is, but a SonarQube that already serves https
    (--sonarqube-external-scheme https) is called directly.
    """
    return uses_bundle_ca(args) and args.sonarqube_external_scheme == "http"


# --custom-ca-dir: the orchestrator and both runtimes import /custom-ca in their entrypoints;
# Vortex can't (its cacerts is root-owned and it doesn't run as root), so it gets a truststore
# built by truststore-init instead.
TRUSTSTORE_OPTS = "-Djavax.net.ssl.trustStore=/custom-truststore/cacerts -Djavax.net.ssl.trustStorePassword=changeit"


# --sonar-secret-key-file: SonarQube's settings encryption key. The orchestrator path is its image's
# own convention, the one the Helm chart mounts it at too.
SONAR_SECRET_KEY_MOUNT = "/opt/sonarqube/secret/sonar-secret.txt"
ORCHESTRATOR_SECRET_KEY_MOUNT = "/sonarcloud/secret/sonar-secret.txt"


def secret_key_volume_line(args: argparse.Namespace, target: str) -> str:
    if not args.sonar_secret_key_file:
        return ""
    return f"\n      - ${{SONAR_SECRET_KEY_FILE:?set SONAR_SECRET_KEY_FILE in .env}}:{target}:ro"


def custom_ca_volume_line(args: argparse.Namespace) -> str:
    if not args.custom_ca_dir:
        return ""
    return "\n      - ${CUSTOM_CA_DIR:?set CUSTOM_CA_DIR in .env}:/custom-ca:ro"


def needs_truststore(args: argparse.Namespace) -> bool:
    return bool(args.custom_ca_dir) and "vortex" in args.components


def truststore_volume_line(args: argparse.Namespace) -> str:
    return "\n      - custom_truststore:/custom-truststore:ro" if needs_truststore(args) else ""


def truststore_completed(args: argparse.Namespace) -> list[str]:
    return ["truststore-init"] if needs_truststore(args) else []


def build_truststore_init(args: argparse.Namespace) -> str:
    if not needs_truststore(args):
        return ""
    return render("compose/truststore-init.tmpl", image=image_ref(args, "truststore-init"))


def sonarqube_image(args: argparse.Namespace, suffix: str) -> str:
    """SonarQube image ref; `suffix` is the edition part of the tag (e.g. `-developer`)."""
    defaults = DEFAULT_IMAGES.get("sonarqube", {})
    registry = args.sonarqube_registry if args.sonarqube_registry is not None else defaults.get("registry", "")
    name = defaults.get("name", "sonarqube")
    tag = args.sonarqube_tag if args.sonarqube_tag is not None else defaults.get("tag", "lts")
    image = f"{registry}/{name}" if registry else name
    return f"{image}:{tag}{suffix}"


def sonarqube_common(args: argparse.Namespace) -> dict[str, str]:
    """Substitutions shared by the single-node SonarQube and every Data Center application node."""
    endpoint, name, user, password = db_env_lines(args)
    server_base_url = "https://${TLS_SERVER_NAME:-localhost}:${SONARQUBE_TLS_PUBLISH_PORT:-9443}" if args.tls_on \
        else "http://localhost:${SONARQUBE_PUBLISH_PORT:-9000}"
    return {
        "db_endpoint": endpoint, "db_name": name, "db_url_params": db_url_params(args),
        "db_user": user, "db_password": password,
        "server_base_url": server_base_url,
        "storage_volume_line": storage_volume_line(args) + secret_key_volume_line(args, SONAR_SECRET_KEY_MOUNT),
    }


def sonarqube_ports_block(args: argparse.Namespace) -> str:
    return "    ports: []  # published by tls-proxy instead" if args.tls_on else \
        "    ports:\n      - \"${SONARQUBE_PUBLISH_PORT:-9000}:9000\""


def extra_hosts_lines(extra_hosts: list[str]) -> str:
    return ("    extra_hosts:\n" + "\n".join(extra_hosts)) if extra_hosts else ""


def depends_on_lines(healthy: list[str], completed: list[str]) -> str:
    return "\n".join(
        [f"      {n}:\n        condition: service_healthy" for n in healthy] +
        [f"      {n}:\n        condition: service_completed_successfully" for n in completed]
    )


def build_sonarqube(args: argparse.Namespace) -> str:
    if args.edition == "none":
        return ""
    if args.edition == "datacenter":
        return build_sonarqube_datacenter(args)
    healthy = ["postgres"] if args.db_mode == "local" else []
    completed = build_storage_services(args)[1] + ["signing-init"]
    return render(
        "compose/sonarqube.tmpl",
        image=sonarqube_image(args, f"-{args.edition}"),
        depends_on_block=depends_on_lines(healthy, completed),
        ports_block=sonarqube_ports_block(args),
        **sonarqube_common(args),
    )


def build_sonarqube_datacenter(args: argparse.Namespace) -> str:
    search_hosts = ",".join(DATACENTER_SEARCH_NODES)
    fragments = [
        render("compose/sonarqube-search.tmpl", node=node, volume_prefix=volume_prefix(node),
               image=sonarqube_image(args, "-datacenter-search"), search_hosts=search_hosts)
        for node in DATACENTER_SEARCH_NODES
    ]
    # Both application nodes must exist from the start (Hazelcast resolves its peers by DNS), so
    # neither depends on the other; they only wait for the search nodes and the one-shot inits.
    healthy = (["postgres"] if args.db_mode == "local" else []) + list(DATACENTER_SEARCH_NODES)
    completed = build_storage_services(args)[1] + ["signing-init"]
    for node, node_ip in zip(DATACENTER_APP_NODES, DATACENTER_APP_NODE_IPS):
        fragments.append(render(
            "compose/sonarqube-app.tmpl",
            node=node, node_ip=f"${{{ip_var(node)}:-{node_ip}}}", volume_prefix=volume_prefix(node),
            image=sonarqube_image(args, "-datacenter-app"), search_hosts=search_hosts,
            depends_on_block=depends_on_lines(healthy, completed),
            **sonarqube_common(args),
        ))
    fragments.append(render(
        "compose/sonarqube-lb.tmpl",
        image=image_ref(args, "sonarqube-lb"),
        depends_on_block=depends_on_lines(list(DATACENTER_APP_NODES), []),
        ports_block=sonarqube_ports_block(args),
    ))
    return "\n".join(fragments)


def sonarqube_url(args: argparse.Namespace) -> tuple[str, list[str]]:
    """Returns (base URL for internal callers, extra_hosts lines) accounting for --edition none."""
    if args.edition == "none":
        host = args.sonarqube_external_host
        # Rancher Desktop/lima map host-gateway to the VM's bridge rather than the host, so this
        # is opt-out: those runtimes already resolve host.docker.internal on their own.
        use_gateway = host == HOST_GATEWAY_NAME and args.host_gateway == "on"
        extra_hosts = [f"      - \"{HOST_GATEWAY_NAME}:host-gateway\""] if use_gateway else []
        if uses_kit(args):
            return f"https://{host}:{SONARQUBE_KIT_PORT}", extra_hosts
        return f"{args.sonarqube_external_scheme}://{host}:{args.sonarqube_external_port}", extra_hosts
    return "http://sonarqube:9000", []


def backing_ports_block(args: argparse.Namespace, port_var: str, default_port: str) -> str:
    """Published ports for the orchestrator/Vortex: none with TLS on, so nothing bypasses the proxy."""
    if not args.tls_on:
        return f"    ports:\n      - \"${{{port_var}:-{default_port}}}:8080\""
    if args.edition == "none":
        return "    ports: []  # published by agentic-proxy instead"
    return "    ports: []  # internal only, SonarQube reaches it over the compose network"


def build_orchestrator(args: argparse.Namespace) -> str:
    sq_url, extra_hosts = sonarqube_url(args)
    endpoint, name, user, password = db_env_lines(args)
    depends_on = []
    if args.edition != "none":
        depends_on.append("sonarqube")
    else:
        depends_on = []
    if args.db_mode == "local":
        depends_on.insert(0, "postgres")
    depends_on += build_storage_services(args)[1]
    depends_on.append("signing-init")
    depends_on_block = "\n".join(
        f"      {n}:\n        condition: service_healthy" if n in ("postgres", "sonarqube") else
        f"      {n}:\n        condition: service_completed_successfully"
        for n in depends_on
    )
    push_urls = []
    if "hunter" in args.components:
        push_urls.append("      AGENTIC_HUNTER_RUNTIME_PUSH_URL: http://hunter-runtime:8090/jobs")
        push_urls.append("      AGENTIC_HUNTER_RUNTIME_SIGNING_KEY_PATH: /run/agentic-signing/orchestrator-to-hunter.key")
    if "remediation" in args.components:
        push_urls.append("      AGENTIC_REMEDIATION_RUNTIME_PUSH_URL: http://remediation-agent-runtime:8090/jobs")
        push_urls.append("      AGENTIC_REMEDIATION_RUNTIME_SIGNING_KEY_PATH: /run/agentic-signing/orchestrator-to-remediation.key")
    extra_hosts_block = extra_hosts_lines(extra_hosts)
    datasource_url_line = ""
    if args.db_mode == "external":
        # application.yml's datasource URL has no hook for extra parameters, so replace it whole;
        # it must stay in step with that URL, ApplicationName included.
        datasource_url_line = (f"\n      SPRING_DATASOURCE_URL: jdbc:postgresql://{endpoint}/{name}"
                               f"?ApplicationName=agentic-orchestrator&{EXTERNAL_DB_SSL_PARAMS}")
    return render(
        "compose/orchestrator.tmpl",
        image=image_ref(args, "agent-orchestrator"),
        db_endpoint=endpoint, db_name=name, db_user=user, db_password=password,
        datasource_url_line=datasource_url_line,
        sonarqube_url=sq_url,
        push_url_lines="\n".join(push_urls),
        depends_on_block=depends_on_block,
        extra_hosts_block=extra_hosts_block,
        ports_block=backing_ports_block(args, "ORCHESTRATOR_PUBLISH_PORT", "9091"),
        github_api_base_url=args.github_api_base_url or "https://api.github.com",
        storage_volume_line=storage_volume_line(args) + custom_ca_volume_line(args)
        + secret_key_volume_line(args, ORCHESTRATOR_SECRET_KEY_MOUNT),
        secret_key_env_line=(f"\n      AGENTIC_SECRET_KEY_PATH: {ORCHESTRATOR_SECRET_KEY_MOUNT}"
                             if args.sonar_secret_key_file else ""),
        read_only_line=("    # Not read_only: the entrypoint imports /custom-ca into the JDK's cacerts."
                        if args.custom_ca_dir else "    read_only: true"),
    )


def build_runtime(args: argparse.Namespace, name: str) -> str:
    if name not in args.components:
        return ""
    template = "compose/hunter-runtime.tmpl" if name == "hunter" else "compose/remediation-runtime.tmpl"
    extra = {}
    if name == "remediation":
        sq_url, extra_hosts = sonarqube_url(args)
        extra["rule_info_endpoint"] = f"{sq_url}/api/rules/show"
        extra["analysis_endpoint"] = f"{sq_url}/api/v2/a3s/private/analyses"
        extra["extra_hosts_block"] = extra_hosts_lines(extra_hosts)
    depends_on = build_storage_services(args)[1] + ["signing-init"]
    depends_on_block = "\n".join(
        f"      {n}:\n        condition: service_completed_successfully" for n in depends_on
    )
    return render(
        template,
        image=image_ref(args, f"{name}-agent" if name == "hunter" else "remediation-agent"),
        sandbox_runtime=args.sandbox,
        depends_on_block=depends_on_block,
        storage_volume_line=storage_volume_line(args, name) + custom_ca_volume_line(args),
        **extra,
    )


def build_egress_proxy(args: argparse.Namespace) -> str:
    if not ({"hunter", "remediation"} & args.components):
        return ""
    sq_url, extra_hosts = sonarqube_url(args)
    sq_scheme = sq_url.split("://", 1)[0]
    sq_host = re.sub(r"^https?://", "", sq_url).split(":")[0]
    sq_port = sq_url.rsplit(":", 1)[-1]
    extra_hosts_block = extra_hosts_lines(extra_hosts)
    return render(
        "compose/egress-proxy.tmpl",
        image=image_ref(args, "egress-proxy"),
        llm_domains=",".join(args.llm_domains),
        storage_allowed_domain=getattr(args, "s3_allowed_domain", ""),
        storage_allowed_port=getattr(args, "s3_allowed_port", ""),
        sqs_proxy_scheme=sq_scheme,
        sqs_proxy_host=sq_host,
        sqs_proxy_port=sq_port,
        orchestrator_proxy_host="orchestrator",
        extra_hosts_block=extra_hosts_block,
    )


def build_vortex(args: argparse.Namespace) -> str:
    if "vortex" not in args.components:
        return ""
    sq_url, extra_hosts = sonarqube_url(args)
    depends_on = []
    if args.edition != "none":
        depends_on.append("sonarqube")
    depends_on += build_storage_services(args)[1] + truststore_completed(args)
    depends_on.append("signing-init")
    depends_on_block = "\n".join(
        f"      {n}:\n        condition: service_healthy" if n == "sonarqube" else
        f"      {n}:\n        condition: service_completed_successfully"
        for n in depends_on
    )
    extra_hosts_block = extra_hosts_lines(extra_hosts)
    return render(
        "compose/vortex.tmpl",
        image=image_ref(args, "vortex"),
        analysis_sonarqube_url=sq_url,
        # The image's entrypoint only defaults JAVA_TOOL_OPTIONS to this heap cap when it's unset.
        truststore_env_line=f"\n      JAVA_TOOL_OPTIONS: -XX:MaxRAMPercentage=50 {TRUSTSTORE_OPTS}"
        if needs_truststore(args) else "",
        depends_on_block=depends_on_block,
        extra_hosts_block=extra_hosts_block,
        ports_block=backing_ports_block(args, "VORTEX_PUBLISH_PORT", "9092"),
        # Vortex only reads the context items SonarQube stores there.
        storage_volume_line=storage_volume_line(args, read_only=True) + truststore_volume_line(args),
    )


def build_tls_proxy(args: argparse.Namespace) -> str:
    if not args.tls_on or args.edition == "none":
        return ""
    return render(
        "compose/tls-proxy.tmpl",
        image=image_ref(args, "tls-proxy"),
        tls_server_name=args.tls_server_name,
    )


def build_agentic_proxy(args: argparse.Namespace) -> str:
    if not args.tls_on or args.edition != "none":
        return ""
    depends_on = []
    if "vortex" in args.components:
        depends_on.append("vortex")
    depends_on.append("orchestrator")
    depends_on_block = "\n".join(f"      {n}:\n        condition: service_healthy" for n in depends_on)
    return render(
        "compose/agentic-proxy.tmpl",
        image=image_ref(args, "tls-proxy"),
        tls_server_name=args.tls_server_name,
        depends_on_block=depends_on_block,
        vortex_flag="1" if "vortex" in args.components else "0",
        vortex_port_line='\n      - "8444:8444"' if "vortex" in args.components else "",
    )


def assemble_compose(args: argparse.Namespace) -> str:
    services = []
    storage_fragment, _ = build_storage_services(args)
    if storage_fragment:
        services.append(storage_fragment)
    truststore_fragment = build_truststore_init(args)
    if truststore_fragment:
        services.append(truststore_fragment)
    services.append(build_signing_init(args))
    for builder in (build_postgres, build_sonarqube, build_orchestrator):
        fragment = builder(args)
        if fragment:
            services.append(fragment)
    for name in ("hunter", "remediation"):
        fragment = build_runtime(args, name)
        if fragment:
            services.append(fragment)
    for builder in (build_egress_proxy, build_vortex, build_tls_proxy, build_agentic_proxy):
        fragment = builder(args)
        if fragment:
            services.append(fragment)

    header = render("compose/header.tmpl", compose_project_name=args.compose_project_name)
    anchors = build_storage_anchors(args)
    networks = build_networks_block(args)
    volumes = build_volumes_block(args)
    services_block = "services:\n" + "\n".join(services)

    return "\n\n".join([header, anchors, networks, volumes, services_block]) + "\n"


# --------------------------------------------------------------------------------------------------
# .env + docs
# --------------------------------------------------------------------------------------------------


def build_env(args: argparse.Namespace) -> str:
    parts = [render("env/header.tmpl")]
    parts.append(f"AGENTIC_SIGNING_SECRET={args.signing_secret}")
    if args.jwt_secret:
        parts.append(f"SONARQUBE_JWT_SECRET={args.jwt_secret}")
        parts.append(f"SONARQUBE_CLUSTER_SUBNET={args.cluster_subnet}")
        for node, node_ip in zip(DATACENTER_APP_NODES, args.app_node_ips):
            parts.append(f"{ip_var(node)}={node_ip}")

    if args.storage == "hostpath":
        parts.append(f"AGENTIC_STORAGE_SOURCE={args.storage_path}")
    if args.storage in ("hostpath", "nfs") and args.edition == "none":
        # The host SonarQube and the containers exchange absolute file paths, so the
        # containers must mount the storage at the same path the host sees it at.
        parts.append(f"AGENTIC_STORAGE_MOUNT={args.storage_path}")
    if args.storage == "s3":
        parts.extend([
            f"AGENTIC_STORAGE_BUCKET={args.s3_bucket}",
            f"AGENTIC_STORAGE_REGION={args.s3_region}",
            f"AGENTIC_STORAGE_ENDPOINT={args.s3_endpoint}",
            f"AGENTIC_STORAGE_ACCESS_KEY={env_str(args.s3_access_key)}",
            f"AGENTIC_STORAGE_SECRET_KEY={env_str(args.s3_secret_key)}",
            f"AGENTIC_STORAGE_PATH_STYLE_ACCESS={args.s3_path_style}",
            f"AGENTIC_STORAGE_PRESIGN_TTL_SECONDS={args.s3_presign_ttl}",
        ])

    if args.tls_on:
        parts.append(f"TLS_SERVER_NAME={args.tls_server_name}")
    if args.custom_ca_dir:
        parts.append(f"CUSTOM_CA_DIR={args.custom_ca_dir}")
    if args.sonar_secret_key_file:
        parts.append(f"SONAR_SECRET_KEY_FILE={args.sonar_secret_key_file}")
    # Never generated: only ever the user's own, carried over from the existing .env.
    parts.extend(f"{key}={value}" for key, value in args.publish_ports.items())

    return "\n".join(parts) + "\n"


def zip_storage_note(args: argparse.Namespace) -> str:
    if args.storage == "hostpath":
        return render("docs/zip-storage-hostpath.tmpl", storage_path=args.storage_path)
    if args.storage == "nfs":
        return render("docs/zip-storage-nfs.tmpl", storage_path=args.storage_path)
    return ""


ZIP_SECRET_KEY_NOTE = """
The orchestrator also reads your SonarQube's settings encryption key, from `SONAR_SECRET_KEY_FILE`
in `.env`, so it can decrypt the `{aes-gcm}` values SonarQube encrypted with it. Point it at the
file your `sonar.secretKeyPath` names (by default `~/.sonar/sonar-secret.txt`).
"""


def zip_https_note(args: argparse.Namespace) -> str:
    if args.sonarqube_external_scheme != "https":
        return ""
    if args.custom_ca_dir:
        return ("Your SonarQube's certificate must be valid for that host name and chain to a CA in "
                "`CUSTOM_CA_DIR` (see step 7) or to a public CA.")
    return ("Your SonarQube's certificate must be valid for that host name and chain to a public CA: "
            "the containers trust nothing else. For a private CA, regenerate with `--custom-ca-dir`.")


def zip_reachability_section(args: argparse.Namespace) -> str:
    if uses_kit(args):
        return render("docs/zip-reachability-kit.tmpl", sonarqube_url=sonarqube_url(args)[0],
                      sonarqube_host=args.sonarqube_external_host,
                      sonarqube_port=args.sonarqube_external_port).rstrip("\n")
    text = render("docs/zip-reachability.tmpl", sonarqube_url=sonarqube_url(args)[0],
                  https_note=zip_https_note(args)).rstrip("\n")
    if uses_bundle_ca(args):
        text += ("\n\nYour SonarQube already serves https, so the containers call it directly: you don't\n"
                 f"need the proxy in `{SONARQUBE_KIT_DIR}/`.")
    return text


def zip_ca_note(args: argparse.Namespace) -> str:
    if not args.custom_ca_dir:
        return ""
    note = render("docs/zip-custom-ca.tmpl", custom_ca_dir=args.custom_ca_dir)
    if not uses_bundle_ca(args):
        return note
    if Path(args.custom_ca_dir).is_absolute():
        return note + (f"\nCopy `tls/ca.crt` from this directory there as `{BUNDLE_CA_FILE}`. It is the CA\n"
                       f"behind `agentic-proxy` and `{SONARQUBE_KIT_DIR}`: the containers reach neither without it.\n")
    return note + (f"\nThe generator put `{BUNDLE_CA_FILE}` there. It is the CA behind `agentic-proxy` and\n"
                   f"`{SONARQUBE_KIT_DIR}`: keep it.\n")


def first_start_steps(args: argparse.Namespace) -> str:
    components = ", ".join(sorted(args.components))
    if args.edition == "none":
        return render("docs/first-start-none.tmpl", components=components).rstrip("\n")
    url = f"https://{args.tls_server_name}:9443" if args.tls_on else "http://localhost:9000"
    return render("docs/first-start-bundled.tmpl", sonarqube_url=url, components=components).rstrip("\n")


def build_docs(args: argparse.Namespace) -> dict[str, str]:
    docs = {"README.md": render(
        "docs/readme.tmpl",
        edition=args.edition,
        components=", ".join(sorted(args.components)),
        storage=args.storage,
        tls="enabled" if args.tls_on else "disabled",
        sandbox=args.sandbox,
        project_name=args.compose_project_name,
        edition_note=render("docs/readme-datacenter.tmpl", cluster_subnet=DATACENTER_CLUSTER_SUBNET)
        if args.edition == "datacenter" else "",
        first_start=first_start_steps(args),
    )}
    if args.edition == "none":
        vortex_url = f"https://{args.tls_server_name}:8444" if args.tls_on else "http://localhost:9092"
        docs["ZIP-INSTRUCTIONS.md"] = render(
            "docs/zip-instructions.tmpl",
            db_host=args.db_host, db_port=args.db_port, db_name=args.db_name, db_user=args.db_user,
            db_url_params=db_url_params(args),
            reachability_section=zip_reachability_section(args),
            ca_note=zip_ca_note(args),
            orchestrator_url=f"https://{args.tls_server_name}:8443" if args.tls_on else "http://localhost:9091",
            vortex_lines=f"sonar.vortex.enabled=true\nsonar.vortex.analysis.url={vortex_url}"
            if "vortex" in args.components else "sonar.vortex.enabled=false",
            secret_key_note=ZIP_SECRET_KEY_NOTE if args.sonar_secret_key_file else "",
            urls_note="Both are served by `agentic-proxy`; the orchestrator and Vortex publish no plain "
                      "port in this bundle." if args.tls_on else
                      "These are the ports published by this bundle; use `ORCHESTRATOR_PUBLISH_PORT`/"
                      "`VORTEX_PUBLISH_PORT` from `.env` instead if you set them.",
            storage_note=zip_storage_note(args),
            tls_section=render("docs/zip-tls-trust.tmpl", tls_server_name=args.tls_server_name)
            if args.tls_on else "TLS is disabled in this bundle; every hop is plain HTTP.",
        )
    return docs


def build_kit(args: argparse.Namespace) -> dict[str, str]:
    """The sonarqube-tls-proxy kit, keyed by path relative to the bundle; empty unless emitted."""
    if not uses_bundle_ca(args):
        return {}
    subs = {"image": image_ref(args, "tls-proxy"), "server_name": args.sonarqube_external_host,
            "upstream_port": args.sonarqube_external_port, "kit_port": SONARQUBE_KIT_PORT}
    return {
        f"{SONARQUBE_KIT_DIR}/docker-compose.yaml": render("kit/docker-compose.tmpl", **subs),
        f"{SONARQUBE_KIT_DIR}/README.md": render("kit/readme.tmpl", **subs),
        f"{SONARQUBE_KIT_DIR}/nginx/sonarqube-tls.conf": render("kit/sonarqube-tls.conf.tmpl", **subs),
        f"{SONARQUBE_KIT_DIR}/entrypoint.sh": (HERE / "tls-proxy" / "entrypoint.sh").read_text(),
        f"{SONARQUBE_KIT_DIR}/nginx.kit.conf.template": (HERE / "tls-proxy" / "nginx.kit.conf.template").read_text(),
    }


# --------------------------------------------------------------------------------------------------
# Bundle CA (--edition none --tls on)
# --------------------------------------------------------------------------------------------------

CA_CONFIG = """[req]
distinguished_name = dn
prompt = no
[dn]
CN = SonarQube agentic bundle CA
[v3_ca]
basicConstraints = critical,CA:TRUE,pathlen:0
keyUsage = critical,keyCertSign,cRLSign
subjectKeyIdentifier = hash
"""

# Python 3.13's strict verification, in the agent runtimes, also wants the key identifiers.
LEAF_CONFIG = """[req]
distinguished_name = dn
prompt = no
[dn]
CN = {cn}
[v3_leaf]
basicConstraints = critical,CA:FALSE
keyUsage = critical,digitalSignature,keyEncipherment
extendedKeyUsage = serverAuth
subjectAltName = {san}
subjectKeyIdentifier = hash
authorityKeyIdentifier = keyid
"""


def san_entries(names: list[str]) -> str:
    entries = []
    for name in dict.fromkeys(names):
        try:
            ipaddress.ip_address(name)
            entries.append(f"IP:{name}")
        except ValueError:
            entries.append(f"DNS:{name}")
    return ",".join(entries)


def openssl(workdir: str, *argv: str) -> str:
    result = subprocess.run(["openssl", *argv], cwd=workdir, capture_output=True, text=True)
    if result.returncode != 0:
        raise ConfigError(f"openssl {argv[0]} failed: {result.stderr.strip()}")
    return result.stdout


def normalize_name(name: str) -> str:
    try:
        return str(ipaddress.ip_address(name))
    except ValueError:
        return name.lower()


def cert_names(cert: Path) -> set[str]:
    """The DNS and IP SANs of the first certificate in `cert`; `-text` rather than `-ext`, which
    LibreSSL lacks."""
    text = openssl(str(cert.parent), "x509", "-in", cert.name, "-noout", "-text")
    match = re.search(r"X509v3 Subject Alternative Name:.*?\n\s*(.+)", text)
    names = set()
    for entry in (match.group(1).split(",") if match else []):
        kind, _, value = entry.strip().partition(":")
        if kind in ("DNS", "IP Address", "IP"):
            names.add(normalize_name(value.strip()))
    return names


def bundle_cert_leaves(args: argparse.Namespace, out_dir: Path) -> dict[Path, list[str]]:
    return {
        # localhost and loopback, as tls-proxy/entrypoint.sh does for its self-signed certificates.
        out_dir / "tls" / "agentic-proxy": [args.tls_server_name, "localhost", "127.0.0.1", "0:0:0:0:0:0:0:1"],
        out_dir / SONARQUBE_KIT_DIR / "tls": [args.sonarqube_external_host],
    }


def check_bundle_certs(args: argparse.Namespace, out_dir: Path) -> tuple[bool, list[str]]:
    """Whether the bundle CA and certificates must be (re)issued. Run before anything is written, so
    a refusal leaves the bundle as it was."""
    leaves = bundle_cert_leaves(args, out_dir)
    existing = [out_dir / "tls" / CA_CERT_FILE] + [d / f for d in leaves for f in (LEAF_CERT_FILE, "tls.key")]
    if not all(path.exists() for path in existing):
        return True, ["issued a CA for this bundle (tls/ca.crt) and certificates for agentic-proxy and "
                      "sonarqube-tls-proxy; the CA key was not kept."]
    mismatched = [leaf_dir.relative_to(out_dir).as_posix() for leaf_dir, names in leaves.items()
                  if cert_names(leaf_dir / LEAF_CERT_FILE) != {normalize_name(n) for n in names}]
    if not mismatched:
        return False, ["kept the certificates already in tls/ and sonarqube-tls-proxy/tls/; delete tls/ "
                       "to issue new ones."]
    if not args.force:
        raise ConfigError(f"the certificates in {', '.join(mismatched)} don't cover the current "
                          f"--tls-server-name/--sonarqube-external-host. Rerun with --force to issue "
                          f"a new CA and certificates, then re-import tls/ca.crt wherever you trust it")
    return True, ["--force: reissued the bundle CA and both certificates because their names changed; "
                  "re-import the new tls/ca.crt everywhere you trusted the old one."]


def write_bundle_certs(args: argparse.Namespace, out_dir: Path, reissue: bool) -> list[str]:
    """Issues the bundle CA and both proxies' certificates when `reissue`, then hands the CA to the
    containers."""
    ca_cert = out_dir / "tls" / CA_CERT_FILE
    leaves = bundle_cert_leaves(args, out_dir)
    notes = []
    if reissue:
        with tempfile.TemporaryDirectory() as work:
            Path(work, "ca.cnf").write_text(CA_CONFIG)
            openssl(work, "req", "-x509", "-new", "-newkey", "rsa:2048", "-nodes", "-sha256", "-days", "3650",
                    "-config", "ca.cnf", "-extensions", "v3_ca", "-keyout", "ca.key", "-out", CA_CERT_FILE)
            ca_cert.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(Path(work, CA_CERT_FILE), ca_cert)
            for leaf_dir, names in leaves.items():
                Path(work, LEAF_CONFIG_FILE).write_text(LEAF_CONFIG.format(cn=names[0], san=san_entries(names)))
                openssl(work, "req", "-new", "-newkey", "rsa:2048", "-nodes", "-config", LEAF_CONFIG_FILE,
                        "-keyout", "leaf.key", "-out", "leaf.csr")
                # 825 days: the longest lifetime Safari and Chrome still accept for a leaf certificate.
                openssl(work, "x509", "-req", "-in", "leaf.csr", "-CA", CA_CERT_FILE, "-CAkey", "ca.key",
                        "-set_serial", str(secrets.randbits(127)), "-days", "825", "-sha256",
                        "-extfile", LEAF_CONFIG_FILE, "-extensions", "v3_leaf", "-out", "leaf.crt")
                leaf_dir.mkdir(parents=True, exist_ok=True)
                # Full chain, so a client that only has the CA can still build the path.
                (leaf_dir / LEAF_CERT_FILE).write_text(Path(work, "leaf.crt").read_text() + Path(work, CA_CERT_FILE).read_text())
                write_file(leaf_dir / "tls.key", Path(work, "leaf.key").read_bytes(), 0o600)

    if Path(args.custom_ca_dir).is_absolute():
        notes.append(f"copy tls/ca.crt into {args.custom_ca_dir} as {BUNDLE_CA_FILE}: the containers "
                     f"can't reach agentic-proxy or your SonarQube without it.")
    else:
        shutil.copyfile(ca_cert, out_dir / args.custom_ca_dir / BUNDLE_CA_FILE)
    return notes


# --------------------------------------------------------------------------------------------------
# Validation scans (rule 6) + entrypoint
# --------------------------------------------------------------------------------------------------


def scan_forbidden(files: dict[str, str]) -> list[str]:
    """Checks each bundle file, keyed by its bundle-relative name, for forbidden strings and leftovers."""
    problems = []
    for needle in FORBIDDEN_STRINGS:
        for label, text in files.items():
            if needle in text:
                problems.append(f"forbidden string leaked into output: {needle!r} in {label}")
    for label, text in files.items():
        for match in re.finditer(r"\$\{([A-Za-z_]\w*)\}", text, re.ASCII):
            problems.append(f"leftover unresolved placeholder ${{{match.group(1)}}} in {label}")
    return problems


def proxy_assets(args: argparse.Namespace) -> dict[str, Path]:
    """Bundle-relative path -> source file, for the proxy configs mounted into the containers."""
    names = ["egress-proxy", "tls-proxy"]
    if args.edition == "datacenter":
        names.append("sonarqube-lb")
    return {src.relative_to(HERE).as_posix(): src
            for name in names for src in sorted((HERE / name).rglob("*")) if src.is_file()}


# --------------------------------------------------------------------------------------------------
# Regeneration: an existing bundle keeps its secrets, and files edited since the last run are only
# overwritten with --force.
# --------------------------------------------------------------------------------------------------


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


# The host ports the compose publishes on; the README tells users to set them in .env.
PUBLISH_PORT_KEYS = ("SONARQUBE_PUBLISH_PORT", "SONARQUBE_TLS_PUBLISH_PORT", "ORCHESTRATOR_PUBLISH_PORT",
                     "VORTEX_PUBLISH_PORT")
# Kept from the existing .env by reuse_env_values, so editing them isn't a user edit.
CARRIED_ENV_KEYS = frozenset({"SONARQUBE_CLUSTER_SUBNET", *(ip_var(node) for node in DATACENTER_APP_NODES),
                              *PUBLISH_PORT_KEYS})


def file_digest(rel: str, data: bytes) -> str:
    """The manifest checksum of a bundle file; for .env, without the keys carried over from the
    existing one."""
    if rel != ".env":
        return sha256(data)
    lines = [line for line in data.decode().splitlines()
             if line.partition("=")[0].strip() not in CARRIED_ENV_KEYS]
    return sha256("\n".join(lines).encode())


def read_manifest(out_dir: Path) -> dict[str, str]:
    path = out_dir / MANIFEST_FILE
    if not path.exists():
        return {}
    try:
        files = json.loads(path.read_text()).get("files", {})
    except (ValueError, AttributeError) as exc:
        raise ConfigError(f"{path} is corrupt; delete it and rerun with --force") from exc
    return files if isinstance(files, dict) else {}


def read_env_values(env_file: Path) -> dict[str, str]:
    values = {}
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            key, sep, value = line.partition("=")
            if sep and not key.lstrip().startswith("#"):
                # compose uses the last occurrence of a duplicated key.
                values[key.strip()] = value.strip()
    return values


def reuse_env_values(args: argparse.Namespace, out_dir: Path) -> list[str]:
    """Carries the existing bundle's secrets over: a new signing secret would break every job in
    flight, and a new JWT secret would log every Data Center user out. Also keeps the cluster
    addresses and published ports the README tells users to edit in .env, so that edit doesn't
    block regeneration."""
    existing = read_env_values(out_dir / ".env")
    args.cluster_subnet = existing.get("SONARQUBE_CLUSTER_SUBNET") or DATACENTER_CLUSTER_SUBNET
    args.app_node_ips = [existing.get(ip_var(node)) or node_ip
                         for node, node_ip in zip(DATACENTER_APP_NODES, DATACENTER_APP_NODE_IPS)]
    args.publish_ports = {key: existing[key] for key in PUBLISH_PORT_KEYS if existing.get(key)}
    if args.rotate_secrets:
        return ["--rotate-secrets: minted new secrets; restart the whole stack with the new .env."] \
            if (out_dir / ".env").exists() else []
    notes = []
    if existing.get("AGENTIC_SIGNING_SECRET"):
        args.signing_secret = existing["AGENTIC_SIGNING_SECRET"]
        notes.append("kept the signing secret from the existing .env; pass --rotate-secrets for a new one.")
    if args.jwt_secret and existing.get("SONARQUBE_JWT_SECRET"):
        args.jwt_secret = existing["SONARQUBE_JWT_SECRET"]
    return notes


def plan_writes(out_dir: Path, files: dict[str, bytes], force: bool) -> tuple[dict[str, list[str]], list[str]]:
    """Sorts `files` into created/updated/unchanged and finds files the last run wrote that this one
    doesn't. Raises unless --force when a file to overwrite was edited since it was generated, or
    was never written by the generator at all."""
    manifest = read_manifest(out_dir)
    plan: dict[str, list[str]] = {"created": [], "updated": [], "unchanged": []}
    edited = []
    for rel, data in files.items():
        path = out_dir / rel
        if not path.exists():
            plan["created"].append(rel)
            continue
        current = path.read_bytes()
        if current == data:
            plan["unchanged"].append(rel)
            continue
        if manifest.get(rel) != file_digest(rel, current):
            edited.append(rel)
        plan["updated"].append(rel)
    if edited and not force:
        raise ConfigError(f"{out_dir} has files that differ from what the generator last wrote there: "
                          f"{', '.join(edited)}. Move your changes into a docker-compose.override.yaml, which "
                          f"the generator never writes, or rerun with --force to overwrite them")
    stale = [rel for rel in manifest if rel not in files]
    return plan, stale


def write_file(path: Path, data: bytes, mode: int | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if mode is None:
        path.write_bytes(data)
        return
    # Created with the final mode, so a secret is never readable by others, even briefly.
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, mode)
    with os.fdopen(fd, "wb") as handle:
        os.fchmod(handle.fileno(), mode)
        handle.write(data)


def remove_stale(out_dir: Path, stale: list[str], manifest: dict[str, str]) -> list[str]:
    notes = []
    for rel in stale:
        path = out_dir / rel
        if not path.exists():
            continue
        if file_digest(rel, path.read_bytes()) == manifest.get(rel):
            path.unlink()
            notes.append(f"removed {rel}: no longer part of this bundle.")
        else:
            notes.append(f"left {rel} in place: no longer part of this bundle, but edited since it was generated.")
    return notes


INPUTS_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "SonarQube agentic Docker Compose generator inputs",
    "type": "object",
    "required": ["edition"],
    # load_config rejects any other key too, so a misspelt one can't silently fall back to a default.
    "additionalProperties": False,
    "properties": {
        "edition": {"type": "string", "enum": list(EDITIONS)},
        "components": {"type": "string", "default": "hunter,remediation,vortex"},
        "db_mode": {"type": "string", "enum": list(DB_MODES), "default": "local"},
        "db_host": {"type": "string"},
        "db_port": {"type": "string", "default": "5432"},
        "db_name": {"type": "string", "default": "sonarqube"},
        "db_user": {"type": "string", "default": "sonarqube"},
        "db_password": {"type": "string"},
        "storage": {"type": "string", "enum": list(STORAGE_MODES), "default": "local"},
        "storage_path": {"type": "string",
                         "description": "absolute host path; with storage nfs and edition none, where "
                                        "the SonarQube host mounts the export"},
        "nfs_server": {"type": "string"},
        "nfs_export": {"type": "string"},
        "s3_bucket": {"type": "string", "default": "agentic-jobs"},
        "s3_region": {"type": "string", "default": "us-east-1"},
        "s3_endpoint": {"type": "string"},
        "s3_access_key": {"type": "string"},
        "s3_secret_key": {"type": "string"},
        "s3_path_style": {"type": "string", "enum": ["true", "false"],
                          "description": "defaults to true with s3_endpoint, false on AWS"},
        "s3_presign_ttl": {"type": "string", "default": "21600"},
        "sandbox": {"type": "string", "pattern": SANDBOX_RUNTIME_RE.pattern, "default": "runsc"},
        "tls": {"type": "string", "enum": ["on", "off"], "default": "on"},
        "tls_server_name": {"type": "string", "default": "localhost"},
        "image_registry": {"type": "string",
                            "description": "overrides registry for every agentic component image, "
                                            "blank for the official Docker Hub image; "
                                            "per-component defaults in default-images.json"},
        "image_tag": {"type": "string",
                      "description": "overrides tag for every agentic component image; "
                                      "per-component defaults in default-images.json"},
        "sonarqube_registry": {"type": "string",
                                "description": "defaults to default-images.json's sonarqube.registry "
                                                "(blank for the official Docker Hub image)"},
        "sonarqube_tag": {"type": "string",
                           "description": "defaults to default-images.json's sonarqube.tag"},
        "llm_domains": {"type": "string", "default": "api.anthropic.com"},
        "github_api_base_url": {"type": "string"},
        "sonarqube_external_host": {"type": "string", "default": HOST_GATEWAY_NAME},
        "sonarqube_external_port": {"type": "string", "default": "9000"},
        "host_gateway": {"type": "string", "enum": ["on", "off"], "default": "on"},
        "sonarqube_external_scheme": {"type": "string", "enum": ["http", "https"], "default": "http"},
        "custom_ca_dir": {"type": "string",
                          "description": "host directory of PEM CA certs every container trusts; "
                                          "relative paths resolve against the bundle directory"},
        "sonar_secret_key_file": {"type": "string",
                                  "description": "host file holding SonarQube's settings encryption key, "
                                                  "shared with the orchestrator; relative paths resolve "
                                                  "against the bundle directory"},
        "project_name": {"type": "string", "pattern": PROJECT_NAME_RE.pattern,
                         "description": "compose project name; defaults to agentic-<edition>"},
    },
}


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv

    if "--print-inputs-schema" in argv:
        print(json.dumps(INPUTS_SCHEMA, indent=2))
        return 0

    try:
        args, _parser = load_config(argv)
        notes = validate_and_normalize(args)
    except ConfigError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    for note in notes:
        print(f"note: {note}", file=sys.stderr)

    compose_text = assemble_compose(args)
    docs = build_docs(args)
    kit = build_kit(args)
    sonar_properties = build_sonarqube_properties(args)

    # write_bundle only carries over secrets and cluster addresses into .env, so the scan holds for it too.
    # The docs and the kit land in the bundle as well, so they are scanned with the compose file.
    problems = scan_forbidden({"docker-compose.yaml": compose_text, "sonarqube/sonar.properties": sonar_properties,
                               ".env": build_env(args), **docs, **kit})
    if problems:
        for problem in problems:
            print(f"error: {problem}", file=sys.stderr)
        return 1

    out = args.out or f"out/{args.edition}"
    if out == "-":
        print(compose_text)
        return 0

    try:
        return write_bundle(args, Path(out), compose_text, sonar_properties, {**docs, **kit})
    except ConfigError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"error: cannot write the bundle to {out}: {exc.strerror or exc} "
              f"({exc.filename or out})", file=sys.stderr)
        return 1


def write_bundle(args: argparse.Namespace, out_dir: Path, compose_text: str, sonar_properties: str,
                 texts: dict[str, str]) -> int:
    notes = reuse_env_values(args, out_dir)
    env_text = build_env(args)

    files: dict[str, bytes] = {"docker-compose.yaml": compose_text.encode(), ".env": env_text.encode()}
    files.update({rel: content.encode() for rel, content in texts.items()})
    if sonar_properties:
        files["sonarqube/sonar.properties"] = sonar_properties.encode()
    assets = proxy_assets(args)
    files.update({rel: src.read_bytes() for rel, src in assets.items()})

    manifest = read_manifest(out_dir)
    plan, stale = plan_writes(out_dir, files, args.force)
    reissue_certs, cert_notes = check_bundle_certs(args, out_dir) if uses_bundle_ca(args) else (False, [])
    out_dir.mkdir(parents=True, exist_ok=True)
    for rel in plan["created"] + plan["updated"]:
        write_file(out_dir / rel, files[rel], 0o600 if rel == ".env" else None)
        if rel in assets:
            shutil.copymode(assets[rel], out_dir / rel)
    # An .env from an older run may still be world-readable.
    (out_dir / ".env").chmod(0o600)
    notes += remove_stale(out_dir, stale, manifest)
    if plan["updated"]:
        notes.append(f"updated {', '.join(plan['updated'])}.")
    write_file(out_dir / MANIFEST_FILE, (json.dumps(
        {"files": {rel: file_digest(rel, data) for rel, data in sorted(files.items())}}, indent=2) + "\n").encode())

    if args.custom_ca_dir and not Path(args.custom_ca_dir).is_absolute():
        # Created here so the certs have somewhere to go, and so Docker doesn't create a
        # root-owned empty one on the first `up`.
        (out_dir / args.custom_ca_dir).mkdir(parents=True, exist_ok=True)
    if uses_bundle_ca(args):
        notes += cert_notes + write_bundle_certs(args, out_dir, reissue_certs)
    for note in notes:
        print(f"note: {note}", file=sys.stderr)

    print(f"wrote bundle to {out_dir}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
