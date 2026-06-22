"""
Tests for report_text.parse_reasoning_trace() — turns the model's raw
STEP1-4 text into structured sections for the RESULTS page expander and the
PDF report.

RPT-S01  splits DETECTION_LIST into one entry per instance with its fields
RPT-S02  VALIDATION entries keep both the value and the explanation
RPT-S03  parsing stops at [INSTANCES_JSON] — JSON/raw sections excluded
RPT-S04  empty DETECTION_LIST ("EMPTY") still parses without crashing
RPT-S05  truncate_before_instances_json keeps STEP text verbatim, drops the JSON tail
RPT-S06  truncate_before_instances_json returns input unchanged if no marker present
"""

from __future__ import annotations

from src.frontend.report_text import parse_reasoning_trace, truncate_before_instances_json

_SAMPLE = """[DETECTION_LIST]
- instance_1:
  - visual_features: red upright cylinder
  - nearby_text: "F 45L"
  - location: upper-left
  - boundary_status: clear

[VALIDATION]
- missing_detection: NO
  - explanation: checked thoroughly
- count_consistency: PASS
  - explanation: 1 = 1 + 0 + 0

[RESULT]

extinguisher_wheeld_foam_45L: 1 (locations: upper-left)

[INSTANCES_JSON]
[{"instance_id": "instance_1", "category": "extinguisher_wheeld_foam_45L"}]

{"extinguisher_wheeld_foam_45L": 1}
"""


def test_rpt_s01_detection_list_per_instance():
    sections = parse_reasoning_trace(_SAMPLE)
    inst1 = sections["DETECTION_LIST"]["instance_1"]
    assert inst1["visual_features"] == "red upright cylinder"
    assert inst1["nearby_text"] == '"F 45L"'
    assert inst1["boundary_status"] == "clear"


def test_rpt_s02_validation_value_and_explanation():
    sections = parse_reasoning_trace(_SAMPLE)
    check = sections["VALIDATION"]["missing_detection"]
    assert check["value"] == "NO"
    assert check["explanation"] == "checked thoroughly"


def test_rpt_s03_stops_before_instances_json():
    sections = parse_reasoning_trace(_SAMPLE)
    assert "INSTANCES_JSON" not in sections


def test_rpt_s04_empty_detection_list():
    raw = "[DETECTION_LIST]\nEMPTY\n\n[VALIDATION]\n- count_consistency: PASS\n  - explanation: n/a\n"
    sections = parse_reasoning_trace(raw)
    assert sections["DETECTION_LIST"] == {}
    assert sections["VALIDATION"]["count_consistency"]["value"] == "PASS"


def test_rpt_s05_truncate_keeps_steps_drops_json():
    text = truncate_before_instances_json(_SAMPLE)
    assert "[DETECTION_LIST]" in text
    assert "[VALIDATION]" in text
    assert "[RESULT]" in text
    assert "[INSTANCES_JSON]" not in text
    assert '"instance_id"' not in text


def test_rpt_s06_truncate_no_marker_returns_input():
    raw = "[DETECTION_LIST]\nEMPTY\n"
    assert truncate_before_instances_json(raw) == raw.rstrip()
