from __future__ import annotations

import logging
import time

from . import category_lookup
from .schemas import (
    CategoryAccuracy,
    ComplianceCheck,
    ComplianceInput,
    ComplianceResult,
    D1AccuracyDecision,
    E4VotingResult,
    GroundTruth,
)

logger = logging.getLogger(__name__)


# ─── D2 · Ranking · Compliance Verdict Decision ──────────────────────────────

_REGULATION_SET = "SOLAS 2020 + FSS Code 2015 (illustrative)"


def d2_check_compliance(inputs: ComplianceInput) -> ComplianceResult:
    if not inputs.total_by_category:
        raise ValueError("ComplianceInput.total_by_category is empty — cannot evaluate compliance.")
    if not inputs.regulation_set:
        raise ValueError("ComplianceInput.regulation_set is empty.")

    counts = inputs.total_by_category
    counts_snapshot = dict(counts)
    space = inputs.space_type

    def _count(*cats: str) -> int:
        return sum(counts.get(c, 0) for c in cats)

    checks: list[ComplianceCheck] = []

    # R01 — CO₂ ≥ 1
    co2 = _count("extinguisher_CO2_5kg")
    checks.append(ComplianceCheck(
        rule_id="R01",
        article="SOLAS II-2/Reg.10.3",
        description="Portable CO₂ extinguisher required (≥1 per plan)",
        status="pass" if co2 >= 1 else "fail",
        required="≥ 1",
        found=str(co2),
        verdict="GO" if co2 >= 1 else "NO_GO",
        is_mock_rule=True,
    ))

    # R02 — Dry powder ≥ 2
    dp = _count("extinguisher_dry_powder_6kg")
    checks.append(ComplianceCheck(
        rule_id="R02",
        article="SOLAS II-2/Reg.10.3",
        description="Dry powder extinguisher required (≥2 per plan)",
        status="pass" if dp >= 2 else "fail",
        required="≥ 2",
        found=str(dp),
        verdict="GO" if dp >= 2 else "NO_GO",
        is_mock_rule=True,
    ))

    # R03 — Foam ≥ 1 (only when space_type="accommodation"; else not_applicable)
    foam = _count("extinguisher_foam_9L")
    if space == "accommodation":
        r03_status = "pass" if foam >= 1 else "warning"
        r03_verdict = "GO" if foam >= 1 else "CONDITIONAL"
    else:
        r03_status = "not_applicable"
        r03_verdict = "N/A"
    checks.append(ComplianceCheck(
        rule_id="R03",
        article="FSS Code Ch.6/2.1",
        description="Foam extinguisher required in accommodation spaces (≥1)",
        status=r03_status,
        required="≥ 1" if space == "accommodation" else None,
        found=str(foam) if space == "accommodation" else None,
        verdict=r03_verdict,
        is_mock_rule=True,
    ))

    # R04 — Total ≥ 4
    total = _count(
        "extinguisher_CO2_5kg", "extinguisher_dry_powder_6kg", "extinguisher_foam_9L",
        "extinguisher_CO2_5kg_spare", "extinguisher_dry_powder_6kg_spare", "extinguisher_foam_9L_spare",
    )
    checks.append(ComplianceCheck(
        rule_id="R04",
        article="SOLAS II-2/Reg.10.3",
        description="Total portable extinguishers adequate (≥4 per plan)",
        status="pass" if total >= 4 else "fail",
        required="≥ 4",
        found=str(total),
        verdict="GO" if total >= 4 else "NO_GO",
        is_mock_rule=True,
    ))

    # R05 — Spare CO₂ required when CO₂ count ≥ 2
    co2_spare = _count("extinguisher_CO2_5kg_spare")
    if co2 >= 2:
        r05_status = "pass" if co2_spare >= 1 else "warning"
        r05_verdict = "GO" if co2_spare >= 1 else "CONDITIONAL"
        r05_found = str(co2_spare)
    else:
        r05_status = "not_applicable"
        r05_verdict = "N/A"
        r05_found = None
    checks.append(ComplianceCheck(
        rule_id="R05",
        article="FSS Code Ch.6/2.2",
        description="Spare CO₂ required when CO₂ count ≥ 2",
        status=r05_status,
        required="≥ 1 spare" if co2 >= 2 else None,
        found=r05_found,
        verdict=r05_verdict,
        is_mock_rule=True,
    ))

    # Aggregate verdict: any fail → NO_GO; any warning → CONDITIONAL; else GO
    statuses = {c.status for c in checks}
    if "fail" in statuses:
        overall = "NO_GO"
    elif "warning" in statuses:
        overall = "CONDITIONAL"
    else:
        overall = "GO"

    result = ComplianceResult(
        overall_verdict=overall,
        checks=checks,
        regulation_set=inputs.regulation_set,
        is_mock=inputs.is_mock,
        counts_snapshot=counts_snapshot,
    )
    logger.info({"node": "D2", "status": "success", "overall_verdict": overall})
    return result


# ─── D1 · Matching · Accuracy Evaluator ─────────────────────────────────────


def d1_evaluate_accuracy(
    voting: E4VotingResult,
    ground_truth: GroundTruth,
) -> D1AccuracyDecision:
    start = time.time()

    try:
        expected = category_lookup.get_canonical_categories(ground_truth.project_id)

        provided_voting = set(voting.votes.keys())
        if provided_voting != expected:
            missing = expected - provided_voting
            extra = provided_voting - expected
            raise ValueError(
                f"voting.votes has invalid keys. Missing: {missing!r}. Extra: {extra!r}."
            )

        provided_gt = set(ground_truth.counts.keys())
        if provided_gt != expected:
            missing = expected - provided_gt
            extra = provided_gt - expected
            raise ValueError(
                f"ground_truth.counts has invalid keys. Missing: {missing!r}. Extra: {extra!r}."
            )

        for cat, vote in voting.votes.items():
            if vote.category != cat:
                raise ValueError(
                    f"vote.category mismatch: key {cat!r} but vote.category={vote.category!r}."
                )
            if vote.n_runs != len(vote.all_counts):
                raise ValueError(
                    f"vote.n_runs={vote.n_runs} does not match"
                    f" len(all_counts)={len(vote.all_counts)} for category {cat!r}."
                )

        lengths = {cat: len(v.all_counts) for cat, v in voting.votes.items()}
        if len(set(lengths.values())) > 1:
            raise ValueError(f"Inconsistent all_counts lengths across categories: {lengths!r}.")
        n_runs = next(iter(set(lengths.values())))
        if n_runs == 0:
            raise ValueError("all_counts is empty for all categories — invalid run history.")

        n_total = len(expected)
        per_category: list[CategoryAccuracy] = []
        n_correct = 0

        for cat in expected:
            vote = voting.votes[cat]
            gt_count = ground_truth.counts[cat]
            voted_count = vote.voted_count
            correct = voted_count is not None and voted_count == gt_count
            if correct:
                n_correct += 1
            per_category.append(
                CategoryAccuracy(
                    category=cat,
                    ground_truth=gt_count,
                    voted_count=voted_count,
                    correct=correct,
                    vote_status=vote.status,
                )
            )

        majority_vote_accuracy_pct = n_correct / n_total * 100.0

        run_accuracies = [
            sum(
                1
                for cat in expected
                if voting.votes[cat].all_counts[i] == ground_truth.counts[cat]
            )
            / n_total
            for i in range(n_runs)
        ]
        single_run_accuracy_avg_pct = sum(run_accuracies) / n_runs * 100.0

        accuracy_gain_pct = majority_vote_accuracy_pct - single_run_accuracy_avg_pct
        image_level_exact_match = n_correct == n_total

        n_accepted = sum(1 for v in voting.votes.values() if v.status == "ACCEPTED")
        auto_accept_rate = n_accepted / n_total

        accepted_correct = sum(
            1
            for acc in per_category
            if voting.votes[acc.category].status == "ACCEPTED" and acc.correct
        )
        accuracy_on_auto_accepted_pct = (
            accepted_correct / n_accepted * 100.0 if n_accepted > 0 else 0.0
        )

        n_manual = sum(1 for v in voting.votes.values() if v.status == "MANUAL_REVIEW_REQUIRED")
        manual_review_rate = n_manual / n_total

        if n_correct == n_total:
            decision, reason, rule_triggered = (
                "PASS",
                f"All {n_total} categories match ground truth.",
                "PASS_ALL",
            )
        elif n_correct == 0:
            decision, reason, rule_triggered = (
                "FAIL",
                "No category matches ground truth.",
                "FAIL_NONE",
            )
        else:
            decision, reason, rule_triggered = (
                "PARTIAL",
                f"{n_correct} of {n_total} categories match ground truth.",
                "PARTIAL",
            )

        inputs_snapshot = {
            "voting": voting.model_dump(),
            "ground_truth": ground_truth.model_dump(),
        }

        result = D1AccuracyDecision(
            per_category=per_category,
            n_correct=n_correct,
            n_total=n_total,
            majority_vote_accuracy_pct=majority_vote_accuracy_pct,
            single_run_accuracy_avg_pct=single_run_accuracy_avg_pct,
            accuracy_gain_pct=accuracy_gain_pct,
            image_level_exact_match=image_level_exact_match,
            auto_accept_rate=auto_accept_rate,
            accuracy_on_auto_accepted_pct=accuracy_on_auto_accepted_pct,
            manual_review_rate=manual_review_rate,
            decision=decision,
            reason=reason,
            rule_triggered=rule_triggered,
            inputs_snapshot=inputs_snapshot,
        )
        logger.info(
            {
                "node": "D1",
                "status": "success",
                "n_correct": n_correct,
                "n_total": n_total,
                "decision": decision,
                "majority_vote_accuracy_pct": majority_vote_accuracy_pct,
                "accuracy_gain_pct": accuracy_gain_pct,
                "duration_ms": round((time.time() - start) * 1000),
            }
        )
        return result

    except Exception as e:
        logger.error(
            {
                "node": "D1",
                "status": "error",
                "error": str(e),
                "duration_ms": round((time.time() - start) * 1000),
            }
        )
        raise
