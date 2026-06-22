# Ship Plan Compliance Auditor — Frontend Design Document

**Service:** `ship_plan_auditor`
**Component:** Streamlit UI (`src/frontend/app_streamlit.py`)
**Status:** Design phase
**Depends on:** `design_backend.md` (backend pipeline), `src/viz.py` (spotlight rendering)
**UI Reference:** ported CSS tokens, card layout, and header bar conventions from an earlier internal Streamlit UI

---

## 1. Overview

A Streamlit web UI exposing fire equipment detection as a single-button end-user tool.

User selects a ship plan image → system detects fire extinguisher instances → displays the original image and an annotated spotlight image side by side, plus count summary and compliance verdict.

All pipeline internals (LLM selection, number of runs, voting mechanism, prompt) are hidden from the user. The UI is a clean detection interface — input is an image, output is a list of detected equipment.

---

## 2. UI State Machine

```
IDLE ─────── [Analyze] ──────► RUNNING ─── pipeline_complete ──► RESULTS
  ▲                                 │                                │
  │                                 │ pipeline_error                 │
  │                                 ▼                                │
  └──────────────── [↺ New Analysis] ◄────────────────────────────────
```

| State | Displayed content |
|-------|---------|
| `IDLE` | Image selector + Analyze button + image preview |
| `RUNNING` | Spinner "Analyzing..." |
| `RESULTS` | Metrics row + Original Plan + Equipment Highlight + equipment panel (incl. All Found Equipment) |

---

## 3. Session State Contract

```python
from __future__ import annotations
from typing import Literal
from pydantic import BaseModel

class FEHSessionState(BaseModel):
    # state machine
    stage: Literal["IDLE", "RUNNING", "RESULTS"] = "IDLE"

    # input
    image_path: str | None = None

    # result — ViewModel (converted from PipelineContext immediately after pipeline_complete, then discarded)
    results_vm: ResultsViewModel | None = None

    # background job status
    job_status: Literal["none", "running", "success", "error"] = "none"
    last_error: str | None = None

    # UI selection state (RESULTS)
    selected_category: str | None = None
    selected_instance_id: str | None = None
```

> `PipelineContext` is never stored in `session_state`; render functions only accept `ResultsViewModel`.

---

## 4. Event → State Transition Table

| Current State | Event | Guard | Next State | session\_state\_patch |
|---|---|---|---|---|
| `IDLE` | `analyze_clicked` | `image_path is not None` | `RUNNING` | `stage="RUNNING"`, `job_status="running"`, `last_error=None` |
| `IDLE` | `analyze_clicked` | `image_path is None` | `IDLE` | — (inline error) |
| `RUNNING` | `pipeline_complete` | — | `RESULTS` | `stage="RESULTS"`, `job_status="success"`, `results_vm=build_results_viewmodel_from_report_data(row["report_data"], ...)` (writes via `save_eval_run` first, then reads the row back, ADR-008), `selected_*=None` |
| `RUNNING` | `pipeline_error` | — | `IDLE` | `stage="IDLE"`, `job_status="error"`, `last_error=error_msg`, `results_vm=None` |
| `RESULTS` | `new_analysis_clicked` | — | `IDLE` | `stage="IDLE"`, `job_status="none"`, `results_vm=None`, `selected_*=None`, `last_error=None` |
| `RESULTS` | `category_clicked` | — | `RESULTS` | `selected_category=cat`, `selected_instance_id=None` |
| `RESULTS` | `instance_clicked` | — | `RESULTS` | `selected_instance_id=id`, `selected_category=None` |
| `RESULTS` | `show_all_clicked` | — | `RESULTS` | `selected_category=None`, `selected_instance_id=None` |
| `*` | unrecognised `(state, event)` | — | — | **HARD FAIL** — raises `ValueError` |

---

## 5. Frontend Pipeline Table

| Node | D/E | Primitive | Node Name | Business Purpose | Args | Return Type | Side Effects | Methodology | Method | Model | Runtime | Error Strategy |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| F-State | E | Select | Resolve Next UI State | Pure function; event + guard → `StateTransitionResult`; does not write `st.session_state` directly | `current_state`, `user_event`, `guard_result` | `StateTransitionResult` | — | ⬜ | Event Guard Table | — | Python | HARD FAIL — unrecognised `(state, event)` raises `ValueError` |
| F-VM | E | Transform | Build Results ViewModel | `eval_runs.report_data` (the same persisted row, ADR-008) → `ResultsViewModel`; shared by both the mock and real paths | `report_data: dict`, `image_path`, `session_id`, `project_id`, `raw_response` | `ResultsViewModel` | — | ⬜ | Direct field mapping + E1b/D2 recomputed | — | Python / Pydantic | HARD FAIL — DB row missing → caller `raise RuntimeError` |
| F-Spotlight | E | Transform | Render Spotlight Image | Calls `render_spotlight()` to produce a PIL Image with bbox overlay | `vm: ResultsViewModel`, `selected_category`, `selected_instance_id` | `PIL.Image` | — | ⬜ | Direct call to `src.viz.render_spotlight` | — | Python / Pillow | SOFT: on render failure → returns the original image, logs WARN |

> **`StateTransitionResult`** = `NamedTuple("StateTransitionResult", [("next_state", str), ("session_state_patch", dict)])`. The app layer calls `_apply_patch(result.session_state_patch)` then `st.rerun()`.
>
> **`pipeline_runner.py`** is an execution-layer helper (not a pipeline-graph node) that calls `run_detection()` on a background thread; the result is written to the `_job_results[session_id]` dict, which the app layer polls.

---

## 6. Backend Integration Contract

```python
# New entry function (see pipeline.py) — frontend-only
run_detection(
    image_path: Path,
    prompt: str,          # resolved per project_id (_prompt_for(), data/prompts/prompt_cot_counts_{project_id}.txt); UI never exposes the actual text (kept private)
    n_runs: int = 5,      # default value; pipeline_runner actually passes n_runs=1; not exposed in the UI
    prompt_label: str,    # the prompt file's stem; not exposed in the UI
    backends: list[str] = ["cloud"],  # fixed to cloud; not exposed in the UI
    project_id: str = "demo_ship_a",  # ADR-006; switchable in the UI since ADR-F13 (Ship selector) — no longer pinned to a single ship
) -> PipelineContext
```

**Fields F-VM reads from `PipelineContext`:**

| Field | Purpose |
|------|------|
| `session_id: str` | Written to `ResultsViewModel.session_id` |
| `image_path: str` | Written to `ResultsViewModel.image_path` |
| `cloud_eval.voting.votes` | → `ResultsViewModel.total_by_category` (E4 consensus counts) |
| `cloud_eval.runs[0].counts.instances` | → `ResultsViewModel.instances` (used by spotlight) |

**Not read by the frontend:** `local_eval`, `report`, `accuracy`, `completed_nodes`, `node_timings`, `ground_truth`

---

## 7. ViewModel Contract

### 7.1 ViewModel Definition

**[Amendment — see ADR-008 (design_backend.md) / ADR-F15]** `ResultsViewModel` is no longer built directly from `PipelineContext` alone; both the mock and real paths now write the result to Postgres `eval_runs` first, then read it back from that same table to render (design_backend.md ADR-008). `compliance_result` (a field added after ADR-F12, documented here for completeness) and `raw_response` (ADR-F15, the model's raw STEP1-4 reasoning text) are the current actual field set:

```python
from __future__ import annotations
from pydantic import BaseModel
from src.backend.schemas import ComplianceResult, DetectedInstance

class ResultsViewModel(BaseModel):
    session_id: str
    image_path: str
    instances: list[DetectedInstance]            # used by spotlight rendering
    total_by_category: dict[str, int]             # shown as "detection results" (zero-filled per project_id's canonical categories)
    compliance_result: ComplianceResult | None = None   # D2 output; renders the IMO Compliance Check panel
    raw_response: str | None = None               # E1's raw text (STEP1-4 reasoning + JSON), ADR-F15; reasoning trace is not rendered when None
```

### 7.2 Transform Function

```python
def build_results_viewmodel_from_report_data(
    report_data: dict,       # eval_runs.report_data (JSONB, same structure as E5Report.data)
    image_path: Path,
    session_id: str,
    project_id: str,
    raw_response: str | None = None,  # eval_runs.raw_response_cloud
) -> ResultsViewModel:
    """Build a ViewModel from a stored eval_runs row (run_id=0 only).

    Shared by both the mock and real-detection paths — both call save_eval_run()
    first and then read back the same row, so there is exactly one rendering
    code path instead of two implementations that could drift apart (ADR-008).
    E1b (free, local OpenCV) and compliance are recomputed here rather than
    stored, because the JSON report itself does not carry display_bbox or the
    compliance result.
    """
    # ... instance_table.cloud (run_id=0) → list of DetectedInstance
    # → category_lookup.get_canonical_categories(project_id) zero-fills counts
    # → e1b_refine_centers() computes display_bbox → d2_check_compliance()
```

> Replaces the former `build_results_viewmodel(ctx)` — previously the only function allowed to reach into `PipelineContext`'s nested fields (deleted, ADR-008) — now both paths write to the DB first and read back, so there is no rendering path that reads `ctx` directly.

### 7.3 Mock Fixture

> **Why this approach:** every call hits a paid API, and development needs a long-lived toggle → Option B was chosen.
> Launch command: `FEH_MOCK=1 conda run -n ship-plan-auditor streamlit run src/frontend/app_streamlit.py`

**[Amendment — ADR-008]** No longer uses the hand-maintained `_MOCK_JSON_BY_IMAGE` filename dict — mock mode now queries the `eval_runs` table directly for the latest row for that `(project_id, image_stem)`, the same table and same source the real-detection path reads:

```python
@st.cache_resource
def _build_mock_vm(project_id: str, image_stem: str) -> ResultsViewModel:
    """Load the latest eval_runs row for this (project, image) from Postgres (no API call)."""
    row = get_latest_eval_run(image_stem, project_id)
    if row is None:
        raise ValueError(f"No eval_runs row for {project_id!r}/{image_stem!r} yet.")
    return build_results_viewmodel_from_report_data(
        row["report_data"], image_path, row["session_id"], project_id,
        raw_response=row["raw_response_cloud"],
    )
```

> The deck dropdown itself is now also DB-driven (`list_validated_image_stems(project_id)`, ADR-F13) — no longer relying on "delete unverified images from disk" (ADR-F11's earlier approach); newly validated images appear in the list automatically, with no code change or file deletion needed. `demo_ship_a` keeps using the 3 images ADR-F11 already cleaned up to (`a_deck`/`b_deck`/`bridge_deck`); `demo_ship_b` likewise only shows images that already have an `eval_runs` row (currently the three split crops `below_main_deck_bow/mid/stern`, design_backend.md ADR-007 Amendment).

---

## 8. Render Contract

The RESULTS-state render function accepts `vm: ResultsViewModel`, not `PipelineContext`.

| Component | Input | Output | Side Effects |
|---|---|---|---|
| Header bar | — | HTML title only: "Ship Plan Compliance Auditor" (ADR-F14; original subtitle removed) | — |
| IDLE Ship selector (ADR-F13) | `category_lookup.list_project_ids()` | `st.selectbox` to choose `project_id` | Writes `session_state.project_id`; clears `image_path` on change |
| IDLE Deck selector | `image_path` list filtered by `project_id` → `list_validated_image_stems(project_id)` | `st.selectbox` + centered preview (ADR-F14) | Writes `image_path` (widget callback) |
| IDLE Analyze button | `image_path`, `project_id` | `st.button` | — |
| RUNNING spinner | — | `st.spinner("Analyzing...")` | — |
| RESULTS "Fire Equipment Detection" section (ADR-F14, navy mini-title bar `.feh-section-header`) | — | Contains: 2 metric cards (Equipment Detected / Instances Located), the Original Plan / Equipment Highlight / Equipment Inventory three-column area, and the Detection Reasoning Trace expander | — |
| RESULTS Original Plan | `vm.image_path` | Unannotated original image, `PIL.Image` via `st.image()`, centered (CSS) | — |
| RESULTS Equipment Highlight | `vm.image_path`, `vm.instances`, `selected_category`, `selected_instance_id` | Annotated image with bbox overlay, `PIL.Image` via `st.image()`, centered (CSS) | — |
| RESULTS Equipment Inventory — All Found Equipment button | `vm.total_by_category` | First item in the list, shows the total across all categories; clicking clears the filter | Writes `selected_category=None`, `selected_instance_id=None` (`show_all_clicked`) |
| RESULTS Equipment Inventory — category buttons | `vm.total_by_category` (iterates the current project's actual categories — ADR-F13 fixed a bug where it previously always iterated `demo_ship_a`'s fixed 6 categories), `selected_category` | One button per category (with count) + expands instance rows (`location_desc` + `nearby_text`) when selected | Writes `selected_category` / `selected_instance_id` (widget callback) |
| RESULTS Detection Reasoning Trace (`st.expander`, ADR-F15) | `vm.raw_response: str \| None` | `None` → not rendered; otherwise renders a collapsible block containing the model's raw STEP1-4 reasoning text + JSON | — |
| RESULTS "IMO Compliance Check" section (ADR-F14, same navy mini-title bar style) | — | Contains: 1 metric card (Compliance Verdict), `_render_compliance_panel`'s rule list | — |
| RESULTS IMO Compliance Check panel (`_render_compliance_panel`) | `vm.compliance_result: ComplianceResult \| None` | `compliance_result=None` → not rendered; otherwise renders the `is_mock` disclaimer banner + one row per rule (`rule_id` / `article` / `description` / required vs. found / status badge pass=green·fail=red·warning=amber·not_applicable=grey); the overall verdict text and color now live in the Compliance Verdict metric card above, so the panel title no longer repeats it (ADR-F14) | — |
| [↺ New Analysis] button | — | `st.button` | — |

---

## 9. Error / Fallback Strategy

| Scenario | Severity | Behavior |
|------|------|------|
| Pipeline raises an exception (E1 API failure, network timeout, etc.) | SOFT | `RUNNING → IDLE`; `st.error()` shows the error; logs WARN |
| Image file missing / unreadable | HARD | Analyze button disabled + inline error; never enters `RUNNING` |
| `build_results_viewmodel()` fails (`cloud_eval` is None or runs is empty) | HARD FAIL | `RUNNING → IDLE`; `st.error()`; logs ERROR |
| `render_spotlight()` fails (corrupted image, etc.) | SOFT | Shows the original image with no overlay; logs WARN |
| unrecognised `(state, event)` | HARD FAIL | raises `ValueError`; never silently ignored |

---

## 10. Test Scenario List

### F-State node

| Scenario ID | Scenario | Input conditions | Expected behavior |
|---|---|---|---|
| F-State-S01 | IDLE + analyze, image present | `stage="IDLE"`, `event="analyze_clicked"`, `image_path` valid | `next_state="RUNNING"` |
| F-State-S02 | IDLE + analyze, no image | `stage="IDLE"`, `event="analyze_clicked"`, `image_path=None` | `next_state="IDLE"`, no transition |
| F-State-S03 | RUNNING + complete | `stage="RUNNING"`, `event="pipeline_complete"` | `next_state="RESULTS"`, `results_vm` is set, `selected_*=None` |
| F-State-S04 | RUNNING + failure | `stage="RUNNING"`, `event="pipeline_error"` | `next_state="IDLE"`, `last_error` is set |
| F-State-S05 | RESULTS + New Analysis | `stage="RESULTS"`, `event="new_analysis_clicked"` | `next_state="IDLE"`, all fields cleared |
| F-State-S06 | RESULTS + select category | `stage="RESULTS"`, `event="category_clicked"` | `selected_category` set, `selected_instance_id=None` |
| F-State-S07 | Unknown `(state, event)` | Any combination not in the table | HARD FAIL — raises `ValueError` |

### F-VM node

| Scenario ID | Scenario | Input conditions | Expected behavior |
|---|---|---|---|
| F-VM-S01 | Normal path, voting valid | `cloud_eval` valid, `runs` non-empty, `voting` not None | `total_by_category` comes from E4's `voted_count` |
| F-VM-S02 | voting is None (fallback) | `cloud_eval` valid, `voting=None` | `total_by_category` comes from `runs[0]` |
| F-VM-S03 | Tie handling | `voted_count=None`, `tied_candidates=[2, 3]` | Uses `tied_candidates[0]` (= 2) |
| F-VM-S04 | `cloud_eval` is None | `cloud_eval=None` | HARD FAIL — raises `ValueError` |
| F-VM-S05 | `runs` is empty | `cloud_eval.runs=[]` | HARD FAIL — raises `ValueError` |

### F-Spotlight node

| Scenario ID | Scenario | Input conditions | Expected behavior |
|---|---|---|---|
| F-Spotlight-S01 | `display_bbox` available | `inst.display_bbox is not None` | Draws using `display_bbox` |
| F-Spotlight-S02 | Falls back to center | `display_bbox=None`, `center is not None` | Draws a default-size box centered on `center` |
| F-Spotlight-S03 | Category filter | `selected_category="extinguisher_CO2_5kg"` | Only CO₂ instances are highlighted |
| F-Spotlight-S04 | Render failure | Corrupted image file | SOFT: returns the original image, logs WARN |

---

## 11. Layout

**[Amendment — ADR-F13/F14/F15]**

```
IDLE:
┌──────────────────────────────────────────────────┐
│  Ship Plan Compliance Auditor                     │
├──────────────────────────────────────────────────┤
│  [Ship ▼]  [Deck Plan ▼]        [▶ Run Analysis] │
│  (image preview, same column as Ship ▼)          │
│                                                   │
└──────────────────────────────────────────────────┘

RUNNING:
┌──────────────────────────────────────────────────┐
│  Ship Plan Compliance Auditor                     │
├──────────────────────────────────────────────────┤
│  ⟳  Analyzing...                                 │
└──────────────────────────────────────────────────┘

RESULTS:
┌──────────────────────────────────────────────────────────────────┐
│  Ship Plan Compliance Auditor                                     │
├────────────────────────────────────────────────────────────────────┤
│  a_deck.png                                   [↺ New Analysis]   │
├────────────────────────────────────────────────────────────────────┤
│  ■ Fire Equipment Detection                                         │ ← .feh-section-header
├─────────────────┬────────────────────────────────────────────────┤
│  Detected: 4    │  Located: 4                                     │
├─────────────────┴─────────────────┬──────────────────────────────┤
│  Original Plan      │  Equipment Highlight  │  Equipment Inventory│
│  (no overlay,       │  (bbox overlay,       │  ● All Found  × 4   │
│   for comparison)   │   gray dim filter)    │  ○ CO₂ 5kg    × 1   │
│                      │                       │  ○ Dry Powder × 3   │
│                      │                       │  ○ Foam 9L    × 0   │
│                      │                       │    (click → highlight)│
├──────────────────────────────────────────────────────────────────────┤
│  ▸ Detection Reasoning Trace (expander, collapsed by default)        │
├──────────────────────────────────────────────────────────────────────┤
│  ■ IMO Compliance Check                                              │ ← .feh-section-header
├─────────────────┬──────────────────────────────────────────────────┤
│  Verdict: GO    │                                                  │
├─────────────────┴──────────────────────────────────────────────────┤
│  [MOCK]                                                              │
│  ⚠️ Mock mode — illustrative only. Not for regulatory submission.    │
│  ✅ SOLAS II-2/Reg.10.3   CO₂ ≥1     found: 1          PASS         │
│  ✅ SOLAS II-2/Reg.10.3   DP  ≥2     found: 4          PASS         │
│  ❌ FSS Code Ch.6/2.1     Foam ≥1    found: 0          FAIL         │
│  ⚠️  FSS Code Ch.6/2.2    Spare CO₂ …                   WARN         │
└─────────────────────┴───────────────────────┴──────────────────────┘
```

---

## 12. Problem Classification Routing

| Step | Output semantics | Problem class |
|------|-----------------|--------|
| Image + pipeline → detection results | Information changes form | Transform |
| Click category → spotlight updates | Selection → visualization | Select/Rank |

Routing: **Transform → Select/Rank**

---

## 13. File Structure

```
src/
  frontend/
    __init__.py
    app_streamlit.py      ← main UI entry point (state machine + render functions)
    pipeline_runner.py    ← background thread (wraps run_detection())
    view_models.py        ← ResultsViewModel + build_results_viewmodel_from_report_data() (ADR-008)
    report_text.py        ← NEW (ADR-F15/F16): parse_reasoning_trace() / truncate_before_instances_json()
    pdf_report.py         ← NEW (ADR-F16): generate_report_pdf() — reportlab, in-memory, no temp files
```

Launch:
```bash
conda run -n ship-plan-auditor streamlit run src/frontend/app_streamlit.py
```

---

## 14. ADR

**ADR-F01: Always cloud backend; pipeline config not exposed to user**
The frontend always uses `backends=["cloud"]`, `n_runs=5` (default). The user only sees detection results, not the pipeline configuration. Reason: this is a single-button detection tool — implementation/configuration details (model choice, run count, prompt) are not meant to be user-tunable, and the prompt itself is kept private.

**ADR-F02: E4 voting result used for total\_by\_category**
`total_by_category` comes from `BackendEvalResult.voting.votes` (E4's consensus counts), not the result of a single run-0. Reason: multi-run voting consensus is more reliable than a single run; what's shown to the user is the final result, not the voting mechanism itself. On a tie, `tied_candidates[0]` is used.

**ADR-F03: Pipeline runs in a background thread**
Streamlit re-runs the whole script on every interaction; `run_detection()` takes 10–120s, so it must run in a `threading.Thread`. The result is written to the module-level `_job_results[session_id]` dict, which the app layer checks on every rerun. No `Queue` is used (only a done/error signal is needed, not per-node progress).

**ADR-F04: No HTTP API layer — frontend imports run\_detection() directly**
Same rationale as the backend service: a single-machine internal tool with no multi-client requirement.

**ADR-F05: PipelineContext discarded after ViewModel transform**
`build_results_viewmodel(ctx)` is called immediately after `pipeline_complete`, and the result is stored in `session_state.results_vm`; `ctx` itself is never stored in `session_state`.

**ADR-F06: Phase 1 keeps DetectedInstance directly in ResultsViewModel**
No `InstanceVM` wrapper layer is introduced. Reconsider if a panel ever needs a computed field that isn't already on `DetectedInstance`.

**ADR-F07: The UI does not expose pipeline implementation details**
Prompt text, model ID, `n_runs`, and the voting mechanism are never shown. The RUNNING state only shows a spinner, never node names.

**ADR-F08: Separate run\_detection() from run\_pipeline()**
The frontend uses `run_detection()` (no ground truth, D1 skipped); evaluation/CLI uses `run_pipeline()` (ground truth present, D1 runs). Both entry functions share the same core node logic; they're kept separate to leave the eval harness's contract unchanged (tests unaffected) while giving the production UI a clean, ground-truth-free entry point.

**ADR-F09: Pinned to a single ship (`demo_ship_a`); no ship switcher** — **Superseded by ADR-F13 (later the same day, 2026-06-22)**
A ship-switcher (multiple `project_id`s + dynamic prompt/category loading) was designed and implemented, then reverted. Reason (at the time of reverting): the demo's purpose was to show a single clean flow to hiring audiences, and the extra complexity of a switcher added no value for the demo; an earlier candidate ship's data also carried a confidentiality risk. `_PROJECT_ID` is now a module-level constant, never enters `session_state`, and no switcher UI is exposed. The `project_id` parameter on `run_detection()`/`run_pipeline()` is kept (for backward compatibility and to leave ADR-006's backend contract unchanged) — the frontend simply never passes a non-default value. (Per ADR convention this entry is left as originally written rather than rewritten after being superseded — see ADR-F13 for why this decision no longer applies.)

**ADR-F10: Per-image mock fixtures, not one fixed canned example**
`_build_mock_vm(image_stem)` looks up `_MOCK_JSON_BY_IMAGE` by `image_stem`, loading that image's own real, previously-run result. Reason: if switching images in mock mode didn't change the result, the demo would look fake; making each image carry its own real result gives an experience equivalent to a real run, at zero API cost. If an image has multiple saved historical results, the most recently timestamped one is used.

**ADR-F11: Dataset trimmed to images with a verified saved result**
`data/images/demo_ship_a/` had `6380_platform` removed (suspected to resemble a real hull number, a confidentiality risk) along with 4 images that had never been run through detection and had no saved result (`f'cl_deck`, `gunway_deck`, `platform`, `poop_deck`); the corresponding ground-truth CSVs were removed at the same time. Reason: a mock-only demo should never let a user pick an image that has nothing real to show after clicking Analyze.

**ADR-F12: Original image shown alongside the annotated spotlight**
An "Original Plan" panel (the plain image, no dim filter, no bbox) was added to the RESULTS page, shown side by side with "Equipment Highlight" (formerly "Spotlight", renamed) so users can directly compare before/after detection. Three-column layout: Original Plan / Equipment Highlight / Equipment Inventory, ratio `[3, 3, 2]`.

**ADR-F13: Reintroduce Ship selector — supersedes ADR-F09**

**Context:** When ADR-F09 reverted the ship switcher, `demo_ship_b` hadn't actually been run end-to-end yet (ADR-006's `category_sets` were just seeded, unexercised data). Now both `demo_ship_a` and `demo_ship_b` have been validated end-to-end with real `eval_runs` data (design_backend.md ADR-007 + Amendment, ADR-008) — ADR-F09's judgment at the time that "a ship switcher has no demo value" no longer holds: both ships now have real, presentable results, so the switcher now demonstrates the system's actual multi-tenant capability (ADR-006), not just decoration.

**Decision:**
1. Add a Ship dropdown to the IDLE page (`category_lookup.list_project_ids()`), selected **before** the Deck dropdown. The `_PROJECT_ID` module constant is removed in favor of `session_state["project_id"]`; switching Ship clears the currently selected `image_path`.
2. The Deck dropdown now filters by `project_id` using `db_results.list_validated_image_stems(project_id)` — showing only images that have a real `eval_runs` record for that ship, continuing ADR-F11's "only show validated images" spirit but without relying on manually deleting files; newly validated images appear automatically.
3. The prompt is now resolved per `project_id` (`_prompt_for(project_id)` → `data/prompts/prompt_cot_counts_{project_id}.txt`), instead of always reading `demo_ship_a`'s prompt file.
4. Fixed a latent bug found along the way: the Equipment Inventory panel previously iterated the hardcoded `_CATEGORY_DISPLAY` (which only had `demo_ship_a`'s 6 categories), so switching to `demo_ship_b` would show the wrong category list (all counts zero). Changed to iterate `vm.total_by_category` instead (already correctly resolved per `project_id`, see `view_models.py`); `_CATEGORY_DISPLAY` is now used only as a display label/color lookup table, and has been filled in with `demo_ship_b`'s 3 unique categories.

**Consequences:** `_build_mock_vm`'s `@st.cache_resource` key changes from `image_stem` to `(project_id, image_stem)`; `start_detection()` is now called with the user-selected `project_id` instead of a constant.

**ADR-F14: RESULTS screen restructured into two titled sections, metrics split between them**

The RESULTS page changed from "3 metric cards sharing one row + a three-column area + a full-width compliance panel" to two sections separated by navy mini-title bars (`.feh-section-header`, same color as the top header but smaller): "Fire Equipment Detection" (Equipment Detected / Instances Located metric cards + the original three-column area + Detection Reasoning Trace) and "IMO Compliance Check" (Compliance Verdict metric card + the original rule-list panel). Splitting the metric cards by which section they belong to, rather than sharing one row above both sections, was the user's explicit choice. `_render_compliance_panel`'s own title text ("IMO Compliance Check" + verdict coloring) was simplified accordingly to avoid duplicating the new section title/metric card, keeping only the MOCK badge and disclaimer. The same change also: renamed the top header to the project name "Ship Plan Compliance Auditor" and dropped the original subtitle; and removed the "Analysis Configuration" info card from the IDLE page.

**Amendment (same day, final state after several iterations):**
- IDLE image preview: the first implementation centered the whole row (base64-embedded HTML + `text-align:center`), but the selector row above it is actually 3 narrow left-aligned columns (Ship/Deck/Run Analysis) plus implicit whitespace, so the image's centering reference (full row width) didn't match the selector's visual reference (the left ~73% of the row) — the image looked off-center to the right. Final approach: the image now sits inside the **same column** as the Ship dropdown (the first column of `st.columns([1.4, 2, 1])`) instead of being centered across the whole row — both share the same left edge, which aligns naturally.
- `Compliance Verdict` metric card: an attempt to make it span the full row like the two "Fire Equipment Detection" metric cards looked oversized/awkward next to `_render_compliance_panel`'s narrow content below it; reverted back to a small, left-aligned card (`st.columns([1, 3])`, card in the first column), matching ADR-F14's original "narrow column" decision.
- `.feh-section-header` gained `margin-bottom: 10px` and its `border-radius` was changed to round all four corners (previously only the top two, on the assumption it would sit flush against the card below; once built, the two needed visible spacing, so rounding all four corners reads better).
- **CSS spacing dead end (tried, reverted, do not repeat):** the Equipment Inventory category button list (each button is 3 separate Streamlit elements: opening div / button / closing div) has large, ugly default spacing. Tried: (1) a global override of `[data-testid="stVerticalBlock"] { gap: ... }` — broke `st.columns()`'s column-width ratios, since the same `gap` property also controls column spacing; (2) `[data-testid="stVerticalBlock"]:has(.feh-cat-btn) { gap: ... }` to scope it precisely — but `:has()` isn't depth-limited, so it matches any ancestor container with a `.feh-cat-btn` **anywhere** inside it, which ended up matching the high-level container wrapping the whole page — effectively global again. Both attempts were reverted; button spacing currently stays at Streamlit's default (ugly but doesn't break layout). A real fix requires collapsing each button's 3 Streamlit elements into fewer calls — a code change, not something CSS alone can reliably solve — left as future work.

**ADR-F15: Raw reasoning trace surfaced in the UI**

`E3CountResult.raw_response` (the model's raw STEP1-4 reasoning text + JSON, persisted to `eval_runs.raw_response_cloud` since design_backend.md ADR-008) had previously only ever been stored, never read or shown by the frontend. Added `ResultsViewModel.raw_response: str | None`; `build_results_viewmodel_from_report_data()` gained an optional parameter of the same name, and both call sites (`pipeline_runner.py`, `app_streamlit.py:_build_mock_vm`) pass `raw_response_cloud` through from the already-fetched `eval_runs` row. Rendered as an `st.expander("Detection Reasoning Trace", expanded=False)` inside the RESULTS page's "Fire Equipment Detection" section; not rendered when there's no value — to avoid the reasoning text (potentially a few KB) pushing the three-column area down.

**Amendment (same day, final rendering approach after three iterations):** Added a shared module `src/frontend/report_text.py` that parses `raw_response` into structured sections following the bracket-marker format the prompt file defines (`[DETECTION_LIST]`/`[MATCHING]`/`[CHECKLIST]`/`[EXCLUDED]`/`[VALIDATION]`/`[RESULT]`, stopping at `[INSTANCES_JSON]` — everything after that is machine-readable JSON and isn't shown). The display went through three iterations:
1. **v1:** Reorganized just the `DETECTION_LIST`/`VALIDATION` sections into a table + PASS/FAIL badges (matching the Equipment Inventory/IMO Compliance Check visual language), dropping the other sections (MATCHING/CHECKLIST/EXCLUDED). User feedback: "this isn't showing the right content" — they wanted to see every step the model itself wrote, not a trimmed-down version.
2. **v2:** Reverted to showing `raw_response` verbatim (truncated only at `[INSTANCES_JSON]`), dumped as one block via `st.text()`, unformatted. User feedback: the background/font didn't look professional enough (compared against the white-card style of the Original Plan panel in a screenshot).
3. **Final version:** Uses `report_text.parse_reasoning_trace()` to parse all 6 sections (none dropped) into a nested bullet structure, rendered with report-style typography — an uppercase mini-heading per section, bolded entry titles (e.g. "Instance 1", with category names prettified by reusing `_CATEGORY_DISPLAY`'s labels), sub-fields shown indented as a list with gray tags, all wrapped in a white card matching the Original Plan panel's style (`.feh-trace-card`). The `Detection Reasoning Trace` expander's title styling was updated to match the rest of `.feh-card-title` (white background, dark text) instead of the navy background.

**ADR-F16: PDF report — generated live with reportlab, downloadable next to "New Analysis"**

**Context:** The user wanted a downloadable report file, with the explicit requirement that it be "genuinely generated, not mocked and read from some folder" — i.e. every download re-renders from the current `vm` (whether in mock or real mode, it's always backed by an actually-run record in `eval_runs`, see design_backend.md ADR-008), not a pre-generated static file.

**Decision:**
1. New module `src/frontend/pdf_report.py`: `generate_report_pdf(vm, project_id, category_labels) -> bytes` builds a PDF in memory with `reportlab` (already a conda-environment dependency; added to `requirements.txt`) and returns bytes. Contents: a title page (project name + ship/deck) → metrics summary table → the Equipment Highlight annotated image (`render_spotlight_node(vm, None, None)`, independent of the on-screen selection state — always fully highlighted) → a Detection Findings table (from `report_text.parse_reasoning_trace`'s `DETECTION_LIST`) → an Equipment Inventory table → an IMO Compliance Check table → an Analysis Summary (see below).
2. `app_streamlit.py:_render_results` adds `st.download_button("⬇ Download Report", data=pdf_bytes, ...)` to the left of "New Analysis"; `pdf_bytes` is computed fresh on every rerun by calling `generate_report_pdf` directly — no caching, no disk write — so the downloaded content always reflects the current `vm`.
3. **Analysis Summary is not a Validation Checks table:** the PDF initially also included the same PASS/FAIL validation checklist as the UI; the user asked for it to be replaced with a "short summary report" style instead (per a reference screenshot: a paragraph of analytical prose, not a table). Replaced with two plain-Python functions, `pdf_report.py:_analysis_summary()` and `_compliance_summary()`, which stitch the `VALIDATION` section's 3 explanation strings and the pass/fail status of `ComplianceResult.checks` into 2 natural-language paragraphs — **without calling any model API**: the detection half reuses the explanation text the model already generated during the original detection call; the compliance half is D2's result (computed locally, never calls a model). The marginal cost of downloading a PDF is zero.
4. Fixed two reportlab rendering bugs (found by actually inspecting a generated PDF, not guessed): (a) reportlab's default Helvetica font has no glyph for U+2082 (the subscript "2" in "CO₂"), rendering as a black box — added `_pdf_text()` to swap `₂` for `<sub>2</sub>` markup; also discovered the Equipment Inventory table column was using plain strings instead of `Paragraph`, so the `<sub>` markup was displayed as literal text — fixed by wrapping consistently in `Paragraph`. (b) The Compliance Check Status column originally showed `check.status.upper()` directly (e.g. `NOT_APPLICABLE`), which overflowed the column width — changed to the same short labels the UI uses (`PASS`/`FAIL`/`WARN`/`N/A`).
5. Detection Findings is placed **before** Equipment Inventory in the PDF (per the user's request — findings are the source the inventory counts are aggregated from, so the logical order should come first).
6. `st.download_button` uses the `data-testid` `stDownloadButton`, which is not the same as `st.button`'s `stButton` — the earlier "secondary button" CSS rule only covered `stButton`, so the download button's coloring didn't match "New Analysis" (dark instead of white background); added a rule covering both testids.

**Consequences:** `requirements.txt` gains `reportlab>=4.0`. New files: `src/frontend/report_text.py` (`parse_reasoning_trace`/`truncate_before_instances_json`, shared by ADR-F15's UI display and this ADR's PDF, so the two don't each parse `raw_response` separately and drift apart) and `src/frontend/pdf_report.py`. New tests: `tests/test_report_text.py` (6 cases).

---

## 15. Task list and implementation status

| Task | Description | Status |
|------|--------|--------|
| T1 | UI State Machine design approved (§2) | ✅ |
| T2 | Session State Contract design approved (§3) | ✅ |
| T3 | Event Transition Table design approved (§4) | ✅ |
| T4 | Frontend Pipeline Table design approved (§5) | ✅ |
| T5 | Backend Integration Contract design approved (§6) | ✅ |
| T6 | ViewModel Contract design approved (§7) | ✅ |
| T7 | Render Contract design approved (§8) | ✅ |
| T8 | Error / Fallback Strategy design approved (§9) | ✅ |
| T9 | Test Scenario List design approved (§10) | ✅ |
| T10 | `pytest tests/` — E / D / V nodes all green | ✅ |
| T11 | `run_detection()` added to `pipeline.py` | ✅ |
| T12 | `src/frontend/__init__.py` + `view_models.py` | ✅ |
| T13 | Tests: F-VM S01–S05 | ✅ |
| T14 | Tests: F-State S01–S07 | ✅ |
| T15 | Tests: F-Spotlight S01–S04 | ✅ |
| T16 | `app_streamlit.py` Mock Shell (all three states exercised via `_MOCK_RESULTS_VM`) | ✅ |
| T17 | `pipeline_runner.py` — background thread | ✅ |
| T18 | `app_streamlit.py` — bind real `run_detection()` | ✅ |
| T19 | Manual smoke test — IDLE → RUNNING → RESULTS golden path | ✅ |
| T20 | Manual smoke test — category click → spotlight filtering | ✅ |
| T21 | Designed + implemented + reverted the ship-switcher feature (multiple `project_id` switching) — decided to keep a single-ship demo (ADR-F09) | ✅ |
| T22 | Dataset trimmed: removed `6380_platform` + 4 images with no saved result (ADR-F11) | ✅ |
| T23 | Mock fixture changed to switch per image (`_build_mock_vm(image_stem)`, ADR-F10) | ✅ |
| T24 | Added Original Plan panel, three-column layout (ADR-F12) | ✅ |
| T25 | Added "All Found Equipment" button to Equipment Inventory | ✅ |
| T26 | CSS: images centered within their own column | ✅ |
| T27 | Re-implemented the ship-switcher: Ship dropdown + DB-driven deck filtering, superseding ADR-F09 (ADR-F13) | ✅ |
| T28 | Fixed the bug where Equipment Inventory iterated the hardcoded `_CATEGORY_DISPLAY` (ADR-F13) | ✅ |
| T29 | Split the RESULTS page into two sections (Fire Equipment Detection / IMO Compliance Check), with metric cards split by section (ADR-F14) | ✅ |
| T30 | Top header changed to the project name; removed the Analysis Configuration card and centered the image on IDLE (ADR-F14) | ✅ |
| T31 | Wired `raw_response` into `ResultsViewModel`, added the Detection Reasoning Trace expander (ADR-F15) | ✅ |
| T32 | `report_text.py`: `parse_reasoning_trace()` parses all 6 sections + `truncate_before_instances_json()`; Detection Reasoning Trace changed to report-style typography (white card + nested bullets), finalized after 3 iterations (ADR-F15 amendment) | ✅ |
| T33 | Fixed IDLE image preview position: changed from "centered across the row" to sharing a column with the Ship dropdown; reverted `Compliance Verdict` back to a narrow column; added `margin-bottom` + all-corner rounding to `.feh-section-header` (ADR-F14 amendment) | ✅ |
| T34 | Attempted to fix Equipment Inventory button-list spacing (global gap / scoped `:has()` gap); both attempts reverted after breaking `st.columns()` layout; reverted to Streamlit's default spacing (ADR-F14 amendment, recorded to avoid repeating the same dead end) | ❌ Reverted |
| T35 | Added `generate_report_pdf()` to `pdf_report.py` + `report_text.py`; added a live-generated Download Report button to the left of "New Analysis" (ADR-F16) | ✅ |
| T36 | PDF content iteration: Analysis Summary replaced the Validation Checks table, Detection Findings moved before Equipment Inventory, fixed two reportlab bugs — the CO₂ subscript black box and Status column overflow (ADR-F16) | ✅ |
| T37 | Tests: report_text RPT-S01–S06; added `reportlab>=4.0` to `requirements.txt` | ✅ |
