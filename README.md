# Ship Plan Compliance Auditor

[![CI](https://github.com/juanita-cao/ship-plan-compliance-auditor/actions/workflows/ci.yml/badge.svg)](https://github.com/juanita-cao/ship-plan-compliance-auditor/actions/workflows/ci.yml)
![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-blue)
![React](https://img.shields.io/badge/UI-React%20%2B%20FastAPI-61DAFB)
![Streamlit](https://img.shields.io/badge/UI-Streamlit-red)
![Postgres](https://img.shields.io/badge/DB-Postgres-336791)
![OpenCV](https://img.shields.io/badge/CV-OpenCV-5C3EE8)
![Tests](https://img.shields.io/badge/tests-257%20passing-brightgreen)

**[Live demo →](https://ship-design-compliance-demo.innerdrivestudio.com/)** (click *Enter Demo*; recorded results, no sign-up) · [original Streamlit version](https://ship-plan-auditor.streamlit.app/)

An LLM-powered fire-equipment auditor for ship deck plans, built to be **explainable by design**: every run ships with a visible reasoning trace, click-to-locate evidence highlighting on the original plan, and a per-rule compliance verdict with cited regulation articles — so a human reviewer can verify the *why*, not just trust the *what*.

**100% category-level count accuracy** on the validated demo plans, with self-consistency voting and a confidence-tiered gate that automatically routes low-agreement detections to manual review instead of silently guessing.

---

## Demo Preview

[![Results: equipment highlight and per-rule verdict](docs/assets/web/results.jpg)](https://ship-design-compliance-demo.innerdrivestudio.com/)

<table>
<tr>
<td width="50%"><img src="docs/assets/web/login.jpg" alt="Login — fictional classification society"><br><sub>Login — fictional classification society</sub></td>
<td width="50%"><img src="docs/assets/web/overview.jpg" alt="Vessel Overview — derived status per vessel"><br><sub>Vessel Overview — derived status per vessel</sub></td>
</tr>
<tr>
<td width="50%"><img src="docs/assets/web/vessel.jpg" alt="Vessel — step bar, deck picker, plan preview"><br><sub>Vessel — step bar, deck picker, plan preview</sub></td>
<td width="50%"><img src="docs/assets/web/results.jpg" alt="Results — click equipment to locate it, per-rule verdict"><br><sub>Results — click equipment to locate it, per-rule verdict</sub></td>
</tr>
<tr>
<td width="50%"><img src="docs/assets/web/review.jpg" alt="Human review — confirm or flag each detection"><br><sub>Human review — confirm or flag each detection</sub></td>
<td width="50%"><img src="docs/assets/web/signoff.jpg" alt="Sign-off — a signed review cannot be edited"><br><sub>Sign-off — a signed review cannot be edited</sub></td>
</tr>
<tr>
<td width="50%"><img src="docs/assets/web/report.jpg" alt="Printable survey report from History"><br><sub>Printable survey report from History</sub></td>
<td width="50%"><img src="docs/assets/web/copilot.jpg" alt="Copilot — cited answers, short + expandable basis"><br><sub>Copilot — cited answers, short + expandable basis</sub></td>
</tr>
<tr>
<td width="50%"><img src="docs/assets/web/upload.jpg" alt="Upload — specification and dropzone"><br><sub>Upload — specification and dropzone</sub></td>
<td width="50%"><img src="docs/assets/web/segment.jpg" alt="Segment review — drag, resize, add or remove deck boxes"><br><sub>Segment review — drag, resize, add or remove deck boxes</sub></td>
</tr>
</table>

---

## What this demonstrates

- **Explainable, audit-first detection — not a black box.** Every result keeps the model's full reasoning trace and exposes click-to-highlight evidence localization: select a category and its exact bounding box lights up on the original plan, cutting the time a human auditor spends hunting for what the model found.
- **Self-consistency for reliability, not just a single LLM call.** The model runs N times per image; per-category counts are reconciled by majority vote, with a calibrated ratio gate that flags low-agreement categories for `MANUAL_REVIEW_REQUIRED` instead of returning an unverified number.
- **A free, deterministic refinement layer alongside the paid model call.** A local OpenCV blob-detection pass corrects instance coordinates without any additional API spend — hybrid LLM + classical CV, not LLM-only.
- **Domain rules layered on top of the detection output.** A small, swappable rule table (modeled loosely on SOLAS/FSS Code extinguisher-count requirements) turns raw counts into a pass/fail/warning verdict per rule plus an overall verdict, each with a cited article.
- **Multi-tenant data model.** Detection categories, compliance rule sets, and demo datasets are looked up per "project" (per ship) from Postgres, not hardcoded — adding a new ship/category set is a data change, not a code change.
- **A real-time generated PDF audit report**, built with `reportlab` from the same ViewModel the UI renders from — not a pre-rendered file read off disk.

> ⚠️ The compliance rule table shipped here is **illustrative only** — built for demonstration purposes, not validated against a current regulatory text. Don't use it for actual regulatory submission.

---

## Architecture

```
Deck plan image ──► E1 vision-LLM detect ──► E1b OpenCV center refine ──┐
                        (N runs)                  (free, local)        │
                                                                        ▼
                                                            E4 majority vote ──┬──► D1 accuracy (eval mode)
                                                                               └──► D2 compliance check
                                                                                          │
                                                                                          ▼
                                                                              E5 report ──► web app / Streamlit + PDF
```

Design documents:
- [`docs/design_backend.md`](docs/design_backend.md) — pipeline table, data contracts, ADRs
- [`docs/design_frontend.md`](docs/design_frontend.md) — Streamlit UI: state machine, ViewModel, screen flow
- [`docs/design_web_app.md`](docs/design_web_app.md) — React + FastAPI web app: screens, state machines, upload specification, Copilot page, static demo

## Tech stack

| Layer | Tools |
|---|---|
| LLM / Vision | OpenAI vision API (structured outputs), Ollama (local model option) |
| Detection / CV | OpenCV, NumPy |
| Backend | Python 3.11, Pydantic v2, psycopg3, httpx, tenacity (retry) |
| Data | Postgres (Supabase), multi-tenant category/rule lookup |
| Web API | FastAPI, Uvicorn, Pydantic, Pillow, pypdfium2 (PDF upload), classical image segmentation (no model) |
| Web frontend | React 18, TypeScript, Vite, Ant Design, React Query, React Router, react-i18next (EN / ZH) |
| Web state | Pure state machines (review, upload, analysis), browser storage for reviews, ViewModel-style API types |
| Original UI | Streamlit, Pillow, ViewModel-pattern state management |
| Reporting | ReportLab (server-rendered PDF); printable survey report in the web app |
| Quality / CI | pytest (257 backend tests), Vitest (62 frontend tests), ruff, TypeScript strict, GitHub Actions |
| Hosting | Free static demo on Cloudflare / Render static (recorded results, no backend); Streamlit Community Cloud for the original UI |

Engineering approach (contract-first workflow):

1. Define input/output schemas before implementing pipeline logic.
2. Separate detection execution, validation checks, and decision interpretation (compliance rules) into distinct stages.
3. Preserve raw model outputs (the detection reasoning trace) for inspection rather than discarding them after parsing.
4. Use explicit verification gates before presenting results as decision support (majority voting, local geometric refinement, compliance checks all run before anything is shown to the user).
5. Persist run metadata and structured outputs (Postgres) for reproducibility — the same stored row backs both the live detection path and the demo/mock path, so there is exactly one rendering code path to maintain.
6. Keep the UI layer separate from the detection pipeline through a ViewModel-style interface (`ResultsViewModel`), so the frontend never touches raw pipeline state.

---

## Quickstart

```bash
git clone https://github.com/juanita-cao/ship-plan-compliance-auditor.git
cd ship-plan-compliance-auditor
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in DATABASE_URL at minimum

# apply schema + seed data to that Postgres instance
psql "$DATABASE_URL" -f src/backend/db/migrations/001_category_lookup.sql
psql "$DATABASE_URL" -f src/backend/db/migrations/002_eval_runs.sql
psql "$DATABASE_URL" -f src/backend/db/seed_data.sql

# run the backend test suite (257 tests)
pytest -q

# lint
ruff check .

# launch the UI in mock mode (no API key needed — replays a stored
# detection result from Postgres for each demo image)
FEH_MOCK=1 streamlit run src/frontend/app_streamlit.py
```

Requires Python 3.11+ (the codebase uses `X | None` union syntax evaluated at runtime by Pydantic) and a reachable Postgres instance.

CI runs the same lint + test commands against an ephemeral Postgres on every push — see [`.github/workflows/ci.yml`](.github/workflows/ci.yml).

---

## Web app (React + FastAPI) and free static demo

A SaaS-style web app sits on the same detection pipeline: vessel overview, review queue and history, a human review and sign-off loop, plan upload with deck segmentation, and a cited, recorded-answer Copilot page.

```bash
# live version: FastAPI backend + React frontend
uvicorn backend.api.main:app --reload --port 8000
cd frontend && npm ci && npm run dev          # http://localhost:5173

# static demo: recorded results, no backend, free to host anywhere
cd frontend && npm run build:static && npm run preview:static   # http://localhost:4173
```

The static build serves pre-exported responses from `frontend/public/demo-data/`; upload and segmentation need the live backend. See [docs/static_deploy.md](docs/static_deploy.md). The Copilot page answers 10 recorded questions, each with sources, a short answer with expandable basis, and explicit "missing file" handling ([docs/mock_chat_qa.md](docs/mock_chat_qa.md)). All vessels, surveyors and the classification society in the demo are fictional.

## Data note

Sample deck plan images are demo assets with identifying details (hull/IMO numbers, company markings) removed. Compliance rules are illustrative, modeled loosely on SOLAS/FSS Code extinguisher-count requirements — not validated against a current regulatory text, and not a substitute for a real regulatory review.

The detection prompt itself is not included in this repo — a deliberate choice, not an oversight. This means **live mode is not runnable out of the box**; mock mode (Postgres-backed, no API calls) is what powers the hosted demo above and what the preview screenshot reflects.

The evaluation harness (`run_eval.py`) supports comparing a local model (via Ollama) against a cloud model side by side, for cost/accuracy trade-off testing. All results shown in the demo dataset and this repo's docs were produced by the cloud backend; the local-model path is part of the harness's design but wasn't the one exercised for these specific numbers.

---

## Project structure

```
data/             demo deck-plan images, ground-truth counts, recorded detection results
docs/             design documents — read before the corresponding code was written
src/backend/      detection pipeline, schemas, compliance rules, Postgres access
src/frontend/     Streamlit UI, ViewModel layer, PDF report generation
backend/api/      FastAPI app: projects, detection, highlights, plan upload + segmentation
frontend/         React + TypeScript web app (and the static demo build + exported demo data)
scripts/          static demo export
tests/            257 tests: pipeline stages, API, upload + segmentation, static export
```

---

## Current Scope

Implemented:
- Explainable detection: visible reasoning trace + click-to-highlight evidence localization on the original plan
- Vision-LLM detection pipeline with self-consistency majority voting across N runs
- 100% category-level count accuracy on the validated demo plans
- Free, local OpenCV refinement pass for instance coordinates
- Postgres-backed multi-tenant category lookup — adding a ship/category set is a data change, not a code change
- IMO-style compliance rule engine with per-rule GO/NO-GO verdicts and cited articles
- Streamlit UI: mock mode (Postgres-backed, no API calls) + live mode
- Real-time PDF audit report generation from the same ViewModel the UI renders from
- Web app (React + FastAPI): vessel overview with derived status, review queue and history, human review with sign-off, printable survey report
- Plan upload with specification checks and deck segmentation (draggable, resizable, addable boxes)
- Copilot page: 10 recorded Q&A with sources, expandable basis, and explicit "missing file" answers
- Free static demo build (recorded results, no backend), EN / ZH
- CI: lint + 257 tests against an ephemeral Postgres on every push

Not implemented:
- Live mode is not runnable out of the box in this public repo — no detection prompt is shipped (see [Data note](#data-note)); bring your own to exercise it
- Production-grade compliance rules calibrated against a current regulatory text
- Multi-user authentication or persistent storage beyond the single shared demo database (web app reviews live in the browser)
- A live LLM behind the Copilot page — its answers are recorded examples; uploaded decks get a clearly labelled sample result

Per-step implementation status: `docs/design_backend.md`, `docs/design_frontend.md` and `docs/design_web_app.md`, each under "Task list and implementation status".
