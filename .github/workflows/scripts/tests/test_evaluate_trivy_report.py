"""Tests for evaluate-trivy-report.py's CVSS scoring/banding policy.

Run with: python3 -m pytest .github/workflows/scripts/tests -v
"""

import importlib.util
import sys
from pathlib import Path

import pytest

SCRIPT_PATH = Path(__file__).resolve().parent.parent / "evaluate-trivy-report.py"
FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


def _load_module():
    spec = importlib.util.spec_from_file_location("evaluate_trivy_report", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules["evaluate_trivy_report"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def evaluator():
    return _load_module()


def _evaluate(evaluator, fixture_name):
    return evaluator.evaluate_path(FIXTURES_DIR / fixture_name)


def test_nvd_v4_takes_precedence_over_v3_and_v2(evaluator):
    result = _evaluate(evaluator, "nvd_v4_precedence.json")
    (finding,) = result.findings
    assert finding.source == "CVSS.nvd.v4"
    assert finding.band == "CRITICAL"
    assert result.violations


def test_nvd_v3_selected_when_v4_absent(evaluator):
    result = _evaluate(evaluator, "nvd_v3_fallback.json")
    (finding,) = result.findings
    assert finding.source == "CVSS.nvd.v3"
    assert finding.band == "HIGH"


def test_nvd_v2_selected_when_v4_and_v3_absent(evaluator):
    result = _evaluate(evaluator, "nvd_v2_fallback.json")
    (finding,) = result.findings
    assert finding.source == "CVSS.nvd.v2"
    assert finding.band == "MEDIUM"


def test_highest_non_nvd_source_selected_as_fallback(evaluator):
    result = _evaluate(evaluator, "other_source_fallback.json")
    (finding,) = result.findings
    # ghsa (8.9) beats redhat (6.5); both are non-nvd, so the higher score wins.
    # 8.9 rounds up to 9, so the resulting band is CRITICAL, not HIGH.
    assert finding.source == "CVSS.ghsa.v3"
    assert finding.band == "CRITICAL"


def test_trivy_severity_fallback_when_no_cvss(evaluator):
    result = _evaluate(evaluator, "severity_fallback.json")
    (finding,) = result.findings
    assert finding.source == "Trivy.Severity"
    assert finding.band == "HIGH"
    assert result.violations


def test_unknown_severity_with_no_cvss_data_fails_policy(evaluator):
    # No CVSS anywhere and Trivy's own severity is UNKNOWN -- zero information,
    # not an informed "no impact" verdict, so this must fail closed.
    result = _evaluate(evaluator, "unknown_severity_fails.json")
    (finding,) = result.findings
    assert finding.band == "UNKNOWN"
    assert result.violations


def test_select_cvss_does_not_drop_a_real_zero_nvd_score(evaluator):
    # A genuine CVSS score of 0.0 is falsy in Python but is real, informed
    # data (NONE band) -- it must not be treated as "field absent".
    assert evaluator.select_cvss({"nvd": {"V3Score": 0.0}}) == (0.0, "CVSS.nvd.v3")


def test_select_cvss_nvd_zero_still_beats_other_sources(evaluator):
    # NVD precedence must hold even when NVD's score is 0.0: a non-nvd
    # fallback must never be selected while an NVD field is present.
    cvss = {"nvd": {"V3Score": 0.0}, "ghsa": {"V3Score": 7.0}}
    assert evaluator.select_cvss(cvss) == (0.0, "CVSS.nvd.v3")


def test_score_to_band_none_is_not_a_failing_band(evaluator):
    # A real CVSS score of 0.0 (NONE band) is informed data saying "no impact"
    # and must be distinguished from UNKNOWN (no data at all) -- NONE passes.
    assert "NONE" not in evaluator.FAILING_BANDS
    assert evaluator.score_to_band(0.0) == "NONE"


def test_upward_rounding_at_band_boundary(evaluator):
    # Raw score 3.1 (Low, < 4.0) rounds UP to 4 -> Medium, and must fail.
    result = _evaluate(evaluator, "boundary_rounding.json")
    (finding,) = result.findings
    assert finding.band == "MEDIUM"
    assert result.violations


def test_medium_plus_fixed_finding_fails_policy(evaluator):
    result = _evaluate(evaluator, "medium_plus_fails.json")
    assert result.violations
    (finding,) = result.findings
    assert finding.band == "MEDIUM"


def test_unexpired_suppression_is_displayed_and_does_not_fail(evaluator):
    # Governed suppressions are surfaced via ExperimentalModifiedFindings
    # (--show-suppressed, the field name real Trivy 0.70.0+/0.74.0 actually
    # populates) and never appear in Vulnerabilities, so they must never fail
    # the policy.
    result = _evaluate(evaluator, "unexpired_suppression.json")
    assert not result.findings
    assert not result.violations
    assert result.suppressed
    target, entry = result.suppressed[0]
    assert entry["Finding"]["VulnerabilityID"] == "CVE-2024-0008"

    # Exercise the actual formatter, not just the fixture's own shape, so a
    # regression in id/package extraction (e.g. reverting the Finding-nesting
    # fix) would fail this suite.
    line = evaluator._format_suppressed(target, entry)
    assert "CVE-2024-0008" in line
    assert "pkg=libexample8" in line
    assert "status=ignored" in line


def test_format_suppressed_falls_back_to_top_level_fields(evaluator):
    # Older/alternate Trivy shapes may put the vuln fields at the entry's own
    # top level instead of nested under "Finding" -- cover that branch too.
    flat = {
        "Status": "ignored",
        "Source": ".trivyignore.yaml",
        "VulnerabilityID": "CVE-2024-0009",
        "PkgName": "libflat9",
    }
    line = evaluator._format_suppressed("target", flat)
    assert "CVE-2024-0009" in line
    assert "pkg=libflat9" in line


def test_expired_suppression_reappears_and_fails(evaluator):
    # Once Trivy's ignore rule expires, the finding moves back into Vulnerabilities
    # and must be evaluated (and fail) normally, like any other finding.
    result = _evaluate(evaluator, "expired_suppression_reappears.json")
    assert result.violations
    (finding,) = result.findings
    assert finding.id == "CVE-2024-0008"
    assert finding.band == "HIGH"


def test_clean_report_has_no_findings_or_violations(evaluator):
    result = _evaluate(evaluator, "no_violations_clean.json")
    assert not result.findings
    assert not result.violations


@pytest.mark.parametrize(
    "score, expected_band",
    [
        (0.0, "NONE"),
        (0.1, "LOW"),
        (3.0, "LOW"),
        (3.1, "MEDIUM"),  # rounds up to 4
        (4.0, "MEDIUM"),
        (6.0, "MEDIUM"),
        (6.1, "HIGH"),  # rounds up to 7
        (7.0, "HIGH"),
        (8.0, "HIGH"),
        (8.1, "CRITICAL"),  # rounds up to 9
        (9.0, "CRITICAL"),
        (10.0, "CRITICAL"),
    ],
)
def test_score_to_band_rounds_up_never_down(evaluator, score, expected_band):
    assert evaluator.score_to_band(score) == expected_band


def test_main_exits_zero_for_clean_report(evaluator, capsys):
    exit_code = evaluator.main([str(FIXTURES_DIR / "no_violations_clean.json")])
    capsys.readouterr()
    assert exit_code == 0


def test_main_exits_nonzero_for_violations(evaluator, capsys):
    exit_code = evaluator.main([str(FIXTURES_DIR / "medium_plus_fails.json")])
    capsys.readouterr()
    assert exit_code != 0
