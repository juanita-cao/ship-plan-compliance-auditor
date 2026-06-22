"""Parse E1's raw STEP1-4 reasoning trace into structured sections.

The model's raw_response (see schemas.py:E3CountResult.raw_response) follows a
fixed bracket-marker format defined in the prompt files (e.g.
data/prompts/prompt_cot_counts_demo_ship_b.txt STEP 1-4): [DETECTION_LIST],
[MATCHING], [CHECKLIST], [EXCLUDED], [VALIDATION], [RESULT], then
[INSTANCES_JSON] + a final bare JSON line. Parsing stops at [INSTANCES_JSON]
— everything from there on is machine-readable, not meant for human display.

Shared by the RESULTS page expander and the PDF report (pdf_report.py) so
both render from the same structured data instead of two parsers drifting
apart.
"""

from __future__ import annotations

import re

_SECTION_RE = re.compile(r"^\[([A-Z_]+)\]\s*$", re.MULTILINE)


def _parse_bullet_block(text: str) -> dict[str, dict[str, str]]:
    """Parse '- key: value\\n  - subkey: value' blocks into {key: {"value": v, subkey: v2}}."""
    result: dict[str, dict[str, str]] = {}
    current_key: str | None = None
    for line in text.splitlines():
        if not line.strip():
            continue
        if line.startswith("- "):
            key, _, val = line[2:].partition(":")
            current_key = key.strip()
            result[current_key] = {"value": val.strip()}
        elif line.startswith("  - ") and current_key is not None:
            subkey, _, val = line[4:].partition(":")
            result[current_key][subkey.strip()] = val.strip()
    return result


def truncate_before_instances_json(raw: str) -> str:
    """Return raw_response up to (not including) the [INSTANCES_JSON] marker.

    Keeps the model's own step-by-step text (DETECTION_LIST, MATCHING,
    CHECKLIST, EXCLUDED, VALIDATION, RESULT) verbatim, formatting untouched —
    only the trailing machine-readable JSON is dropped.
    """
    m = re.search(r"^\[INSTANCES_JSON\]\s*$", raw, re.MULTILINE)
    return raw[: m.start()].rstrip() if m else raw.rstrip()


def parse_reasoning_trace(raw: str) -> dict[str, dict[str, dict[str, str]]]:
    """Split raw_response into named sections, each parsed as nested bullets.

    Returns e.g. {"DETECTION_LIST": {"instance_1": {"value": "", "visual_features": "...", ...}}}.
    Sections from [INSTANCES_JSON] onward are dropped (machine-readable JSON).
    """
    matches = list(_SECTION_RE.finditer(raw))
    sections: dict[str, dict[str, dict[str, str]]] = {}
    for i, m in enumerate(matches):
        name = m.group(1)
        if name == "INSTANCES_JSON":
            break
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(raw)
        sections[name] = _parse_bullet_block(raw[start:end])
    return sections
