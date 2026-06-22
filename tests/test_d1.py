"""
L2 Node Unit Tests for d1_evaluate_accuracy (D1 · Decide · Accuracy Evaluator).

Contract Test Scenario List: D1-S01 through D1-S16 (design_backend.md §7.10).

Verifies that D1:
- Computes PASS/PARTIAL/FAIL correctly (D1-S01 to D1-S04).
- Computes accuracy_gain_pct sign correctly (D1-S05, D1-S06).
- Computes auto_accept_rate correctly (D1-S07).
- Returns 0.0 for accuracy_on_auto_accepted_pct when no ACCEPTED categories (D1-S08).
- Includes inputs_snapshot with required keys (D1-S09).
- Returns per_category with 6 entries covering all canonical categories (D1-S10).
- Treats voted_count=None (tie) as incorrect (D1-S11).
- Validates voting.votes and ground_truth.counts for canonical completeness (D1-S12 to D1-S14).
- Computes single_run_accuracy_avg_pct from all_counts (D1-S15).
- Raises ValueError on inconsistent all_counts lengths (D1-S16).

Out of scope:
- Does not test E1, E2, E3, or E4 logic.
- Does not test pipeline orchestration.
- Does not test E5 report generation.
"""

from __future__ import annotations

from collections import Counter

import pytest

from src.backend.d_nodes import d1_evaluate_accuracy
from src.backend.schemas import (
    CANONICAL_CATEGORIES,
    CANONICAL_CATEGORY_SET,
    VOTE_THRESHOLD_ACCEPT,
    VOTE_THRESHOLD_WARN,
    CategoryVote,
    E4VotingResult,
    GroundTruth,
)

_CATS = list(CANONICAL_CATEGORIES)


def _make_vote(
    cat: str,
    voted_count: int | None,
    all_counts: list[int],
    status: str,
    is_tie: bool = False,
    tied_candidates: list[int] | None = None,
    vote_mode: str = "voting",
) -> CategoryVote:
    n_runs = len(all_counts)
    counter = Counter(all_counts)
    majority_freq = counter.most_common(1)[0][1] if all_counts else 0
    ratio = majority_freq / n_runs if n_runs > 0 else 0.0
    return CategoryVote(
        category=cat,
        voted_count=voted_count,
        all_counts=all_counts,
        majority_freq=majority_freq,
        n_runs=n_runs,
        ratio=ratio,
        is_tie=is_tie,
        tied_candidates=tied_candidates,
        vote_mode=vote_mode,
        status=status,
        threshold_accept=VOTE_THRESHOLD_ACCEPT,
        threshold_warn=VOTE_THRESHOLD_WARN,
    )


def _uniform_voting(
    overrides: dict[str, int] | None = None,
    n_runs: int = 5,
    status: str = "ACCEPTED",
) -> E4VotingResult:
    """All runs agree; overrides sets voted_count (and all_counts) for specific categories."""
    votes = {}
    for cat in CANONICAL_CATEGORIES:
        count = (overrides or {}).get(cat, 0)
        votes[cat] = _make_vote(cat, voted_count=count, all_counts=[count] * n_runs, status=status)
    return E4VotingResult(votes=votes)


def _gt(overrides: dict[str, int] | None = None) -> GroundTruth:
    return GroundTruth(counts={**{cat: 0 for cat in CANONICAL_CATEGORIES}, **(overrides or {})})


# ─── D1-S01 to D1-S04: PASS / PARTIAL / FAIL ─────────────────────────────────


def test_d1_s01_all_correct_pass() -> None:
    result = d1_evaluate_accuracy(_uniform_voting(), _gt())
    assert result.decision == "PASS"
    assert result.n_correct == 6
    assert result.majority_vote_accuracy_pct == pytest.approx(100.0)
    assert result.image_level_exact_match is True


def test_d1_s02_five_correct_partial() -> None:
    result = d1_evaluate_accuracy(_uniform_voting({"extinguisher_CO2_5kg": 99}), _gt())
    assert result.decision == "PARTIAL"
    assert result.n_correct == 5
    assert result.image_level_exact_match is False


def test_d1_s03_one_correct_partial() -> None:
    result = d1_evaluate_accuracy(_uniform_voting({cat: 99 for cat in _CATS[:-1]}), _gt())
    assert result.decision == "PARTIAL"
    assert result.n_correct == 1
    assert result.image_level_exact_match is False


def test_d1_s04_all_wrong_fail() -> None:
    result = d1_evaluate_accuracy(_uniform_voting({cat: 99 for cat in _CATS}), _gt())
    assert result.decision == "FAIL"
    assert result.n_correct == 0
    assert result.majority_vote_accuracy_pct == pytest.approx(0.0)
    assert result.image_level_exact_match is False


# ─── D1-S05, D1-S06: accuracy_gain_pct sign ──────────────────────────────────


def test_d1_s05_accuracy_gain_positive() -> None:
    # Cat 5: majority votes 0 (correct), but 2 out of 5 runs were wrong
    # Other cats always correct → majority better than per-run average
    cat5 = _CATS[-1]
    votes = {cat: _make_vote(cat, 0, [0, 0, 0, 0, 0], "ACCEPTED") for cat in _CATS[:-1]}
    votes[cat5] = _make_vote(cat5, 0, [1, 2, 0, 0, 0], "ACCEPTED_WITH_WARNING")
    result = d1_evaluate_accuracy(E4VotingResult(votes=votes), _gt())
    assert result.accuracy_gain_pct > 0
    assert result.majority_vote_accuracy_pct > result.single_run_accuracy_avg_pct


def test_d1_s06_accuracy_gain_negative() -> None:
    # Cat 5: majority votes 1 (wrong), but 2 out of 5 runs happened to be correct (count=0)
    # Other cats always correct → majority worse than per-run average
    cat5 = _CATS[-1]
    votes = {cat: _make_vote(cat, 0, [0, 0, 0, 0, 0], "ACCEPTED") for cat in _CATS[:-1]}
    votes[cat5] = _make_vote(cat5, 1, [1, 1, 1, 0, 0], "ACCEPTED_WITH_WARNING")
    result = d1_evaluate_accuracy(E4VotingResult(votes=votes), _gt())
    assert result.accuracy_gain_pct < 0
    assert result.majority_vote_accuracy_pct < result.single_run_accuracy_avg_pct


# ─── D1-S07: auto_accept_rate ─────────────────────────────────────────────────


def test_d1_s07_auto_accept_rate_correct() -> None:
    votes = {}
    for i, cat in enumerate(_CATS):
        if i < 4:
            status = "ACCEPTED"
        elif i == 4:
            status = "ACCEPTED_WITH_WARNING"
        else:
            status = "MANUAL_REVIEW_REQUIRED"
        votes[cat] = _make_vote(cat, 0, [0, 0, 0, 0, 0], status)
    result = d1_evaluate_accuracy(E4VotingResult(votes=votes), _gt())
    assert result.auto_accept_rate == pytest.approx(4 / 6)


# ─── D1-S08: accuracy_on_auto_accepted_pct = 0.0 when no ACCEPTED ─────────────


def test_d1_s08_accuracy_on_auto_accepted_zero_when_no_accepted() -> None:
    votes = {cat: _make_vote(cat, 0, [0, 0, 0, 0, 0], "MANUAL_REVIEW_REQUIRED") for cat in _CATS}
    result = d1_evaluate_accuracy(E4VotingResult(votes=votes), _gt())
    assert result.accuracy_on_auto_accepted_pct == pytest.approx(0.0)


# ─── D1-S09: inputs_snapshot keys ────────────────────────────────────────────


def test_d1_s09_inputs_snapshot_contains_voting_and_ground_truth() -> None:
    result = d1_evaluate_accuracy(_uniform_voting(), _gt())
    assert "voting" in result.inputs_snapshot
    assert "ground_truth" in result.inputs_snapshot


# ─── D1-S10: per_category coverage ───────────────────────────────────────────


def test_d1_s10_per_category_has_six_entries_covering_all_canonical() -> None:
    result = d1_evaluate_accuracy(_uniform_voting(), _gt())
    assert len(result.per_category) == 6
    assert {a.category for a in result.per_category} == CANONICAL_CATEGORY_SET


# ─── D1-S11: voted_count=None (tie) → incorrect ──────────────────────────────


def test_d1_s11_tie_voted_count_none_is_incorrect() -> None:
    cat_tie = _CATS[0]
    votes = {cat: _make_vote(cat, 0, [0, 0, 0, 0, 0], "ACCEPTED") for cat in _CATS[1:]}
    votes[cat_tie] = _make_vote(
        cat_tie,
        voted_count=None,
        all_counts=[1, 2, 1, 2, 3],
        status="MANUAL_REVIEW_REQUIRED",
        is_tie=True,
        tied_candidates=[1, 2],
    )
    result = d1_evaluate_accuracy(E4VotingResult(votes=votes), _gt())
    assert result.n_correct == 5
    assert result.image_level_exact_match is False
    tie_acc = next(a for a in result.per_category if a.category == cat_tie)
    assert tie_acc.voted_count is None
    assert tie_acc.correct is False


# ─── D1-S12 to D1-S14: input validation ──────────────────────────────────────


def test_d1_s12_voting_missing_canonical_key_raises() -> None:
    votes = {cat: _make_vote(cat, 0, [0] * 5, "ACCEPTED") for cat in _CATS[1:]}
    with pytest.raises(ValueError):
        d1_evaluate_accuracy(E4VotingResult(votes=votes), _gt())


def test_d1_s13_ground_truth_missing_canonical_key_raises() -> None:
    bad_gt = GroundTruth.model_construct(counts={cat: 0 for cat in _CATS[1:]})
    with pytest.raises(ValueError):
        d1_evaluate_accuracy(_uniform_voting(), bad_gt)


def test_d1_s14_voting_non_canonical_key_raises() -> None:
    votes = {cat: _make_vote(cat, 0, [0] * 5, "ACCEPTED") for cat in _CATS}
    votes["extinguisher_halon_6kg"] = _make_vote("extinguisher_halon_6kg", 0, [0] * 5, "ACCEPTED")
    with pytest.raises(ValueError):
        d1_evaluate_accuracy(E4VotingResult(votes=votes), _gt())


# ─── D1-S15: single_run_accuracy_avg_pct from all_counts ─────────────────────


def test_d1_s15_single_run_accuracy_avg_pct_correct() -> None:
    # GT all zeros, n_runs=3
    # Cat 0-4: all_counts=[0,0,0] → always correct
    # Cat 5: all_counts=[1,0,0] → run 0 wrong, runs 1-2 correct
    # Per run: run0=5/6, run1=6/6, run2=6/6
    cat5 = _CATS[-1]
    votes = {cat: _make_vote(cat, 0, [0, 0, 0], "ACCEPTED") for cat in _CATS[:-1]}
    votes[cat5] = _make_vote(cat5, 0, [1, 0, 0], "ACCEPTED_WITH_WARNING")
    result = d1_evaluate_accuracy(E4VotingResult(votes=votes), _gt())
    expected = (5 / 6 + 6 / 6 + 6 / 6) / 3 * 100.0
    assert result.single_run_accuracy_avg_pct == pytest.approx(expected, rel=1e-4)


# ─── D1-S16: inconsistent all_counts length → ValueError ─────────────────────


def test_d1_s16_inconsistent_all_counts_length_raises() -> None:
    votes = {}
    for i, cat in enumerate(_CATS):
        n = 4 if i == 0 else 5
        votes[cat] = _make_vote(cat, 0, [0] * n, "ACCEPTED")
    with pytest.raises(ValueError):
        d1_evaluate_accuracy(E4VotingResult(votes=votes), _gt())


# ─── D1-S17, D1-S18: empty all_counts, category key mismatch ─────────────────


def test_d1_s17_empty_all_counts_raises() -> None:
    votes = {cat: _make_vote(cat, 0, [], "ACCEPTED") for cat in _CATS}
    with pytest.raises(ValueError):
        d1_evaluate_accuracy(E4VotingResult(votes=votes), _gt())


def test_d1_s18_vote_category_mismatch_raises() -> None:
    votes = {cat: _make_vote(cat, 0, [0] * 5, "ACCEPTED") for cat in _CATS}
    wrong_cat = _CATS[1]
    votes[_CATS[0]] = _make_vote(wrong_cat, 0, [0] * 5, "ACCEPTED")
    with pytest.raises(ValueError):
        d1_evaluate_accuracy(E4VotingResult(votes=votes), _gt())


# ─── D1-S19: vote.n_runs mismatch → ValueError ────────────────────────────────


def test_d1_s19_vote_n_runs_mismatch_raises() -> None:
    votes = {cat: _make_vote(cat, 0, [0] * 5, "ACCEPTED") for cat in _CATS}
    v = votes[_CATS[0]]
    # Force n_runs to disagree with len(all_counts)
    votes[_CATS[0]] = CategoryVote(
        category=_CATS[0],
        voted_count=v.voted_count,
        all_counts=v.all_counts,
        majority_freq=v.majority_freq,
        n_runs=99,
        ratio=v.ratio,
        is_tie=v.is_tie,
        status=v.status,
        threshold_accept=v.threshold_accept,
        threshold_warn=v.threshold_warn,
    )
    with pytest.raises(ValueError):
        d1_evaluate_accuracy(E4VotingResult(votes=votes), _gt())


# ─── D1-S20: ground_truth extra non-canonical key → ValueError ────────────────


def test_d1_s20_ground_truth_extra_non_canonical_key_raises() -> None:
    bad_gt = GroundTruth.model_construct(
        counts={**{cat: 0 for cat in _CATS}, "extinguisher_halon_6kg": 0}
    )
    with pytest.raises(ValueError):
        d1_evaluate_accuracy(_uniform_voting(), bad_gt)
