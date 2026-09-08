#!/usr/bin/env python3
"""Evaluate a Trivy JSON vulnerability report against the repository's CI policy.

Policy: a finding fails CI if its CVSS-derived severity band is Medium, High, or
Critical. Vulnerabilities without an upstream fix, and vulnerabilities suppressed
by a governed, unexpired .trivyignore.yaml entry, are expected to already be
absent from the report's "Vulnerabilities" list (enforced by the Trivy invocation
itself via --ignore-unfixed and --ignorefile) -- this script only judges whatever
findings Trivy hands it.

CVSS score selection precedence, per finding:
  1. CVSS.nvd v4   (CVSS.nvd.V40Score)
  2. CVSS.nvd v3   (CVSS.nvd.V3Score)
  3. CVSS.nvd v2   (CVSS.nvd.V2Score)
  4. The highest score reported by any other CVSS source/version
  5. Trivy's own Severity field, only when no CVSS score is available at all

Numeric CVSS scores are rounded UP (never down) to the nearest whole number
before being mapped to a band, so a borderline score is never under-classified.

Not GitHub Actions-specific: run directly against any Trivy JSON report file.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

NVD_SOURCE = "nvd"

# CVSS score field, in precedence order, together with its human-readable label.
CVSS_VERSION_FIELDS = (
    ("V40Score", "v4"),
    ("V3Score", "v3"),
    ("V2Score", "v2"),
)

TRIVY_SEVERITY_TO_BAND = {
    "UNKNOWN": "UNKNOWN",
    "LOW": "LOW",
    "MEDIUM": "MEDIUM",
    "HIGH": "HIGH",
    "CRITICAL": "CRITICAL",
}

FAILING_BANDS = frozenset({"MEDIUM", "HIGH", "CRITICAL"})

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
    """Round the score UP to the nearest whole number, then map to a band."""
    rounded = math.ceil(score)
    if rounded <= 0:
        return "NONE"
    if rounded <= 3:
        return "LOW"
    if rounded <= 6:
        return "MEDIUM"
    if rounded <= 8:
        return "HIGH"
    return "CRITICAL"


def _best_field(scores: dict[str, Any]) -> Optional[tuple[float, str]]:
    """Return (score, version_label) for the highest-precedence populated field."""
    for cvss_field, version in CVSS_VERSION_FIELDS:
        value = scores.get(cvss_field)
        if value:
            return float(value), version
    return None


def select_cvss(cvss: dict[str, Any]) -> Optional[tuple[float, str]]:
    """Select (score, source_label) for a finding's CVSS map, per repo policy."""
    nvd_scores = cvss.get(NVD_SOURCE) or {}
    nvd_best = _best_field(nvd_scores)
    if nvd_best:
        score, version = nvd_best
        return score, f"CVSS.nvd.{version}"

    best: Optional[tuple[float, str, str]] = None  # (score, source, version)
    for source, scores in cvss.items():
        if source == NVD_SOURCE or not scores:
            continue
        for cvss_field, version in CVSS_VERSION_FIELDS:
            value = scores.get(cvss_field)
            if not value:
                continue
            value = float(value)
            if best is None or value > best[0]:
                best = (value, source, version)

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


def evaluate_path(path: Path) -> ReportResult:
    with path.open(encoding="utf-8") as fh:
        report = json.load(fh)
    return evaluate_report(report)


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "reports",
        nargs="+",
        type=Path,
        help="Path(s) to Trivy JSON report file(s) to evaluate.",
    )
    args = parser.parse_args(argv)

    total_violations = 0

    for report_path in args.reports:
        print(f"== Evaluating {report_path} ==")
        result = evaluate_path(report_path)

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
            print(f"-- POLICY VIOLATION: {len(violations)} finding(s) at Medium band or higher --")
            total_violations += len(violations)
        else:
            print("-- no policy violations --")
        print()

    if total_violations:
        print(f"FAILED: {total_violations} finding(s) violate the CVSS >= Medium policy.")
        return 1

    print("PASSED: no findings violate the CVSS >= Medium policy.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
