"""Postgres-backed category lookup tests (ADR-006) — CL-S01 through CL-S10.

Integration tests against the real local Postgres instance (DB connectivity
is the whole point of this module, so these are not mocked away).
"""

from __future__ import annotations

import os

import psycopg
import pytest

from src.backend import category_lookup

_TEST_DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql://localhost:5432/ship_plan_auditor"
)


@pytest.fixture(autouse=True)
def _env_and_cache(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", _TEST_DATABASE_URL)
    category_lookup.clear_cache()
    yield
    category_lookup.clear_cache()


@pytest.fixture
def count_connects(monkeypatch):
    calls = {"n": 0}
    real_connect = category_lookup._connect

    def _counting_connect():
        calls["n"] += 1
        return real_connect()

    monkeypatch.setattr(category_lookup, "_connect", _counting_connect)
    return calls


def test_cl_s01_demo_ship_a_categories():
    """CL-S01: known project_id 'demo_ship_a' returns its 6 canonical categories."""
    result = category_lookup.get_canonical_categories("demo_ship_a")
    assert result == frozenset(
        {
            "extinguisher_CO2_5kg",
            "extinguisher_CO2_5kg_spare",
            "extinguisher_dry_powder_6kg",
            "extinguisher_dry_powder_6kg_spare",
            "extinguisher_foam_9L",
            "extinguisher_foam_9L_spare",
        }
    )


def test_cl_s02_demo_ship_b_categories():
    """CL-S02: known project_id 'demo_ship_b' returns its 4 canonical categories."""
    result = category_lookup.get_canonical_categories("demo_ship_b")
    assert result == frozenset(
        {
            "extinguisher_DCP_5kg",
            "extinguisher_CO2_5kg",
            "extinguisher_wheeld_foam_45L",
            "extinguisher_water_9L",
        }
    )


def test_cl_s03_unknown_project_id_raises():
    """CL-S03: unknown project_id raises ValueError, nothing cached."""
    with pytest.raises(ValueError):
        category_lookup.get_canonical_categories("nonexistent_ship")


def test_cl_s04_empty_project_id_raises_without_query(count_connects):
    """CL-S04: empty project_id raises ValueError immediately — no DB query."""
    with pytest.raises(ValueError):
        category_lookup.get_canonical_categories("")
    assert count_connects["n"] == 0


def test_cl_s05_repeated_call_hits_cache(count_connects):
    """CL-S05: second call for the same project_id is a cache hit (1 DB round-trip total)."""
    first = category_lookup.get_canonical_categories("demo_ship_a")
    second = category_lookup.get_canonical_categories("demo_ship_a")
    assert first == second
    assert count_connects["n"] == 1


def test_cl_s06_demo_ship_b_dcp_synonyms():
    """CL-S06: known canonical_name returns its synonyms."""
    result = category_lookup.get_synonyms("extinguisher_DCP_5kg", "demo_ship_b")
    assert result == frozenset({"P", "DCP", "DP", "D.C.P."})


def test_cl_s07_canonical_name_not_in_project_raises():
    """CL-S07: canonical_name not part of project_id's set raises ValueError."""
    with pytest.raises(ValueError):
        category_lookup.get_synonyms("extinguisher_DCP_5kg", "demo_ship_a")


def test_cl_s08_canonical_name_with_no_synonyms_returns_empty():
    """CL-S08: canonical_name exists but has zero synonym rows -> empty frozenset, no error."""
    with psycopg.connect(_TEST_DATABASE_URL) as conn:
        set_id = conn.execute(
            "SELECT id FROM category_sets WHERE name = 'demo_ship_a'"
        ).fetchone()[0]
        new_id = conn.execute(
            """
            INSERT INTO canonical_categories (category_set_id, canonical_name)
            VALUES (%s, '_test_zero_synonym_category')
            RETURNING id
            """,
            (set_id,),
        ).fetchone()[0]
        conn.commit()

    try:
        result = category_lookup.get_synonyms("_test_zero_synonym_category", "demo_ship_a")
        assert result == frozenset()
    finally:
        with psycopg.connect(_TEST_DATABASE_URL) as conn:
            conn.execute("DELETE FROM canonical_categories WHERE id = %s", (new_id,))
            conn.commit()


def test_cl_s09_repeated_synonym_call_hits_cache(count_connects):
    """CL-S09: second get_synonyms call for the same (canonical_name, project_id) is a cache hit."""
    first = category_lookup.get_synonyms("extinguisher_DCP_5kg", "demo_ship_b")
    second = category_lookup.get_synonyms("extinguisher_DCP_5kg", "demo_ship_b")
    assert first == second
    assert count_connects["n"] == 1


def test_cl_s10_clear_cache_forces_requery(count_connects):
    """CL-S10: clear_cache() resets the cache — next call re-queries the DB."""
    category_lookup.get_canonical_categories("demo_ship_a")
    category_lookup.clear_cache()
    category_lookup.get_canonical_categories("demo_ship_a")
    assert count_connects["n"] == 2


def test_cl_s11_list_project_ids_sorted():
    """CL-S11: list_project_ids() returns all known project_ids, sorted."""
    result = category_lookup.list_project_ids()
    assert result == ["demo_ship_a", "demo_ship_b"]


def test_cl_s12_repeated_list_project_ids_hits_cache(count_connects):
    """CL-S12: second list_project_ids() call is a cache hit."""
    first = category_lookup.list_project_ids()
    second = category_lookup.list_project_ids()
    assert first == second
    assert count_connects["n"] == 1


def test_cl_s13_clear_cache_resets_project_ids_too(count_connects):
    """CL-S13: clear_cache() also resets the project_ids cache."""
    category_lookup.list_project_ids()
    category_lookup.clear_cache()
    category_lookup.list_project_ids()
    assert count_connects["n"] == 2
