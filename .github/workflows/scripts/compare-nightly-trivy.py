#!/usr/bin/env python3
"""Compare retained nightly policy summaries without executing artifact contents."""

import argparse
import io
import json
import re
import subprocess
import zipfile
from itertools import islice
from pathlib import Path
from urllib.parse import quote

MAX_ARCHIVE_BYTES = 32 * 1024 * 1024
MAX_SUMMARY_BYTES = 2 * 1024 * 1024
# Slack cuts attachment text at about 2000 characters.
MAX_MESSAGE_BYTES = 1800
MAX_BASELINE_RUNS = 100
SCAN_JOB_NAME = re.compile(r"Security Scan \(([a-z-]+)\)")
ARTIFACT_NAME = re.compile(r"trivy-([a-z-]+)-attempt-(\d+)")


def api(path):
    """Use gh's authenticated transport, including its artifact redirect handling."""
    return subprocess.check_output(["gh", "api", path], timeout=120)


def pages(path, key):
    page = 1
    while True:
        separator = "&" if "?" in path else "?"
        items = json.loads(api(f"{path}{separator}per_page=100&page={page}"))[key]
        yield from items
        if len(items) < 100:
            return
        page += 1


def eligible(run, branches, workflow_id):
    return (
        run.get("workflow_id") == workflow_id
        and run.get("event") == "workflow_dispatch"
        and run.get("status") == "completed"
        and run.get("display_title", "").startswith("Nightly CI (")
        and run.get("head_branch") in branches
    )


def previous_run(current, runs, branches):
    # GitHub returns workflow runs in descending creation order.
    for run in runs:
        if (eligible(run, branches, current["workflow_id"])
                and run["head_branch"] == current["head_branch"]
                and run["run_number"] < current["run_number"]):
            return run
    return None


def summary_findings(archive, edition):
    with zipfile.ZipFile(io.BytesIO(archive)) as zipped:
        info = zipped.getinfo(f"trivy-{edition}-summary.json")
        if info.file_size > MAX_SUMMARY_BYTES:
            raise ValueError("Summary exceeds size limit")
        summary = json.loads(zipped.read(info))
    return parse_summary(summary)


def parse_summary(summary):
    if (not isinstance(summary, dict) or summary.get("schema_version") != 1
            or not isinstance(summary.get("reports"), list) or not summary["reports"]):
        raise ValueError("Unsupported or empty summary")
    findings = set()
    for report in summary["reports"]:
        if not isinstance(report, dict) or not isinstance(report.get("violations"), list):
            raise ValueError("Invalid violations array")
        for finding in report["violations"]:
            if not isinstance(finding, dict):
                raise ValueError("Invalid finding")
            identity = (finding["id"], finding.get("package", ""))
            if not isinstance(identity[0], str) or not identity[0] or not isinstance(identity[1], str):
                raise ValueError("Invalid finding identity")
            findings.add(identity)
    return findings


def selected_artifacts(artifacts, attempt):
    selected = {}
    for artifact in artifacts:
        match = ARTIFACT_NAME.fullmatch(artifact["name"])
        if not match or int(match[2]) > attempt:
            continue
        edition, number = match[1], int(match[2])
        if edition not in selected or number > selected[edition][0]:
            selected[edition] = (number, artifact)
    return {edition: item[1] for edition, item in selected.items()}


def scan_attempts(root, run):
    attempts = {}
    for job in pages(f"{root}/actions/runs/{run['id']}/jobs?filter=all", "jobs"):
        match = SCAN_JOB_NAME.fullmatch(job["name"])
        if match and job["run_attempt"] <= run["run_attempt"]:
            edition = match[1]
            attempts[edition] = max(attempts.get(edition, 0), job["run_attempt"])
    return attempts


def load_findings(root, run):
    findings = {}
    attempts = scan_attempts(root, run) if run["run_attempt"] > 1 else None
    artifacts = pages(f"{root}/actions/runs/{run['id']}/artifacts", "artifacts")
    for edition, artifact in selected_artifacts(artifacts, run["run_attempt"]).items():
        expected_attempt = attempts.get(edition) if attempts is not None else 1
        if int(ARTIFACT_NAME.fullmatch(artifact["name"])[2]) != expected_attempt:
            print(f"Skipping Trivy artifact without a matching scan attempt for {edition}.")
            continue
        try:
            findings[edition] = artifact_findings(root, artifact, edition)
        except (KeyError, ValueError, zipfile.BadZipFile, subprocess.SubprocessError):
            # Do not log artifact data or transport errors, which may contain secrets.
            print(f"Skipping unusable Trivy artifact for {edition}.")
    return findings


def artifact_findings(root, artifact, edition):
    if artifact["expired"] or artifact["size_in_bytes"] > MAX_ARCHIVE_BYTES:
        raise ValueError("Scan-attempt artifact unavailable or too large")
    archive = api(f"{root}/actions/artifacts/{int(artifact['id'])}/zip")
    if len(archive) > MAX_ARCHIVE_BYTES:
        raise ValueError("Artifact exceeds size limit")
    return summary_findings(archive, edition)


def slack_text(value):
    return value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def message(current, baseline, run):
    added = {edition: current[edition] - baseline[edition]
             for edition in current.keys() & baseline.keys()}
    entries = [(edition, cve, package) for edition in sorted(added)
               for cve, package in sorted(added[edition])]
    if not entries:
        return ""
    url = run["html_url"]
    # Links come first so a truncated message still has them.
    lines = [f"{len(entries)} new Trivy policy findings on {slack_text(run['head_branch'])}",
             f"<{url}|Nightly run> · <{url}#artifacts|Scan results>"]
    budget = MAX_MESSAGE_BYTES - 100
    for index, (edition, cve, package) in enumerate(entries):
        line = f"• {edition}: {slack_text(cve)} — {slack_text(package or '(package unknown)')}"
        if len(("\n".join(lines) + line).encode()) > budget:
            lines.append(f"…and {len(entries) - index} more findings. See scan results.")
            break
        lines.append(line)
    return "\n".join(lines)


def baseline_findings(root, current, runs, branches, editions):
    baseline = {}
    for run in islice(runs, MAX_BASELINE_RUNS):
        if previous_run(current, [run], branches) is None:
            continue
        available = load_findings(root, run)
        for edition in editions - baseline.keys():
            if edition in available:
                baseline[edition] = available[edition]
        if editions <= baseline.keys():
            break
    return baseline


def notified_findings(root, run_id):
    notified = {}
    workflow = json.loads(api(f"{root}/actions/workflows/notify-nightly-trivy.yml"))
    default_branch = json.loads(api(root))["default_branch"]
    name = f"trivy-notified-{run_id}"
    for artifact in pages(f"{root}/actions/artifacts?name={name}", "artifacts"):
        if artifact["name"] != name:
            continue
        producer = json.loads(api(f"{root}/actions/runs/{int(artifact['workflow_run']['id'])}"))
        if (producer["workflow_id"] != workflow["id"]
                or producer["event"] not in {"workflow_run", "workflow_dispatch"}
                or producer.get("head_branch") != default_branch):
            continue
        if artifact["expired"] or artifact["size_in_bytes"] > MAX_ARCHIVE_BYTES:
            raise ValueError("Notification history unavailable; cannot safely replay")
        archive = api(f"{root}/actions/artifacts/{int(artifact['id'])}/zip")
        if len(archive) > MAX_ARCHIVE_BYTES:
            raise ValueError("Notification history exceeds size limit")
        with zipfile.ZipFile(io.BytesIO(archive)) as zipped:
            info = zipped.getinfo("trivy-notification.json")
            if info.file_size > MAX_SUMMARY_BYTES:
                raise ValueError("Notification history exceeds size limit")
            record = json.loads(zipped.read(info))
        for edition, values in record["findings"].items():
            notified.setdefault(edition, set()).update(tuple(value) for value in values)
    return notified


def compare(repository, run_id, branches, deduplicate=False):
    root = f"repos/{repository}"
    workflow = json.loads(api(f"{root}/actions/workflows/push_and_pr.yml"))
    current = json.loads(api(f"{root}/actions/runs/{run_id}"))
    result = {"text": "", "findings": {}}
    if not eligible(current, branches, workflow["id"]):
        print("Run is not an eligible completed nightly; no notification.")
        return result
    runs = pages(
        f"{root}/actions/workflows/{workflow['id']}/runs?event=workflow_dispatch"
        f"&branch={quote(current['head_branch'], safe='')}", "workflow_runs"
    )
    current_findings = load_findings(root, current)
    baseline = baseline_findings(root, current, runs, branches, current_findings.keys())
    sent = notified_findings(root, run_id) if deduplicate else {}
    for edition in baseline:
        baseline[edition] |= sent.get(edition, set())
    result["text"] = message(current_findings, baseline, current)
    result["findings"] = {edition: sorted(current_findings[edition] - baseline[edition])
                          for edition in baseline}
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--run-id", type=int, required=True)
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", args.repository) or args.run_id <= 0:
        parser.error("Invalid repository or run ID")
    branches = json.loads(Path(".github/supported_branches.json").read_text())["supported_branches"]
    # A fixed output path avoids using run metadata as a filesystem path.
    Path("trivy-notification.json").write_text(json.dumps(
        compare(args.repository, args.run_id, branches, deduplicate=True),
    ))


if __name__ == "__main__":
    main()
