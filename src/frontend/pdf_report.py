"""Generate a downloadable PDF report from a ResultsViewModel.

Built fresh from `vm` on every download click (reportlab, in-memory, no temp
files, no pre-rendered fixtures) — the underlying data is always whatever
real eval_runs row backs the ViewModel currently on screen (mock mode shows
a past real run's data; live mode shows the run that just completed), so the
PDF is a real report of real detection output either way, not a canned demo
file read off disk.
"""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    Image as RLImage,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from src.frontend.report_text import parse_reasoning_trace
from src.frontend.spotlight import render_spotlight_node
from src.frontend.view_models import ResultsViewModel

_NAVY = colors.HexColor("#125993")
_GREEN = colors.HexColor("#00B42A")
_RED = colors.HexColor("#F53F3F")
_AMBER = colors.HexColor("#FF7D00")
_GRAY = colors.HexColor("#86909C")
_LIGHT_BG = colors.HexColor("#F2F3F5")

_VERDICT_COLOR = {"GO": _GREEN, "NO_GO": _RED, "CONDITIONAL": _AMBER}
_STATUS_COLOR = {"pass": _GREEN, "fail": _RED, "warning": _AMBER, "not_applicable": _GRAY}
_STATUS_LABEL = {"pass": "PASS", "fail": "FAIL", "warning": "WARN", "not_applicable": "N/A"}
_VALIDATION_GOOD = {"missing_detection": "NO", "misclassification": "NO", "count_consistency": "PASS"}


def _pdf_text(text: str) -> str:
    """Sanitize text for reportlab Paragraph rendering.

    reportlab's default Helvetica font has no glyph for U+2082 SUBSCRIPT TWO
    (the "₂" in "CO₂", baked into d_nodes.py's rule descriptions) — it
    renders as a black replacement box. Swap it for proper <sub> markup
    using a plain ASCII "2", which renders correctly in the same font.
    """
    return text.replace("₂", "<sub>2</sub>")


def _analysis_summary(validation: dict, total: int) -> str:
    """Turn the model's 3 validation checks into a short prose paragraph
    instead of a checklist — same underlying explanations, written as
    sentences rather than rows."""
    md = validation.get("missing_detection", {})
    mc = validation.get("misclassification", {})
    cc = validation.get("count_consistency", {})
    all_clear = (
        md.get("value") == _VALIDATION_GOOD["missing_detection"]
        and mc.get("value") == _VALIDATION_GOOD["misclassification"]
        and cc.get("value") == _VALIDATION_GOOD["count_consistency"]
    )
    opening = (
        f"The detection model identified {total} fire equipment instance(s) on this deck plan "
        + ("with no flagged gaps in coverage and no classification ambiguity."
           if all_clear else
           "; its self-review flagged the following concerns.")
    )
    sentences = [opening]
    for check in (md, mc, cc):
        explanation = check.get("explanation")
        if explanation:
            sentences.append(explanation)
    return " ".join(_pdf_text(s) for s in sentences)


def _compliance_summary(cr) -> str:
    """Short prose synthesis of the IMO compliance result — built from the
    same ComplianceCheck rows the table above already shows, not a new call."""
    applicable = [c for c in cr.checks if c.status != "not_applicable"]
    failed = [c for c in applicable if c.status != "pass"]
    passed = [c for c in applicable if c.status == "pass"]

    opening = (
        f"Compliance assessment against {cr.regulation_set} returned an overall "
        f"<b>{cr.overall_verdict}</b> verdict"
    )
    if not failed:
        sentence = f"{opening}, with all {len(passed)} applicable rule(s) satisfied."
    else:
        failed_desc = "; ".join(
            f"{c.rule_id} ({_pdf_text(c.description)}, required {c.required}, found {c.found})"
            for c in failed
        )
        sentence = (
            f"{opening}. {len(passed)} of {len(applicable)} applicable rule(s) passed; "
            f"the following did not: {failed_desc}."
        )
    return sentence


def _styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle("title", parent=base["Title"], textColor=_NAVY, fontSize=20),
        "subtitle": ParagraphStyle("subtitle", parent=base["Normal"], textColor=_GRAY, fontSize=10),
        "h2": ParagraphStyle("h2", parent=base["Heading2"], textColor=_NAVY, fontSize=13, spaceBefore=14, spaceAfter=6),
        "body": ParagraphStyle("body", parent=base["BodyText"], fontSize=9, leading=13),
        "small": ParagraphStyle("small", parent=base["BodyText"], fontSize=8, textColor=_GRAY, leading=11),
    }


def generate_report_pdf(
    vm: ResultsViewModel,
    project_id: str,
    category_labels: dict[str, str],
) -> bytes:
    """Render vm into a formatted PDF report, returned as bytes (for st.download_button)."""
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=2 * cm, rightMargin=2 * cm, topMargin=1.8 * cm, bottomMargin=1.8 * cm,
    )
    s = _styles()
    deck_name = Path(vm.image_path).stem
    story = []

    story.append(Paragraph("Ship Plan Compliance Auditor", s["title"]))
    story.append(Paragraph(f"Fire Equipment Detection Report &nbsp;&middot;&nbsp; {project_id} / {deck_name}", s["subtitle"]))
    story.append(Spacer(1, 0.6 * cm))

    cr = vm.compliance_result
    total = sum(vm.total_by_category.values())
    verdict = cr.overall_verdict if cr else "N/A"
    summary_data = [["Equipment Detected", "Instances Located", "Compliance Verdict"],
                     [str(total), str(len(vm.instances)), verdict]]
    summary_table = Table(summary_data, colWidths=[5.5 * cm] * 3)
    summary_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), _LIGHT_BG),
        ("TEXTCOLOR", (0, 0), (-1, 0), _GRAY),
        ("FONTSIZE", (0, 0), (-1, 0), 8),
        ("FONTSIZE", (0, 1), (-1, 1), 16),
        ("FONTNAME", (0, 1), (-1, 1), "Helvetica-Bold"),
        ("TEXTCOLOR", (2, 1), (2, 1), _VERDICT_COLOR.get(verdict, colors.black)),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#E5E6EB")),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E5E6EB")),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(summary_table)

    # Equipment Highlight image (full highlight — independent of any on-screen selection)
    try:
        img = render_spotlight_node(vm, None, None)
        img_buf = BytesIO()
        img.convert("RGB").save(img_buf, format="PNG")
        img_buf.seek(0)
        w, h = img.size
        max_w = 17 * cm
        scale = min(1.0, max_w / w)
        story.append(Spacer(1, 0.6 * cm))
        story.append(Paragraph("Equipment Highlight", s["h2"]))
        story.append(RLImage(img_buf, width=w * scale, height=h * scale))
    except Exception:
        pass

    # Detection Findings (from the model's raw reasoning trace) — ahead of
    # Equipment Inventory, since these are the per-instance findings the
    # inventory counts are aggregated from.
    sections = parse_reasoning_trace(vm.raw_response) if vm.raw_response else {}
    detections = sections.get("DETECTION_LIST", {})
    validation = sections.get("VALIDATION", {})

    if detections:
        story.append(Paragraph("Detection Findings", s["h2"]))
        det_rows = [["#", "Visual Description", "Label", "Location"]]
        for i, (_inst_id, fields) in enumerate(detections.items(), start=1):
            det_rows.append([
                str(i),
                Paragraph(_pdf_text(fields.get("visual_features", "")), s["body"]),
                _pdf_text(fields.get("nearby_text", "")),
                Paragraph(_pdf_text(fields.get("location", "")), s["body"]),
            ])
        det_table = Table(det_rows, colWidths=[1 * cm, 7 * cm, 2.5 * cm, 5.6 * cm])
        det_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), _LIGHT_BG),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E5E6EB")),
            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#E5E6EB")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        story.append(det_table)

    # Equipment Inventory
    story.append(Paragraph("Equipment Inventory", s["h2"]))
    inv_rows = [["Category", "Count"]]
    for cat, count in vm.total_by_category.items():
        inv_rows.append([Paragraph(_pdf_text(category_labels.get(cat, cat)), s["body"]), str(count)])
    inv_table = Table(inv_rows, colWidths=[10 * cm, 3 * cm])
    inv_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), _LIGHT_BG),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E5E6EB")),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#E5E6EB")),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(inv_table)

    # IMO Compliance Check
    if cr is not None:
        story.append(Paragraph("IMO Compliance Check", s["h2"]))
        if cr.is_mock:
            story.append(Paragraph("Illustrative rules only — not for regulatory submission.", s["small"]))
            story.append(Spacer(1, 0.2 * cm))
        rule_rows = [["Rule", "Description", "Required", "Found", "Status"]]
        for check in cr.checks:
            rule_rows.append([
                check.rule_id,
                Paragraph(
                    f"{_pdf_text(check.description)}<br/><font size=7 color='#86909C'>{check.article}</font>",
                    s["body"],
                ),
                check.required or "—",
                check.found or "—",
                _STATUS_LABEL.get(check.status, check.status.upper()),
            ])
        rule_table = Table(rule_rows, colWidths=[1.5 * cm, 7.5 * cm, 2.3 * cm, 2.3 * cm, 2.5 * cm])
        style = [
            ("BACKGROUND", (0, 0), (-1, 0), _LIGHT_BG),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E5E6EB")),
            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#E5E6EB")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]
        for i, check in enumerate(cr.checks, start=1):
            style.append(("TEXTCOLOR", (4, i), (4, i), _STATUS_COLOR.get(check.status, colors.black)))
            style.append(("FONTNAME", (4, i), (4, i), "Helvetica-Bold"))
        rule_table.setStyle(TableStyle(style))
        story.append(rule_table)

    # Analysis Summary — short prose synthesis of the model's validation
    # checks and the IMO compliance result, instead of checklists/tables.
    if validation or cr is not None:
        story.append(Paragraph("Analysis Summary", s["h2"]))
        if validation:
            story.append(Paragraph(_analysis_summary(validation, total), s["body"]))
            story.append(Spacer(1, 0.2 * cm))
        if cr is not None:
            story.append(Paragraph(_compliance_summary(cr), s["body"]))

    doc.build(story)
    return buf.getvalue()
