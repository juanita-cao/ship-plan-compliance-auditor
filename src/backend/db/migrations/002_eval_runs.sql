-- ADR-007 amendment — Postgres-backed eval run results
-- Persists what run_eval.py / the live frontend pipeline produce, so both the
-- mock demo path and the real detection path read from the same source of
-- truth instead of flat files in experiments/results/ or in-process memory.

BEGIN;

CREATE TABLE eval_runs (
    id                  SERIAL PRIMARY KEY,
    session_id          TEXT NOT NULL UNIQUE,
    project_id          TEXT NOT NULL,
    image_stem          TEXT NOT NULL,
    target_short        INTEGER,
    prompt_label        TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    report_data         JSONB NOT NULL,
    raw_response_cloud  TEXT,
    spotlight_png_path  TEXT
);

CREATE INDEX idx_eval_runs_image_stem ON eval_runs(project_id, image_stem, created_at DESC);

COMMIT;
