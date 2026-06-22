"""D2 compliance checker unit tests — D2-S01 through D2-S08."""
from __future__ import annotations

import pytest

from src.backend.d_nodes import d2_check_compliance
from src.backend.schemas import ComplianceInput

_REG = "SOLAS 2020 + FSS Code 2015 (illustrative)"

def _inp(co2=0, dp=0, foam=0, co2_spare=0, space_type=None):
    return ComplianceInput(
        total_by_category={
            "extinguisher_CO2_5kg": co2,
            "extinguisher_CO2_5kg_spare": co2_spare,
            "extinguisher_dry_powder_6kg": dp,
            "extinguisher_dry_powder_6kg_spare": 0,
            "extinguisher_foam_9L": foam,
            "extinguisher_foam_9L_spare": 0,
        },
        regulation_set=_REG,
        is_mock=True,
        space_type=space_type,
    )


def test_d2_s01_all_pass():
    """D2-S01: All rules pass — nominal deck."""
    result = d2_check_compliance(_inp(co2=1, dp=4, foam=1, space_type=None))
    assert result.overall_verdict == "GO"
    assert all(c.status in ("pass", "not_applicable") for c in result.checks)


def test_d2_s02_co2_missing():
    """D2-S02: CO₂=0 → R01 fail → NO_GO."""
    result = d2_check_compliance(_inp(co2=0, dp=4, foam=1))
    assert result.overall_verdict == "NO_GO"
    r01 = next(c for c in result.checks if c.rule_id == "R01")
    assert r01.status == "fail"
    assert r01.verdict == "NO_GO"


def test_d2_s03_dp_below_min():
    """D2-S03: DP=1 → R02 fail → NO_GO."""
    result = d2_check_compliance(_inp(co2=1, dp=1, foam=1))
    assert result.overall_verdict == "NO_GO"
    r02 = next(c for c in result.checks if c.rule_id == "R02")
    assert r02.status == "fail"


def test_d2_s04_total_too_low():
    """D2-S04: total=3 → R04 fail → NO_GO."""
    result = d2_check_compliance(_inp(co2=1, dp=2, foam=0))
    assert result.overall_verdict == "NO_GO"
    r04 = next(c for c in result.checks if c.rule_id == "R04")
    assert r04.status == "fail"


def test_d2_s05_foam_not_applicable_no_spare_trigger():
    """D2-S05: foam=0, space_type=None → R03 N/A; CO₂=1 < 2 so R05 N/A → GO."""
    result = d2_check_compliance(_inp(co2=1, dp=4, foam=0, space_type=None))
    assert result.overall_verdict == "GO"
    r03 = next(c for c in result.checks if c.rule_id == "R03")
    assert r03.status == "not_applicable"
    r05 = next(c for c in result.checks if c.rule_id == "R05")
    assert r05.status == "not_applicable"


def test_d2_s06_foam_warning_accommodation():
    """D2-S06: foam=0, space_type='accommodation' → R03 warning → CONDITIONAL."""
    result = d2_check_compliance(_inp(co2=1, dp=4, foam=0, space_type="accommodation"))
    assert result.overall_verdict == "CONDITIONAL"
    r03 = next(c for c in result.checks if c.rule_id == "R03")
    assert r03.status == "warning"
    assert r03.verdict == "CONDITIONAL"


def test_d2_s07_spare_rule_triggered():
    """D2-S07: CO₂=2, spare=0 → R05 warning → CONDITIONAL."""
    result = d2_check_compliance(_inp(co2=2, dp=4, foam=1, co2_spare=0))
    assert result.overall_verdict == "CONDITIONAL"
    r05 = next(c for c in result.checks if c.rule_id == "R05")
    assert r05.status == "warning"
    assert r05.verdict == "CONDITIONAL"


def test_d2_s08_empty_counts_hard_fail():
    """D2-S08: empty total_by_category → ValueError (HARD FAIL)."""
    with pytest.raises(ValueError, match="empty"):
        d2_check_compliance(ComplianceInput(
            total_by_category={},
            regulation_set=_REG,
            is_mock=True,
        ))


def test_d2_counts_snapshot():
    """ComplianceResult carries a snapshot of input counts."""
    inp = _inp(co2=1, dp=4, foam=0)
    result = d2_check_compliance(inp)
    assert result.counts_snapshot["extinguisher_CO2_5kg"] == 1


def test_d2_all_checks_mock_flagged():
    """All checks must have is_mock_rule=True in Phase 1."""
    result = d2_check_compliance(_inp(co2=1, dp=4, foam=1))
    assert all(c.is_mock_rule for c in result.checks)
