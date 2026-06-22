# Ship Plan Compliance Auditor

A black-box detection tool that reads a ship deck plan image, locates fire-fighting
equipment (extinguishers by type), and checks the result against a configurable set
of compliance rules — surfaced through a Streamlit UI with a downloadable PDF report.

## What this demonstrates

- **Vision-LLM detection as a structured pipeline, not a single prompt call.** The
  model runs multiple times per image; per-category results are reconciled with
  majority voting before anything reaches the user.
- **A free, deterministic refinement layer alongside the paid model call.** A local
  OpenCV blob-detection pass corrects instance coordinates without any additional
  API spend.
- **Domain rules layered on top of the detection output.** A small, swappable rule
  table (modeled loosely on SOLAS/FSS Code extinguisher-count requirements) turns raw
  counts into a pass/fail/warning verdict per rule plus an overall verdict.
- **Multi-tenant data model.** Detection categories, compliance rule sets, and demo
  datasets are looked up per "project" (per ship) from Postgres, not hardcoded —
  adding a new ship/category set is a data change, not a code change.
- **A real-time generated PDF report**, built with `reportlab` from the same
  ViewModel the UI renders from — not a pre-rendered file read off disk.

## How it works

1. User picks a ship and a deck plan image in the Streamlit UI.
2. The image + a structured prompt go to a vision-capable LLM, run several times.
3. A local OpenCV pass refines each detected instance's on-image coordinates (free,
   no extra API call).
4. Per-category counts are reconciled across runs by majority vote.
5. Counts are checked against the project's compliance rule table.
6. Results — annotated image, category counts, compliance verdict, the model's own
   reasoning trace, and a downloadable PDF — are rendered back to the user.

All of this (image, model choice, run count, voting, prompt) is hidden behind a
single "Run Analysis" button — the UI is a clean black-box tool, not a pipeline
debugger.

> ⚠️ The compliance rule table shipped here is **illustrative only** — built for
> demonstration purposes, not validated against a current regulatory text. Don't use
> it for actual regulatory submission.

## Engineering Approach

This project follows a contract-first workflow:

1. Define input/output schemas before implementing pipeline logic.
2. Separate detection execution, validation checks, and decision interpretation
   (compliance rules) into distinct stages.
3. Preserve raw model outputs (the detection reasoning trace) for inspection rather
   than discarding them after parsing.
4. Use explicit verification gates before presenting results as decision support
   (majority voting, local geometric refinement, compliance checks all run before
   anything is shown to the user).
5. Persist run metadata and structured outputs (Postgres) for reproducibility — the
   same stored row backs both the live detection path and the demo/mock path, so
   there is exactly one rendering code path to maintain.
6. Keep the UI layer separate from the detection pipeline through a ViewModel-style
   interface (`ResultsViewModel`), so the frontend never touches raw pipeline state.

## Tech stack

Python · Pydantic · Streamlit · Postgres · OpenCV · reportlab · pytest

## Running locally

Requires Python 3.11+ (the codebase uses `X | None` union syntax throughout).

```bash
pip install -r requirements.txt
cp .env.example .env   # fill in DATABASE_URL at minimum
```

**Mock mode** (no API key needed — replays a previously stored detection result from
Postgres for each demo image):

```bash
FEH_MOCK=1 streamlit run src/frontend/app_streamlit.py
```

**Live mode** (calls a real vision-LLM, requires `OPENAI_API_KEY` and/or a local
Ollama server):

```bash
streamlit run src/frontend/app_streamlit.py
```

Either mode requires a reachable Postgres instance with the schema in
`src/backend/db/migrations/` applied and seeded via `src/backend/db/seed_data.sql`.

## Project structure

- `src/backend/` — detection pipeline, compliance rules, category lookup, Postgres access
- `src/frontend/` — Streamlit UI, ViewModel layer, PDF report generation
- `tests/` — unit tests for every stage above
- `docs/design_backend.md`, `docs/design_frontend.md` — full design docs, including
  the task list and implementation status for each layer

## Disclaimer

Sample deck plan images are demo assets with identifying details (hull/IMO numbers,
company markings) removed. Compliance rules are illustrative and not a substitute
for a real regulatory review.

The evaluation harness (`run_eval.py`) supports comparing a local model (via Ollama)
against a cloud model side by side — useful for cost/accuracy trade-off testing. All
results shown in the demo dataset and this repo's docs were produced by the cloud
backend; the local-model path is part of the harness's design but wasn't the one
exercised for these specific numbers.
