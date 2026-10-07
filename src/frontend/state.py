from __future__ import annotations

from typing import NamedTuple


StateTransitionResult = NamedTuple(
    "StateTransitionResult",
    [("next_state", str), ("session_state_patch", dict)],
)


def resolve_next_state(
    current_state: str,
    event: str,
    guard_result: dict,
) -> StateTransitionResult:
    if current_state == "IDLE":
        if event == "analyze_clicked":
            if guard_result.get("image_path") is not None:
                return StateTransitionResult(
                    next_state="RUNNING",
                    session_state_patch={
                        "stage": "RUNNING",
                        "job_status": "running",
                        "last_error": None,
                    },
                )
            else:
                return StateTransitionResult(next_state="IDLE", session_state_patch={})

    elif current_state == "RUNNING":
        if event == "pipeline_complete":
            return StateTransitionResult(
                next_state="RESULTS",
                session_state_patch={
                    "stage": "RESULTS",
                    "job_status": "success",
                    "results_vm": guard_result.get("results_vm"),
                    "selected_category": None,
                    "selected_instance_id": None,
                },
            )
        if event == "pipeline_error":
            return StateTransitionResult(
                next_state="IDLE",
                session_state_patch={
                    "stage": "IDLE",
                    "job_status": "error",
                    "last_error": guard_result.get("error_msg"),
                    "results_vm": None,
                },
            )

    elif current_state == "RESULTS":
        if event == "new_analysis_clicked":
            return StateTransitionResult(
                next_state="IDLE",
                session_state_patch={
                    "stage": "IDLE",
                    "job_status": "none",
                    "results_vm": None,
                    "selected_category": None,
                    "selected_instance_id": None,
                    "last_error": None,
                },
            )
        if event == "category_clicked":
            return StateTransitionResult(
                next_state="RESULTS",
                session_state_patch={
                    "selected_category": guard_result.get("category"),
                    "selected_instance_id": None,
                },
            )
        if event == "instance_clicked":
            return StateTransitionResult(
                next_state="RESULTS",
                session_state_patch={
                    "selected_instance_id": guard_result.get("instance_id"),
                    "selected_category": None,
                },
            )
        if event == "show_all_clicked":
            return StateTransitionResult(
                next_state="RESULTS",
                session_state_patch={
                    "selected_category": None,
                    "selected_instance_id": None,
                },
            )

    raise ValueError(
        f"Unrecognised (state, event) combination: ({current_state!r}, {event!r})"
    )
