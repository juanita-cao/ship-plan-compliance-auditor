"""ADR-006 — Postgres-backed category lookup.

category_sets.name IS the project_id. Each project's canonical categories and
their label synonyms are looked up here and cached in-memory for the life of
the process (no TTL) — this is a lookup/config table, not a transactional
data store, so it does not change during a single pipeline run.

See docs/design_backend.md Section 7.10 (category_lookup scenarios CL-S01
through CL-S10) and ADR-006 for the full rationale.
"""

from __future__ import annotations

import os

import psycopg

_categories_cache: dict[str, frozenset[str]] = {}
_synonyms_cache: dict[tuple[str, str], frozenset[str]] = {}
_project_ids_cache: list[str] | None = None


def _connect() -> psycopg.Connection:
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise ValueError("DATABASE_URL is not set")
    return psycopg.connect(database_url)


def get_canonical_categories(project_id: str) -> frozenset[str]:
    """Canonical category names for a project_id (= category_sets.name)."""
    if not project_id:
        raise ValueError("project_id must be a non-empty string")
    if project_id in _categories_cache:
        return _categories_cache[project_id]

    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT cc.canonical_name
            FROM canonical_categories cc
            JOIN category_sets cs ON cs.id = cc.category_set_id
            WHERE cs.name = %s
            """,
            (project_id,),
        ).fetchall()

    if not rows:
        raise ValueError(f"Unknown project_id: {project_id!r}")

    result = frozenset(row[0] for row in rows)
    _categories_cache[project_id] = result
    return result


def get_synonyms(canonical_name: str, project_id: str) -> frozenset[str]:
    """Label synonyms (raw_label values) for one canonical category within a project."""
    if not canonical_name or not project_id:
        raise ValueError("canonical_name and project_id must be non-empty strings")
    cache_key = (project_id, canonical_name)
    if cache_key in _synonyms_cache:
        return _synonyms_cache[cache_key]

    with _connect() as conn:
        category_row = conn.execute(
            """
            SELECT cc.id
            FROM canonical_categories cc
            JOIN category_sets cs ON cs.id = cc.category_set_id
            WHERE cs.name = %s AND cc.canonical_name = %s
            """,
            (project_id, canonical_name),
        ).fetchone()

        if category_row is None:
            raise ValueError(
                f"canonical_name {canonical_name!r} is not part of "
                f"project_id {project_id!r}'s category set"
            )

        synonym_rows = conn.execute(
            "SELECT raw_label FROM category_synonyms WHERE canonical_category_id = %s",
            (category_row[0],),
        ).fetchall()

    result = frozenset(row[0] for row in synonym_rows)
    _synonyms_cache[cache_key] = result
    return result


def list_project_ids() -> list[str]:
    """All known project_ids (= category_sets.name), sorted. Frontend ship-selector source."""
    global _project_ids_cache
    if _project_ids_cache is not None:
        return _project_ids_cache

    with _connect() as conn:
        rows = conn.execute("SELECT name FROM category_sets ORDER BY name").fetchall()

    _project_ids_cache = [row[0] for row in rows]
    return _project_ids_cache


def clear_cache() -> None:
    """Test helper — resets all in-memory caches. Not used by production code paths."""
    global _project_ids_cache
    _categories_cache.clear()
    _synonyms_cache.clear()
    _project_ids_cache = None
