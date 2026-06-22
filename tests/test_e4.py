"""
L2 Node Unit Tests for e4_vote_per_category (E4 · Select · Per-category Majority Voter).

Contract Test Scenario List: E4-S01 through E4-S15 (design_backend.md §7.10).

Verifies that E4:
- Applies ratio gate correctly at threshold boundaries (E4-S01 to E4-S04).
- Detects ties and forces MANUAL_REVIEW_REQUIRED (E4-S05, E4-S15).
- Returns all six canonical categories in output (E4-S06).
- Records voted_count, majority_freq, all_counts, and audit thresholds correctly (E4-S07, E4-S08).
- Forces ACCEPTED_WITH_WARNING + vote_mode="single_run" when n_runs=1 (E4-S09).
- Votes each category independently (E4-S10).
- Validates inputs: n_runs=0, run count mismatch, missing/extra canonical keys (E4-S11 to E4-S14).
- Produces voted_count=None and tied_candidates list on tie (E4-S15).

Out of scope:
- Does not test E1, E2, or E3 logic.
- Does not test D1 accuracy evaluation or downstream nodes.
- Does not test pipeline orchestration.
"""

from __future__ import annotations

import pytest

from src.backend.e_nodes import e4_vote_per_category
from src.backend.schemas import (
    CANONICAL_CATEGORIES,
    CANONICAL_CATEGORY_SET,
    VOTE_THRESHOLD_ACCEPT,
    VOTE_THRESHOLD_WARN,
    E3CountResult,
)

_ZERO = {cat: 0 for cat in CANONICAL_CATEGORIES}
_CAT = "extinguisher_CO2_5kg"  # default single-category used for most tests


def _run(cat_counts: dict[str, int] | None = None, run_id: int = 0) -> E3CountResult:
    return E3CountResult(
        total_by_category={**_ZERO, **(cat_counts or {})},
        excluded_boundary_cut_count=0,
        excluded_unclear_count=0,
        unknown_count=0,
        run_id=run_id,
    )


def _runs_for(category: str, counts: list[int]) -> list[E3CountResult]:
    """One E3CountResult per entry in counts; only the given category varies."""
    return [_run({category: c}, run_id=i) for i, c in enumerate(counts)]


# ─── E4-S01 to E4-S05: ratio gate and tie detection ──────────────────────────


def test_e4_s01_unanimous_accepted() -> None:
    runs = _runs_for(_CAT, [3, 3, 3, 3])
    result = e4_vote_per_category(runs, n_runs=4)
    vote = result.votes[_CAT]
    assert vote.ratio == pytest.approx(1.0)
    assert vote.status == "ACCEPTED"
    assert vote.is_tie is False
    assert vote.voted_count == 3
    assert vote.vote_mode == "voting"


def test_e4_s02_boundary_at_accept_threshold() -> None:
    # ratio lands exactly on VOTE_THRESHOLD_ACCEPT
    runs = _runs_for(_CAT, [3, 3, 3, 2])
    result = e4_vote_per_category(runs, n_runs=4)
    vote = result.votes[_CAT]
    assert vote.ratio == pytest.approx(VOTE_THRESHOLD_ACCEPT)
    assert vote.status == "ACCEPTED"
    assert vote.is_tie is False


def test_e4_s03_boundary_at_warn_threshold() -> None:
    # Counter {3:2, 2:1, 4:1} — ratio lands exactly on VOTE_THRESHOLD_WARN, no tie
    runs = _runs_for(_CAT, [3, 3, 2, 4])
    result = e4_vote_per_category(runs, n_runs=4)
    vote = result.votes[_CAT]
    assert vote.ratio == pytest.approx(VOTE_THRESHOLD_WARN)
    assert vote.status == "ACCEPTED_WITH_WARNING"
    assert vote.is_tie is False


def test_e4_s04_below_threshold_no_tie_manual_review() -> None:
    # Counter {3:2, others:1 each} — 3 wins with freq=2/8, below VOTE_THRESHOLD_WARN, no tie
    runs = _runs_for(_CAT, [3, 3, 2, 4, 5, 6, 7, 8])
    result = e4_vote_per_category(runs, n_runs=8)
    vote = result.votes[_CAT]
    assert vote.ratio < VOTE_THRESHOLD_WARN
    assert vote.status == "MANUAL_REVIEW_REQUIRED"
    assert vote.is_tie is False
    assert vote.voted_count == 3


def test_e4_s05_tie_forces_manual_review() -> None:
    # Counter {3:2, 4:2} — top-two share freq=2
    runs = _runs_for(_CAT, [3, 4, 3, 4])
    result = e4_vote_per_category(runs, n_runs=4)
    vote = result.votes[_CAT]
    assert vote.is_tie is True
    assert vote.status == "MANUAL_REVIEW_REQUIRED"


# ─── E4-S06: output shape ─────────────────────────────────────────────────────


def test_e4_s06_output_contains_all_six_categories() -> None:
    runs = [_run(run_id=i) for i in range(3)]
    result = e4_vote_per_category(runs, n_runs=3)
    assert set(result.votes.keys()) == CANONICAL_CATEGORY_SET


# ─── E4-S07: field correctness ────────────────────────────────────────────────


def test_e4_s07_voted_count_majority_freq_all_counts_correct() -> None:
    runs = _runs_for(_CAT, [3, 3, 3, 3, 4])
    result = e4_vote_per_category(runs, n_runs=5)
    vote = result.votes[_CAT]
    assert vote.voted_count == 3
    assert vote.majority_freq == 4
    assert sorted(vote.all_counts) == [3, 3, 3, 3, 4]
    assert vote.n_runs == 5


# ─── E4-S08: audit thresholds ─────────────────────────────────────────────────


def test_e4_s08_threshold_constants_in_category_vote() -> None:
    runs = _runs_for(_CAT, [3, 3, 3, 3, 3])
    result = e4_vote_per_category(runs, n_runs=5)
    vote = result.votes[_CAT]
    assert vote.threshold_accept == VOTE_THRESHOLD_ACCEPT
    assert vote.threshold_warn == VOTE_THRESHOLD_WARN


# ─── E4-S09: single run ───────────────────────────────────────────────────────


def test_e4_s09_single_run_forces_accepted_with_warning() -> None:
    runs = _runs_for(_CAT, [2])
    result = e4_vote_per_category(runs, n_runs=1)
    vote = result.votes[_CAT]
    assert vote.vote_mode == "single_run"
    assert vote.status == "ACCEPTED_WITH_WARNING"
    assert vote.is_tie is False
    assert vote.voted_count == 2


# ─── E4-S10: multi-category independence ──────────────────────────────────────


def test_e4_s10_all_six_categories_voted_independently() -> None:
    cat = sorted(CANONICAL_CATEGORIES)
    # Each category gets a distinct distribution so statuses differ
    patterns: dict[str, list[int]] = {
        cat[0]: [3, 3, 3, 3, 3],  # ACCEPTED      well above accept threshold
        cat[1]: [3, 3, 3, 3, 2],  # ACCEPTED      above accept threshold
        cat[2]: [3, 3, 3, 2, 2],  # WARNING       between warn and accept thresholds
        cat[3]: [3, 3, 2, 4, 5],  # MANUAL        below warn threshold, no tie
        cat[4]: [3, 4, 3, 4, 5],  # MANUAL        tie
        cat[5]: [0, 0, 0, 0, 0],  # ACCEPTED      unanimous zero
    }
    runs = [
        E3CountResult(
            total_by_category={c: patterns[c][i] for c in CANONICAL_CATEGORIES},
            excluded_boundary_cut_count=0,
            excluded_unclear_count=0,
            unknown_count=0,
            run_id=i,
        )
        for i in range(5)
    ]
    result = e4_vote_per_category(runs, n_runs=5)
    assert result.votes[cat[0]].status == "ACCEPTED"
    assert result.votes[cat[1]].status == "ACCEPTED"
    assert result.votes[cat[2]].status == "ACCEPTED_WITH_WARNING"
    assert result.votes[cat[3]].status == "MANUAL_REVIEW_REQUIRED"
    assert result.votes[cat[4]].status == "MANUAL_REVIEW_REQUIRED"
    assert result.votes[cat[5]].status == "ACCEPTED"


# ─── E4-S11 to E4-S14: input validation ──────────────────────────────────────


def test_e4_s11_n_runs_zero_raises_value_error() -> None:
    with pytest.raises(ValueError):
        e4_vote_per_category([], n_runs=0)


def test_e4_s12_runs_count_mismatch_raises_value_error() -> None:
    runs = [_run(run_id=i) for i in range(4)]  # 4 runs, n_runs claims 5
    with pytest.raises(ValueError):
        e4_vote_per_category(runs, n_runs=5)


def test_e4_s13_missing_canonical_key_raises_value_error() -> None:
    incomplete = {**_ZERO}
    del incomplete["extinguisher_CO2_5kg"]
    run = E3CountResult(
        total_by_category=incomplete,
        excluded_boundary_cut_count=0,
        excluded_unclear_count=0,
        unknown_count=0,
        run_id=0,
    )
    with pytest.raises(ValueError):
        e4_vote_per_category([run], n_runs=1)


def test_e4_s14_non_canonical_key_raises_value_error() -> None:
    bad = {**_ZERO, "extinguisher_halon_6kg": 1}
    run = E3CountResult(
        total_by_category=bad,
        excluded_boundary_cut_count=0,
        excluded_unclear_count=0,
        unknown_count=0,
        run_id=0,
    )
    with pytest.raises(ValueError):
        e4_vote_per_category([run], n_runs=1)


# ─── E4-S15: tie output contract ──────────────────────────────────────────────


def test_e4_s15_tie_voted_count_none_tied_candidates_listed() -> None:
    # Counter {3:2, 4:2} — tie between 3 and 4
    runs = _runs_for(_CAT, [3, 4, 3, 4])
    result = e4_vote_per_category(runs, n_runs=4)
    vote = result.votes[_CAT]
    assert vote.is_tie is True
    assert vote.voted_count is None
    assert vote.tied_candidates is not None
    assert sorted(vote.tied_candidates) == [3, 4]
    assert vote.majority_freq == 2
    assert vote.status == "MANUAL_REVIEW_REQUIRED"
