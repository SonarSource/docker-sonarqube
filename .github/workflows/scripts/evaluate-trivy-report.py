#!/usr/bin/env python3
"""Evaluate a Trivy JSON vulnerability report against the repository's CI policy.

Policy: a finding fails CI if its CVSS-derived severity band is Medium, High, or
Critical -- or Unknown, meaning no CVSS score and no usable Trivy severity were
available at all, so there's no data to say the finding is safe. Vulnerabilities
without an upstream fix, and vulnerabilities suppressed by a governed, unexpired
.trivyignore.yaml entry, are expected to already be absent from the report's
"Vulnerabilities" list (enforced by the Trivy invocation itself via
--ignore-unfixed and --ignorefile) -- this script only judges whatever findings
Trivy hands it.

CVSS score selection precedence, per finding:
  1. CVSS.nvd v4   (CVSS.nvd.V40Score)
  2. CVSS.nvd v3   (CVSS.nvd.V3Score)
  3. CVSS.nvd v2   (CVSS.nvd.V2Score)
  4. The highest score reported by any other CVSS source/version
  5. Trivy's own Severity field, only when no CVSS score is available at all

Numeric CVSS scores are mapped to their band using the exact official CVSS
qualitative severity ranges (Low 0.1-3.9, Medium 4.0-6.9, High 7.0-8.9,
Critical 9.0-10.0) -- no rounding is applied, since a score already falls
in exactly one of these bands.

Not GitHub Actions-specific: run directly against any Trivy JSON report file.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Optional

NVD_SOURCE = "nvd"

# CVSS score field, in precedence order, together with its human-readable label.
CVSS_VERSION_FIELDS = (
    ("V40Score", "v4"),
    ("V3Score", "v3"),
    ("V2Score", "v2"),
)

CVSS_BANDS = ((0.0, "NONE"), (3.9, "LOW"), (6.9, "MEDIUM"), (8.9, "HIGH"))
BANDS = tuple(band for _, band in CVSS_BANDS) + ("CRITICAL", "UNKNOWN")
TRIVY_SEVERITY_TO_BAND = {band: band for band in BANDS if band != "NONE"}

# UNKNOWN means we have no CVSS score anywhere AND no usable Trivy severity --
# i.e. zero information, not a real "no impact" score. Fail closed on that so
# a human has to look and either fix it or add a governed .trivyignore entry,
# rather than silently trusting an absence of data. NONE (a real score of 0.0)
# is intentionally excluded -- that's an informed "no impact" verdict.
FAILING_BANDS = frozenset({"UNKNOWN", "MEDIUM", "HIGH", "CRITICAL"})

# Trivy's --show-suppressed field name has changed across releases; check both.
SUPPRESSED_FIELDS = ("ModifiedFindings", "ExperimentalModifiedFindings")


@dataclass
class Finding:
    id: str
    target: str
    package: str
    band: str
    score_display: str
    source: str

    @property
    def is_violation(self) -> bool:
        return self.band in FAILING_BANDS


@dataclass
class ReportResult:
    findings: list[Finding] = field(default_factory=list)
    suppressed: list[tuple[str, dict[str, Any]]] = field(default_factory=list)

    @property
    def violations(self) -> list[Finding]:
        return [f for f in self.findings if f.is_violation]


def score_to_band(score: float) -> str:
    """Map a CVSS score to its qualitative band using the official v3.x/v4
    boundaries (NVD qualitative severity rating scale). These are exact float
    ranges, not integers, so no rounding is applied -- a score already sits
    in exactly one band, and comparing it directly is what "never rounds
    down" actually means here.
    """
    for upper_bound, band in CVSS_BANDS:
        if score <= upper_bound:
            return band
    return BANDS[-2]


def _best_field(scores: dict[str, Any]) -> Optional[tuple[float, str]]:
    """Return (score, version_label) for the highest-precedence populated field."""
    for cvss_field, version in CVSS_VERSION_FIELDS:
        value = scores.get(cvss_field)
        if value is not None:
            return float(value), version
    return None


def select_cvss(cvss: dict[str, Any]) -> Optional[tuple[float, str]]:
    """Select (score, source_label) for a finding's CVSS map, per repo policy."""
    nvd_scores = cvss.get(NVD_SOURCE) or {}
    nvd_best = _best_field(nvd_scores)
    if nvd_best:
        score, version = nvd_best
        return score, f"CVSS.nvd.{version}"

    candidates = (
        (float(scores[cvss_field]), source, version)
        for source, scores in cvss.items()
        if source != NVD_SOURCE and scores
        for cvss_field, version in CVSS_VERSION_FIELDS
        if scores.get(cvss_field) is not None
    )
    best = max(candidates, key=lambda candidate: candidate[0], default=None)

    if best:
        score, source, version = best
        return score, f"CVSS.{source}.{version}"

    return None


def evaluate_finding(target: str, vuln: dict[str, Any]) -> Finding:
    vuln_id = vuln.get("VulnerabilityID", "UNKNOWN")
    package = vuln.get("PkgName", "")
    cvss = vuln.get("CVSS") or {}

    selected = select_cvss(cvss)
    if selected is not None:
        score, source = selected
        band = score_to_band(score)
        score_display = f"{score:g}"
    else:
        severity = str(vuln.get("Severity") or "UNKNOWN").upper()
        band = TRIVY_SEVERITY_TO_BAND.get(severity, "UNKNOWN")
        source = "Trivy.Severity"
        score_display = severity

    return Finding(
        id=vuln_id,
        target=target,
        package=package,
        band=band,
        score_display=score_display,
        source=source,
    )


def _iter_results(report: dict[str, Any]):
    for result in report.get("Results") or []:
        yield result.get("Target", ""), result


def evaluate_report(report: dict[str, Any]) -> ReportResult:
    findings: list[Finding] = []
    suppressed: list[tuple[str, dict[str, Any]]] = []

    for target, result in _iter_results(report):
        for vuln in result.get("Vulnerabilities") or []:
            findings.append(evaluate_finding(target, vuln))

        for suppressed_field in SUPPRESSED_FIELDS:
            for entry in result.get(suppressed_field) or []:
                suppressed.append((target, entry))

    return ReportResult(findings=findings, suppressed=suppressed)


def _format_finding(finding: Finding) -> str:
    marker = "FAIL" if finding.is_violation else "ok  "
    return (
        f"[{marker}] {finding.id:<18} pkg={finding.package:<28} "
        f"score={finding.score_display:<6} source={finding.source:<16} "
        f"band={finding.band}"
    )


def _format_suppressed(target: str, entry: dict[str, Any]) -> str:
    # Trivy nests the actual vulnerability under "Finding"; fall back to the
    # entry's own top level in case that shape ever changes.
    finding = entry.get("Finding") or {}
    finding_id = (
        finding.get("VulnerabilityID")
        or entry.get("VulnerabilityID")
        or entry.get("ID")
        or "UNKNOWN"
    )
    package = finding.get("PkgName") or entry.get("PkgName") or ""
    status = entry.get("Status", "?")
    statement = entry.get("Statement") or entry.get("Comment") or ""
    source = entry.get("Source", "?")
    return (
        f"[suppressed] {finding_id:<18} pkg={package:<20} target={target} "
        f"status={status} source={source} statement={statement!r}"
    )


def evaluate_path(path: Path) -> tuple[dict[str, Any], ReportResult]:
    with path.open(encoding="utf-8") as fh:
        report = json.load(fh)
    if not isinstance(report, dict):
        raise ValueError("Trivy report must be a JSON object")
    return report, evaluate_report(report)


def summarize_report(path: Path, report: dict[str, Any], result: ReportResult) -> dict[str, Any]:
    return {
        "report": str(path),
        "image": report.get("ArtifactName", ""),
        "image_id": (report.get("Metadata") or {}).get("ImageID", ""),
        "counts_per_band": {
            band: sum(finding.band == band for finding in result.findings)
            for band in BANDS
        },
        "suppressed_count": len(result.suppressed),
        "violations": [asdict(finding) for finding in result.violations],
    }


def print_report(result: ReportResult) -> None:
    if result.suppressed:
        print(f"-- {len(result.suppressed)} suppressed finding(s) (governed, unexpired) --")
        for target, entry in result.suppressed:
            print(f"  {_format_suppressed(target, entry)}")

    if result.findings:
        print(f"-- {len(result.findings)} finding(s) evaluated --")
        for finding in result.findings:
            print(f"  {_format_finding(finding)}")
    else:
        print("-- no findings --")

    violations = result.violations
    if violations:
        print(f"-- POLICY VIOLATION: {len(violations)} finding(s) in a failing band (Medium+ or Unknown) --")
    else:
        print("-- no policy violations --")
    print()


def write_summary(output: Path, summaries: list[dict[str, Any]]) -> None:
    output_path = Path.cwd() / output.name
    if output_path.is_symlink():
        raise ValueError("--summary-output must not be a symbolic link")
    output_path.write_text(
        json.dumps({"schema_version": 1, "reports": summaries}, indent=2) + "\n",
        encoding="utf-8",
    )


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "reports",
        nargs="+",
        type=Path,
        help="Path(s) to Trivy JSON report file(s) to evaluate.",
    )
    parser.add_argument(
        "--summary-output", type=Path,
        help="Write a versioned JSON summary to a filename in the current directory.",
    )
    args = parser.parse_args(argv)

    if args.summary_output and (args.summary_output.is_absolute() or args.summary_output.name != str(args.summary_output)):
        parser.error("--summary-output must be a filename in the current directory")

    total_violations = 0
    summaries = []
    report_errors = 0

    for report_path in args.reports:
        print(f"== Evaluating {report_path} ==")
        try:
            report, result = evaluate_path(report_path)
            summary = summarize_report(report_path, report, result)
            print_report(result)
        except (OSError, ValueError, TypeError, AttributeError) as error:
            print(f"ERROR: cannot load {report_path}: {error}", file=sys.stderr)
            report_errors += 1
            continue
        summaries.append(summary)
        total_violations += len(result.violations)

    if args.summary_output:
        write_summary(args.summary_output, summaries)

    if report_errors:
        print(f"FAILED: {report_errors} report(s) could not be loaded.", file=sys.stderr)
        return 1

    if total_violations:
        print(f"FAILED: {total_violations} finding(s) violate the policy (CVSS >= Medium, or Unknown with no data).")
        return 1

    print("PASSED: no findings violate the policy (CVSS >= Medium, or Unknown with no data).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
