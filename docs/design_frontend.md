# Ship Plan Compliance Auditor — Frontend Design Document

**Service:** `ship_plan_auditor`
**Component:** Streamlit UI (`src/frontend/app_streamlit.py`)
**Status:** Design phase
**Depends on:** `design_backend.md` (backend pipeline), `src/viz.py` (spotlight rendering)
**UI Reference:** ported CSS tokens, card layout, and header bar conventions from an earlier internal Streamlit UI

---

## 1. Overview

A Streamlit web UI exposing fire equipment detection as a black-box end-user tool.

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

| State | 显示内容 |
|-------|---------|
| `IDLE` | 图片选择器 + Analyze 按钮 + 图片预览 |
| `RUNNING` | Spinner "Analyzing..." |
| `RESULTS` | Metrics row + Original Plan + Equipment Highlight + 设备面板（含 All Found Equipment） |

---

## 3. Session State Contract

```python
from __future__ import annotations
from typing import Literal
from pydantic import BaseModel

class FEHSessionState(BaseModel):
    # 状态机
    stage: Literal["IDLE", "RUNNING", "RESULTS"] = "IDLE"

    # 输入
    image_path: str | None = None

    # 结果 — ViewModel（PipelineContext pipeline_complete 后立即转换并丢弃）
    results_vm: ResultsViewModel | None = None

    # 后台任务状态
    job_status: Literal["none", "running", "success", "error"] = "none"
    last_error: str | None = None

    # UI 选中状态（RESULTS）
    selected_category: str | None = None
    selected_instance_id: str | None = None
```

> `PipelineContext` 不存入 `session_state`；render 函数只接受 `ResultsViewModel`。

---

## 4. Event → State Transition Table

| Current State | Event | Guard | Next State | session\_state\_patch |
|---|---|---|---|---|
| `IDLE` | `analyze_clicked` | `image_path is not None` | `RUNNING` | `stage="RUNNING"`, `job_status="running"`, `last_error=None` |
| `IDLE` | `analyze_clicked` | `image_path is None` | `IDLE` | — (inline error) |
| `RUNNING` | `pipeline_complete` | — | `RESULTS` | `stage="RESULTS"`, `job_status="success"`, `results_vm=build_results_viewmodel_from_report_data(row["report_data"], ...)`（先 `save_eval_run` 落库再读回，ADR-008）, `selected_*=None` |
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
| F-State | E | Select | Resolve Next UI State | 纯函数；event + guard → `StateTransitionResult`；不直接写 `st.session_state` | `current_state`, `user_event`, `guard_result` | `StateTransitionResult` | — | ⬜ | Event Guard Table | — | Python | HARD FAIL — unrecognised `(state, event)` raises `ValueError` |
| F-VM | E | Transform | Build Results ViewModel | `eval_runs.report_data`（已落库的同一份数据，ADR-008）→ `ResultsViewModel`；mock/真实两条路径共用 | `report_data: dict`, `image_path`, `session_id`, `project_id`, `raw_response` | `ResultsViewModel` | — | ⬜ | Direct field mapping + E1b/D2 重新计算 | — | Python / Pydantic | HARD FAIL — DB 行不存在时上层 `raise RuntimeError` |
| F-Spotlight | E | Transform | Render Spotlight Image | 调用 `render_spotlight()` 生成带 bbox 覆盖的 PIL Image | `vm: ResultsViewModel`, `selected_category`, `selected_instance_id` | `PIL.Image` | — | ⬜ | Direct call to `src.viz.render_spotlight` | — | Python / Pillow | SOFT: render 失败 → 返回原图，log WARN |

> **`StateTransitionResult`** = `NamedTuple("StateTransitionResult", [("next_state", str), ("session_state_patch", dict)])`. App layer 调用 `_apply_patch(result.session_state_patch)` 后 `st.rerun()`。
>
> **`pipeline_runner.py`** 是执行层 helper（非 pipeline 图节点），在后台线程中调用 `run_detection()`，结果写入 `_job_results[session_id]` dict，app layer 轮询检查。

---

## 6. Backend Integration Contract

```python
# 新增入口函数（见 pipeline.py）— 前端专用
run_detection(
    image_path: Path,
    prompt: str,          # 按 project_id 解析（_prompt_for()，data/prompts/prompt_cot_counts_{project_id}.txt）；UI 不暴露具体文本（商业秘密）
    n_runs: int = 5,      # 默认值；pipeline_runner 实际传 n_runs=1；UI 不暴露
    prompt_label: str,    # 取该 prompt 文件 stem；UI 不暴露
    backends: list[str] = ["cloud"],  # 固定 cloud；UI 不暴露
    project_id: str = "demo_ship_a",  # ADR-006；ADR-F13 起 UI 可切换（Ship selector），不再固定单船
) -> PipelineContext
```

**F-VM 从 `PipelineContext` 读取的字段：**

| 字段 | 用途 |
|------|------|
| `session_id: str` | 写入 `ResultsViewModel.session_id` |
| `image_path: str` | 写入 `ResultsViewModel.image_path` |
| `cloud_eval.voting.votes` | → `ResultsViewModel.total_by_category`（E4 共识计数）|
| `cloud_eval.runs[0].counts.instances` | → `ResultsViewModel.instances`（spotlight 用）|

**前端不读取：** `local_eval`、`report`、`accuracy`、`completed_nodes`、`node_timings`、`ground_truth`

---

## 7. ViewModel Contract

### 7.1 ViewModel 定义

**[修订 — 见 ADR-008（design_backend.md）/ ADR-F15]** `ResultsViewModel` 不再只由 `PipelineContext` 直接构建；mock 和真实两条路径现在都先把结果写入 Postgres `eval_runs`，再从同一张表读出来渲染（design_backend.md ADR-008）。`compliance_result`（ADR-F12 之后补的字段，此处一并补全文档）和 `raw_response`（ADR-F15，模型 STEP1-4 推理原文）是当前实际字段集：

```python
from __future__ import annotations
from pydantic import BaseModel
from src.backend.schemas import ComplianceResult, DetectedInstance

class ResultsViewModel(BaseModel):
    session_id: str
    image_path: str
    instances: list[DetectedInstance]            # spotlight 渲染用
    total_by_category: dict[str, int]             # 展示为"检测结果"（按 project_id 的 canonical categories 补零）
    compliance_result: ComplianceResult | None = None   # D2 输出，渲染 IMO Compliance Check 面板
    raw_response: str | None = None               # E1 原始文本（STEP1-4 推理 + JSON），ADR-F15；无值时不渲染 reasoning trace
```

### 7.2 Transform 函数

```python
def build_results_viewmodel_from_report_data(
    report_data: dict,       # eval_runs.report_data（JSONB，与 E5Report.data 同结构）
    image_path: Path,
    session_id: str,
    project_id: str,
    raw_response: str | None = None,  # eval_runs.raw_response_cloud
) -> ResultsViewModel:
    """Build a ViewModel from a stored eval_runs row (run_id=0 only).

    Shared by mock 和真实检测两条路径——两边都先 save_eval_run() 再读回同一行，
    所以渲染逻辑只有一份，不会出现两条路径各自实现、逐渐分叉的问题（ADR-008）。
    E1b（免费、本地 OpenCV）和 compliance 在这里重新计算，而不是存储，因为
    JSON report 本身不携带 display_bbox 或 compliance 结果。
    """
    # ... instance_table.cloud（run_id=0）→ DetectedInstance 列表
    # → category_lookup.get_canonical_categories(project_id) 补零计数
    # → e1b_refine_centers() 算 display_bbox → d2_check_compliance()
```

> 取代了原先「唯一允许深入访问 `PipelineContext` 嵌套字段的函数」`build_results_viewmodel(ctx)`（已删除，ADR-008）——现在两条路径都先落库再读回，不存在直接读 `ctx` 的渲染路径。

### 7.3 Mock Fixture

> **选择依据：** 每次调用需付费 API，开发期需长期可切换 → 选 Option B。
> 启动命令：`FEH_MOCK=1 conda run -n ship-plan-auditor streamlit run src/frontend/app_streamlit.py`

**[修订 — ADR-008]** 不再用手维护的 `_MOCK_JSON_BY_IMAGE` 文件名字典——mock 模式直接查 `eval_runs` 表里该 `(project_id, image_stem)` 最新的一行，和真实检测路径读的是同一张表，同一个来源：

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

> Deck 下拉列表本身也改成 DB 驱动（`list_validated_image_stems(project_id)`，ADR-F13）——不再依赖"把没验证过的图从磁盘删掉"（ADR-F11 当时的做法），新验证的图会自动出现在列表里，不用改代码或删文件。`demo_ship_a` 沿用 ADR-F11 已经清理过的 3 张图（`a_deck`/`b_deck`/`bridge_deck`）；`demo_ship_b` 同理只展示已有 `eval_runs` 行的图（目前是 `below_main_deck_bow/mid/stern` 三张拆分图，design_backend.md ADR-007 Amendment）。

---

## 8. Render Contract

RESULTS 状态的 render 函数接受 `vm: ResultsViewModel`，不接受 `PipelineContext`。

| Component | 输入 | 输出 | Side Effects |
|---|---|---|---|
| Header bar | — | HTML title only：「Ship Plan Compliance Auditor」（ADR-F14，原 subtitle 已去掉） | — |
| IDLE Ship 选择区（ADR-F13） | `category_lookup.list_project_ids()` | `st.selectbox`，选择哪个 `project_id` | 写 `session_state.project_id`；切换时清空 `image_path` |
| IDLE Deck 选择区 | `project_id` → `list_validated_image_stems(project_id)` 过滤后的 `image_path` 列表 | `st.selectbox` + 居中显示的 preview（ADR-F14） | 写 `image_path`（widget callback） |
| IDLE Analyze 按钮 | `image_path`, `project_id` | `st.button` | — |
| RUNNING spinner | — | `st.spinner("Analyzing...")` | — |
| RESULTS「Fire Equipment Detection」section（ADR-F14，导航蓝小标题条 `.feh-section-header`） | — | 包含：2 个指标卡片（Equipment Detected / Instances Located）、Original Plan / Equipment Highlight / Equipment Inventory 三栏、Detection Reasoning Trace expander | — |
| RESULTS Original Plan | `vm.image_path` | 未标注原图，`PIL.Image` via `st.image()`，居中显示（CSS） | — |
| RESULTS Equipment Highlight | `vm.image_path`, `vm.instances`, `selected_category`, `selected_instance_id` | 带 bbox 覆盖的标注图，`PIL.Image` via `st.image()`，居中显示（CSS） | — |
| RESULTS Equipment Inventory — All Found Equipment 按钮 | `vm.total_by_category` | 列表第一项，显示全部类别合计；点击清空筛选 | 写 `selected_category=None`, `selected_instance_id=None`（`show_all_clicked`） |
| RESULTS Equipment Inventory — 分类按钮 | `vm.total_by_category`（按当前 project 实际类别遍历，ADR-F13 修复了之前固定遍历 `demo_ship_a` 6 类别的 bug）, `selected_category` | 每分类一个按钮（含 count）+ 选中时展开实例行（`location_desc` + `nearby_text`） | 写 `selected_category` / `selected_instance_id`（widget callback） |
| RESULTS Detection Reasoning Trace（`st.expander`，ADR-F15） | `vm.raw_response: str \| None` | `None` → 不渲染；否则渲染可折叠区块，内容为模型 STEP1-4 推理原文 + JSON | — |
| RESULTS「IMO Compliance Check」section（ADR-F14，同款导航蓝小标题条） | — | 包含：1 个指标卡片（Compliance Verdict）、`_render_compliance_panel` 规则列表 | — |
| RESULTS IMO Compliance Check 面板（`_render_compliance_panel`） | `vm.compliance_result: ComplianceResult \| None` | `compliance_result=None` → 不渲染；否则渲染 `is_mock` 时的 disclaimer 横幅 + 每条规则一行（`rule_id` / `article` / `description` / required vs found / 状态徽章 pass\green·fail\red·warning\amber·not\_applicable\grey）；整体 verdict 文字与配色已移到上方 section 的 Compliance Verdict 指标卡片，面板标题不再重复显示（ADR-F14） | — |
| \[↺ New Analysis\] 按钮 | — | `st.button` | — |

---

## 9. Error / Fallback Strategy

| 场景 | 级别 | 行为 |
|------|------|------|
| pipeline 抛出异常（E1 API 失败、网络超时等） | SOFT | `RUNNING → IDLE`；`st.error()` 显示错误；log WARN |
| 图片文件不存在 / 不可读 | HARD | Analyze 按钮 disabled + inline error；不进入 `RUNNING` |
| `build_results_viewmodel()` 失败（`cloud_eval` 为 None 或 runs 空） | HARD FAIL | `RUNNING → IDLE`；`st.error()`；log ERROR |
| `render_spotlight()` 失败（图片损坏等） | SOFT | 显示原图无 overlay；log WARN |
| unrecognised `(state, event)` | HARD FAIL | raises `ValueError`；不静默忽略 |

---

## 10. Test Scenario List

### F-State 节点

| Scenario ID | 场景 | 输入条件 | 预期行为 |
|---|---|---|---|
| F-State-S01 | IDLE + analyze，有图片 | `stage="IDLE"`, `event="analyze_clicked"`, `image_path` 有效 | `next_state="RUNNING"` |
| F-State-S02 | IDLE + analyze，无图片 | `stage="IDLE"`, `event="analyze_clicked"`, `image_path=None` | `next_state="IDLE"`，不转换 |
| F-State-S03 | RUNNING + 完成 | `stage="RUNNING"`, `event="pipeline_complete"` | `next_state="RESULTS"`，`results_vm` 已设置，`selected_*=None` |
| F-State-S04 | RUNNING + 失败 | `stage="RUNNING"`, `event="pipeline_error"` | `next_state="IDLE"`，`last_error` 已设置 |
| F-State-S05 | RESULTS + New Analysis | `stage="RESULTS"`, `event="new_analysis_clicked"` | `next_state="IDLE"`，所有字段清空 |
| F-State-S06 | RESULTS + 选分类 | `stage="RESULTS"`, `event="category_clicked"` | `selected_category` 设置，`selected_instance_id=None` |
| F-State-S07 | 未知 `(state, event)` | 任意不在表中的组合 | HARD FAIL — raises `ValueError` |

### F-VM 节点

| Scenario ID | 场景 | 输入条件 | 预期行为 |
|---|---|---|---|
| F-VM-S01 | 正常路径，voting 有效 | `cloud_eval` 有效，`runs` 非空，`voting` 非 None | `total_by_category` 来自 E4 `voted_count` |
| F-VM-S02 | voting 为 None（fallback） | `cloud_eval` 有效，`voting=None` | `total_by_category` 来自 `runs[0]` |
| F-VM-S03 | tie 处理 | `voted_count=None`, `tied_candidates=[2, 3]` | 使用 `tied_candidates[0]`（= 2） |
| F-VM-S04 | `cloud_eval` 为 None | `cloud_eval=None` | HARD FAIL — raises `ValueError` |
| F-VM-S05 | `runs` 为空 | `cloud_eval.runs=[]` | HARD FAIL — raises `ValueError` |

### F-Spotlight 节点

| Scenario ID | 场景 | 输入条件 | 预期行为 |
|---|---|---|---|
| F-Spotlight-S01 | `display_bbox` 可用 | `inst.display_bbox is not None` | 以 `display_bbox` 绘制 |
| F-Spotlight-S02 | 降级到 center | `display_bbox=None`, `center is not None` | 以 center 为中心绘制默认尺寸框 |
| F-Spotlight-S03 | 分类过滤 | `selected_category="extinguisher_CO2_5kg"` | 仅 CO₂ 实例高亮 |
| F-Spotlight-S04 | render 失败 | 图片文件损坏 | SOFT: 返回原图，log WARN |

---

## 11. Layout（参考 ship\_fire\_reviewer）

**[修订 — ADR-F13/F14/F15]**

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
| 图片 + pipeline → 检测结果 | 信息换形式 | Transform |
| 点击分类 → spotlight 更新 | 选择 → 可视化 | Select/Rank |

Routing: **Transform → Select/Rank**

---

## 13. File Structure

```
src/
  frontend/
    __init__.py
    app_streamlit.py      ← 主 UI 入口（state machine + render functions）
    pipeline_runner.py    ← background thread（wraps run_detection()）
    view_models.py        ← ResultsViewModel + build_results_viewmodel_from_report_data()（ADR-008）
    report_text.py        ← NEW（ADR-F15/F16）：parse_reasoning_trace() / truncate_before_instances_json()
    pdf_report.py         ← NEW（ADR-F16）：generate_report_pdf() — reportlab, in-memory, no temp files
```

Launch:
```bash
conda run -n ship-plan-auditor streamlit run src/frontend/app_streamlit.py
```

---

## 14. ADR

**ADR-F01: Always cloud backend; pipeline config not exposed to user**
前端固定使用 `backends=["cloud"]`，`n_runs=5`（默认值）。用户只看到检测结果，不看到参数配置。原因：该产品是黑盒检测工具，实现细节为商业秘密。

**ADR-F02: E4 voting result used for total\_by\_category**
`total_by_category` 取自 `BackendEvalResult.voting.votes`（E4 共识计数），不是单轮 run-0 的结果。原因：多轮投票共识比单轮更可靠；显示给用户的是最终结果，不暴露 voting 机制。Tie 时用 `tied_candidates[0]`。

**ADR-F03: Pipeline runs in a background thread**
Streamlit 每次交互重跑脚本；`run_detection()` 耗时 10–120s，必须在 `threading.Thread` 中运行。结果写入模块级 `_job_results[session_id]` dict，app layer 每次 rerun 时检查。不使用 Queue（只需 done/error 信号，不需要逐节点进度）。

**ADR-F04: No HTTP API layer — frontend imports run\_detection() directly**
同前述服务：单机内部工具，无多客户端需求。

**ADR-F05: PipelineContext discarded after ViewModel transform**
`pipeline_complete` 后立即调用 `build_results_viewmodel(ctx)`，结果存入 `session_state.results_vm`；`ctx` 不存入 `session_state`。

**ADR-F06: Phase 1 keeps DetectedInstance directly in ResultsViewModel**
不引入 `InstanceVM` 包装层。重新评估条件：面板需要不在 `DetectedInstance` 上的计算字段时引入。

**ADR-F07: fire\_eval\_harness UI 不暴露 pipeline 实现细节**
Prompt、模型 ID、n\_runs、voting 机制均不显示。RUNNING 状态只显示 spinner，不显示节点名。

**ADR-F08: Separate run\_detection() from run\_pipeline()**
前端使用 `run_detection()`（无 GT，D1 跳过）；评估 / CLI 使用 `run_pipeline()`（有 GT，D1 运行）。两个入口函数共享核心节点逻辑，分开是为了保持 eval harness 契约不变（测试不受影响），同时给生产 UI 一个干净的无 GT 入口。

**ADR-F09: Pinned to a single ship (`demo_ship_a`); no ship switcher** — **Superseded by ADR-F13（2026-06-22 同日晚些时候）**
曾设计并实现过换船按钮（多 `project_id` 切换 + 动态 prompt/category 加载），后撤销。原因（撤销时）：demo 目的是面向招聘方展示单一干净的流程，多船切换增加的复杂度对 demo 没有价值；且早期备选船数据涉及保密风险。`_PROJECT_ID` 现为模块级常量，不进 `session_state`，也不暴露任何切换 UI。`run_detection()` / `run_pipeline()` 的 `project_id` 参数保留（向后兼容、ADR-006 后端契约不变），只是前端从不传入非默认值。（此条按 ADR 惯例保留原文，不因后续撤销而改写——见 ADR-F13 为何这个决定不再适用。）

**ADR-F10: Per-image mock fixtures, not one fixed canned example**
`_build_mock_vm(image_stem)` 按 `image_stem` 查 `_MOCK_JSON_BY_IMAGE`，加载该图自己跑过的真实结果。原因：mock 模式下切换图片若结果不变，demo 看起来像假的；改成"每张图各自有真结果"后，体验等同真实跑一遍，但不花 API 费用。同一张图若有多份历史保存结果，取时间戳最新的一份。

**ADR-F11: Dataset trimmed to images with a verified saved result**
`data/images/demo_ship_a/` 删除了 `6380_platform`（疑似真实船号，保密风险）及 4 张从未跑过检测、没有保存结果的图（`f'cl_deck`、`gunway_deck`、`platform`、`poop_deck`），对应 ground truth CSV 同步删除。原因：mock-only 的 demo 不应该让用户选到一张点了 Analyze 也没有真实结果可展示的图。

**ADR-F12: Original image shown alongside the annotated spotlight**
RESULTS 页新增「Original Plan」面板（无 dim 滤镜、无 bbox 的原图），与「Equipment Highlight」（原 Spotlight，已改名）并排显示，供用户直接对比检测前后效果。三栏布局：Original Plan / Equipment Highlight / Equipment Inventory，比例 `[3, 3, 2]`。

**ADR-F13: Reintroduce Ship selector — supersedes ADR-F09**

**Context:** ADR-F09 撤销换船功能时，`demo_ship_b` 还没有真正跑通过（ADR-006 的 category_sets 是空跑的种子数据）。现在 `demo_ship_a` 和 `demo_ship_b` 都已端到端验证过、都有真实 `eval_runs` 数据（design_backend.md ADR-007 + Amendment、ADR-008）——ADR-F09 当时"多船切换没有 demo 价值"的判断不再成立：两条船都是真实可展示的结果，切换器现在展示的是系统真正的多租户能力（ADR-006），不是摆设。

**Decision:**
1. IDLE 页新增 Ship 下拉（`category_lookup.list_project_ids()`），在 Deck 下拉**之前**选。`_PROJECT_ID` 模块常量删除，改为 `session_state["project_id"]`；切换 Ship 时清空已选的 `image_path`。
2. Deck 下拉改为按 `project_id` 用 `db_results.list_validated_image_stems(project_id)` 过滤——只展示该船在 `eval_runs` 里有真实记录的图，延续 ADR-F11"只展示验证过的图"的精神，但不再依赖手动删文件，新验证的图自动出现。
3. Prompt 改为按 `project_id` 解析（`_prompt_for(project_id)` → `data/prompts/prompt_cot_counts_{project_id}.txt`），不再固定读 `demo_ship_a` 的 prompt 文件。
4. 顺带修复一个潜在 bug：Equipment Inventory 面板原先遍历的是硬编码的 `_CATEGORY_DISPLAY`（只含 `demo_ship_a` 6 个类别），切到 `demo_ship_b` 会显示错误的类别列表（全部计数为 0）。改为遍历 `vm.total_by_category`（已经按 `project_id` 正确解析，见 `view_models.py`），`_CATEGORY_DISPLAY` 只用作展示用的 label/color 查找表，现已补全 `demo_ship_b` 的 3 个专属类别。

**Consequences:** `_build_mock_vm` 的 `@st.cache_resource` key 从 `image_stem` 变成 `(project_id, image_stem)`；`start_detection()` 调用传入用户选中的 `project_id` 而非常量。

**ADR-F14: RESULTS screen restructured into two titled sections, metrics split between them**

RESULTS 页从「3 张指标卡片共享一行 + 三栏区域 + 全宽 compliance 面板」改为两个用导航蓝小标题条（`.feh-section-header`，颜色与顶部主 header 一致但更小）分隔的 section：「Fire Equipment Detection」（含 Equipment Detected / Instances Located 指标卡 + 原三栏区域 + Detection Reasoning Trace）与「IMO Compliance Check」（含 Compliance Verdict 指标卡 + 原规则列表面板）。指标卡按归属拆开而不是放在两个 section 上方共享，是用户明确选择的方案。`_render_compliance_panel` 的标题文字（"IMO Compliance Check" + verdict 配色）随之简化掉，避免和新的 section 标题/指标卡重复，只保留 MOCK 徽章和 disclaimer。同一次改动顺带：顶部 header 文案改为项目名「Ship Plan Compliance Auditor」，去掉原 subtitle；IDLE 页删除「Analysis Configuration」信息卡。

**修订（同日，多轮迭代后的最终状态）：**
- IDLE 图片预览：最初实现是"整行居中"（base64 内嵌 HTML + `text-align:center`），但选择器那一行本身是左侧 3 个窄栏（Ship/Deck/Run Analysis）+ 隐式留白，导致图片的居中基准（整行宽度）跟选择器的视觉基准（左侧 73% 宽度）不一致，看起来像图片偏右。最终方案：图片改为放进跟 Ship 下拉**同一个 column**（`st.columns([1.4, 2, 1])` 的第一栏），不再用整行居中——两者共享同一个左边界，视觉上自然对齐。
- `Compliance Verdict` 指标卡：曾经尝试改成跟「Fire Equipment Detection」的两个指标卡一样占满整行，但跟下面 `_render_compliance_panel` 的窄内容对比显得过大/不协调；最终改回小卡片 + 左对齐（`st.columns([1, 3])`，卡片放第一栏），与最初 ADR-F14 决定的"窄列"方案一致。
- `.feh-section-header` 补了 `margin-bottom: 10px` 并把 `border-radius` 改成四角都圆（之前是只圆上面两角，假设它会跟下方卡片视觉相连，实际改完后两者之间需要留白，四角圆角才不会显得突兀）。
- **CSS 间距踩坑记录（已尝试、已撤销，不要重复）：** Equipment Inventory 分类按钮列表（每个按钮是 3 个独立 Streamlit 元素：开 div / button / 闭 div）默认间距很大很丑。尝试过：(1) 全局覆盖 `[data-testid="stVerticalBlock"] { gap: ... }` —— 破坏了 `st.columns()` 横向布局的列宽比例（同一个 gap 属性也控制列间距）；(2) `[data-testid="stVerticalBlock"]:has(.feh-cat-btn) { gap: ... }` 试图精确限定范围 —— 但 `:has()` 不限制层级，只要某个祖先容器内**任意深度**存在 `.feh-cat-btn`，就会命中，结果还是命中了包裹整页内容的高层容器，等于变相全局。两次都撤销，现在按钮间距维持 Streamlit 默认（丑但不破坏布局）。真正修复需要把每个按钮的 3 个 Streamlit 元素合并成更少的调用，是代码改动，不是纯 CSS 能稳妥解决的，留作后续工作。

**ADR-F15: Raw reasoning trace surfaced in the UI**

`E3CountResult.raw_response`（模型 STEP1-4 推理原文 + JSON，design_backend.md ADR-008 起持久化到 `eval_runs.raw_response_cloud`）此前只存库，前端从未读取或展示。新增 `ResultsViewModel.raw_response: str | None`，`build_results_viewmodel_from_report_data()` 新增同名可选参数，两条调用路径（`pipeline_runner.py`、`app_streamlit.py:_build_mock_vm`）都从已查到的 `eval_runs` 行里把 `raw_response_cloud` 传进去。渲染为 RESULTS 页「Fire Equipment Detection」section 内的 `st.expander("Detection Reasoning Trace", expanded=False)`，无值时不渲染——避免推理文本（可能几 KB）把三栏区域往下挤。

**修订（同日，三轮迭代后的最终渲染方式）：** 新增共享模块 `src/frontend/report_text.py`，按 prompt 文件定义的 bracket marker 格式（`[DETECTION_LIST]`/`[MATCHING]`/`[CHECKLIST]`/`[EXCLUDED]`/`[VALIDATION]`/`[RESULT]`，止于 `[INSTANCES_JSON]`——之后是给机器读的 JSON，不展示）把 `raw_response` 解析成结构化 section。展示方式经过三轮：
1. 第一版：把 `DETECTION_LIST`/`VALIDATION` 两个 section 重新组织成表格 + PASS/FAIL 徽章（跟 Equipment Inventory/IMO Compliance Check 同款视觉语言），其余 section（MATCHING/CHECKLIST/EXCLUDED）被舍弃。用户反馈"现在的内容不对"——要求看到模型自己写的全部 step，不要被精简掉。
2. 第二版：改回展示 `raw_response` 原文（只在 `[INSTANCES_JSON]` 处截断），用 `st.text()` 整段输出，格式不变。用户反馈背景/字体不够专业（截图对比 Original Plan 卡片的白底样式）。
3. **最终版：** 用 `report_text.parse_reasoning_trace()` 把全部 6 个 section（不再舍弃任何一个）解析成嵌套 bullet 结构，渲染成报告排版——每个 section 一个大写小标题，每条目加粗作标题（如 "Instance 1"、复用 `_CATEGORY_DISPLAY` 的 label 给类别名美化），子字段缩进展示为带灰色标签的列表，包在跟 Original Plan 同款的白底卡片（`.feh-trace-card`）里。`Detection Reasoning Trace` expander 标题样式同步改成跟其余 `.feh-card-title` 一致（白底深色字），不再用导航蓝底。

**ADR-F16: PDF report — generated live with reportlab, downloadable next to "New Analysis"**

**Context:** 用户想要一个可下载的报告文件，要求"真实生成的，不是 mock 然后在某个文件夹里读取的"——即每次下载都从当前 `vm`（无论 mock 还是真实模式，背后都是 `eval_runs` 里真实跑过的那条记录，见 design_backend.md ADR-008）重新渲染，不是预生成的静态文件。

**Decision:**
1. 新模块 `src/frontend/pdf_report.py`：`generate_report_pdf(vm, project_id, category_labels) -> bytes`，用 `reportlab`（已是 conda 环境里的依赖，补进 `requirements.txt`）在内存中构建 PDF，返回 bytes。内容：标题页（项目名+船/deck）→ 指标摘要表 → Equipment Highlight 标注图（`render_spotlight_node(vm, None, None)`，跟 UI 上的选中状态无关，总是全量高亮）→ Detection Findings 表（来自 `report_text.parse_reasoning_trace` 的 `DETECTION_LIST`）→ Equipment Inventory 表 → IMO Compliance Check 表 → Analysis Summary（见下）。
2. `app_streamlit.py:_render_results` 在 "New Analysis" 左边新增 `st.download_button("⬇ Download Report", data=pdf_bytes, ...)`，`pdf_bytes` 每次 rerun 直接调用 `generate_report_pdf` 现算，不缓存、不落盘——下载内容永远反映当前 `vm`。
3. **Analysis Summary 不是 Validation Checks 表格：** 最初 PDF 里也放了跟 UI 同款的 PASS/FAIL 验证清单，用户要求换成"一小段总结的 report"风格（参考截图：一段分析性文字，不是表格）。改为 `pdf_report.py:_analysis_summary()` + `_compliance_summary()` 两个纯 Python 函数，把 `VALIDATION` section 的 3 条 explanation 文字、以及 `ComplianceResult.checks` 的通过/未通过情况，拼接成 2 段自然语言段落——**不调用任何新的模型 API**：detection 部分用的是模型在最初那次检测调用里已经生成的 explanation 原文；compliance 部分是 D2（本地计算，从不调模型）的结果。下载 PDF 的边际成本是 0。
4. 修了两个 reportlab 渲染 bug（实际生成 PDF 肉眼检查发现的，不是猜的）：(a) reportlab 默认 Helvetica 字体没有 U+2082（"CO₂" 里的下标 2）字形，渲染成黑方块——加了 `_pdf_text()` 把 `₂` 换成 `<sub>2</sub>` 标记；同时发现 Equipment Inventory 表格那一列用的是裸字符串而不是 `Paragraph`，导致 `<sub>` 标记被当成纯文字显示出来——改成统一用 `Paragraph` 包裹。(b) Compliance Check 的 Status 列原先直接显示 `check.status.upper()`（如 `NOT_APPLICABLE`），列宽不够导致溢出——改成跟 UI 一致的短标签（`PASS`/`FAIL`/`WARN`/`N/A`）。
5. PDF 内 Detection Findings 排在 Equipment Inventory **之前**（用户要求——findings 是 inventory 计数的来源，逻辑顺序应该在前）。
6. `st.download_button` 用的 `data-testid` 是 `stDownloadButton`，跟 `st.button` 的 `stButton` 不是同一个——之前"Secondary 按钮"的 CSS 规则只覆盖了 `stButton`，导致下载按钮配色跟 "New Analysis" 不一致（深色而不是白底），补了一条同时覆盖两个 testid 的规则。

**Consequences:** `requirements.txt` 新增 `reportlab>=4.0`。新文件 `src/frontend/report_text.py`（`parse_reasoning_trace`/`truncate_before_instances_json`，供 ADR-F15 的 UI 展示和本 ADR 的 PDF 共用，避免两处各自解析 `raw_response` 再次分叉）、`src/frontend/pdf_report.py`。新测试 `tests/test_report_text.py`（6 cases）。

---

## 15. Task list and implementation status

| Task | 描述 | Status |
|------|------|--------|
| T1 | UI State Machine 设计通过（§2） | ✅ |
| T2 | Session State Contract 设计通过（§3） | ✅ |
| T3 | Event Transition Table 设计通过（§4） | ✅ |
| T4 | Frontend Pipeline Table 设计通过（§5） | ✅ |
| T5 | Backend Integration Contract 设计通过（§6） | ✅ |
| T6 | ViewModel Contract 设计通过（§7） | ✅ |
| T7 | Render Contract 设计通过（§8） | ✅ |
| T8 | Error / Fallback Strategy 设计通过（§9） | ✅ |
| T9 | Test Scenario List 设计通过（§10） | ✅ |
| T10 | `pytest tests/` — E / D / V 节点全绿 | ✅ |
| T11 | `run_detection()` 添加至 `pipeline.py` | ✅ |
| T12 | `src/frontend/__init__.py` + `view_models.py` | ✅ |
| T13 | Tests: F-VM S01–S05 | ✅ |
| T14 | Tests: F-State S01–S07 | ✅ |
| T15 | Tests: F-Spotlight S01–S04 | ✅ |
| T16 | `app_streamlit.py` Mock Shell（三状态用 `_MOCK_RESULTS_VM` 跑通） | ✅ |
| T17 | `pipeline_runner.py` — background thread | ✅ |
| T18 | `app_streamlit.py` — bind real `run_detection()` | ✅ |
| T19 | Manual smoke test — IDLE → RUNNING → RESULTS golden path | ✅ |
| T20 | Manual smoke test — 分类点击 → spotlight 过滤 | ✅ |
| T21 | 设计 + 实现 + 撤销换船功能（多 `project_id` 切换） — 决定保留单船 demo（ADR-F09） | ✅ |
| T22 | 数据集精简：删除 `6380_platform` + 4 张无保存结果的图（ADR-F11） | ✅ |
| T23 | Mock fixture 改为按图片切换（`_build_mock_vm(image_stem)`，ADR-F10） | ✅ |
| T24 | 新增 Original Plan 面板，三栏布局（ADR-F12） | ✅ |
| T25 | Equipment Inventory 新增 "All Found Equipment" 按钮 | ✅ |
| T26 | CSS：图片在各自 column 内居中 | ✅ |
| T27 | 重新实现换船功能：Ship 下拉 + DB 驱动的 deck 过滤，撤销 ADR-F09（ADR-F13） | ✅ |
| T28 | 修复 Equipment Inventory 遍历硬编码 `_CATEGORY_DISPLAY` 的 bug（ADR-F13） | ✅ |
| T29 | RESULTS 页拆分为两个 section（Fire Equipment Detection / IMO Compliance Check），指标卡按归属拆开（ADR-F14） | ✅ |
| T30 | 顶部 header 改为项目名，IDLE 页删除 Analysis Configuration 卡片并居中图片（ADR-F14） | ✅ |
| T31 | `raw_response` 接入 `ResultsViewModel`，新增 Detection Reasoning Trace expander（ADR-F15） | ✅ |
| T32 | `report_text.py`：`parse_reasoning_trace()` 解析全部 6 个 section + `truncate_before_instances_json()`，Detection Reasoning Trace 改为报告排版（白底卡片 + 嵌套 bullet），3 轮迭代后定稿（ADR-F15 修订） | ✅ |
| T33 | IDLE 图片预览位置修正：从"整行居中"改成跟 Ship 下拉同一栏；`Compliance Verdict` 改回窄列；`.feh-section-header` 补 `margin-bottom` + 四角圆角（ADR-F14 修订） | ✅ |
| T34 | 尝试修 Equipment Inventory 按钮列表间距（全局 gap / `:has()` 限定 gap），两次都因破坏 `st.columns()` 布局被撤销，恢复 Streamlit 默认间距（ADR-F14 修订，记录避免重复踩坑） | ❌ 撤销 |
| T35 | `pdf_report.py` + `report_text.py` 新增 `generate_report_pdf()`，"New Analysis" 左侧新增实时生成的 Download Report 按钮（ADR-F16） | ✅ |
| T36 | PDF 内容迭代：Analysis Summary 取代 Validation Checks 表格，Detection Findings 移到 Equipment Inventory 之前，修复 CO₂ 下标黑方块 + Status 列溢出两个 reportlab bug（ADR-F16） | ✅ |
| T37 | Tests: report_text RPT-S01–S06；新增 `reportlab>=4.0` 到 `requirements.txt` | ✅ |
