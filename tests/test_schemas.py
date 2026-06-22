"""
L1 Schema / Contract Tests for schemas.py.

Verifies Pydantic model constraints, field types, and validators are correct.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.backend.schemas import (
    CANONICAL_CATEGORIES,
    CANONICAL_CATEGORY_SET,
    VOTE_THRESHOLD_ACCEPT,
    VOTE_THRESHOLD_WARN,
    BackendEvalResult,
    CategoryVote,
    E3CountResult,
    GroundTruth,
    PipelineContext,
)

# ─── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture
def all_zero_counts() -> dict[str, int]:
    return {cat: 0 for cat in CANONICAL_CATEGORIES}


# ─── GroundTruth ──────────────────────────────────────────────────────────────


class TestGroundTruth:
    def test_valid_all_six_categories_accepted(self, all_zero_counts):
        gt = GroundTruth(counts=all_zero_counts)
        assert set(gt.counts.keys()) == CANONICAL_CATEGORY_SET

    def test_non_zero_counts_accepted(self, all_zero_counts):
        counts = {**all_zero_counts, "extinguisher_CO2_5kg": 3}
        gt = GroundTruth(counts=counts)
        assert gt.counts["extinguisher_CO2_5kg"] == 3

    def test_missing_one_category_raises(self, all_zero_counts):
        counts = dict(all_zero_counts)
        del counts["extinguisher_CO2_5kg"]
        with pytest.raises(ValidationError, match="Missing"):
            GroundTruth(counts=counts)

    def test_missing_spare_category_raises(self, all_zero_counts):
        counts = dict(all_zero_counts)
        del counts["extinguisher_foam_9L_spare"]
        with pytest.raises(ValidationError, match="Missing"):
            GroundTruth(counts=counts)

    def test_extra_non_canonical_category_raises(self, all_zero_counts):
        counts = {**all_zero_counts, "extinguisher_halon_6kg": 0}
        with pytest.raises(ValidationError, match="Extra"):
            GroundTruth(counts=counts)

    def test_unknown_key_not_allowed(self, all_zero_counts):
        counts = {**all_zero_counts, "unknown": 0}
        with pytest.raises(ValidationError):
            GroundTruth(counts=counts)

    def test_image_id_optional_defaults_none(self, all_zero_counts):
        gt = GroundTruth(counts=all_zero_counts)
        assert gt.image_id is None

    def test_image_id_stored_when_provided(self, all_zero_counts):
        gt = GroundTruth(counts=all_zero_counts, image_id="B_deck")
        assert gt.image_id == "B_deck"


# ─── E3CountResult ────────────────────────────────────────────────────────────


class TestE3CountResult:
    def test_total_by_category_and_run_id_stored(self, all_zero_counts):
        result = E3CountResult(total_by_category=all_zero_counts, run_id=2)
        assert result.run_id == 2
        assert result.total_by_category["extinguisher_CO2_5kg"] == 0

    def test_non_zero_counts_stored(self, all_zero_counts):
        counts = {**all_zero_counts, "extinguisher_dry_powder_6kg": 4}
        result = E3CountResult(total_by_category=counts, run_id=0)
        assert result.total_by_category["extinguisher_dry_powder_6kg"] == 4


# ─── CategoryVote ─────────────────────────────────────────────────────────────


class TestCategoryVote:
    def _make_vote(self, **overrides) -> CategoryVote:
        base = {
            "category": "extinguisher_CO2_5kg",
            "voted_count": 3,
            "all_counts": [3, 3, 3, 3, 3],
            "majority_freq": 5,
            "n_runs": 5,
            "ratio": 1.0,
            "is_tie": False,
            "status": "ACCEPTED",
        }
        return CategoryVote(**{**base, **overrides})

    def test_accepted_when_ratio_at_threshold(self):
        vote = self._make_vote(ratio=VOTE_THRESHOLD_ACCEPT, status="ACCEPTED")
        assert vote.status == "ACCEPTED"

    def test_warning_when_ratio_at_lower_threshold(self):
        vote = self._make_vote(majority_freq=3, ratio=VOTE_THRESHOLD_WARN, status="ACCEPTED_WITH_WARNING")
        assert vote.status == "ACCEPTED_WITH_WARNING"

    def test_manual_review_when_below_threshold(self):
        vote = self._make_vote(majority_freq=2, ratio=0.40, status="MANUAL_REVIEW_REQUIRED")
        assert vote.status == "MANUAL_REVIEW_REQUIRED"

    def test_is_tie_field_present_and_stored(self):
        vote = self._make_vote(is_tie=True, status="MANUAL_REVIEW_REQUIRED")
        assert vote.is_tie is True

    def test_is_tie_false_by_default_in_clear_majority(self):
        vote = self._make_vote()
        assert vote.is_tie is False

    def test_threshold_constants_recorded_in_vote(self):
        vote = self._make_vote()
        assert vote.threshold_accept == VOTE_THRESHOLD_ACCEPT
        assert vote.threshold_warn == VOTE_THRESHOLD_WARN

    def test_all_counts_stored_verbatim(self):
        counts = [3, 3, 4, 3, 3]
        vote = self._make_vote(all_counts=counts)
        assert vote.all_counts == counts


# ─── PipelineContext ──────────────────────────────────────────────────────────


class TestPipelineContext:
    @pytest.fixture
    def base_ctx(self, all_zero_counts) -> PipelineContext:
        return PipelineContext(
            image_path="data/images/B_deck.png",
            prompt_label="short",
            n_runs=5,
            ground_truth=GroundTruth(counts=all_zero_counts),
        )

    def test_session_id_auto_generated_as_uuid(self, base_ctx):
        assert len(base_ctx.session_id) == 36
        assert base_ctx.session_id.count("-") == 4

    def test_two_contexts_have_distinct_session_ids(self, all_zero_counts):
        gt = GroundTruth(counts=all_zero_counts)
        ctx1 = PipelineContext(image_path="a.png", prompt_label="s", n_runs=3, ground_truth=gt)
        ctx2 = PipelineContext(image_path="a.png", prompt_label="s", n_runs=3, ground_truth=gt)
        assert ctx1.session_id != ctx2.session_id

    def test_completed_nodes_starts_empty(self, base_ctx):
        assert base_ctx.completed_nodes == []

    def test_errors_starts_empty(self, base_ctx):
        assert base_ctx.errors == []

    def test_default_report_mode_is_full(self, base_ctx):
        assert base_ctx.report_mode == "full"

    def test_local_and_cloud_eval_default_none(self, base_ctx):
        assert base_ctx.local_eval is None
        assert base_ctx.cloud_eval is None


# ─── BackendEvalResult ────────────────────────────────────────────────────────


class TestBackendEvalResult:
    def test_failed_status_stores_error_message(self):
        result = BackendEvalResult(
            backend="cloud",
            api_model_id="gpt-x",
            status="failed",
            error_message="ConnectionError: timed out",
        )
        assert result.status == "failed"
        assert result.error_message == "ConnectionError: timed out"

    def test_failed_backend_runs_defaults_to_empty_list(self):
        result = BackendEvalResult(backend="local", api_model_id="llava", status="failed")
        assert result.runs == []

    def test_failed_backend_voting_and_accuracy_default_none(self):
        result = BackendEvalResult(backend="cloud", api_model_id="gpt-x", status="failed")
        assert result.voting is None
        assert result.accuracy is None

    def test_success_status_accepted(self):
        result = BackendEvalResult(backend="local", api_model_id="llava", status="success")
        assert result.status == "success"
