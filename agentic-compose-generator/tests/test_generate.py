"""Unit tests for generate.py: input validation, the output scans and regeneration.

Stdlib only, like the generator. Run from agentic-compose-generator/ with:
  python3 -m unittest discover -s tests -v
"""

import contextlib
import importlib.util
import io
import json
import stat
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT_PATH = Path(__file__).resolve().parent.parent / "generate.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("generate", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules["generate"] = module
    spec.loader.exec_module(module)
    return module


gen = _load_module()


def run(*argv: str) -> tuple[int, str, str]:
    stdout, stderr = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        code = gen.main(list(argv))
    return code, stdout.getvalue(), stderr.getvalue()


def env_value(bundle: Path, key: str) -> str:
    for line in (bundle / ".env").read_text().splitlines():
        if line.startswith(f"{key}="):
            return line.split("=", 1)[1]
    raise AssertionError(f"{key} not in .env")


class InputsSchemaTest(unittest.TestCase):
    def test_schema_is_json_and_requires_edition(self):
        code, out, _ = run("--print-inputs-schema")
        self.assertEqual(code, 0)
        schema = json.loads(out)
        self.assertEqual(schema["required"], ["edition"])
        self.assertIn("storage", schema["properties"])

    def test_every_profile_matches_the_schema_keys(self):
        properties = set(json.loads(run("--print-inputs-schema")[1])["properties"])
        for profile in sorted((SCRIPT_PATH.parent / "profiles").glob("*.json")):
            with self.subTest(profile=profile.name):
                self.assertLessEqual(set(json.loads(profile.read_text())), properties)


class ProfilesTest(unittest.TestCase):
    # tests/lint.sh also validates these bundles with `docker compose config`; this runs without Docker.
    def test_every_profile_generates(self):
        for profile in sorted((SCRIPT_PATH.parent / "profiles").glob("*.json")):
            with self.subTest(profile=profile.name), tempfile.TemporaryDirectory() as tmp:
                bundle = Path(tmp) / "bundle"
                code, _, err = run("--profile", str(profile), "--out", str(bundle))
                self.assertEqual(code, 0, err)
                self.assertTrue((bundle / "docker-compose.yaml").is_file())
                self.assertTrue((bundle / gen.MANIFEST_FILE).is_file())


class RefusalsTest(unittest.TestCase):
    def assert_refused(self, *argv: str, message: str):
        code, out, err = run(*argv, "--out", "-")
        self.assertEqual(code, 1, err)
        self.assertEqual(out, "")
        self.assertIn(message, err)

    def test_nfs_without_server(self):
        self.assert_refused("--edition", "developer", "--storage", "nfs", message="--nfs-server")

    def test_edition_none_with_local_storage(self):
        self.assert_refused("--edition", "none", "--storage", "local", message="--storage")

    def test_external_db_without_host(self):
        self.assert_refused("--edition", "developer", "--db", "external", "--db-password", "x",
                            message="--db-host")

    def test_unknown_profile_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            profile = Path(tmp) / "p.json"
            profile.write_text(json.dumps({"edition": "developer", "storgae": "local"}))
            self.assert_refused("--profile", str(profile), message="storgae")


class ScanForbiddenTest(unittest.TestCase):
    def test_leftover_placeholder(self):
        problems = gen.scan_forbidden("image: ${UNRESOLVED}\n", "")
        self.assertEqual(len(problems), 1)
        self.assertIn("UNRESOLVED", problems[0])

    def test_compose_defaults_are_not_placeholders(self):
        self.assertEqual(gen.scan_forbidden("port: ${PORT:-9000}\n", "A=b\n"), [])

    def test_forbidden_strings(self):
        saved = gen.FORBIDDEN_STRINGS
        gen.FORBIDDEN_STRINGS = ("do-not-ship",)
        try:
            self.assertEqual(len(gen.scan_forbidden("x: do-not-ship\n", "")), 1)
            self.assertEqual(len(gen.scan_forbidden("", "X=do-not-ship\n")), 1)
            self.assertEqual(gen.scan_forbidden("x: fine\n", ""), [])
        finally:
            gen.FORBIDDEN_STRINGS = saved

    def test_docs_are_scanned(self):
        # The heading of the bundle README, which appears nowhere in the compose file or .env.
        saved = gen.FORBIDDEN_STRINGS
        gen.FORBIDDEN_STRINGS = ("agentic pack — generated bundle",)
        try:
            code, out, err = run("--edition", "developer", "--out", "-")
        finally:
            gen.FORBIDDEN_STRINGS = saved
        self.assertEqual(code, 1, err)
        self.assertIn("forbidden string leaked into output", err)


class LoadConfigTest(unittest.TestCase):
    def test_abbreviated_flags_are_refused(self):
        # An abbreviation would escape the CLI-over-profile check, so argparse must reject it.
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            gen.load_config(["--edition", "developer", "--db-pass", "x"])


class S3EgressTest(unittest.TestCase):
    def resolve(self, *argv: str):
        args, _parser = gen.load_config(["--edition", "developer", "--storage", "s3",
                                         "--s3-bucket", "jobs", "--s3-region", "eu-west-1", *argv])
        notes = gen.validate_and_normalize(args)
        return args, notes

    def test_aws_defaults_to_virtual_hosted_bucket_host(self):
        args, notes = self.resolve()
        self.assertEqual(args.s3_path_style, "false")
        self.assertEqual(args.s3_allowed_domain, "jobs.s3.eu-west-1.amazonaws.com")
        self.assertEqual(args.s3_allowed_port, "443")
        self.assertFalse([n for n in notes if "s3-path-style" in n])

    def test_aws_path_style_allowlists_the_regional_host(self):
        args, notes = self.resolve("--s3-path-style", "true")
        self.assertEqual(args.s3_allowed_domain, "s3.eu-west-1.amazonaws.com")
        self.assertTrue([n for n in notes if "every bucket in the region" in n])

    def test_endpoint_defaults_to_path_style(self):
        args, _notes = self.resolve("--s3-endpoint", "http://minio:9000")
        self.assertEqual(args.s3_path_style, "true")
        self.assertEqual(args.s3_allowed_domain, "minio")
        self.assertEqual(args.s3_allowed_port, "9000")

    def test_endpoint_keeps_an_explicit_style(self):
        args, _notes = self.resolve("--s3-endpoint", "https://s3.example.com", "--s3-path-style", "false")
        self.assertEqual(args.s3_path_style, "false")
        self.assertEqual(args.s3_allowed_port, "443")


class ImageRefTest(unittest.TestCase):
    def args(self, *argv: str):
        args, _ = gen.load_config(["--edition", "developer", *argv])
        gen.validate_and_normalize(args)
        return args

    def test_defaults_are_public_docker_hub_images(self):
        args = self.args()
        for component in gen.AGENTIC_IMAGES:
            self.assertTrue(gen.image_ref(args, component).startswith("sonarsource/"), component)

    def test_image_tag_overrides_agentic_images_only(self):
        args = self.args("--image-tag", "9.9.9")
        self.assertTrue(gen.image_ref(args, "agent-orchestrator").endswith(":9.9.9"))
        self.assertNotIn("9.9.9", gen.image_ref(args, "postgres"))

    def test_third_party_images_are_pinned_by_digest(self):
        for component, image in gen.DEFAULT_IMAGES.items():
            if component in gen.AGENTIC_IMAGES or component == "sonarqube":
                continue
            with self.subTest(component=component):
                self.assertTrue(image.get("digest", "").startswith("sha256:"))


class RegenerationTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.bundle = Path(self._tmp.name) / "bundle"

    def tearDown(self):
        self._tmp.cleanup()

    def generate(self, *extra: str) -> tuple[int, str]:
        code, _, err = run("--edition", "developer", "--tls", "off", "--out", str(self.bundle), *extra)
        return code, err

    def test_env_is_private(self):
        self.assertEqual(self.generate()[0], 0)
        self.assertEqual(stat.S_IMODE((self.bundle / ".env").stat().st_mode), 0o600)

    def test_signing_secret_is_kept_then_rotated(self):
        self.assertEqual(self.generate()[0], 0)
        secret = env_value(self.bundle, "AGENTIC_SIGNING_SECRET")
        self.assertGreaterEqual(len(secret), 32)

        self.assertEqual(self.generate()[0], 0)
        self.assertEqual(env_value(self.bundle, "AGENTIC_SIGNING_SECRET"), secret)

        self.assertEqual(self.generate("--rotate-secrets")[0], 0)
        self.assertNotEqual(env_value(self.bundle, "AGENTIC_SIGNING_SECRET"), secret)

    def test_user_edit_needs_force(self):
        self.assertEqual(self.generate()[0], 0)
        compose = self.bundle / "docker-compose.yaml"
        compose.write_text(compose.read_text() + "# my edit\n")

        code, err = self.generate()
        self.assertEqual(code, 1)
        self.assertIn("docker-compose.yaml", err)
        self.assertIn("# my edit", compose.read_text())

        self.assertEqual(self.generate("--force")[0], 0)
        self.assertNotIn("# my edit", compose.read_text())


if __name__ == "__main__":
    unittest.main()
