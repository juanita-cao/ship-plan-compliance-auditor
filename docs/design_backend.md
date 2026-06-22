# Ship Plan Compliance Auditor — Design Document

**Service:** `ship_plan_auditor`
**Status:** Core pipeline, Postgres-backed category lookup (ADR-006), and run persistence (ADR-008) implemented; two demo ship category sets validated end-to-end (ADR-007); Streamlit frontend complete.
**Environment:** `conda activate ship-plan-auditor` · Python 3.11

---

## 1. Overview

A CLI-based accuracy evaluation harness for ship fire equipment detection prompts.

Runs the detection pipeline **N times** on a test image using **two backends** (local llava + cloud model from env), applies **per-category majority voting with ratio-based uncertainty gating**, compares results against ground truth, and outputs a structured accuracy report.

**Purpose:** Validate prompt design and model selection before integrating into a production fire-equipment-detection service. Each run produces quantitative evidence for: single-run accuracy, majority-vote accuracy, accuracy gain from voting, and manual-review rate. Backend failures are handled independently — one failing backend produces a degraded but useful report.

**Roadmap position:**
```
Phase 0 (this service) — Count-level voting + accuracy report
Phase 1               — Instance-level voting (zone-based clustering)
Phase 2               — Prompt ensemble (compare short vs long in same run)
Phase 3               — Crop ensemble (zone-cropped images)
Phase 4               — Integrate validated logic into the production backend
Phase 5               — Frontend (Streamlit)
```

---

## 2. Canonical Categories

**[AMENDMENT — see ADR-006]** Canonical categories are no longer a single hardcoded Python constant. Each ship/project has its own **category set** (a named collection of canonical categories), looked up by `project_id` from Postgres. The six categories below are the `demo_ship_a` category set — the original dataset this harness was built against — and remain the default/example set. A second set, `demo_ship_b` (4 categories, no spares), exists for the public-portfolio synthetic dataset. See ADR-006 for the full schema and rationale.

**`demo_ship_a` category set** (original six):

| Category | Description |
|----------|-------------|
| `extinguisher_CO2_5kg` | CO₂ 5 kg extinguisher |
| `extinguisher_CO2_5kg_spare` | CO₂ 5 kg spare unit |
| `extinguisher_dry_powder_6kg` | Dry powder 6 kg extinguisher |
| `extinguisher_dry_powder_6kg_spare` | Dry powder 6 kg spare unit |
| `extinguisher_foam_9L` | Foam 9 L extinguisher |
| `extinguisher_foam_9L_spare` | Foam 9 L spare unit |

**`demo_ship_b` category set** (synthetic public demo, 4 categories, no spares):

| Category | Description |
|----------|-------------|
| `extinguisher_DCP_5kg` | Dry Chemical Powder 5 kg extinguisher |
| `extinguisher_CO2_5kg` | CO₂ 5 kg extinguisher |
| `extinguisher_wheeld_foam_45L` | Wheeled foam 45 L extinguisher |
| `extinguisher_water_9L` | Water 9 L extinguisher |

Both sets are extinguishing-agent-type × capacity combinations drawn from the agent types in **IMO Resolution A.951(23)** ("Improved Guidelines for Marine Portable Fire Extinguishers" — water, foam, dry powder/chemical, CO₂, wet chemical) — the canonical *agent-type* taxonomy is anchored to this IMO guidance rather than invented per-project; only the specific label abbreviations used on a given drawing (the **synonyms**, e.g. "DCP" vs "DP" vs "P") vary by drawing office/project, and that variation is what the synonym table absorbs (ADR-006).

Instances not matching any category in the active set are recorded as `unknown` (not a canonical category; excluded from accuracy calculations and ground truth comparisons, but tracked separately).

---

## 3. Environment

```bash
conda activate ship-plan-auditor

# Run evaluation
conda run -n ship-plan-auditor python run_eval.py \
  --image data/images/demo_ship_a/B_deck.png \
  --prompt-file data/prompts/prompt_short.txt \
  --ground-truth data/ground_truth/demo_ship_a/B_deck.csv \
  --n-runs 5
  # --project-id omitted here: inferred from --ground-truth's parent dir name ("demo_ship_a")

# Run tests
conda run -n ship-plan-auditor python -m pytest tests/ -v

# Lint + format
conda run -n ship-plan-auditor python -m ruff format .
conda run -n ship-plan-auditor python -m ruff check .
```

`.env` at service root:

```
OPENAI_API_KEY=your-key-here
OPENAI_VISION_MODEL=<your_openai_vision_model_id>
OLLAMA_VISION_MODEL=llava
OLLAMA_BASE_URL=http://localhost:11434
DATABASE_URL=postgresql://user:pass@localhost:5432/ship_plan_auditor   # ADR-006 — category lookup DB
```

`OPENAI_VISION_MODEL` and `OLLAMA_VISION_MODEL` are read at runtime. The actual value is recorded in `api_model_id` in every `BackendEvalResult` and in the report — never hardcoded in code.

---

## 4. Problem Classification Routing

| Step | Output semantics | Problem class |
|------|-----------------|--------|
| image + prompt → per-run instance counts (×N runs, ×2 backends) | Information changes form | Transform |
| N sets of per-category counts → one voted count per category | Select winning candidate per category | Select/Rank |
| Voted counts + ground truth → accuracy metrics + report | Information changes form | Transform |

**Routing: Transform → Select/Rank → Transform**

---

## 5. Pipeline Graph

### 5.1 Diagram

```
Per-run node (E1 + E1b), executed N × 2 times (N runs × 2 backends):

  E1 🔳  Extract
  image + structured prompt → LLM (OpenAI Responses API / Ollama)
  short-side=800px PIL resize before API call
  model returns a per-instance list (center [cx,cy] per instance) + counts JSON → E3CountResult
         │
         ▼
  E1b ⬜  Detect (OpenCV Center Refiner)
  for each instance with a valid center: search window around LLM center → HSV red mask →
  area-filtered blobs → centroid of blob closest to LLM center replaces original center
  keeps original center + logs warning if no qualifying blob found
  pure local, no API call, <5ms/instance → E3CountResult (centers refined)

Outer Pipeline (per backend, then combined):

  [N × E3CountResult (refined)]
         │
         ▼
       E4 ⬜          ← per-category majority vote + ratio gate
         │
         ▼
       D1 ⬜          ← voted vs ground truth → accuracy metrics      (repeats once per backend)

  After both backends finish:

       D2 ⬜          ← primary backend's voted counts → IMO compliance verdict (runs once, not per-backend; WARN + continue if it raises — COMPLIANCE_MODE="off" skips entirely)
         │
         ▼
       E5 ⬜          ← degraded-aware comparison report

V&V Layer (after pipeline completes):

  V1 ⬜  sequence check (non-blocking)
  V2 ⬜  trace output → logs/
```

---

## 6. Pipeline Table

### Main Pipeline

| Node | D/E | Primitive | Node Name | Business Purpose | Args | Return Type | Side Effects | Methodology | Method | Model | Runtime | Error Strategy |
|------|-----|-----------|-----------|-----------------|------|-------------|--------------|-------------|--------|-------|---------|----------------|
| E1 · `e1_extract_counts` | E | Detect | Visual Count Extractor | Normalize image to short-side=800px (PIL LANCZOS) → send image + structured prompt to LLM; model returns a per-instance list (id, category, supporting text, approximate center) + per-category counts JSON; records `input_image_size` | `image_path: Path, prompt: str, backend: Literal["local","cloud"], run_id: int` | `E3CountResult` | LLM API call | ✅ | Structured-output vision LLM call; parsed into typed instance list + counts | Cloud: `OPENAI_VISION_MODEL` via OpenAI Responses API (`client.responses.create`, `timeout=120s`) · Local: `OLLAMA_VISION_MODEL` via Ollama httpx (`timeout=120s`) | RETRY(3) → HARD FAIL |
| E1b · `e1b_refine_centers` | E | Detect | OpenCV Center Refiner | For each instance with a valid center: validate center in [0,1]×[0,1] → crop search window (3× box) → HSV red mask → area-filtered blobs → centroid of blob **closest to LLM center** → replace LLM center; keep original + warn if no qualifying blob or invalid center | `image_path: Path, result: E3CountResult` | `E3CountResult` (centers refined in-place) | — | ⬜ | OpenCV HSV color filter + connected components + proximity selection | — | Local Python+OpenCV < 5ms/instance | SOFT (keep original center on failure) |
| ~~E2~~ | ~~E~~ | ~~Transform~~ | ~~Regex Rule Classifier~~ | **Removed** — replaced by model in-context reasoning in `prompt_cot_counts.txt` (see ADR-001) | — | — | — | — | — | — | — | — |
| ~~E3~~ | ~~E~~ | ~~Transform~~ | ~~Category Aggregator~~ | **Removed** — model's own aggregation step replaces Python clear-instance counting (see ADR-001) | — | — | — | — | — | — | — | — |
| E4 · `e4_vote_per_category` | E | Select | Per-category Majority Voter | Select majority count per category across N runs (self-consistency); apply a calibrated ratio gate with three confidence tiers (high-confidence accept / accept-with-warning / manual-review-required); ties (top-2 counts share same freq) always→manual-review | `runs: list[E3CountResult], n_runs: int` | `E4VotingResult` | — | ✅ | Majority vote + ratio threshold gate + tie detection | — | Python `collections.Counter` | HARD FAIL |
| D1 · `d1_evaluate_accuracy` | D | Matching | Accuracy Evaluator | Match voted counts vs ground truth; compute 7 accuracy metrics | `voting: E4VotingResult, ground_truth: GroundTruth` | `D1AccuracyDecision` | — | ⬜ | Exact count match per category | — | Python | HARD FAIL |
| D2 · `d2_check_compliance` | D | Matching | Compliance Checker | Check voted counts against IMO regulations (SOLAS/FSS Code); produce per-rule GO/NO-GO with cited article | `inputs: ComplianceInput` | `ComplianceResult` | — | ✅ | Rule engine (mock: hardcoded rules; real: LLM-assisted) | — | Python | HARD FAIL on invalid input; WARN + continue at pipeline level (non-blocking) |
| E5 · `e5_generate_report` | E | Execute | Report Generator | Format both backends' metrics into degraded-aware comparison report + summary/instance tables; print stdout; write JSON + CSV files | `ctx: PipelineContext` | `E5Report` | stdout print · JSON + 2× CSV write `experiments/results/` | ⬜ | String template + `model_dump_json()` + `csv.DictWriter` | — | Python | WARN + continue |

### V&V Layer

| Node | D/E | Primitive | Node Name | Business Purpose | Args | Return Type | Side Effects | Methodology | Method | Model | Runtime | Error Strategy |
|------|-----|-----------|-----------|-----------------|------|-------------|--------------|-------------|--------|-------|---------|----------------|
| V1 · `v1_sequence_check` | E | Detect | Sequence Verifier | Verify `completed_nodes` contains expected nodes in order for given report_mode; flag gaps, unknowns, duplicates, and order violations | `ctx: PipelineContext` | `V1Report` | — | ⬜ | Assertion chain | — | Python | WARN (non-blocking) |
| V2 · `v2_trace_output` | E | Transform | Trace Output | Serialize full `PipelineContext` + V1 verification result to JSON trace file | `ctx: PipelineContext, v1_report: V1Report` | `V2Trace` | file write `logs/` | ⬜ | `model_dump_json()` | — | Python | HARD FAIL |

---

## 7. Data Contracts

All node boundaries use Pydantic `BaseModel`. Fields annotated `# Phase N:` are reserved for future phases — do not remove.

### 7.1 Input Models

**[AMENDMENT — see ADR-006]** `CANONICAL_CATEGORIES` as a single module-level frozenset is replaced by a per-`category_set` lookup loaded from Postgres and cached in memory. `GroundTruth` now carries (or is constructed with) the `project_id` needed to resolve which category set applies; validation checks against *that set's* canonical categories, not a single global constant.

```python
# category_lookup.py (new) — loaded once per process, cached
def get_canonical_categories(project_id: str) -> frozenset[str]:
    """Query category_sets → canonical_categories for this project_id.
    Result cached in-memory (functools.lru_cache or module-level dict)
    so the pipeline does not hit Postgres on every validation call."""

def get_synonyms(canonical_name: str, project_id: str) -> frozenset[str]:
    """Query category_synonyms for all raw_label variants of this
    canonical category within the project's category_set."""


class GroundTruth(BaseModel):
    counts: dict[str, int]        # keyed by canonical category name
    project_id: str                # NEW — resolves which category_set applies
    image_id: str | None = None    # Phase 1+: multi-image evaluation

    @model_validator(mode="after")
    def _validate_canonical_categories(self) -> "GroundTruth":
        canonical = get_canonical_categories(self.project_id)
        provided = set(self.counts.keys())
        if provided != canonical:
            missing = canonical - provided
            extra = provided - canonical
            raise ValueError(
                f"GroundTruth for project_id={self.project_id!r} must contain "
                f"exactly that project's canonical categories. "
                f"Missing: {missing!r}. Extra (not allowed): {extra!r}."
            )
        return self
```

`CANONICAL_CATEGORIES` (the old global frozenset) is retained **only** as the seed data for the `demo_ship_a` category set in the migration — it is no longer imported/referenced directly by `schemas.py`, `e_nodes.py`, or `d_nodes.py` once ADR-006 lands.

### 7.2 E1 — Visual Count Extractor

E1 now returns `E3CountResult` directly. The model performs detection + classification + aggregation in one pass; no intermediate `RawInstance` or `ClassifiedInstance` objects exist.

```python
# E3CountResult is also the E1 output type (see 7.4 below)
```

### ~~7.3 E2 — Regex Rule Classifier~~

**Removed.** `ClassifiedInstance`, `E2ClassificationResult`, `ClassificationRule`, `ClassificationConfig` no longer exist. See ADR-001.

### 7.4 E3CountResult — Per-run Count Result

`E3CountResult` is now produced directly by E1 (model outputs counts + instances). The `excluded_*` and `unknown_count` fields have been removed — the model reports what it counts; exclusion logic is baked into the prompt.

```python
class DetectedInstance(BaseModel):
    instance_id: str              # e.g. "i1", "instance_2"
    category: str                 # canonical category or "unknown"
    nearby_text: str              # label text visible near the object in the image
    location_desc: str            # human-readable location description
    center: list[float] | None = None   # [cx, cy] normalized 0.0–1.0; center of red cylinder symbol
    center_refined: bool = False  # True if E1b OpenCV refinement was applied

class E3CountResult(BaseModel):
    total_by_category: dict[str, int]              # per canonical category count; model's final answer
    run_id: int
    instances: list[DetectedInstance] = []         # parsed from [INSTANCES_JSON] block; empty if marker absent
    input_image_size: tuple[int, int] | None = None  # (w, h) of image sent to model (after resize)
```

**Viz rendering:** `render_spotlight()` in `src/viz.py` draws a fixed-size box around each `center` using constants `_BOX_HW = 0.030` (half-width as fraction of image width) and `_BOX_HH = 0.045` (half-height as fraction of image height). These values were calibrated on poop_deck (2848×2212) and validated on a_deck. The fixed-size approach is intentional: it decouples box size from model output quality.

### 7.5 E4 — Per-category Majority Voter

```python
class CategoryVote(BaseModel):
    category: str
    voted_count: int | None  # None when is_tie=True (no winner declared)
    all_counts: list[int]    # one entry per run, e.g. [3, 3, 4, 3, 3]
    majority_freq: int       # frequency of voted_count (or tied frequency when is_tie=True)
    n_runs: int
    ratio: float             # majority_freq / n_runs
    is_tie: bool             # True if top-2 counts share same frequency → forces MANUAL_REVIEW_REQUIRED
    tied_candidates: list[int] | None = None  # populated when is_tie=True, e.g. [3, 4]
    vote_mode: Literal["voting", "single_run"] = "voting"  # "single_run" when n_runs=1 → forces ACCEPTED_WITH_WARNING
    status: Literal["ACCEPTED", "ACCEPTED_WITH_WARNING", "MANUAL_REVIEW_REQUIRED"]
    # Gate thresholds (calibrated values omitted here; recorded for audit at runtime):
    threshold_accept: float
    threshold_warn: float

class E4VotingResult(BaseModel):
    votes: dict[str, CategoryVote]    # keyed by canonical category
    # Phase 1 extension:
    # instance_clusters: list[InstanceCluster] | None = None
```

### 7.6 D1 — Accuracy Evaluator

```python
class CategoryAccuracy(BaseModel):
    category: str
    ground_truth: int
    voted_count: int | None  # None when CategoryVote.is_tie=True (no winner)
    correct: bool            # False when voted_count is None
    vote_status: str         # from CategoryVote.status

class D1AccuracyDecision(BaseModel):
    per_category: list[CategoryAccuracy]
    n_correct: int
    n_total: int                             # = len(CANONICAL_CATEGORIES) = 6 (constant)
    majority_vote_accuracy_pct: float        # n_correct / n_total × 100.0 — status-independent
    single_run_accuracy_avg_pct: float       # avg per-run accuracy from all_counts (baseline)
    accuracy_gain_pct: float                 # majority_vote_accuracy_pct − single_run_accuracy_avg_pct
    image_level_exact_match: bool            # True iff ALL canonical categories correct simultaneously
    auto_accept_rate: float                  # fraction of categories with status ACCEPTED
    accuracy_on_auto_accepted_pct: float     # among ACCEPTED categories only, fraction correct × 100.0
    manual_review_rate: float                # fraction flagged MANUAL_REVIEW_REQUIRED
    decision: Literal["PASS", "FAIL", "PARTIAL"]
    reason: str
    rule_triggered: str
    inputs_snapshot: dict
    # Phase 1 extension:
    # per_instance_precision: float | None = None
    # per_instance_recall: float | None = None
```

### 7.7 E5 — Report Generator

```python
class E5Report(BaseModel):
    text: str                        # formatted human-readable report (stdout)
    data: dict                       # structured data (JSON to file)
    # data minimum top-level keys: metadata, metrics, voting, accuracy, mode, degraded_reason
    output_path: str | None          # None when write_status == "failed"
    report_mode: Literal["full", "local_only", "cloud_only"]
    degraded_reason: str | None = None       # set when report_mode != "full"; mirrored in data
    write_status: Literal["success", "failed"]  # SOFT failure: report returned even if write fails
    write_error: str | None = None           # OSError message when write_status == "failed"
```

**File write strategy: SOFT.** OSError is caught, logged, and `write_status="failed"` / `write_error` are set on the returned report. The report (text + data) is always returned. JSON file is not mandatory for the eval to be useful.

**Filename / overwrite:** `{image_stem}_{session_id[:8]}.json`. Session ID is a UUID generated fresh per `PipelineContext` construction; first 8 chars provide uniqueness with readable image name prefix.

**CSV exports:** `_write_csvs()` writes alongside the JSON for each backend with data:
- `{image_stem}_{session_id[:8]}_{backend}_summary.csv` — columns: `image, backend, category, ground_truth, run_1…run_N, voted, ratio, status, correct`
- `{image_stem}_{session_id[:8]}_{backend}_instances.csv` — columns: `image, backend, run, instance_id, category, nearby_text, location_desc, center_x, center_y, center_refined`

**data top-level keys:** `metadata`, `summary_table`, `instance_table`, `metrics`, `voting`, `accuracy`, `mode`, `degraded_reason`

**7 core metrics** (must appear in both `text` and `data["metrics"]`):
- `majority_vote_accuracy_pct`
- `single_run_accuracy_avg_pct`
- `accuracy_gain_pct`
- `image_level_exact_match`
- `auto_accept_rate`
- `accuracy_on_auto_accepted_pct`
- `manual_review_rate`

### 7.8 Pipeline State

```python
class SingleRunResult(BaseModel):
    """Captures one E1 run result."""
    run_id: int
    counts: E3CountResult              # model's final per-category counts for this run

class BackendEvalResult(BaseModel):
    """One backend's N runs + voting + accuracy decision. status tracks independent failure."""
    backend: Literal["local", "cloud"]
    api_model_id: str
    status: Literal["success", "failed"]
    error_message: str | None = None   # populated if status == "failed"
    runs: list[SingleRunResult]        # may be empty if status == "failed"
    voting: E4VotingResult | None = None
    accuracy: D1AccuracyDecision | None = None

class PipelineContext(BaseModel):
    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = Field(default_factory=datetime.now)
    image_path: str
    prompt_label: str           # e.g. "short" or "long" — for display and audit
    n_runs: int
    ground_truth: GroundTruth
    local_eval: BackendEvalResult | None = None
    cloud_eval: BackendEvalResult | None = None
    report_mode: Literal["full", "local_only", "cloud_only"] = "full"
    compliance_result: ComplianceResult | None = None  # D2 output; None if D2 skipped
    report: E5Report | None = None
    completed_nodes: list[str] = Field(default_factory=list)
    node_timings: dict[str, float] = Field(default_factory=dict)
    errors: list[str] = Field(default_factory=list)
```

### 7.9 V&V

```python
class V1Report(BaseModel):
    is_clean: bool
    missing_nodes: list[str]
    warnings: list[str]

class V2Trace(BaseModel):
    session_id: str
    output_path: str   # always set; HARD FAIL if write fails
```

**V1 sequence rules (checked in order):**
1. Invalid `report_mode` → `ValueError` (hard fail before any check)
2. Missing required nodes → `is_clean=False`, added to `missing_nodes`
3. Order violations (dependency before dependent) → `is_clean=False`, added to `warnings`
4. Unknown node names → `is_clean=False`, added to `warnings`
5. Duplicate entries → `is_clean` unchanged, added to `warnings` (warning-only)

Expected order per mode:
- `full`: E4_local → D1_local → E4_cloud → D1_cloud → E5
- `local_only`: E4_local → D1_local → E5 (E4_cloud/D1_cloud absence is legal)
- `cloud_only`: E4_cloud → D1_cloud → E5 (E4_local/D1_local absence is legal)

**V2 trace file schema (written JSON):**
```json
{
  "session_id": "...",
  "timestamp": "...",
  "completed_nodes": [...],
  "node_timings": {...},
  "errors": [...],
  "report_mode": "...",
  "verification": { "is_clean": ..., "missing_nodes": [...], "warnings": [...] }
}
```
Filename: `logs/{session_id}_trace.json`. `logs/` created if missing. Write failure → HARD FAIL (raise OSError + log).

**PII/secret safety:** Out of scope for Phase 0. `PipelineContext` fields written verbatim (image_path, prompt_label, session_id). No credentials or model API keys are stored in PipelineContext.

---

### 7.10 Contract Test Scenario Lists (Step 4b)

Part of this project's structured design-review process. These scenarios are the canonical source for T5–T8 Red tests — test implementations must map directly to rows below; no new scenarios added during coding without design doc update.

**Node naming convention for `completed_nodes`:** per-backend aggregate nodes use `{node}_{backend}` (e.g. `E4_local`, `D1_cloud`); final nodes use bare name (`E5`). Per-run entries optional.

---

#### E1 · `e1_extract_counts`

**Implementation rules:**
- **2× PIL upscale：** 调用前将图片用 PIL LANCZOS resize 到 2× 尺寸，编码为 PNG base64。
- **Config 校验（即时 raise，不进入重试）：** 无效 `backend` → ValueError；`image_path` 不存在 → FileNotFoundError；`OPENAI_VISION_MODEL` / `OLLAMA_VISION_MODEL` 未设置 → KeyError。
- **Cloud API：** OpenAI Responses API — `client.responses.create(...)`，`response.output_text`；`timeout=120s`；`detail="original"`。
- **Local API：** Ollama httpx POST；`format=json`；`timeout=120s`。
- **JSON 提取：** `raw.rfind("{")` 定位最后一个 JSON block；`raw.rfind("}")` 取右边界。允许 response 前有 CoT 文本。
- **解析：** `json.loads(...)` → 校验全部 6 个 canonical category 存在，否则 → retry；额外 key 不报错（忽略）。
- **重试策略：** 最多 3 次，指数退避 `2^attempt` 秒（上限 10s）；3 次全失败 → RuntimeError (HARD FAIL)。

| Scenario ID | 场景 | 输入条件 | 预期输出 / 行为 |
|---|------|---------|----------------|
| E1-S01 | Cloud 正常返回 | OPENAI_VISION_MODEL 已设置；mock 返回含合法 JSON counts 的字符串 | result.run_id==run_id, result.total_by_category 含全部 6 个 canonical categories |
| E1-S02 | Local 正常返回 | OLLAMA_VISION_MODEL 已设置；mock httpx 返回含合法 JSON counts 的字符串 | result.run_id==run_id, total_by_category 非空 |
| E1-S03 | run_id 写入结果 | run_id=2, backend="cloud" | result.run_id==2 |
| E1-S04 | CoT + JSON 混合 response 中提取最后 JSON block | response = "reasoning text ... {counts json}" | 正确解析 JSON counts，忽略前置文本 |
| E1-S05 | 全零 counts 正常返回 | LLM 未检测到任何灭火器 → all zeros JSON | result.total_by_category 全部为 0，不报错 |
| E1-S06 | OPENAI_VISION_MODEL 未设置 | backend="cloud"，无该 env var | 立即 raises，不调用 API，不进入重试 |
| E1-S07 | OLLAMA_VISION_MODEL 未设置 | backend="local"，无该 env var | 立即 raises，不调用 API，不进入重试 |
| E1-S08 | JSON 解析失败全部 3 次 → HARD FAIL | mock 每次返回无 JSON block 的字符串 | raises RuntimeError，共调用 API 3 次 |
| E1-S09 | canonical category 缺失全部 3 次 → HARD FAIL | mock 返回 `{"extinguisher_CO2_5kg": 1}` (只有 1 个 key) | raises RuntimeError，共调用 API 3 次 |
| E1-S10 | API 错误第 1 次失败，第 2 次成功（重试恢复） | mock 第 1 次 raise Exception，第 2 次成功 | 共调用 API 2 次，返回正常 E3CountResult |
| E1-S11 | API 错误全部 3 次 → HARD FAIL | mock 每次 raise Exception | raises RuntimeError，共调用 API 3 次 |
| E1-S12 | 无效 backend → ValueError（即时，不重试） | backend="invalid" | 立即 raises ValueError，不调用任何 API |
| E1-S13 | 图片以 PNG base64 编码发送（含 2× upscale） | 任意合法图片文件 | request body 含 base64 encoded PNG；图片尺寸为原始的 2× |
| E1-S14 | 图片文件不存在 → FileNotFoundError（即时） | image_path 指向不存在的文件 | 立即 raises FileNotFoundError，不调用任何 API |

---

#### E1b · `e1b_refine_centers`

**Implementation rules:**
- Runs on the **original image** (not the resized image sent to the LLM). Center coordinates are normalized 0–1 fractions; `cx * w_orig` maps correctly to original pixel space.
- **Center validation:** if `center is None` or any coordinate outside `[0.0, 1.0]`, pass through unchanged + `logger.warning`.
- Search window = `3 × _BOX_HW` wide × `3 × _BOX_HH` tall (in original image pixel space), clamped to image bounds.
- Red HSV mask: hue ∈ [0°,10°] ∪ [170°,180°], saturation ≥ 80, value ≥ 80.
- **Area filter:** reject blobs with area < `_MIN_BLOB_AREA_PX` (noise) or area > `_MAX_BLOB_AREA_FRAC × window_area` (large background regions).
- **Proximity selection:** from qualifying blobs, select the centroid **closest to the original LLM center** (Euclidean distance in pixel space). Do NOT select by largest area.
- SOFT failure: if no qualifying blob, keep original center + `logger.warning`.
- `center_refined=True` set only when centroid successfully replaces the original center.
- Refined center does not affect `total_by_category`, E4 voting, or D1 accuracy — centers are used only by `viz.py`.

| Scenario ID | 场景 | 输入条件 | 预期输出 / 行为 |
|---|------|---------|----------------|
| E1b-S01 | 红色 blob 找到 → 质心替换 LLM center | 合成图：已知红色矩形，LLM center 轻微偏移 | result center ≈ 红色矩形质心；center_refined=True |
| E1b-S02 | 搜索窗口内无红色 blob → 保留原 center | 合成图：搜索区域全灰 | center 不变；center_refined=False；warning logged |
| E1b-S03 | center=None 的 instance 原样通过 | instance.center=None | 返回的 instance.center 仍为 None，center_refined=False |
| E1b-S04 | 搜索窗口超出图片边界 → clamp 后正常运行 | center 靠近图片边缘 | 不 raise；clamp 到 [0, img_w/h]；正常返回 |
| E1b-S05 | instances=[] → 返回空列表 | E3CountResult.instances=[] | 返回 instances=[]，无 exception |
| E1b-S06 | center_refined 仅在成功替换时为 True | 混合：部分有红 blob，部分无 | 有 blob 的 instance.center_refined=True；无 blob 的 center_refined=False |
| E1b-S07 | 输入 E3CountResult 其他字段不变 | 任意 | total_by_category / run_id / input_image_size 与输入相同 |
| E1b-S08 | 多个 blob，选最近而非最大 | 合成图：两个红色矩形，一大（远）一小（近 LLM center）| 选小的（近的）blob 质心；center_refined=True |
| E1b-S09 | 极小 blob 被过滤（噪声忽略） | 合成图：仅有 < _MIN_BLOB_AREA_PX 的红色点 | center 不变；center_refined=False；warning logged |
| E1b-S10 | center 越界 → soft fallback | instance.center=[1.5, 0.5]（越界） | center 不变；center_refined=False；warning logged；不 raise |
| E1b-S11 | 图片路径不可读 → 返回原始 result，不 raise | image_path 指向不存在的文件 | 原始 result 原样返回；不 raise；warning logged |

---

#### E4 · `e4_vote_per_category`

**Decision rules:** ratio = majority_freq / n_runs. Thresholds: ACCEPTED ≥ `VOTE_THRESHOLD_ACCEPT`, ACCEPTED_WITH_WARNING ≥ `VOTE_THRESHOLD_WARN`, else MANUAL_REVIEW_REQUIRED (calibrated values in `schemas.py`, not repeated here). Tie overrides all: if top-2 count values share same frequency → MANUAL_REVIEW_REQUIRED + is_tie=True regardless of ratio.

| Scenario ID | 场景 | 输入条件 | 预期输出 / 行为 |
|---|------|---------|----------------|
| E4-S01 | 全票一致 | n_runs=4, counts=[3,3,3,3] | ratio=1.0, status=ACCEPTED, is_tie=False |
| E4-S02 | 边界 ratio 恰好落在 accept 阈值上 → ACCEPTED（非 WARNING） | counts=[3,3,3,2] → freq=3/4 | status=ACCEPTED, is_tie=False |
| E4-S03 | 边界 ratio 恰好落在 warn 阈值上 → ACCEPTED_WITH_WARNING（非 MANUAL） | counts=[3,3,2,4] → freq=2/4 | status=ACCEPTED_WITH_WARNING, is_tie=False |
| E4-S04 | ratio 低于 warn 阈值，无 tie → MANUAL_REVIEW_REQUIRED | n_runs=8, counts=[3,3,2,4,5,6,7,8] → winner=3, freq=2/8 | status=MANUAL_REVIEW_REQUIRED, is_tie=False |
| E4-S05 | Tie: 前两名频次相同 → 强制 MANUAL_REVIEW | n_runs=4, counts=[3,4,3,4] → {3:2,4:2} | is_tie=True, status=MANUAL_REVIEW_REQUIRED |
| E4-S06 | 输出包含全部 6 个 canonical categories | 任意输入 | len(result.votes)==6, keys==CANONICAL_CATEGORIES |
| E4-S07 | voted_count / majority_freq / all_counts 全部正确 | counts=[3,3,3,3,4] | voted_count=3, majority_freq=4, all_counts 存储所有 5 个值 |
| E4-S08 | threshold 常量记录在 CategoryVote 中（审计） | 任意 | threshold_accept==VOTE_THRESHOLD_ACCEPT, threshold_warn==VOTE_THRESHOLD_WARN |
| E4-S09 | n_runs=1 单次运行 → 强制 WARNING（无投票发生） | 1 run, count=2 | vote_mode="single_run", status=ACCEPTED_WITH_WARNING, is_tie=False, voted_count=2 |
| E4-S10 | 所有 6 个 category 同时独立投票 | 6 个 category 各有不同分布 | 每个 category 的 status 独立计算，互不影响 |
| E4-S11 | n_runs=0 → ValueError | n_runs=0 | ValueError raised |
| E4-S12 | runs 数量与 n_runs 不符 → ValueError | n_runs=5, len(runs)=4 | ValueError raised |
| E4-S13 | run.total_by_category 缺少 canonical key → ValueError | 某 run 的 total_by_category 只有 5 个 key | ValueError raised |
| E4-S14 | run.total_by_category 含非 canonical key → ValueError | 某 run 含 "extinguisher_halon_6kg" key | ValueError raised |
| E4-S15 | Tie 时 voted_count=None，tied_candidates 列出平票值 | counts=[3,4,3,4,5] → {3:2,4:2,5:1} | voted_count=None, tied_candidates=[3,4], majority_freq=2, is_tie=True, status=MANUAL_REVIEW_REQUIRED |

---

#### D1 · `d1_evaluate_accuracy`

**[AMENDMENT] 函数签名：** `runs: list[E3CountResult]` 参数已移除。single_run_accuracy_avg_pct 改从 `CategoryVote.all_counts` 计算，不再需要原始 runs 列表。新签名：`d1_evaluate_accuracy(voting: E4VotingResult, ground_truth: GroundTruth) → D1AccuracyDecision`。

**Decision rules（业务规则，Phase 1 定死）:**
- PASS: n_correct == n_total（全部 6 个 category 精确匹配）
- FAIL: n_correct == 0
- PARTIAL: 0 < n_correct < n_total

**n_correct / majority_vote_accuracy_pct：** 基于 `voted_count == gt.counts[cat]`，与 E4 status 无关（包含 MANUAL_REVIEW_REQUIRED 和 ACCEPTED_WITH_WARNING 的 category）。`voted_count=None`（tie）的 category 视为 incorrect，不计入 n_correct。

**majority_vote_accuracy_pct** = `n_correct / n_total × 100.0`

**accuracy_gain_pct** = `majority_vote_accuracy_pct − single_run_accuracy_avg_pct`

**single_run_accuracy_avg_pct：** 对每个 run index i（0..n_runs-1），`correct_i = count of cats where voting.votes[cat].all_counts[i] == gt.counts[cat]`；求 `mean(correct_i / n_total) × 100.0`。要求所有 category 的 `all_counts` 长度相同（同一 pipeline 组装保证），否则 ValueError。

**accuracy_on_auto_accepted_pct：** 仅限 `status == "ACCEPTED"` 的 categories 中，`voted_count == gt.counts[cat]` 的比例 × 100.0；当 ACCEPTED 数量为 0 时返回 0.0（不除以零）。

**Input validation：** 校验 `voting.votes` 和 `ground_truth.counts` 均恰好包含全部 6 个 canonical categories，否则 ValueError。

| Scenario ID | 场景 | 输入条件 | 预期输出 / 行为 |
|---|------|---------|----------------|
| D1-S01 | 全部 6/6 正确 | voted==GT for all 6 | decision=PASS, n_correct=6, majority_vote_accuracy_pct=100.0, image_level_exact_match=True |
| D1-S02 | 5/6 正确 | 1 category voted≠GT | decision=PARTIAL, n_correct=5, image_level_exact_match=False |
| D1-S03 | 1/6 正确 | 5 categories voted≠GT | decision=PARTIAL, n_correct=1, image_level_exact_match=False |
| D1-S04 | 0/6 正确 | all voted≠GT | decision=FAIL, n_correct=0, majority_vote_accuracy_pct=0.0, image_level_exact_match=False |
| D1-S05 | accuracy_gain_pct 正值（voting 有增益） | majority_vote=80%, single_run_avg=60% | accuracy_gain_pct=20.0 |
| D1-S06 | accuracy_gain_pct 负值（voting 有损） | majority_vote=60%, single_run_avg=80% | accuracy_gain_pct=-20.0 |
| D1-S07 | auto_accept_rate 计算正确 | 4 ACCEPTED, 2 非 ACCEPTED | auto_accept_rate≈0.667 |
| D1-S08 | accuracy_on_auto_accepted_pct: ACCEPTED=0 时返回 0.0 | all categories MANUAL_REVIEW_REQUIRED | accuracy_on_auto_accepted_pct=0.0 |
| D1-S09 | inputs_snapshot 包含审计字段 | 任意 | inputs_snapshot 含 "voting" 和 "ground_truth" 键 |
| D1-S10 | per_category 有且仅有 6 条（canonical 全覆盖） | 任意 | len(per_category)==6 |
| D1-S11 | tie（voted_count=None）视为 incorrect | 1 category is_tie=True（voted_count=None），其余 voted==GT | correct=False for tie category，n_correct 不含该 category |
| D1-S12 | voting.votes 缺少 canonical category → ValueError | voting.votes 只有 5 个 key | raises ValueError |
| D1-S13 | ground_truth.counts 缺少 canonical category → ValueError | ground_truth.counts 只有 5 个 key | raises ValueError |
| D1-S14 | voting 含非 canonical category → ValueError | voting.votes 含 "extinguisher_halon_6kg" | raises ValueError |
| D1-S15 | all_counts 对齐 → single_run_accuracy_avg_pct 正确 | n_runs=3，每 category 的 all_counts 均长度 3 | single_run_accuracy_avg_pct 数值正确 |
| D1-S16 | all_counts 长度不一致 → ValueError | 某 category 的 all_counts 长度与其他不同 | raises ValueError |

---

#### D2 · `d2_check_compliance`

> Merged from the former standalone `docs/design_compliance.md` (retired — content now lives here and in `design_frontend.md`'s Render Contract / Layout for the panel UI).

**Schemas:**

```python
class ComplianceInput(BaseModel):
    total_by_category: dict[str, int]                        # from E4 voting output
    regulation_set: str                                      # e.g. "SOLAS 2020 + FSS Code 2015 (illustrative)"
    is_mock: bool                                            # True in Phase 1
    space_type: Literal["accommodation"] | None = None       # Phase 1: accommodation or unknown

class ComplianceCheck(BaseModel):
    rule_id: str                                             # e.g. "R01"
    article: str                                             # e.g. "SOLAS II-2/Reg.10.3"
    description: str
    status: Literal["pass", "fail", "warning", "not_applicable"]
    required: str | None
    found: str | None
    verdict: Literal["GO", "NO_GO", "CONDITIONAL", "N/A"]    # warning maps to CONDITIONAL
    is_mock_rule: bool                                       # True = illustrative, not verified legal conclusion

class ComplianceResult(BaseModel):
    overall_verdict: Literal["GO", "NO_GO", "CONDITIONAL"]
    checks: list[ComplianceCheck]
    regulation_set: str
    is_mock: bool
    counts_snapshot: dict[str, int]                          # copy of total_by_category at evaluation time (audit trail)
```

**Mock rules (Phase 1, hardcoded in `d_nodes.py`; all checks `is_mock_rule=True`, illustrative only — not verified legal conclusions):**

| Rule ID | Article | Description | Threshold | On fail / no match |
|---------|---------|-------------|-----------|---------------------|
| R01 | SOLAS II-2/Reg.10.3 | CO₂ extinguisher required | ≥ 1 | `fail` → `NO_GO` |
| R02 | SOLAS II-2/Reg.10.3 | Dry powder extinguisher required | ≥ 2 | `fail` → `NO_GO` |
| R03 | FSS Code Ch.6/2.1 | Foam extinguisher in accommodation spaces | ≥ 1, only checked when `space_type="accommodation"` | `space_type=None` → `not_applicable`; else `warning` → `CONDITIONAL` |
| R04 | SOLAS II-2/Reg.10.3 | Total portable extinguishers adequate (CO₂+DP+Foam, incl. spares) | ≥ 4 | `fail` → `NO_GO` |
| R05 | FSS Code Ch.6/2.2 | Spare CO₂ required once CO₂ count ≥ 2 | ≥ 1 spare, only checked when CO₂ ≥ 2 | CO₂ < 2 → `not_applicable`; else `warning` → `CONDITIONAL` |

**Verdict aggregation:** any `fail` → `overall_verdict="NO_GO"`; else any `warning` → `"CONDITIONAL"`; else (`pass`/`not_applicable` only) → `"GO"`.

**Error strategy:** `total_by_category` empty/None or `regulation_set` empty → **HARD FAIL** (`ValueError`) — these are caller bugs, not data conditions to absorb. At the pipeline level, D2 itself is **non-blocking**: `run_pipeline()` wraps the call in try/except and on any exception logs a WARN and leaves `ctx.compliance_result=None`, so a compliance-rule bug never aborts an otherwise-successful detection run (see Section 6 Pipeline Table, D2 row).

**Feature flag:** `feature_flags.py::COMPLIANCE_MODE` (env `FEH_COMPLIANCE`) — `"off"` skips D2 entirely (`ctx.compliance_result=None`); `"mock"` (default) runs the hardcoded rules above with `is_mock=True`; `"config"`/`"llm"` are future phases (rules from `rules_compliance.json` / LLM-assisted interpretation), not yet implemented.

| Scenario ID | 场景 | 输入条件 | 预期输出 / 行为 |
|---|------|---------|----------------|
| D2-S01 | 全部规则通过 | co2=1, dp=4, foam=1, space_type=None | overall_verdict=GO, 所有 check.status ∈ {pass, not_applicable} |
| D2-S02 | CO₂ 缺失 → R01 fail | co2=0, dp=4, foam=1 | overall_verdict=NO_GO, R01.status=fail |
| D2-S03 | Dry powder 低于下限 → R02 fail | co2=1, dp=1, foam=1 | overall_verdict=NO_GO, R02.status=fail |
| D2-S04 | 总数过低 → R04 fail | co2=1, dp=2, foam=0 | overall_verdict=NO_GO, R04.status=fail |
| D2-S05 | foam=0 且 space_type=None → R03 N/A；co2=1<2 → R05 也 N/A | co2=1, dp=4, foam=0, space_type=None | overall_verdict=GO |
| D2-S06 | foam=0 且 space_type="accommodation" → R03 warning | co2=1, dp=4, foam=0, space_type="accommodation" | overall_verdict=CONDITIONAL, R03.status=warning |
| D2-S07 | CO₂=2 触发 spare 规则，spare=0 → R05 warning | co2=2, dp=4, foam=1, co2_spare=0 | overall_verdict=CONDITIONAL, R05.status=warning |
| D2-S08 | 空 counts → HARD FAIL | total_by_category={} | raises ValueError |
| D2-S09 | counts_snapshot 携带评估时的原始计数（审计） | co2=1, dp=4, foam=0 | result.counts_snapshot["extinguisher_CO2_5kg"]==1 |
| D2-S10 | Phase 1 全部 check 标记 is_mock_rule=True | co2=1, dp=4, foam=1 | all(c.is_mock_rule for c in result.checks) |

**Frontend rendering** (`_render_compliance_panel()` in `app_streamlit.py`): see `design_frontend.md` Section 8 Render Contract and Section 11 Layout.

---

#### E5 · `e5_generate_report`

**Input contract:** E5 reads pre-computed results from `ctx` only. Must not invoke E4 voting, D1 accuracy evaluation, or any model/API call.

**Filename:** `experiments/results/{ctx.session_id}.json` — UUID uniqueness prevents silent overwrite.

**Output dir:** `experiments/results/` is created if it does not exist (`mkdir -p` equivalent).

**File write failure:** log error, set `output_path=None`, continue — do not raise.

| Scenario ID | 场景 | 输入条件 | 预期输出 / 行为 |
|---|------|---------|----------------|
| E5-S01 | Full mode | ctx.report_mode="full" | report_mode="full", text 含 LOCAL + CLOUD + COMPARISON 三个区块 |
| E5-S02 | Local-only mode（降级） | ctx.report_mode="local_only" | report_mode="local_only", text 含 ⚠ 降级说明，无 COMPARISON 区块，degraded_reason 非 None |
| E5-S03 | Cloud-only mode（降级） | ctx.report_mode="cloud_only" | report_mode="cloud_only", text 含 ⚠ 降级说明，无 COMPARISON 区块，degraded_reason 非 None |
| E5-S04 | 文件写入 | 任意成功场景 | output_path 非 None，文件名为 {session_id}.json，文件存在于 experiments/results/ |
| E5-S05 | data 字段可 JSON 序列化 | 任意 | json.dumps(report.data) 不抛异常（可 round-trip）|
| E5-S06 | text 包含全部 7 个核心 metrics 关键词 | 任意 | text 含 "majority_vote_accuracy_pct"、"accuracy_gain_pct" 等全部 7 个 metric 名称 |
| E5-S07 | report_mode 无效 → ValueError | ctx.report_mode 为非法值 | raises ValueError |
| E5-S08 | output_dir 不存在时自动创建 | experiments/results/ 不存在 | 目录被创建，文件写入成功，output_path 非 None |
| E5-S09 | 文件写入失败 → SOFT，不 raise | 模拟 OSError（patch Path.write_text） | output_path=None，函数正常返回，error 被 log |
| E5-S10 | data 含必要顶层 key | 任意 | data 含 "metadata"、"metrics"、"voting"、"accuracy"、"mode"、"degraded_reason" 六个顶层 key |
| E5-S11 | degraded_reason 写入 data | ctx.report_mode="local_only" | data["degraded_reason"] 非 None，与 E5Report.degraded_reason 相同 |
| E5-S12 | write_status="success" 正常写入 | 任意成功场景 | write_status="success"，write_error=None |
| E5-S13 | write_status="failed" + write_error 写入失败时设置 | 模拟 OSError | write_status="failed"，write_error 含 OSError 信息 |

---

#### category_lookup · `get_canonical_categories` / `get_synonyms` (ADR-006, T18)

**Implementation rules:**
- `get_canonical_categories(project_id: str) -> frozenset[str]`: query `category_sets` (by `name == project_id`) → join `canonical_categories`; result cached in-memory keyed by `project_id` (module-level dict, process-lifetime, no TTL).
- `get_synonyms(canonical_name: str, project_id: str) -> frozenset[str]`: query `category_synonyms` for the canonical category identified by `(project_id, canonical_name)`; cached keyed by `(project_id, canonical_name)`.
- `list_project_ids() -> list[str]`: `SELECT name FROM category_sets ORDER BY name`; cached as a single module-level list (no key — there's only ever one such list). Added for the frontend ship selector (design_frontend.md ADR-F10) — not part of the original ADR-006 scope, but same module/pattern.
- `get_canonical_categories`/`get_synonyms` raise `ValueError` immediately for empty/unknown identifiers — never return an empty set to mean "not found" (ambiguous with "found, but zero rows"). `list_project_ids` has no identifier to be "not found", so an empty table legitimately returns `[]`, not an error.
- `clear_cache()` test helper resets all three caches; not used by production code paths.

| Scenario ID | 场景 | 输入条件 | 预期输出 / 行为 |
|---|------|---------|----------------|
| CL-S01 | 已知 project_id 返回完整 canonical 集合（demo_ship_a） | project_id="demo_ship_a" | 返回 frozenset，len==6，内容与 Section 2 表一致 |
| CL-S02 | 已知 project_id 返回完整 canonical 集合（demo_ship_b） | project_id="demo_ship_b" | 返回 frozenset，len==4，内容与 Section 2 表一致 |
| CL-S03 | 未知 project_id → ValueError | project_id="nonexistent_ship" | raises ValueError，不缓存任何结果 |
| CL-S04 | 空字符串 project_id → ValueError（立即，不查库） | project_id="" | raises ValueError，DB 查询计数为 0 |
| CL-S05 | 重复调用同一 project_id → 第二次走缓存 | 连续调用两次 get_canonical_categories("demo_ship_a") | 两次返回值相等；DB 查询计数仅为 1（mock 计数验证） |
| CL-S06 | 已知 canonical_name 返回其 synonyms | canonical_name="extinguisher_DCP_5kg", project_id="demo_ship_b" | 返回 frozenset 含 "P"/"DCP"/"DP"/"D.C.P." |
| CL-S07 | canonical_name 不属于该 project_id 的 set → ValueError | canonical_name="extinguisher_DCP_5kg", project_id="demo_ship_a" | raises ValueError（demo_ship_a 没有这个分类） |
| CL-S08 | canonical_name 存在但暂无 synonym 记录 → 返回空集（非错误） | 任意暂无 synonym 行的 canonical_category | 返回 frozenset() ，不 raise |
| CL-S09 | 重复调用同一 (canonical_name, project_id) → 第二次走缓存 | 连续调用两次 get_synonyms 同一组参数 | 两次返回值相等；DB 查询计数仅为 1 |
| CL-S10 | clear_cache() 后强制重新查库 | get_canonical_categories(...) → clear_cache() → 再调用一次 | DB 查询计数为 2（缓存被清空，第二次重新查询） |
| CL-S11 | 列出全部 project_id，按字母排序 | 当前数据库有 demo_ship_a + demo_ship_b | 返回 `["demo_ship_a", "demo_ship_b"]` |
| CL-S12 | 重复调用 list_project_ids() → 第二次走缓存 | 连续调用两次 | 两次返回值相等；DB 查询计数仅为 1 |
| CL-S13 | clear_cache() 也清空 project_ids 缓存 | list_project_ids() → clear_cache() → 再调用一次 | DB 查询计数为 2 |

---

#### V1 · `v1_sequence_check`

| Scenario ID | 场景 | 输入条件 | 预期输出 / 行为 |
|---|------|---------|----------------|
| V1-S01 | Full mode 全部节点完成且顺序正确 | completed_nodes=["E4_local","D1_local","E4_cloud","D1_cloud","E5"] | is_clean=True, missing_nodes=[], warnings=[] |
| V1-S02 | E5 缺失 | "E5" 不在 completed_nodes | is_clean=False, missing_nodes=["E5"] |
| V1-S03 | D1_local 缺失（非降级 full mode） | report_mode="full"，但 "D1_local" 不在 completed_nodes | is_clean=False, missing_nodes=["D1_local"] |
| V1-S04 | 降级 local_only（cloud 节点合法缺失） | report_mode="local_only"，completed_nodes=["E4_local","D1_local","E5"] | is_clean=True，warnings 含降级说明 |
| V1-S05 | 降级 cloud_only（local 节点合法缺失） | report_mode="cloud_only"，completed_nodes=["E4_cloud","D1_cloud","E5"] | is_clean=True，warnings 含降级说明 |
| V1-S06 | 未知节点出现在 completed_nodes | completed_nodes 含 "X_unknown" | is_clean=False，warnings 含未知节点说明 |
| V1-S07 | 顺序违反（D1 先于 E4） | completed_nodes=["D1_local","E4_local","E4_cloud","D1_cloud","E5"] | is_clean=False，warnings 含顺序违反说明 |
| V1-S08 | 重复节点 | completed_nodes 含 "E5" 两次 | is_clean 不受影响（warning-only），warnings 含重复节点说明 |
| V1-S09 | report_mode 无效 → ValueError | ctx.report_mode 为非法值 | raises ValueError |

---

#### V2 · `v2_trace_output`

| Scenario ID | 场景 | 输入条件 | 预期输出 / 行为 |
|---|------|---------|----------------|
| V2-S01 | 正常写入 | 任意完成的 ctx | result.output_path 非 None，文件名为 {session_id}_trace.json，存在于 logs/ |
| V2-S02 | 写入 JSON 有效 | 任意 | 写入文件可被 json.loads() 解析 |
| V2-S03 | session_id 记录正确 | 任意 | result.session_id == ctx.session_id |
| V2-S04 | trace 含最小 schema 字段 | 任意 | JSON 含 "session_id"、"timestamp"、"completed_nodes"、"node_timings"、"errors"、"report_mode" |
| V2-S05 | trace 含 V1 验证结果 | 任意 | JSON 含 "verification" key，内含 is_clean、missing_nodes、warnings |
| V2-S06 | logs/ 不存在时自动创建 | logs/ 目录缺失 | 目录被创建，文件写入成功 |
| V2-S07 | 文件写入失败 → HARD FAIL | 模拟 OSError | raises OSError，error 被 log |
| V2-S08 | 文件名含 session_id + _trace 后缀 | 任意 | output_path 文件名为 "{session_id}_trace.json" |

---

## 8. ~~Classification Rules Config~~ — Removed (ADR-001)

`src/backend/configs/classification_rules.json` **has been deleted.** Rule-based regex classification (E2) was replaced by in-context model reasoning in `prompt_cot_counts.txt` after T11 smoke testing showed higher accuracy. See ADR-001 for the full rationale.

The classification rules (R1s/R1/R2s/R2/R3s/R3) are now encoded in the prompt's STEP 2 matching instructions rather than in a JSON config file. This section is preserved for reference only — do not restore these rules or the E2 node without updating the ADR.

---

## 9. Diagrams

### 9.1 Software Architecture

```mermaid
flowchart TB
    subgraph cli["CLI"]
        RUN["run_eval.py\n--image --prompt-file\n--ground-truth --n-runs"]
    end

    subgraph service["ship_plan_auditor/src/backend/"]
        PIPE["pipeline.py\nrun_pipeline()"]
        EN["e_nodes.py\nE1 · E1b · E4 · E5"]
        DN["d_nodes.py\nD1"]
        VV["vv.py\nV1 · V2"]
        SCH["schemas.py"]
        PROMPT["data/prompts/\nprompt_cot_counts.txt"]
    end

    subgraph ext["External (independent failure)"]
        OA["OpenAI API\nOPENAI_VISION_MODEL"]
        OL["Ollama :11434\nOLLAMA_VISION_MODEL"]
    end

    subgraph out["Output"]
        SO["stdout\naccuracy report + tables"]
        RS["experiments/results/\n{image}_{id8}.json\n{image}_{id8}_{backend}_summary.csv\n{image}_{id8}_{backend}_instances.csv"]
        LG["logs/\ntrace_*.json"]
    end

    RUN --> PIPE
    PIPE --> EN & DN & VV
    EN & DN & VV --> SCH
    EN --> PROMPT
    EN -. "local (may fail)" .-> OL
    EN -. "cloud (may fail)" .-> OA
    PIPE --> SO & RS & LG
```

### 9.2 Data Model

```mermaid
classDiagram
    PipelineContext --> BackendEvalResult : local_eval / cloud_eval
    PipelineContext --> E5Report : report
    PipelineContext --> GroundTruth : ground_truth

    BackendEvalResult --> SingleRunResult : runs[N]
    BackendEvalResult --> E4VotingResult : voting
    BackendEvalResult --> D1AccuracyDecision : accuracy

    SingleRunResult --> E3CountResult : counts

    E4VotingResult --> CategoryVote : votes{}
    D1AccuracyDecision --> CategoryAccuracy : per_category[]

    note for E3CountResult "Produced directly by E1\n(model outputs counts)\nNo RawInstance or ClassifiedInstance"
```

### 9.3 Sequence Diagram

```mermaid
sequenceDiagram
    participant CLI as run_eval.py
    participant PIPE as pipeline.py
    participant E1 as e1_extract_counts
    participant E4 as e4_vote_per_category
    participant D1 as d1_evaluate_accuracy
    participant D2 as d2_check_compliance
    participant E5 as e5_generate_report
    participant OL as Ollama :11434
    participant OA as OpenAI Responses API

    CLI->>PIPE: run_pipeline(image, prompt_cot_counts, gt, n=5)

    Note over PIPE: local backend (errors caught independently)
    loop N=5 runs · backend="local"
        PIPE->>E1: (image, prompt, "local", run_id=i)
        Note over E1: PIL 2× upscale → PNG base64
        E1->>OL: POST /api/generate {format:"json", model:OLLAMA_VISION_MODEL}
        OL-->>E1: CoT text + counts JSON
        Note over E1: rfind("{") → json.loads → E3CountResult
        E1-->>PIPE: E3CountResult
    end
    PIPE->>E4: runs[5] (local)
    E4-->>PIPE: E4VotingResult (ratio gate applied)
    PIPE->>D1: voting, ground_truth
    D1-->>PIPE: D1AccuracyDecision (7 metrics)
    Note over PIPE: ctx.local_eval.status = "success"

    Note over PIPE: cloud backend (errors caught independently)
    loop N=5 runs · backend="cloud"
        PIPE->>E1: (image, prompt, "cloud", run_id=i)
        Note over E1: PIL 2× upscale → PNG base64
        E1->>OA: client.responses.create(model:OPENAI_VISION_MODEL, input_image, detail:"original")
        OA-->>E1: response.output_text (CoT + counts JSON)
        Note over E1: rfind("{") → json.loads → E3CountResult
        E1-->>PIPE: E3CountResult
    end
    PIPE->>E4: runs[5] (cloud)
    E4-->>PIPE: E4VotingResult
    PIPE->>D1: voting, ground_truth
    D1-->>PIPE: D1AccuracyDecision
    Note over PIPE: ctx.cloud_eval.status = "success"
    Note over PIPE: determine report_mode (full / local_only / cloud_only)

    alt COMPLIANCE_MODE != "off"
        PIPE->>D2: primary.voting.votes (cloud_eval if success, else local_eval)
        D2-->>PIPE: ComplianceResult (GO/NO-GO per rule + overall verdict)
        Note over PIPE: ctx.compliance_result set; exceptions caught → WARN + continue
    end

    PIPE->>E5: ctx
    E5-->>PIPE: E5Report (degraded-aware)
    Note over PIPE: V1 sequence check → V2 trace output
    PIPE-->>CLI: PipelineContext
    CLI->>CLI: print ctx.report.text
```

---

## 10. Sample Report Output

The eval report compares two backends (a local model and a cloud model) per image, one row per category:

```
Category                    GT  R1  R2  R3  R4  R5  Voted  Freq  Ratio  Status      Correct?
extinguisher_CO2_5kg         3   3   3   3   3   3     3   5/5   1.00  ACCEPTED        ✓
...
```

Per-backend summary metrics: single-run accuracy (avg across runs), majority-vote accuracy,
image-level exact match, accuracy gain from voting, auto-accept rate, accuracy on
auto-accepted instances, manual-review rate — then a side-by-side comparison block across
backends. If one backend fails mid-run, the report degrades gracefully and shows only the
backend that succeeded, with a warning line.

---

## 11. Ground Truth CSV Format

**[AMENDMENT — see ADR-006]** Ground truth lives under `data/ground_truth/{project_id}/{image_id}.csv` — the directory name is the `project_id` used to resolve the category set (Section 2). The CSV itself is unchanged (still just `category,count` rows); which categories are valid/required is now determined by looking up `project_id`'s category set in Postgres, not by a hardcoded global list.

`demo_ship_a` example (`data/ground_truth/demo_ship_a/a_deck.csv`):
```csv
category,count
extinguisher_CO2_5kg,3
extinguisher_CO2_5kg_spare,0
extinguisher_dry_powder_6kg,4
extinguisher_dry_powder_6kg_spare,0
extinguisher_foam_9L,2
extinguisher_foam_9L_spare,1
```

`demo_ship_b` example (`data/ground_truth/demo_ship_b/main_deck.csv`):
```csv
category,count
extinguisher_DCP_5kg,4
extinguisher_CO2_5kg,0
extinguisher_wheeld_foam_45L,0
extinguisher_water_9L,1
```

One file per image. File name: `{image_id}.csv`. Unknown instances are not in the ground truth — they are tracked separately and excluded from accuracy calculations.

Phase 1+ multi-image format (backwards-compatible extension):
```csv
image_id,category,count
B_deck,extinguisher_CO2_5kg,3
...
```

---

## 12. Project Structure

```
ship_plan_auditor/
├── data/
│   ├── images/{project_id}/        ← test images, one subdir per project (e.g. demo_ship_a, demo_ship_b)
│   ├── prompts/                    ← prompt_cot_counts.txt (demo_ship_a, active) · prompt_cot_counts_demo_ship.txt
│   └── ground_truth/{project_id}/  ← {image_id}.csv per project (Section 11)
├── docs/
│   ├── design_backend.md
│   └── design_frontend.md      ← Streamlit UI design (Dev + Review mode)
├── experiments/
│   └── results/             ← ADR-008: {image_stem}_t{target_short}/ subfolders, e.g. below_main_deck_bow_t800/
│       └── {image}_{id8}.json · {image}_{id8}_{backend}_summary.csv · {image}_{id8}_{backend}_instances.csv · {image}_{id8}_{backend}_spotlight.png · {image}_{id8}_{backend}_raw_response.txt
├── logs/                    ← V2 trace files
├── src/
│   ├── viz.py               ← render_spotlight() — PIL spotlight overlay for UI · save_run_artifacts() (ADR-008)
│   ├── frontend/
│   │   ├── __init__.py
│   │   ├── app_streamlit.py ← Streamlit UI entry point (IDLE/RUNNING/RESULTS); mock mode reads eval_runs (ADR-008)
│   │   ├── pipeline_runner.py ← background thread wrapper for run_detection(); saves to + reads back from eval_runs (ADR-008)
│   │   └── view_models.py   ← build_results_viewmodel_from_report_data() — shared by mock + real paths (ADR-008)
│   └── backend/
│       ├── e_nodes.py        ← E1 (e1_extract_counts) · E1b (e1b_refine_centers) · E4 · E5 · experiment_dir() (ADR-008)
│       ├── d_nodes.py        ← D1
│       ├── vv.py             ← V1 · V2
│       ├── pipeline.py       ← run_pipeline() / run_detection()
│       ├── schemas.py        ← all Pydantic models
│       ├── category_lookup.py ← (ADR-006): Postgres-backed category_set/canonical/synonym lookup, in-memory cache
│       ├── db_results.py    ← NEW (ADR-008): save_eval_run / get_latest_eval_run / get_eval_run_by_session
│       ├── db/
│       │   ├── migrations/   ← 001_category_lookup.sql (ADR-006) · 002_eval_runs.sql (ADR-008)
│       │   └── seed_data.sql ← demo_ship_a (6 cat) + demo_ship_b (4 cat, IMO A.951(23)-anchored) seed rows
│       └── configs/
│           └── .env          ← API keys + DATABASE_URL (not committed)
├── tests/
│   ├── test_e1.py           ← e1_extract_counts (19 tests)
│   ├── test_e1b.py          ← e1b_refine_centers (OpenCV center refiner)
│   ├── test_e1b_stages.py   ← e1b_refine_centers internal stage-level unit tests
│   ├── test_e2.py           ← stub (E2 removed)
│   ├── test_e3.py           ← stub (E3 removed)
│   ├── test_e4.py
│   ├── test_d1.py
│   ├── test_e5.py
│   ├── test_vv.py
│   ├── test_schemas.py
│   ├── test_pipeline.py
│   ├── test_category_lookup.py
│   ├── test_db_results.py   ← NEW (ADR-008)
│   └── test_frontend_view_models.py ← rewritten for build_results_viewmodel_from_report_data (ADR-008)
├── .env                     ← not committed
├── .gitignore
├── requirements.txt
└── run_eval.py              ← CLI entry point
```

---

## 13. Task list and implementation status

Pure pipeline / CLI — flat task numbering in pipeline-graph order.

| Task | Status | Scope | Description | Quality Gate |
|------|--------|-------|-------------|--------------|
| T0 | ✅ Done | Setup | Directory structure, `.env`, `requirements.txt`, `ruff` config, `pytest.ini` | `ruff format . && ruff check .` pass |
| T1 | ✅ Done | schemas.py | All Pydantic models (Section 7); simplified after ADR-001 (E2/E3 removed) | Schema contract tests pass |
| T2 | ✅ Done | E1 | `e1_extract_counts` — 2× upscale + Responses API + CoT counts JSON extraction; both backends; mock in tests (19 tests) | TDD green · ruff · pytest |
| T3 | ~~Removed~~ | ~~E2~~ | ~~`e2_classify_instances`~~ — replaced by model in-context reasoning (ADR-001) | — |
| T4 | ~~Removed~~ | ~~E3~~ | ~~`e3_aggregate_counts`~~ — replaced by model's own aggregation step (ADR-001) | — |
| T5 | ✅ Done | E4 | `e4_vote_per_category` — majority vote + ratio gate + tie detection | TDD green · ruff · pytest |
| T6 | ✅ Done | D1 | `d1_evaluate_accuracy` — 7 metrics including image-level exact match | TDD green · ruff · pytest |
| T7 | ✅ Done | E5 | `e5_generate_report` — degraded-aware report + file write | TDD green · ruff · pytest |
| T8 | ✅ Done | V&V | `v1_sequence_check` + `v2_trace_output` | TDD green · ruff · pytest |
| T9 | ✅ Done | pipeline.py | `run_pipeline()` with independent backend error handling; integration test (all mocked) | Integration test green (121 total tests pass) |
| T10 | ✅ Done | run_eval.py | CLI entry point (`argparse`) | Manual invocation works |
| T11 | ✅ Done | Smoke test | Parallel 5-run test on real images (a_deck, b_deck) with `test_b.py`; validated Option B accuracy; confirmed 2× upscale fixes foam_9L detection | 5/5 majority vote correct on b_deck; human review passed |
| T12 | ✅ Done | viz.py | `render_spotlight()` — PIL RGBA dim overlay + fixed-size box per center (`_BOX_HW=0.030, _BOX_HH=0.045`); category color borders; `--save-viz` CLI flag writes spotlight PNG to results/ | Manual visual test on poop_deck + a_deck: all instances highlighted correctly |
| T13 | ✅ Done | bbox→center refactor | ADR-004: `DetectedInstance.bbox→center [cx,cy]`; prompt updated to output center point; `viz.py` uses fixed `_BOX_HW/_BOX_HH`; CSV columns updated to `center_x/y`; `input_image_size` audit field added | All 121 tests pass |
| T15 | ✅ Done | E1b | `e1b_refine_centers` in `e_nodes.py`: OpenCV HSV red mask + area-filtered blobs + closest-to-LLM-center selection; center validation; sets `center_refined=True`; SOFT fallback; wired into `pipeline.py` after E1; 11 contract tests in `tests/test_e1b.py` | TDD green · visual smoke test pending |
| T14 | ⬜ | frontend | `src/frontend/pipeline_runner.py` — background thread wrapper; `src/frontend/app_streamlit.py` — IDLE/RUNNING/RESULTS state machine; Dev mode + Review mode; spotlight integration | Smoke test: IDLE→RUNNING→RESULTS golden path; spotlight selection; Review mode GT save |
| T16 | ✅ Done | db | Provision local Postgres; write `src/backend/db/migrations/` SQL for `category_sets`, `canonical_categories`, `category_synonyms` (ADR-006 schema) | Tables created; `\d` confirmed expected columns/constraints |
| T17 | ✅ Done | db | `src/backend/db/seed_data.sql` — seed `demo_ship_a` (6 categories, from current `CANONICAL_CATEGORIES`) and `demo_ship_b` (4 categories, IMO A.951(23)-anchored) category sets + initial synonyms (DCP/DP/P, etc.) | Both sets queryable; row counts verified (9 + 11 synonyms) |
| T18 | ✅ Done | category_lookup.py | `get_canonical_categories(project_id)` + `get_synonyms(canonical_name, project_id)`; in-memory cache (process-lifetime, no TTL needed at this scale) | `tests/test_category_lookup.py` CL-S01–S10, all passing against local Postgres; `ruff check` clean |
| T19 | ✅ Done | schemas.py | `GroundTruth` gains `project_id: str = "demo_ship_a"`; `PipelineContext` also gains `project_id` (needed even when `ground_truth=None` in production mode); validator resolves canonical set via `category_lookup.get_canonical_categories()` | `tests/test_schemas.py` 27/27 passing unmodified |
| T20 | ✅ Done | e_nodes.py / d_nodes.py / pipeline.py | Replaced all direct `CANONICAL_CATEGORIES` / `CANONICAL_CATEGORY_SET` references (E1 parse, E4 voting, D1 accuracy, E5 report tables) with `category_lookup` calls; `project_id` threaded through `e1_extract_counts`/`e4_vote_per_category`/`run_pipeline`/`run_detection` as a trailing defaulted param (`="demo_ship_a"`) — zero existing call sites broke | Full suite 199/199 passing; only mechanical fix needed was 2 test mock signatures (`_e1_ok` etc. in test_pipeline.py/test_run_detection.py) gaining the same trailing param |
| T21 | ✅ Done | run_eval.py | Added `--project-id` CLI flag (defaults inferred from `--ground-truth` parent directory name per Section 11) | `ruff check` clean (own lines); inference logic is `args.project_id or args.ground_truth.parent.name` |

---

---

## 14. Architectural Decision Records

### ADR-001 — Remove E2/E3; Model Outputs Counts Directly

**Date:** 2026-06-10
**Status:** Accepted

**Context:**
Original design: E1 extracts raw instances (RawInstance array) → E2 applies regex rules (classification_rules.json) → E3 counts only `clear` instances. T11 smoke testing used `test_b.py` to validate an alternative approach ("Option B") where the model performs detection + classification + aggregation in a single LLM call using a structured prompt (`prompt_cot_counts.txt`).

**Decision:**
Remove E2 and E3 from the pipeline. E1 (`e1_extract_counts`) now sends `prompt_cot_counts.txt` and expects the model to output final per-category counts as the last JSON block in its response.

**Reasons:**
1. **Higher accuracy**: T11 smoke testing on b_deck (GT: DP6=2, foam9L=1, CO2=0) showed Option B achieves 5/5 correct majority votes with 2× upscale, vs. Option A's miscounts on CO2 (fixed suppression system confusion) and foam9L (label illegibility at original resolution).
2. **Simpler pipeline**: Removes 2 transform nodes, 4 Pydantic models (`RawInstance`, `E1DetectionResult`, `ClassifiedInstance`, `E2ClassificationResult`), `ClassificationConfig`, and `classification_rules.json`. 
3. **Prompt encodes domain logic better**: several visual-disambiguation rules (distinguishing true target instances from visually similar but irrelevant symbols) are reasoning tasks that regex on text cannot handle reliably.

**Consequences:**
- `classification_rules.json` deleted.
- `E3CountResult` schema simplified: removed `excluded_boundary_cut_count`, `excluded_unclear_count`, `unknown_count`.
- `SingleRunResult` simplified: removed `detection` and `classification` fields.
- `e1_extract_counts` uses OpenAI Responses API (`client.responses.create`) with `timeout=120s` (up from 60s, needed for thinking-enabled models).
- Phase 1 instance-level analysis (bbox, zone_id clustering) will require a new E1 variant that elicits structured instance output — not a regression of today's removal.

---

### ADR-002 — Normalize Image to Short-Side = 800 px Before LLM Call

**Date:** 2026-06-10
**Status:** Accepted (supersedes initial "2× upscale" approach)

**Context:**
Original pipeline sent images at native resolution. T11 smoke testing showed foam 9L detection improved dramatically with larger images. Initial approach: 2× PIL upscale unconditionally. Problem: large platform images (3228×2144, short=2144) upscaled to 6456×4288 — too slow and too expensive (15 OpenAI tiles). Small images like b_deck (894×648, short=648) need upscaling; large images like 6380_platform need downscaling.

**Decision:**
Replace fixed 2× multiplier with a **normalize-to-target** strategy: `scale = _E1_TARGET_SHORT / short_side`. Constant `_E1_TARGET_SHORT = 800` in `e_nodes.py`. All images are resized (up or down) so the short side equals exactly 800 px. `None` = send at original size (for debugging/comparison).

**Reasons:**
1. **Optimal minimum from sweep:** Swept b_deck at target-short=800/1000/1200/1500 (n=3 each). Both 800 and 1000 gave 6/6 ACCEPTED. 800 is the minimum that maintains accuracy.
2. **Token cost:** 800 px short side → ~6 OpenAI 512×512 tiles ≈ 1100 image tokens. vs. 1500 px → ~15 tiles. ~60% token reduction.
3. **Handles all image sizes:** b_deck (894×648 → upscale to ~1108×800), platform (3228×2144 → downscale to ~1204×800). No edge cases.

**Consequences:**
- `_E1_TARGET_SHORT = 800` is the default; can be overridden per-run with `--target-short` CLI flag.
- `timeout=120s` retained for thinking-enabled cloud models.
- Images are always resampled with PIL LANCZOS; output encoded as PNG base64.

---

### ADR-003 — Instance-Level Output + CSV Export

**Date:** 2026-06-10
**Status:** Accepted

**Context:**
Count-level results (6 numbers per run) are insufficient for debugging false positives/negatives. Need to see which specific instances were detected and whether the same instance is found consistently across runs.

**Decision:**
1. Extend `prompt_cot_counts.txt` FINAL RESULT section: model outputs a `[INSTANCES_JSON]` array before the counts JSON block. Each entry: `{instance_id, category, nearby_text, location_desc, center: [cx,cy]}` (center as normalized 0.0–1.0 fractions; superseded by ADR-004).
2. Add `DetectedInstance` Pydantic model; add `instances: list[DetectedInstance]` to `E3CountResult`.
3. E5 produces two structured tables in stdout and JSON: **summary_table** (per-category GT vs voted with per-run counts and accuracy) and **instance_table** (all instances across all runs with location + center).
4. E5 exports both tables as CSV alongside the JSON, named `{image_stem}_{session_id[:8]}_{backend}_summary.csv` and `{image_stem}_{session_id[:8]}_{backend}_instances.csv`.

**Reasons:**
1. Instance table enables manual verification: you can check whether the same physical extinguisher is detected in each run (consistent `nearby_text` + similar center).
2. CSV is directly openable in Excel/Numbers for non-code review.
3. Center coordinates enable spotlight viz and future Phase 1 zone-based clustering without re-prompting.

**Consequences:**
- `[INSTANCES_JSON]` parsing is best-effort: if marker absent (e.g. local Ollama models), `instances=[]` and no instance CSV is written.
- `center` is nullable; stored as two CSV columns (`center_x, center_y`).
- Parallel runs via `ThreadPoolExecutor(max_workers=n_runs)` in `_run_backend()` — N runs complete in ~1× wall time instead of N× wall time.
- Phase 1 instance-level note in ADR-001 Consequences is superseded: instance output is now live in Phase 0.

---

### ADR-004 — bbox → center Point + Fixed-Size Box

**Date:** 2026-06-11
**Status:** Accepted

**Context:**
ADR-003 asked the model to output `bbox: [x1, y1, x2, y2]` (full bounding box of the callout group). Visual review showed boxes were consistently too small — the model drew tight boxes around only the red cylinder symbol, missing the white label and text. Increasing prompt padding and asking for "full callout group" improved coverage but not reliably; some callouts still clipped. The core problem: estimating 4 boundary coordinates is harder for a vision LLM than finding a center point.

**Decision:**
1. Change `[INSTANCES_JSON]` output field from `bbox: [x1,y1,x2,y2]` to `center: [cx,cy]` — center of the red cylinder symbol, normalized 0–1.
2. In `viz.py`, draw a **fixed-size box** around each center using calibrated constants `_BOX_HW = 0.030`, `_BOX_HH = 0.045` (fractions of image width/height).
3. `DetectedInstance.bbox` renamed to `DetectedInstance.center`; validator updated (len=2, 0≤cx≤1, 0≤cy≤1).
4. CSV columns `bbox_x1/y1/x2/y2` replaced by `center_x, center_y`.

**Reasons:**
1. **Simpler model task**: finding a point center is more reliable than estimating 4 boundary values.
2. **Consistent box size**: all extinguisher callout groups in a given drawing are the same physical size; a fixed box calibrated once works across all instances.
3. **Decoupled concerns**: box display size is a viz constant, not a model output quality issue.

**Calibration:** `_BOX_HW=0.030, _BOX_HH=0.045` validated on poop_deck (2848×2212) and a_deck (838×775) — all instances contained within box at both resolutions.

**Consequences:**
- Model output is simpler; center prediction is more accurate than bbox prediction.
- Box size is fixed; edge cases where a callout group is unusually large will still be contained (callouts are standardized on ship fire plans).
- E1b (ADR-005) further refines the center using OpenCV, addressing residual LLM localization error.

---

### ADR-005 — E1b OpenCV Center Refiner

**Date:** 2026-06-11
**Status:** Accepted

**Context:**
After ADR-004 (center point output), visual review of a_deck showed 2 of 5 instances had inaccurate center points — the model placed the center on an adjacent element rather than the red cylinder. Counting accuracy was unaffected (100%), but spotlight boxes were misaligned. The LLM is good at counting and classification but imprecise at pixel-level localization.

**Decision:**
Add an E1b node (`e1b_refine_centers`) in `e_nodes.py` that runs after E1 and before E4. For each instance with a valid center:
1. Validate center is within [0,1]×[0,1]; if not, keep original + warn.
2. Crop a search window (3× box size) around the LLM center from the **original image**.
3. Convert to HSV; apply red mask: hue ∈ [0°,10°] ∪ [170°,180°], saturation ≥ 80, value ≥ 80.
4. Find connected components; filter by area (reject noise < `_MIN_BLOB_AREA_PX`; reject large background > `_MAX_BLOB_AREA_FRAC × window_area`).
5. From qualifying blobs, select the centroid **closest to the LLM center** (not the largest).
6. If blob found: replace center with refined centroid; set `center_refined=True`.
7. If no qualifying blob: keep original center; log warning.

**Node classification rationale:** "Detect" is one of this project's processing primitives (alongside Generate/Transform/Execute/Select/Extract). OpenCV blob detection is a Detect operation regardless of being deterministic — the primitive is classified by output semantics, not implementation mechanism. Therefore E1b, not D-something. Sub-letter notation (E1b) is used because this node was inserted after E1 in an already-approved pipeline graph; it preserves existing node numbers and makes the insertion point visible in the name.

**Reasons:**
1. **Commercial CV pattern**: two-stage coarse-to-fine — LLM provides semantic understanding + approximate location; OpenCV provides sub-pixel precision.
2. **No training required**: HSV red filtering is parameter-free for this domain.
3. **No API cost**: pure local OpenCV, < 5 ms per instance.
4. **Proximity over size**: selecting the blob closest to the LLM center is more robust than selecting the largest, which can pick up large background decorations.
5. **Area filter**: rejects both tiny noise and large non-target regions (panel backgrounds, lines).
6. **Audit trail**: `center_refined` flag records whether refinement was applied.

**Consequences:**
- Requires `opencv-python` in `requirements.txt`.
- E1b lives in `e_nodes.py` (all E nodes are kept in one file, by convention).
- Center coordinates are normalized 0–1 fractions; `cx * w_orig` maps correctly to original pixel space without additional scaling (equal-ratio resize preserves normalized coords).
- SOFT failure: if no qualifying blob, original center is preserved — pipeline never fails due to E1b.
- `center_refined` column in instances CSV for audit.
- Refined center does NOT affect `total_by_category`, E4 voting, or D1 accuracy.

---

### ADR-006 — Postgres-Backed Category Lookup (category_sets / canonical_categories / category_synonyms)

**Date:** 2026-06-19
**Status:** Accepted — implemented (T16–T21 done; see ADR-007 for the follow-up rename and first end-to-end validation of the `demo_ship_b` category set)

**Context:**
`CANONICAL_CATEGORIES` has been a hardcoded six-item Python frozenset since T1, referenced directly in `schemas.py`, `e_nodes.py` (6 sites), and `d_nodes.py` (8 sites). This service was built against one ship's fire safety plan legend (`demo_ship_a`). Adding a second dataset for the public portfolio demo (`demo_ship_b` — 4 categories, no spares, different sizes: DCP 5kg, CO2 5kg, wheeled foam 45L, water 9L) immediately broke `GroundTruth` validation, because the validator checked equality against the single global set.

This is not a one-off problem. Every drawing office labels the same physical extinguisher types differently (dry chemical powder appears as "DCP", "DP", or "P" across different legends seen so far), and every ship/project may have a different *count* of categories (3, 6, 10+ depending on vessel class and equipment fit). Hardcoding a new Python constant (or a second one, `DEMO_SHIP_CATEGORY_SET`) per dataset does not scale — it is the same mistake repeated.

**Decision:**
Move the canonical category taxonomy and its label synonyms out of code and into three Postgres tables, scoped per `project_id`:

```sql
category_sets            (id, name UNIQUE, description)
canonical_categories      (id, category_set_id FK, canonical_name, UNIQUE(category_set_id, canonical_name))
category_synonyms         (id, canonical_category_id FK, raw_label, source_note, UNIQUE(canonical_category_id, raw_label))
```

`category_sets.name` **is** the `project_id` (e.g. `"demo_ship_a"`, `"demo_ship_b"`) — no separate ship/project mapping table is needed. Lookup flow: `project_id` → one `category_sets` row → its `canonical_categories` (replaces the global frozenset for that project) → each category's `category_synonyms` (maps an LLM-observed label like `"P"` or `"DP"` back to the canonical name, eventually feeding E1/E1b's classification matching).

The canonical *agent-type* taxonomy (not the per-drawing labels) is anchored to **IMO Resolution A.951(23)** — "Improved Guidelines for Marine Portable Fire Extinguishers" — which defines the recognized extinguishing-agent types (water, water with additives, foam, dry powder/chemical standard and multi-purpose, CO₂, wet chemical) and minimum capacities (≥5 kg for powder/CO₂, ≥9 L for foam). Both existing category sets (`demo_ship_a`, `demo_ship_b`) are agent-type × capacity combinations drawn from this guidance, not arbitrary per-project invention. New category sets for future ships should be defined the same way: pick the IMO agent type(s) actually present on that ship's plan, attach the capacity shown on the legend, and only then add project-specific label synonyms.

**Explicit non-goals (scope discipline):**
- No image BLOBs in the database — reference images (if ever added) are `image_path` + `image_hash` columns, never binary content in Postgres.
- No user accounts, no permissions/roles system.
- No complex audit log beyond the existing `source_note` / `date_added`-style columns already in the schema.
- No admin dashboard / CRUD UI — new `category_sets`/`canonical_categories`/`category_synonyms` rows are added via SQL or a small script, not a web form.
- Postgres choice (over SQLite) is partly a deliberate skill-demonstration choice (client-server RDBMS, not just an embedded file) — not because this table's scale requires it. Expected scale even at dozens of ships is hundreds to low thousands of rows total — this is explicitly a small reference/lookup table, not a transactional system.

**Reasons:**
1. **Root-causes the recurring hardcoding problem** instead of patching it per dataset (the `DEMO_SHIP_CATEGORY_SET` constant added ad hoc before this ADR is superseded and removed — see T20).
2. **Matches how the real-world problem actually varies**: canonical agent types are stable (IMO-anchored, rarely change); per-drawing labels are the only thing that varies, and only the synonym table needs to grow when a new drawing office's abbreviation is encountered — no code change required.
3. **MDM pattern**: canonical/golden-record table + synonym/alias table is the standard data-engineering pattern for "many input vocabularies, one true taxonomy" — not a bespoke design.
4. **Unmatched labels degrade safely**: a label with no synonym row falls through to `unknown` (already an existing, tested code path) rather than silently misclassifying — new synonyms are added only after a human reviews an `unknown` and confirms the mapping.

**Consequences:**
- `GroundTruth` gains a required `project_id: str` field (Section 7.1); existing `demo_ship_a` ground truth CSVs need this column/path context, existing tests need updating (T19).
- `data/images/` and `data/ground_truth/` are now organized as `{project_id}/{image_id}.{png,csv}` (Section 11/12) — already the case in practice (`demo_ship_a/`, `demo_ship_b/` subdirectories exist) ahead of this ADR; this ADR formalizes it.
- `run_eval.py` needs a `--project-id` flag, inferable from the ground-truth path so existing invocation style mostly still works (T21).
- Requires a running Postgres instance (`DATABASE_URL` env var, Section 3) for any pipeline run, including tests (or a mocked/test-DB fixture — to be decided at T18 implementation time).
- Deployment to the public portfolio copy is **not required by this ADR** — the public Streamlit Cloud demo runs in mock mode by default and does not need a live DB connection; this lookup system is for real/local usage of the private original.

---

### ADR-007 — Rename `ship_set_v1`/`demo_ship` → `demo_ship_a`/`demo_ship_b`; First End-to-End Validation of `demo_ship_b`

**Date:** 2026-06-22
**Status:** Accepted

**Context:**
ADR-006 introduced two `category_sets`: `ship_set_v1` (the original 6-category dataset this harness was built against) and `demo_ship` (a synthetic 4-category set built specifically to be public-portfolio-safe). T17 seeded both into Postgres and added their image/ground-truth data under `data/{images,ground_truth}/{ship_set_v1,demo_ship}/`, but only `ship_set_v1` was ever actually wired into `run_eval.py` runs and the Streamlit frontend (`app_streamlit.py:_PROJECT_ID` was hardcoded to `"ship_set_v1"`, with no switcher — ADR-F09 in `design_frontend.md`). `demo_ship`'s DB rows and on-disk data existed but had never been run through the pipeline.

This created two problems: (1) the names `ship_set_v1`/`demo_ship` implied an asymmetry — "the real ship" vs. "the toy demo" — that no longer matched reality, since both datasets are demo-safe; (2) a second `category_set` that is seeded but never executed doesn't actually demonstrate that ADR-006's per-project lookup works end-to-end — it's just inert rows.

**Decision:**
1. Rename both category sets symmetrically: `ship_set_v1` → `demo_ship_a`, `demo_ship` → `demo_ship_b`. Applied to: live Postgres `category_sets.name` rows (+ `category_synonyms.source_note` audit text), `seed_data.sql`, `data/images/{old}→{new}/`, `data/ground_truth/{old}→{new}/`, prompt files (`prompt_cot_counts.txt`→`prompt_cot_counts_demo_ship_a.txt`, `prompt_cot_counts_demo_ship.txt`→`prompt_cot_counts_demo_ship_b.txt`), every `project_id: str = "ship_set_v1"` code default (`schemas.py` ×2, `pipeline.py` ×2, `e_nodes.py` ×2, `app_streamlit.py`, `pipeline_runner.py`), and test fixtures/function names (`test_cl_s01_ship_set_v1_categories` → `test_cl_s01_demo_ship_a_categories`, etc.).
2. Bring `demo_ship_b` fully live for the first time: ran `run_eval.py --cloud-only` against 2 of its 4 images (`main_deck`, `below_main_deck`) with real cloud-model calls. `forecastle_deck`/`wheelhouse_deck` are excluded from the active demo set for now (kept on disk, not deleted — same caution as ADR-F11) until a second pass validates them too.

**Validation results:** Running `demo_ship_b` end-to-end surfaced several real bugs invisible to a counts-only metric — a missing color-map entry, a hardcoded pixel threshold calibrated on one image's aspect ratio that silently failed on a much wider one, and an edge case where two nearby instances' boxes could overlap and visually hide each other. All were fixed (see `e_nodes.py`/`viz.py` for the current logic). One deck plan (`below_main_deck`, an unusually wide/short crop) remained run-to-run unstable on one category even after the fixes; splitting it into three near-square crops (`_bow`/`_mid`/`_stern`) resolved this, consistent with detection reliability correlating with aspect ratio rather than raw resolution — the split crops are the demo-ready artifacts going forward.

**Reasons:**
1. Symmetric naming removes the implicit "real ship vs. toy demo" asymmetry the old names carried, matching both datasets' actual (demo-safe) sensitivity status.
2. A `category_set` that's seeded but never executed doesn't demonstrate anything about ADR-006's multi-tenant lookup — running `demo_ship_b` end-to-end is what actually exercises it.
3. Visual auditing (not just category-count accuracy) catches bugs a pure counts metric can't — a box silently hiding behind another box doesn't change the count, but it's still wrong.

**Consequences:**
- All `ship_set_v1`/`demo_ship` references repo-wide are now `demo_ship_a`/`demo_ship_b` (DB rows, `seed_data.sql`, prompt filenames, code defaults, test names).
- `_bow`/`_mid`/`_stern` crops are the demo-ready artifacts for that deck going forward (see ADR-008 for where results are stored); the full unsplit image is kept as a known-imperfect case, not silently dropped.
- New regression tests added for the ownership-gate and distance-gate fixes (`test_e1b_stages.py`, `test_e2.py`).

---

### ADR-008 — Postgres-Backed `eval_runs` Persistence (Mock + Real Frontend Paths Both Read From It)

**Date:** 2026-06-22
**Status:** Accepted — implemented

**Context:**
Before this change, a finished pipeline run's result lived in one of two places depending on how it was produced, and neither was durable/queryable: (1) `run_eval.py` wrote a JSON + 2 CSVs (+ optional PNG/raw text behind `--save-viz`) to a flat `experiments/results/{image}_{session_id[:8]}.*` layout — useful for local inspection, but nothing else reads it back; (2) the live Streamlit frontend's real-detection path (`pipeline_runner.py:start_detection`) ran the pipeline and kept the resulting `ResultsViewModel` only in an in-process `_job_results` dict — gone on process restart, never written anywhere. Separately, the frontend's **mock** demo path (`app_streamlit.py:_build_mock_vm`) read from a hand-maintained dict literal, `_MOCK_JSON_BY_IMAGE: dict[str, str]`, mapping each image stem to one specific JSON filename — every time a better/re-run result replaced an old one, this dict had to be manually edited in source code. There was no single place that answered "what's the current best result for this image" durably.

**Decision:**
1. New table `eval_runs` (`src/backend/db/migrations/002_eval_runs.sql`): `session_id` (unique), `project_id`, `image_stem`, `target_short`, `prompt_label`, `created_at`, `report_data` (JSONB — the same dict `E5Report.data` already builds, unchanged), `raw_response_cloud` (text), `spotlight_png_path` (text, file path — the PNG itself stays on disk, not in the DB).
2. New module `src/backend/db_results.py` — `save_eval_run(ctx, target_short, spotlight_png_path=None)`, `get_latest_eval_run(image_stem, project_id)` (most recent row), `get_eval_run_by_session(session_id)`. Same raw-`psycopg`, no-ORM style as `category_lookup.py` (ADR-006). **Purely additive** — `e1_extract_counts`, `e1b_refine_centers`, `e4_vote_per_category`, `e5_generate_report` are unmodified; `E5Report.data` was already a public field, so there was nothing in the core pipeline that needed to change to make this possible.
3. `run_eval.py` calls `save_eval_run` after `e5_generate_report` runs (soft-fails with a warning, doesn't crash the CLI run, mirroring E5's own file-write error handling).
4. `pipeline_runner.py`'s real-detection path now also calls `save_eval_run`, then immediately **reads its own row back** via `get_eval_run_by_session` and builds the `ResultsViewModel` from that — rather than building it directly from the in-memory `ctx`. This means mock mode and real mode share **one** rendering function, `view_models.py:build_results_viewmodel_from_report_data(report_data, image_path, session_id, project_id)`, instead of two parallel implementations that could drift apart. The old `build_results_viewmodel(ctx)` (ctx-direct, voting-aware) and its dedicated test file were deleted as dead code once nothing called it anymore.
5. `app_streamlit.py:_build_mock_vm` now calls `get_latest_eval_run(image_stem, _PROJECT_ID)` instead of looking up `_MOCK_JSON_BY_IMAGE`; that dict and the `experiments/results/`-reading logic it required are gone.
6. The model's full raw text response (STEP1–4 reasoning trace + final JSON; previously parsed once in `_e1_parse_counts` and then discarded) is now kept: `E3CountResult.raw_response: str | None`, populated in `_e1_parse_counts`, persisted via `raw_response_cloud`. Saved to disk too when `--save-viz`/real-mode artifacts are written (`{prefix}_cloud_raw_response.txt`).
7. New shared helper `e_nodes.py:experiment_dir(image_path, target_short)` → `experiments/results/{image_stem}_t{target_short}/`, replacing the old flat `experiments/results/{image}_{id8}.*` layout. Both `run_eval.py` and `pipeline_runner.py` write into this same per-(image, resolution) subfolder, so re-runs of the same image accumulate together instead of scattering across the results root. `_REPORT_OUTPUT_DIR` (module global in `e_nodes.py`, originally introduced for E5's file write) is set per-run to the computed subfolder by whichever caller is running — same pattern already used for `_E1_TARGET_SHORT` (CLI override), now reused for this.
8. New shared `viz.py:save_run_artifacts(ctx, output_dir)` (moved out of `run_eval.py`'s private `_save_viz`) writes the spotlight PNG + raw-response txt; called by both `run_eval.py` (behind `--save-viz`) and unconditionally by the real frontend path, so a real detection run leaves the same on-disk artifacts as a CLI eval run.
9. Removed `pipeline.py:_save_debug_run`/`_DEBUG_DIR` — an unconditional per-run-per-backend debug dump (`experiments/debug/{prompt_label}_{session_id}/run_{n}_{backend}_counts.json`) that had accumulated hundreds of folders over the day's testing with zero downstream consumer (not read by any report, the DB, or mock mode). Deleted along with the accumulated `experiments/debug/` folders (one of which had also accidentally been written to `~/experiments/debug` instead of the project directory, from a shell working-directory mistake during this same session — unrelated to the feature itself, also cleaned up).

**Reasons:**
- A real production service persists results durably and queryably; neither flat files keyed by random session-id nor an in-process dict that dies on restart does that. Postgres was already a project dependency (ADR-006) — reusing it costs one new table, not a new system.
- Sharing one render function between mock and real paths (point 4) removes a class of bug where the two paths' rendering logic could silently diverge over time.
- Hand-editing a filename-to-image dict in source every time a better demo result is produced doesn't scale and isn't how a real app would work; querying "latest row for this image" does.
- The raw model response (point 6) had been computed and then thrown away for no reason — keeping it costs nothing and enables showing the actual reasoning trace in a future UI feature, which was explicitly requested for the demo.

**Consequences:**
- Migration: `src/backend/db/migrations/002_eval_runs.sql`. New tests: `tests/test_db_results.py` (5 cases, real local-Postgres integration, same convention as `test_category_lookup.py`); `tests/test_frontend_view_models.py` rewritten (5 cases) for `build_results_viewmodel_from_report_data`.
- **Known limitation, not fixed today:** `pipeline_runner.py` sets `e_nodes._REPORT_OUTPUT_DIR` (a module-level global) per detection request before calling `run_detection`. Two detections from different users/sessions running concurrently in separate threads would race on this global and could write into the wrong subfolder. Not a problem for today's single-user manual testing; before this app serves concurrent users, `output_dir` needs to be threaded through `run_pipeline`/`e5_generate_report` as an explicit parameter instead of a mutated global.
- **No history-browsing UI** was added (deliberately deferred — see `design_frontend.md`). `get_latest_eval_run` always returns the single most recent row for an image; if several runs of the same image vary in quality (they do — see ADR-007 Amendment's coordinate-drift finding), the unwanted rows (and their on-disk files) must be manually deleted so that "latest" points at the desired one. Exercised in practice today for `a_deck`/`b_deck`/`bridge_deck`.
- File-based artifacts (JSON/CSV/PNG/raw-response txt) are **not replaced** by the DB — both are written. Files remain the human-browsable debug trail; the DB is the new single source of truth for what the frontend renders.
- `experiments/results/` is now organized as `{image_stem}_t{target_short}/` subfolders project-wide.
