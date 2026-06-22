-- ADR-006 — Postgres-backed category lookup
-- See docs/design_backend.md Section 2, 7.1, 11, ADR-006 for full rationale.
--
-- category_sets.name IS the project_id (e.g. "demo_ship_a", "demo_ship_b") —
-- no separate ship/project mapping table.

BEGIN;

CREATE TABLE category_sets (
    id          SERIAL PRIMARY KEY,
    name        TEXT NOT NULL UNIQUE,
    description TEXT
);

CREATE TABLE canonical_categories (
    id              SERIAL PRIMARY KEY,
    category_set_id INTEGER NOT NULL REFERENCES category_sets(id) ON DELETE CASCADE,
    canonical_name  TEXT NOT NULL,
    UNIQUE (category_set_id, canonical_name)
);

CREATE TABLE category_synonyms (
    id                    SERIAL PRIMARY KEY,
    canonical_category_id INTEGER NOT NULL REFERENCES canonical_categories(id) ON DELETE CASCADE,
    raw_label             TEXT NOT NULL,
    source_note           TEXT,
    UNIQUE (canonical_category_id, raw_label)
);

CREATE INDEX idx_canonical_categories_set ON canonical_categories(category_set_id);
CREATE INDEX idx_category_synonyms_canonical ON category_synonyms(canonical_category_id);

COMMIT;
