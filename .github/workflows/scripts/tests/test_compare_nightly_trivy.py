"""Fixtures for nightly identity comparison and notification boundaries."""
import importlib.util
import io
import json
import zipfile
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location(
    "nightly", Path(__file__).parents[1] / "compare-nightly-trivy.py"
)
nightly = importlib.util.module_from_spec(spec)
spec.loader.exec_module(nightly)


def run(number=2, **changes):
    result = dict(id=number, run_number=number, run_attempt=2, workflow_id=9,
                  event="workflow_dispatch", status="completed", head_branch="master",
                  display_title="Nightly CI (master)", html_url=f"https://github.com/org/repo/actions/runs/{number}")
    return result | changes


def archive(findings, version=1):
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as zipped:
        zipped.writestr("trivy-community-summary.json", json.dumps({
            "schema_version": version,
            "reports": [{"violations": [{"id": cve, "package": package} for cve, package in findings]}],
        }))
    return output.getvalue()


@pytest.mark.parametrize("changes", [
    {"event": "push"}, {"event": "pull_request"}, {"head_branch": "feature"},
    {"display_title": "CI (master)"}, {"workflow_id": 8}, {"status": "in_progress"},
])
def test_ineligible_runs(changes):
    assert not nightly.eligible(run(**changes), ["master"], 9)


def test_previous_is_same_branch_and_older_nightly():
    candidates = [run(1), run(3), run(1, head_branch="release/1"), run(1, event="push")]
    assert nightly.previous_run(run(), candidates, ["master", "release/1"]) == run(1)
    assert nightly.previous_run(run(), [], ["master"]) is None


def test_identity_comparison_and_grouping():
    baseline = {"community": {("CVE-1", "liba")}, "enterprise": set()}
    current = {"community": {("CVE-1", "liba"), ("CVE-1", "libb")},
               "enterprise": {("CVE-2", "libc")}, "developer": {("CVE-3", "libd")}}
    text = nightly.message(current, baseline, run())
    assert "CVE-1 — libb" in text
    assert "CVE-2 — libc" in text
    assert "CVE-1 — liba" not in text
    assert "CVE-3" not in text
    assert "#artifacts" in text
    assert "master" in text
    assert nightly.message(current, current, run()) == ""
    assert nightly.message(current, {}, run()) == ""


def test_artifact_schema_and_slack_escaping():
    assert nightly.summary_findings(archive([("CVE-1", "liba")]), "community") == {("CVE-1", "liba")}
    unsupported = archive([], version=2)
    with pytest.raises(ValueError):
        nightly.summary_findings(unsupported, "community")
    assert "<!channel>" not in nightly.message(
        {"community": {("CVE-1", "<!channel>")}}, {"community": set()}, run())


def test_latest_attempt_only(monkeypatch):
    artifacts = [dict(id=1, name="trivy-community-attempt-1", expired=False, size_in_bytes=10),
                 dict(id=2, name="trivy-community-attempt-2", expired=False, size_in_bytes=10)]
    monkeypatch.setattr(nightly, "pages", lambda *args: artifacts)
    monkeypatch.setattr(nightly, "scan_attempts", lambda *args: {"community": 2})
    calls = []

    def api(path):
        calls.append(path)
        return archive([("CVE-1", "liba")])

    monkeypatch.setattr(nightly, "api", api)
    assert nightly.load_findings("repos/org/repo", run()) == {"community": {("CVE-1", "liba")}}
    assert calls == ["repos/org/repo/actions/artifacts/2/zip"]
    artifacts[1]["expired"] = True
    current = run()
    assert nightly.load_findings("repos/org/repo", current) == {}


@pytest.mark.parametrize("event", ["push", "pull_request"])
def test_manual_input_cannot_bypass_eligibility(monkeypatch, event):
    def api(path):
        return json.dumps({"id": 9} if path.endswith("push_and_pr.yml") else run(event=event)).encode()
    monkeypatch.setattr(nightly, "api", api)
    monkeypatch.setattr(nightly, "pages", lambda *args: pytest.fail("Must not read artifacts or baseline"))
    assert nightly.compare("org/repo", 2, ["master"])["text"] == ""


def test_first_nightly_records_baseline(monkeypatch):
    monkeypatch.setattr(nightly, "api", lambda path: json.dumps(
        {"id": 9} if path.endswith("push_and_pr.yml") else run()).encode())
    monkeypatch.setattr(nightly, "pages", lambda *args: [])
    monkeypatch.setattr(nightly, "load_findings", lambda *args: {"community": set()})
    assert nightly.compare("org/repo", 2, ["master"])["text"] == ""


def test_paginated_api(monkeypatch):
    monkeypatch.setattr(nightly, "api", lambda path: json.dumps({
        "artifacts": list(range(100)) if path.endswith("&page=1") else [100],
    }).encode())
    assert list(nightly.pages("repos/org/repo/artifacts", "artifacts")) == list(range(101))


@pytest.mark.parametrize("reports", [None, {}, "", [{"violations": {}}],
                                     [{"violations": ""}], [{"violations": None}],
                                     [{"violations": [None]}]])
def test_malformed_baseline_is_rejected(reports):
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as zipped:
        zipped.writestr("trivy-community-summary.json", json.dumps({
            "schema_version": 1, "reports": reports,
        }))
    data = output.getvalue()
    with pytest.raises(ValueError):
        nightly.summary_findings(data, "community")


def test_full_comparison_with_mocked_transport(monkeypatch):
    def api(path):
        if path.endswith("push_and_pr.yml"):
            return json.dumps({"id": 9}).encode()
        return json.dumps(run()).encode()

    monkeypatch.setattr(nightly, "api", api)
    monkeypatch.setattr(nightly, "pages", lambda *args: [run(1)])
    monkeypatch.setattr(nightly, "load_findings", lambda root, item: {
        "community": {("CVE-1", "liba")} if item["id"] == 2 else set(),
    })
    text = nightly.compare("org/repo", 2, ["master"])["text"]
    assert "CVE-1 — liba" in text
    assert text.count("Nightly run") == 1


@pytest.mark.parametrize("unusable", [b"not a zip", archive([], version=2)])
def test_unusable_edition_does_not_hide_valid_findings(monkeypatch, unusable):
    artifacts = [dict(id=1, name="trivy-enterprise-attempt-2", expired=False, size_in_bytes=10),
                 dict(id=2, name="trivy-community-attempt-2", expired=False, size_in_bytes=10)]
    monkeypatch.setattr(nightly, "pages", lambda *args: artifacts)
    monkeypatch.setattr(nightly, "scan_attempts", lambda *args: {"community": 2, "enterprise": 2})
    monkeypatch.setattr(nightly, "api", lambda path: unusable if "/1/zip" in path else archive([("CVE-1", "liba")]))
    assert nightly.load_findings("repos/org/repo", run()) == {"community": {("CVE-1", "liba")}}


def test_baseline_lookup_stops_at_previous_nightly():
    def candidates():
        yield run(3)
        yield run(1)
        pytest.fail("Older pages must not be consumed")
    assert nightly.previous_run(run(), candidates(), ["master"]) == run(1)



def test_partial_rerun_selects_highest_attempt_per_edition():
    artifacts = [dict(name="trivy-community-attempt-1", id=1),
                 dict(name="trivy-enterprise-attempt-1", id=2),
                 dict(name="trivy-enterprise-attempt-2", id=3),
                 dict(name="trivy-community-attempt-3", id=4)]
    assert nightly.selected_artifacts(artifacts, 2) == {
        "community": artifacts[0], "enterprise": artifacts[2],
    }


def test_baseline_skips_unusable_runs_per_edition(monkeypatch):
    monkeypatch.setattr(nightly, "load_findings", lambda root, item: {
        3: {}, 2: {"community": set()}, 1: {"enterprise": {("CVE-1", "liba")}},
    }[item["id"]])
    assert nightly.baseline_findings("repos/org/repo", run(4),
                                     [run(3), run(2), run(1)], ["master"],
                                     {"community", "enterprise"}) == {
        "community": set(), "enterprise": {("CVE-1", "liba")},
    }


def test_unknown_package_preserves_other_findings():
    summary = {"schema_version": 1, "reports": [{"violations": [
        {"id": "CVE-1", "package": ""}, {"id": "CVE-2", "package": "liba"},
    ]}]}
    assert nightly.parse_summary(summary) == {("CVE-1", ""), ("CVE-2", "liba")}


def test_large_message_keeps_links_and_omitted_count():
    findings = {("CVE-" + str(index), "package" * 20) for index in range(500)}
    text = nightly.message({"community": findings}, {"community": set()}, run())
    assert len(text.encode()) <= nightly.MAX_MESSAGE_BYTES
    assert "more findings" in text
    assert text.splitlines()[1].endswith("#artifacts|Scan results>")


def test_rerun_suppresses_delivered_findings_but_sends_new_ones(monkeypatch):
    monkeypatch.setattr(nightly, "api", lambda path: json.dumps(
        {"id": 9} if path.endswith("push_and_pr.yml") else run()).encode())
    monkeypatch.setattr(nightly, "pages", lambda *args: [run(1)])
    monkeypatch.setattr(nightly, "load_findings", lambda root, item: {
        "community": {("CVE-1", "liba"), ("CVE-2", "libb")} if item["id"] == 2 else set(),
    })
    monkeypatch.setattr(nightly, "notified_findings", lambda *args: {"community": {("CVE-1", "liba")}})
    result = nightly.compare("org/repo", 2, ["master"], deduplicate=True)
    assert "CVE-1" not in result["text"]
    assert "CVE-2" in result["text"]
    assert result["findings"] == {"community": [("CVE-2", "libb")]}



def test_notification_receipts_require_trusted_workflow(monkeypatch):
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as zipped:
        zipped.writestr("trivy-notification.json", json.dumps({
            "findings": {"community": [["CVE-1", "liba"]]},
        }))
    data = output.getvalue()
    artifacts = [dict(id=1, name="trivy-notified-2", expired=False,
                      size_in_bytes=len(data), workflow_run={"id": 10}),
                 dict(id=2, name="trivy-notified-2", expired=False,
                      size_in_bytes=len(data), workflow_run={"id": 11})]
    monkeypatch.setattr(nightly, "pages", lambda *args: artifacts)
    downloads = []

    def api(path):
        if path == "repos/org/repo":
            return json.dumps({"default_branch": "master"}).encode()
        if path.endswith("notify-nightly-trivy.yml"):
            return json.dumps({"id": 20}).encode()
        if path.endswith("/runs/10"):
            return json.dumps({"workflow_id": 20, "event": "pull_request"}).encode()
        if path.endswith("/runs/11"):
            return json.dumps({"workflow_id": 20, "event": "workflow_run", "head_branch": "master"}).encode()
        downloads.append(path)
        return data

    monkeypatch.setattr(nightly, "api", api)
    assert nightly.notified_findings("repos/org/repo", 2) == {"community": {("CVE-1", "liba")}}
    assert downloads == ["repos/org/repo/actions/artifacts/2/zip"]


@pytest.mark.parametrize("jobs,expected", [
    ([{"name": "Security Scan (community)", "run_attempt": 1},
      {"name": "Security Scan (enterprise)", "run_attempt": 2}], {"community": set()}),
    ([{"name": "Security Scan (community)", "run_attempt": 2}], {}),
    ([{"name": "Security Scan (community)", "run_attempt": 1},
      {"name": "Security Scan (community)", "run_attempt": 2}], {}),
    ([], {}),
])
def test_missing_rerun_artifact_never_falls_back(monkeypatch, jobs, expected):
    artifacts = [dict(id=1, name="trivy-community-attempt-1", expired=False, size_in_bytes=10)]
    monkeypatch.setattr(nightly, "pages", lambda path, key: jobs if key == "jobs" else artifacts)
    monkeypatch.setattr(nightly, "api", lambda path: archive([]))
    assert nightly.load_findings("repos/org/repo", run(run_attempt=3)) == expected


def test_baseline_history_is_bounded(monkeypatch):
    calls = []
    monkeypatch.setattr(nightly, "load_findings", lambda root, item: calls.append(item["id"]) or {})

    def candidates():
        for number in range(nightly.MAX_BASELINE_RUNS):
            yield run(number)
        pytest.fail("Baseline lookup must not consume another page")

    assert nightly.baseline_findings("repos/org/repo", run(1000), candidates(),
                                     ["master"], {"community"}) == {}
    assert len(calls) == nightly.MAX_BASELINE_RUNS


@pytest.mark.parametrize("event", ["workflow_dispatch", "workflow_run"])
def test_feature_branch_receipt_is_not_downloaded(monkeypatch, event):
    monkeypatch.setattr(nightly, "pages", lambda *args: [
        dict(id=1, name="trivy-notified-2", workflow_run={"id": 10}),
    ])

    def api(path):
        if path == "repos/org/repo":
            return json.dumps({"default_branch": "master"}).encode()
        if path.endswith("notify-nightly-trivy.yml"):
            return json.dumps({"id": 20}).encode()
        if path.endswith("/runs/10"):
            return json.dumps({"workflow_id": 20, "event": event, "head_branch": "feature"}).encode()
        pytest.fail("Untrusted receipt must not be downloaded")

    monkeypatch.setattr(nightly, "api", api)
    assert nightly.notified_findings("repos/org/repo", 2) == {}
