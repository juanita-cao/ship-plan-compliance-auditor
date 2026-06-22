"""
Fire Equipment Detection — Streamlit UI
3-state machine: IDLE → RUNNING → RESULTS
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

from PIL import Image as _PILImage

# Ensure service root is on sys.path
_SERVICE_ROOT = Path(__file__).parent.parent.parent
if str(_SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(_SERVICE_ROOT))

from dotenv import load_dotenv
load_dotenv(_SERVICE_ROOT / "src" / "backend" / "configs" / ".env")

import streamlit as st  # noqa: E402

from src.frontend.pipeline_runner import _TIMEOUT_S, clear_job, poll_job, start_detection  # noqa: E402
from src.frontend.spotlight import render_spotlight_node  # noqa: E402
from src.frontend.state import resolve_next_state  # noqa: E402
from src.frontend.view_models import ResultsViewModel  # noqa: E402

# ─── Dev flags ───────────────────────────────────────────────────────────────

_USE_MOCK = os.getenv("FEH_MOCK", "0") == "1"

# ─── Project (ADR-F13 — ship selector; demo_ship_a/b both validated end-to-end) ──

_PROJECT_DEFAULT = "demo_ship_a"


def _images_dir(project_id: str) -> Path:
    return _SERVICE_ROOT / "data" / "images" / project_id


def _prompt_for(project_id: str) -> tuple[str, str]:
    path = _SERVICE_ROOT / "data" / "prompts" / f"prompt_cot_counts_{project_id}.txt"
    text = path.read_text().strip()
    return text, path.stem


# ─── Category display config ─────────────────────────────────────────────────
# One flat dict for both projects — category name strings don't collide across
# projects, so no per-project nesting is needed.

_CATEGORY_DISPLAY: dict[str, dict] = {
    # demo_ship_a
    "extinguisher_CO2_5kg":              {"label": "CO₂ 5kg",              "color": "#0FC6C2"},
    "extinguisher_CO2_5kg_spare":        {"label": "CO₂ 5kg (spare)",      "color": "#0FC6C2"},
    "extinguisher_dry_powder_6kg":       {"label": "Dry Powder 6kg",        "color": "#FF7D00"},
    "extinguisher_dry_powder_6kg_spare": {"label": "Dry Powder 6kg (spare)", "color": "#FF7D00"},
    "extinguisher_foam_9L":              {"label": "Foam 9L",               "color": "#1664FF"},
    "extinguisher_foam_9L_spare":        {"label": "Foam 9L (spare)",       "color": "#1664FF"},
    # demo_ship_b (extinguisher_CO2_5kg shared with demo_ship_a above)
    "extinguisher_DCP_5kg":              {"label": "DCP 5kg",               "color": "#FF7D00"},
    "extinguisher_wheeld_foam_45L":      {"label": "Wheeled Foam 45L",      "color": "#1664FF"},
    "extinguisher_water_9L":             {"label": "Water 9L",              "color": "#7B61FF"},
}
_CATEGORY_FALLBACK = {"label": None, "color": "#F5A623"}  # label filled in with the raw category name

_NAVY = "#125993"

# ─── Mock fixture (Step 3 Mock Shell) ─────────────────────────────────────────
# Mock mode shows whatever the latest real eval_runs row is for the selected
# image — same source of truth (Postgres) as the real detection path, no
# separate file-based fixture to keep in sync.

_MOCK_DEFAULT_IMAGE = "a_deck"


@st.cache_resource
def _build_mock_vm(project_id: str, image_stem: str) -> ResultsViewModel:
    """Load the latest eval_runs row for this (project, image) from Postgres (no API call)."""
    from src.backend.db_results import get_latest_eval_run
    from src.frontend.view_models import build_results_viewmodel_from_report_data

    images_dir = _images_dir(project_id)
    image_path = images_dir / f"{image_stem}.png"
    if not image_path.exists():
        image_stem = _MOCK_DEFAULT_IMAGE
        image_path = images_dir / f"{image_stem}.png"

    row = get_latest_eval_run(image_stem, project_id)
    if row is None:
        raise ValueError(
            f"No eval_runs row found for project_id={project_id!r}, image_stem={image_stem!r}. "
            "Run run_eval.py for this image at least once first."
        )

    return build_results_viewmodel_from_report_data(
        row["report_data"], image_path, row["session_id"], project_id,
        raw_response=row["raw_response_cloud"],
    )

# ─── CSS ─────────────────────────────────────────────────────────────────────

_CSS = f"""
<style>
/* Hide Streamlit chrome */
#MainMenu, footer, header {{ visibility: hidden; }}
.block-container {{ padding-top: 0 !important; }}

.stApp {{
    background-color: #f2f3f5;
    color: #1d2129;
}}
/* Widget labels */
[data-testid="stWidgetLabel"] p,
[data-testid="stWidgetLabel"] label,
.stSelectbox label {{
    color: #1d2129 !important;
}}
/* Error / warning alerts */
[data-testid="stAlert"] p,
[data-testid="stAlert"] div {{
    color: #1d2129 !important;
}}
/* Header bar */
.feh-header {{
    background: {_NAVY};
    padding: 14px 32px 12px;
    margin: 0 -1rem 1.5rem -1rem;
    display: flex;
    align-items: baseline;
    gap: 12px;
}}
.feh-header-title {{
    color: #ffffff !important;
    font-size: 18px;
    font-weight: 600;
    letter-spacing: 0.2px;
    margin: 0;
}}
.feh-header-sub {{
    color: rgba(255,255,255,0.65) !important;
    font-size: 12px;
    margin: 0;
}}
/* Cards */
.feh-card {{
    background: #ffffff;
    border: 1px solid #e5e6eb;
    border-radius: 4px;
    padding: 8px 24px;
    margin-bottom: 16px;
}}
.feh-card-title {{
    font-size: 14px;
    font-weight: 600;
    color: #1d2129;
    margin-bottom: 0px;
    padding-bottom: 0px;
}}
/* Section header (smaller version of the top navy bar) */
.feh-section-header {{
    background: {_NAVY};
    color: #ffffff;
    padding: 8px 16px;
    border-radius: 4px;
    font-size: 13px;
    font-weight: 600;
    margin: 20px 0 10px;
}}
/* Metric card */
.feh-metric {{
    background: #ffffff;
    border: 1px solid #e5e6eb;
    border-radius: 4px;
    padding: 14px 18px;
    text-align: center;
    margin-bottom: 16px;
}}
.feh-metric-value {{
    font-size: 28px;
    font-weight: 700;
    color: #1d2129;
    line-height: 1.2;
}}
.feh-metric-label {{
    font-size: 12px;
    color: #86909c;
    margin-top: 4px;
}}
/* Divider */
.feh-divider {{
    height: 1px;
    background: #e5e6eb;
    margin: 4px 0 20px;
}}
/* Category buttons */
.feh-cat-btn button {{
    background: #ffffff !important;
    border: 1px solid #e5e6eb !important;
    color: #1d2129 !important;
    border-radius: 3px !important;
    font-size: 13px !important;
    text-align: left !important;
    padding: 5px 10px !important;
    width: 100% !important;
}}
.feh-cat-btn-active button {{
    background: #e8f4ff !important;
    border-color: {_NAVY} !important;
    color: {_NAVY} !important;
    font-weight: 600 !important;
}}
/* Category rows */
.feh-cat-row {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 6px 0;
    border-bottom: 1px solid #f7f8fa;
    font-size: 13px;
    color: #1d2129;
}}
.feh-inst-row {{
    font-size: 12px;
    color: #4e5969;
    padding: 4px 0 4px 18px;
    border-bottom: 1px solid #f7f8fa;
}}
.feh-total {{
    font-size: 13px;
    font-weight: 600;
    color: #1d2129;
    padding-top: 10px;
}}
/* Compliance rule rows */
.feh-rule-row {{
    display: flex;
    align-items: flex-start;
    gap: 12px;
    padding: 10px 0;
    border-bottom: 1px solid #f2f3f5;
}}
.feh-rule-id {{
    font-size: 11px;
    font-weight: 600;
    color: #4e5969;
    width: 32px;
    flex-shrink: 0;
    margin-top: 2px;
}}
.feh-rule-body {{
    flex: 1;
}}
.feh-rule-article {{
    font-size: 11px;
    color: #86909c;
    margin-bottom: 2px;
}}
.feh-rule-desc {{
    font-size: 13px;
    color: #1d2129;
    margin-bottom: 3px;
}}
.feh-rule-meta {{
    font-size: 11px;
    color: #86909c;
}}
.feh-rule-meta code {{
    background: #f2f3f5;
    padding: 1px 4px;
    border-radius: 2px;
    font-size: 11px;
}}
.feh-badge {{
    display: inline-block;
    padding: 2px 8px;
    border-radius: 2px;
    font-size: 12px;
    font-weight: 600;
    line-height: 20px;
    flex-shrink: 0;
}}
/* Results: constrain deck plan image height */
.feh-plan-img [data-testid="stImage"] img {{
    max-height: 560px;
    width: 100% !important;
    object-fit: contain;
    object-position: top;
}}
/* Center images horizontally within their column */
[data-testid="stImage"] {{
    display: flex;
    justify-content: center;
}}
/* Secondary button override — st.download_button uses a different testid
   (stDownloadButton) than st.button (stButton), so both need this rule for
   Download Report to match New Analysis. */
[data-testid="stButton"] > button[kind="secondary"],
[data-testid="stDownloadButton"] > button[kind="secondary"] {{
    background: #ffffff !important;
    border: 1px solid #e5e6eb !important;
    color: #1d2129 !important;
    text-align: left !important;
}}
/* Detection Reasoning Trace expander — same card-title look as Original Plan etc. */
[data-testid="stExpander"] summary {{
    background: #ffffff !important;
    border: 1px solid #e5e6eb !important;
    border-radius: 4px !important;
    padding: 10px 16px !important;
}}
[data-testid="stExpander"] summary p {{
    font-size: 14px !important;
    font-weight: 600 !important;
    color: #1d2129 !important;
}}
/* Reasoning trace — report typography, white card like Original Plan etc. */
.feh-trace-card {{
    background: #ffffff;
    border: 1px solid #e5e6eb;
    border-radius: 4px;
    padding: 4px 20px 16px;
}}
.feh-trace-heading {{
    font-size: 13px;
    font-weight: 700;
    color: {_NAVY};
    text-transform: uppercase;
    letter-spacing: 0.4px;
    margin: 18px 0 8px;
    padding-top: 12px;
    border-top: 1px solid #f2f3f5;
}}
.feh-trace-heading:first-of-type {{
    border-top: none;
    padding-top: 4px;
}}
.feh-trace-list {{
    list-style: none;
    margin: 0;
    padding: 0;
}}
.feh-trace-list > li {{
    font-size: 13px;
    color: #1d2129;
    padding: 6px 0;
    border-bottom: 1px solid #f7f8fa;
}}
.feh-trace-list > li:last-child {{
    border-bottom: none;
}}
.feh-trace-key {{
    font-weight: 600;
    color: #1d2129;
}}
.feh-trace-value {{
    color: #4e5969;
}}
.feh-trace-sublist {{
    list-style: none;
    margin: 6px 0 0;
    padding: 0 0 0 16px;
}}
.feh-trace-sublist > li {{
    font-size: 12px;
    color: #4e5969;
    line-height: 1.6;
    padding: 2px 0;
}}
.feh-trace-subkey {{
    font-weight: 600;
    color: #86909c;
}}
</style>
"""

# ─── Session state helpers ────────────────────────────────────────────────────

_STATE_DEFAULTS = {
    "stage": "IDLE",
    "project_id": _PROJECT_DEFAULT,
    "image_path": None,
    "results_vm": None,
    "job_status": "none",
    "last_error": None,
    "selected_category": None,
    "selected_instance_id": None,
    "session_id": None,
}


def _init_state() -> None:
    for k, v in _STATE_DEFAULTS.items():
        if k not in st.session_state:
            st.session_state[k] = v


def _apply_patch(patch: dict) -> None:
    for k, v in patch.items():
        st.session_state[k] = v


# ─── Image helpers ───────────────────────────────────────────────────────────

_PREVIEW_BOX = (760, 340)  # max (width, height) for idle preview thumbnail


def _load_preview(path: str | Path) -> _PILImage.Image:
    img = _PILImage.open(path).convert("RGB")
    img.thumbnail(_PREVIEW_BOX, _PILImage.LANCZOS)
    return img



# ─── Image listing ────────────────────────────────────────────────────────────

def _list_images(project_id: str) -> list[Path]:
    """Decks for this project that have at least one validated eval_runs row.

    Same "verified only" spirit as ADR-F11, but DB-driven instead of relying
    on unvalidated images having been deleted from data/images/ — so a newly
    validated image becomes selectable automatically, no code/file change.
    """
    from src.backend.db_results import list_validated_image_stems

    images_dir = _images_dir(project_id)
    if not images_dir.exists():
        return []
    validated = set(list_validated_image_stems(project_id))
    return sorted(
        p for p in images_dir.glob("*.png")
        if not p.name.startswith("._") and p.stem in validated
    )


# ─── Render functions ─────────────────────────────────────────────────────────

def _render_idle() -> None:
    from src.backend import category_lookup

    project_ids = category_lookup.list_project_ids()
    current_project = st.session_state.get("project_id", _PROJECT_DEFAULT)
    proj_idx = project_ids.index(current_project) if current_project in project_ids else 0

    col_ship, col_deck, col_btn = st.columns([1.4, 2, 1])
    with col_ship:
        selected_project = st.selectbox(
            "Ship", project_ids, index=proj_idx, label_visibility="collapsed"
        )
    if selected_project != current_project:
        # Ship changed — drop any deck selection carried over from the old project.
        st.session_state["project_id"] = selected_project
        st.session_state["image_path"] = None

    images = _list_images(selected_project)
    if not images:
        st.warning(f"No validated decks found for {selected_project!r} yet.")
        return

    image_names = [p.name for p in images]
    current = st.session_state.get("image_path")
    current_name = Path(current).name if current else None
    default_idx = image_names.index(current_name) if current_name in image_names else 0

    with col_deck:
        selected_name = st.selectbox(
            "Deck Plan", image_names, index=default_idx, label_visibility="collapsed"
        )
    with col_btn:
        run_clicked = st.button("▶  Run Analysis", type="primary", use_container_width=True)

    selected_path = str(_images_dir(selected_project) / selected_name)
    st.session_state["image_path"] = selected_path

    # Image sits directly under the Ship dropdown — same column width/position,
    # not centered on the full row (which would drift right of the Ship selector).
    col_img_pos, _, _ = st.columns([1.4, 2, 1])
    with col_img_pos:
        st.image(_load_preview(selected_path))

    if st.session_state.get("last_error"):
        st.error(st.session_state["last_error"])

    if run_clicked:
        result = resolve_next_state(
            current_state="IDLE",
            event="analyze_clicked",
            guard_result={"image_path": st.session_state.get("image_path")},
        )
        _apply_patch(result.session_state_patch)
        if result.next_state == "RUNNING" and not _USE_MOCK:
            import uuid
            sid = str(uuid.uuid4())
            st.session_state["session_id"] = sid
            prompt, prompt_label = _prompt_for(selected_project)
            start_detection(
                session_id=sid,
                image_path=Path(st.session_state["image_path"]),
                prompt=prompt,
                prompt_label=prompt_label,
                project_id=selected_project,
            )
        st.rerun()


def _render_running() -> None:
    if _USE_MOCK:
        with st.spinner("Analyzing..."):
            time.sleep(1)
        image_stem = Path(st.session_state.get("image_path", "")).stem
        project_id = st.session_state.get("project_id", _PROJECT_DEFAULT)
        result = resolve_next_state(
            "RUNNING", "pipeline_complete",
            {"results_vm": _build_mock_vm(project_id, image_stem)},
        )
        _apply_patch(result.session_state_patch)
        st.rerun()
        return

    sid = st.session_state.get("session_id")

    if sid is None:
        result = resolve_next_state("RUNNING", "pipeline_error", {"error_msg": "No job ID"})
        _apply_patch(result.session_state_patch)
        st.rerun()
        return

    with st.spinner("Analyzing..."):
        while True:
            job = poll_job(sid)
            if job and job["status"] != "running":
                break
            if job and (time.time() - job.get("started_at", time.time())) > _TIMEOUT_S:
                result = resolve_next_state(
                    "RUNNING", "pipeline_error",
                    {"error_msg": f"Detection timed out after {_TIMEOUT_S}s — check logs"},
                )
                clear_job(sid)
                _apply_patch(result.session_state_patch)
                st.rerun()
                return
            time.sleep(1)

    if job["status"] == "success":
        result = resolve_next_state(
            "RUNNING", "pipeline_complete", {"results_vm": job["vm"]}
        )
        clear_job(sid)
    else:
        result = resolve_next_state(
            "RUNNING", "pipeline_error", {"error_msg": job.get("error", "Unknown error")}
        )
        clear_job(sid)

    _apply_patch(result.session_state_patch)
    st.rerun()


_TRACE_SECTION_TITLE = {
    "DETECTION_LIST": "Detection List",
    "MATCHING": "Matching",
    "CHECKLIST": "Checklist",
    "EXCLUDED": "Excluded",
    "VALIDATION": "Validation",
    "RESULT": "Result",
}
_TRACE_KEY_LABEL = {
    "missing_detection": "Missing Detection",
    "misclassification": "Misclassification",
    "count_consistency": "Count Consistency",
    "unknown": "Unknown",
    "excluded_boundary": "Excluded (Boundary-Cut)",
}


def _trace_key_label(key: str) -> str:
    """Pretty-print a section's bullet key: instance ids, known fixed labels,
    or fall back to this app's existing category display labels/raw name."""
    import re

    if re.fullmatch(r"instance_\d+", key):
        return f"Instance {key.split('_')[1]}"
    if key in _TRACE_KEY_LABEL:
        return _TRACE_KEY_LABEL[key]
    return _CATEGORY_DISPLAY.get(key, {}).get("label", key)


def _render_reasoning_trace(raw_response: str) -> None:
    """Render every STEP1-4 section (all content kept, nothing summarized away)
    with report-style typography — section headings, bold labels, nested
    bullets — instead of a monospace text dump."""
    from src.frontend.report_text import parse_reasoning_trace

    sections = parse_reasoning_trace(raw_response)
    html = ['<div class="feh-trace-card">']
    for name, items in sections.items():
        if not items:
            continue
        html.append(f'<div class="feh-trace-heading">{_TRACE_SECTION_TITLE.get(name, name.title())}</div>')
        html.append('<ul class="feh-trace-list">')
        for key, fields in items.items():
            value = fields.get("value", "")
            entry = f'<span class="feh-trace-key">{_trace_key_label(key)}</span>'
            if value:
                entry += f' <span class="feh-trace-value">{value}</span>'
            sub_fields = {k: v for k, v in fields.items() if k != "value" and v}
            if sub_fields:
                entry += '<ul class="feh-trace-sublist">'
                for subkey, subval in sub_fields.items():
                    label = subkey.replace("_", " ").title()
                    entry += f'<li><span class="feh-trace-subkey">{label}:</span> {subval}</li>'
                entry += "</ul>"
            html.append(f"<li>{entry}</li>")
        html.append("</ul>")
    html.append("</div>")
    st.markdown("".join(html), unsafe_allow_html=True)


def _render_compliance_panel(vm: ResultsViewModel) -> None:
    cr = vm.compliance_result
    if cr is None:
        return

    _STATUS_BADGE = {
        "pass":           ("#E8FFEA", "#00B42A", "PASS"),
        "fail":           ("#FFECE8", "#F53F3F", "FAIL"),
        "warning":        ("#FFF7E8", "#FF7D00", "WARN"),
        "not_applicable": ("#f2f3f5", "#86909c", "N/A"),
    }

    mock_badge = (
        ' <span style="font-size:11px;background:#f2f3f5;border:1px solid #e5e6eb;'
        'border-radius:3px;padding:1px 6px;color:#4e5969">MOCK</span>'
        if cr.is_mock else ""
    )
    # Title text + verdict now live in the section header / Compliance Verdict
    # metric card above this panel (see _render_results) — this card only
    # carries the MOCK badge (if any) and the rule list.
    st.markdown(
        f'<div class="feh-card"><div class="feh-card-title">{mock_badge}</div>',
        unsafe_allow_html=True,
    )
    if cr.is_mock:
        st.markdown(
            '<div style="font-size:11px;color:#86909c;margin-bottom:12px">'
            '⚠️ Illustrative rules only — not for regulatory submission.</div>',
            unsafe_allow_html=True,
        )
    for check in cr.checks:
        bg, fg, lbl = _STATUS_BADGE.get(check.status, ("#f2f3f5", "#86909c", "—"))
        req_str = f"req: <code>{check.required}</code>" if check.required else ""
        found_str = f"found: <code>{check.found}</code>" if check.found else ""
        meta = " &nbsp;·&nbsp; ".join(filter(None, [req_str, found_str]))
        st.markdown(
            f'<div class="feh-rule-row">'
            f'<div class="feh-rule-id">{check.rule_id}</div>'
            f'<div class="feh-rule-body">'
            f'<div class="feh-rule-article">{check.article}</div>'
            f'<div class="feh-rule-desc">{check.description}</div>'
            f'<div class="feh-rule-meta">{meta}</div>'
            f'</div>'
            f'<span class="feh-badge" style="background:{bg};color:{fg}">{lbl}</span>'
            f'</div>',
            unsafe_allow_html=True,
        )
    st.markdown("</div>", unsafe_allow_html=True)


def _render_results(vm: ResultsViewModel) -> None:
    from src.frontend.pdf_report import generate_report_pdf

    fname = Path(vm.image_path).name
    project_id = st.session_state.get("project_id", _PROJECT_DEFAULT)

    col_title, col_pdf, col_btn = st.columns([5, 1.4, 1])
    with col_title:
        st.markdown(
            f'<p style="color:#1d2129;font-weight:600;font-size:15px;margin:0 0 8px">{fname}</p>',
            unsafe_allow_html=True,
        )
    with col_pdf:
        category_labels = {cat: cfg["label"] for cat, cfg in _CATEGORY_DISPLAY.items()}
        pdf_bytes = generate_report_pdf(vm, project_id, category_labels)
        st.download_button(
            "⬇ Download Report",
            data=pdf_bytes,
            file_name=f"{Path(vm.image_path).stem}_report.pdf",
            mime="application/pdf",
            use_container_width=True,
        )
    with col_btn:
        if st.button("↺ New Analysis", use_container_width=True):
            result = resolve_next_state("RESULTS", "new_analysis_clicked", {})
            _apply_patch(result.session_state_patch)
            st.rerun()

    total = sum(vm.total_by_category.values())
    cr = vm.compliance_result
    verdict = cr.overall_verdict if cr else "—"
    verdict_color = {"GO": "#00B42A", "NO_GO": "#F53F3F", "CONDITIONAL": "#FF7D00"}.get(verdict, "#1d2129")

    def _metric(col, value, label, v_color="#1d2129") -> None:
        markup = (
            f'<div class="feh-metric">'
            f'<div class="feh-metric-value" style="color:{v_color}">{value}</div>'
            f'<div class="feh-metric-label">{label}</div>'
            f'</div>'
        )
        if col is None:
            st.markdown(markup, unsafe_allow_html=True)
        else:
            with col:
                st.markdown(markup, unsafe_allow_html=True)

    # ── Section 1: Fire Equipment Detection ─────────────────────────────────
    st.markdown('<div class="feh-section-header">Fire Equipment Detection</div>', unsafe_allow_html=True)

    m1, m2 = st.columns(2)
    _metric(m1, total, "Equipment Detected")
    _metric(m2, len(vm.instances), "Instances Located")

    selected_cat = st.session_state.get("selected_category")
    selected_inst = st.session_state.get("selected_instance_id")

    col_orig, col_img, col_panel = st.columns([3, 3, 2])

    with col_orig:
        st.markdown('<div class="feh-card"><div class="feh-card-title">Original Plan</div>', unsafe_allow_html=True)
        original = _PILImage.open(vm.image_path).convert("RGB")
        original.thumbnail((760, 560), _PILImage.LANCZOS)
        st.image(original)
        st.markdown("</div>", unsafe_allow_html=True)

    with col_img:
        st.markdown('<div class="feh-card"><div class="feh-card-title">Equipment Highlight</div>', unsafe_allow_html=True)
        spotlight = render_spotlight_node(vm, selected_cat, selected_inst)
        spotlight.thumbnail((760, 560), _PILImage.LANCZOS)
        st.image(spotlight)
        st.markdown("</div>", unsafe_allow_html=True)

    with col_panel:
        st.markdown('<div class="feh-card"><div class="feh-card-title">Equipment Inventory</div>', unsafe_allow_html=True)
        st.caption("Select a category to highlight on the plan.")

        total_all = sum(vm.total_by_category.values())
        is_all_active = selected_cat is None and selected_inst is None
        all_btn_class = "feh-cat-btn-active" if is_all_active else "feh-cat-btn"
        st.markdown(f'<div class="{all_btn_class}">', unsafe_allow_html=True)
        if st.button(
            f"● All Found Equipment  ×{total_all}",
            key="cat_all",
            use_container_width=True,
        ):
            result = resolve_next_state("RESULTS", "show_all_clicked", {})
            _apply_patch(result.session_state_patch)
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

        for cat, count in vm.total_by_category.items():
            cfg = _CATEGORY_DISPLAY.get(cat) or {"label": cat, "color": _CATEGORY_FALLBACK["color"]}
            is_active = selected_cat == cat
            cat_instances = [i for i in vm.instances if i.category == cat]
            btn_class = "feh-cat-btn-active" if is_active else "feh-cat-btn"

            st.markdown(f'<div class="{btn_class}">', unsafe_allow_html=True)
            if st.button(
                f"● {cfg['label']}  ×{count}",
                key=f"cat_{cat}",
                use_container_width=True,
            ):
                if is_active:
                    result = resolve_next_state("RESULTS", "show_all_clicked", {})
                else:
                    result = resolve_next_state("RESULTS", "category_clicked", {"category": cat})
                _apply_patch(result.session_state_patch)
                st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)

            if is_active and cat_instances:
                for inst in cat_instances:
                    st.markdown(
                        f'<div class="feh-inst-row">{inst.location_desc}'
                        f' — <em>{inst.nearby_text}</em></div>',
                        unsafe_allow_html=True,
                    )

        st.markdown(
            f'<div class="feh-total">Total detected: {total}</div>',
            unsafe_allow_html=True,
        )
        st.markdown("</div>", unsafe_allow_html=True)

    if vm.raw_response:
        with st.expander("Detection Reasoning Trace", expanded=False):
            _render_reasoning_trace(vm.raw_response)

    # ── Section 2: IMO Compliance Check ──────────────────────────────────────
    st.markdown('<div class="feh-section-header">IMO Compliance Check</div>', unsafe_allow_html=True)
    col_verdict, _ = st.columns([1, 3])
    _metric(col_verdict, verdict, "Compliance Verdict", verdict_color)
    _render_compliance_panel(vm)


# ─── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    st.set_page_config(page_title="Ship Plan Compliance Auditor", layout="wide")
    st.markdown(_CSS, unsafe_allow_html=True)
    st.markdown(
        '<div class="feh-header">'
        '<p class="feh-header-title">Ship Plan Compliance Auditor</p>'
        "</div>",
        unsafe_allow_html=True,
    )

    _init_state()

    stage = st.session_state.get("stage", "IDLE")

    if stage == "IDLE":
        _render_idle()
    elif stage == "RUNNING":
        _render_running()
    elif stage == "RESULTS":
        vm = st.session_state.get("results_vm")
        if vm is None:
            st.error("No results available.")
            _apply_patch({"stage": "IDLE", "job_status": "none"})
            st.rerun()
        else:
            _render_results(vm)


if __name__ == "__main__":
    main()
