-- ADR-006 — seed data for category_sets / canonical_categories / category_synonyms
-- See docs/design_backend.md Section 2 (category set tables) and ADR-006.
--
-- Synonyms are seeded conservatively from what has actually been observed so
-- far (the original prompt_cot_counts.txt matching rules for demo_ship_a;
-- the demo_ship_b legend image for demo_ship_b). New synonyms get added here (or
-- via a future small script) as new drawing-office abbreviations are
-- encountered — that is the whole point of this table (ADR-006).

BEGIN;

-- ─── demo_ship_a — original 6-category set ─────────────────────────────────

INSERT INTO category_sets (name, description) VALUES
    ('demo_ship_a', 'Original dataset this harness was built against. 6 categories incl. spares.');

INSERT INTO canonical_categories (category_set_id, canonical_name)
SELECT id, c.canonical_name
FROM category_sets, (VALUES
    ('extinguisher_CO2_5kg'),
    ('extinguisher_CO2_5kg_spare'),
    ('extinguisher_dry_powder_6kg'),
    ('extinguisher_dry_powder_6kg_spare'),
    ('extinguisher_foam_9L'),
    ('extinguisher_foam_9L_spare')
) AS c(canonical_name)
WHERE category_sets.name = 'demo_ship_a';

-- Synonyms — from prompt_cot_counts_demo_ship_a.txt STEP 2 matching rules (R1-R6)
INSERT INTO category_synonyms (canonical_category_id, raw_label, source_note)
SELECT cc.id, s.raw_label, 'prompt_cot_counts_demo_ship_a.txt R1-R6'
FROM canonical_categories cc
JOIN category_sets cs ON cs.id = cc.category_set_id AND cs.name = 'demo_ship_a'
JOIN (VALUES
    ('extinguisher_CO2_5kg', 'CO2'),
    ('extinguisher_CO2_5kg', 'CO₂'),
    ('extinguisher_CO2_5kg_spare', 'CO2-S'),
    ('extinguisher_CO2_5kg_spare', 'CO₂-S'),
    ('extinguisher_dry_powder_6kg', 'P'),
    ('extinguisher_dry_powder_6kg_spare', 'P-S'),
    ('extinguisher_foam_9L', 'F'),
    ('extinguisher_foam_9L', 'FOAM'),
    ('extinguisher_foam_9L_spare', 'F-S')
) AS s(canonical_name, raw_label) ON s.canonical_name = cc.canonical_name;

-- ─── demo_ship_b — public-portfolio synthetic set, IMO A.951(23)-anchored ─────

INSERT INTO category_sets (name, description) VALUES
    ('demo_ship_b', 'Synthetic public-portfolio demo dataset. 4 categories, no spares. Agent types per IMO Resolution A.951(23).');

INSERT INTO canonical_categories (category_set_id, canonical_name)
SELECT id, c.canonical_name
FROM category_sets, (VALUES
    ('extinguisher_DCP_5kg'),
    ('extinguisher_CO2_5kg'),
    ('extinguisher_wheeld_foam_45L'),
    ('extinguisher_water_9L')
) AS c(canonical_name)
WHERE category_sets.name = 'demo_ship_b';

-- Synonyms — from the demo_ship_b legend image (user-provided) + common
-- real-world abbreviation variants for the same agent type (DCP/DP/P)
INSERT INTO category_synonyms (canonical_category_id, raw_label, source_note)
SELECT cc.id, s.raw_label, 'demo_ship_b legend image, 2026-06-19'
FROM canonical_categories cc
JOIN category_sets cs ON cs.id = cc.category_set_id AND cs.name = 'demo_ship_b'
JOIN (VALUES
    ('extinguisher_DCP_5kg', 'P'),
    ('extinguisher_DCP_5kg', 'DCP'),
    ('extinguisher_DCP_5kg', 'DP'),
    ('extinguisher_DCP_5kg', 'D.C.P.'),
    ('extinguisher_CO2_5kg', 'CO2'),
    ('extinguisher_CO2_5kg', 'CO₂'),
    ('extinguisher_wheeld_foam_45L', 'F'),
    ('extinguisher_wheeld_foam_45L', 'FOAM'),
    ('extinguisher_wheeld_foam_45L', 'WHEELED'),
    ('extinguisher_water_9L', 'W'),
    ('extinguisher_water_9L', 'WATER')
) AS s(canonical_name, raw_label) ON s.canonical_name = cc.canonical_name;

COMMIT;
