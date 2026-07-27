"""
student_4_cascade/test_failure.py

Student 4: Deterministic reproduction of downstream cascade failures.

The script compares:
1. An unguarded flow that allows corrupted Actor state into downstream code.
2. A guarded flow that validates state invariants and triggers safe rollback.
"""

from __future__ import annotations

import os
import sys
from typing import Any

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from contract import AgentState
from student_4_cascade.snippet import (
    validate_downstream_state_guardrail,
)


def build_state(
    *,
    execution_status: str = "SUCCESS",
    executed_tool: str = "apply_hotfix",
    analyzed_service: str = "auth-service-v2",
    executed_service: str = "auth-service-v2",
    safety_level: str = "SENSITIVE",
    include_recommended_action: bool = True,
    include_executed_params: bool = True,
    include_output: bool = True,
    include_sanitized_call: bool = True,
    include_execution_record: bool = True,
) -> AgentState:
    """Create deterministic valid or corrupted graph states."""

    analysis_payload: dict[str, Any] = {
        "service_id": analyzed_service,
        "error_code": "ERR_MEM_LEAK_503",
        "root_cause": "Connection pool exhaustion",
        "target_component": analyzed_service,
        "confidence_score": 0.95,
    }

    if include_recommended_action:
        analysis_payload["recommended_action"] = "apply_hotfix"

    execution_record: dict[str, Any] = {
        "tool": executed_tool,
        "status": execution_status,
        "safety_level": safety_level,
    }

    if include_executed_params:
        execution_record["executed_params"] = {
            "service_id": executed_service,
            "patch_version": "v2.4.1",
        }

    if include_output:
        execution_record["output"] = (
            "SAFE MOCK EXECUTION: Patch operation completed."
        )

    executed_tools = (
        [execution_record]
        if include_execution_record
        else []
    )

    sanitized_tool_calls = (
        ["apply_hotfix"]
        if include_sanitized_call
        else []
    )

    return AgentState(
        raw_input="CASCADE_FAIL deterministic validation scenario",
        analysis_payload=analysis_payload,
        sanitized_tool_calls=sanitized_tool_calls,
        executed_tools=executed_tools,
        system_status="VALIDATING",
    )


def unsafe_downstream_consumer(state: AgentState) -> str:
    """
    Simulate unsafe downstream application code.

    This function assumes that Actor output is valid and accesses fields
    without checking status, authorization, tool consistency, or service
    consistency. Corrupted state may therefore crash or silently propagate.
    """

    last_tool = state.executed_tools[-1]

    return (
        f"Resolved service "
        f"{last_tool['executed_params']['service_id']} "
        f"using {last_tool['tool']}: "
        f"{last_tool['output']}"
    )


def build_test_scenarios() -> list[tuple[str, AgentState, bool]]:
    """
    Return scenario name, state, and expected validation decision.

    expected_valid=True means the Validator should approve the state.
    expected_valid=False means the Validator must reject the state.
    """

    return [
        (
            "Valid Actor execution",
            build_state(),
            True,
        ),
        (
            "Failed tool execution status",
            build_state(execution_status="FAILED_500"),
            False,
        ),
        (
            "Missing execution output",
            build_state(include_output=False),
            False,
        ),
        (
            "Missing executed parameters",
            build_state(include_executed_params=False),
            False,
        ),
        (
            "Executed tool differs from recommendation",
            build_state(executed_tool="restart_service"),
            False,
        ),
        (
            "Execution targets the wrong service",
            build_state(executed_service="payment-service-prod"),
            False,
        ),
        (
            "Tool absent from sanitized calls",
            build_state(include_sanitized_call=False),
            False,
        ),
        (
            "Invalid destructive safety level",
            build_state(safety_level="DESTRUCTIVE"),
            False,
        ),
        (
            "Empty execution history",
            build_state(include_execution_record=False),
            False,
        ),
        (
            "Missing recommended action",
            build_state(include_recommended_action=False),
            False,
        ),
    ]


def run_unguarded_baseline(
    scenarios: list[tuple[str, AgentState, bool]],
) -> dict[str, int]:
    """Run invalid states directly through unsafe downstream code."""

    print("\n" + "=" * 70)
    print("BASELINE: GUARDRAIL DISABLED")
    print("=" * 70)

    invalid_states_reaching_downstream = 0
    downstream_crashes = 0
    silent_corruptions = 0

    for name, state, expected_valid in scenarios:
        if expected_valid:
            continue

        invalid_states_reaching_downstream += 1

        try:
            result = unsafe_downstream_consumer(state)
            silent_corruptions += 1
            print(f"[UNSAFE PASS] {name}")
            print(f"  Corrupted result reached downstream: {result}")
        except (KeyError, IndexError, TypeError) as exc:
            downstream_crashes += 1
            print(f"[CASCADE CRASH] {name}")
            print(f"  {type(exc).__name__}: {exc}")

    return {
        "invalid_total": invalid_states_reaching_downstream,
        "invalid_reached_downstream": invalid_states_reaching_downstream,
        "downstream_crashes": downstream_crashes,
        "silent_corruptions": silent_corruptions,
    }


def run_guarded_validation(
    scenarios: list[tuple[str, AgentState, bool]],
) -> dict[str, int]:
    """Run all states through the Student 4 Validator guardrail."""

    print("\n" + "=" * 70)
    print("OPTIMIZED: GUARDRAIL ENABLED")
    print("=" * 70)

    valid_total = 0
    valid_accepted = 0
    invalid_total = 0
    invalid_blocked = 0
    false_positives = 0
    false_negatives = 0
    rollback_count = 0

    for name, state, expected_valid in scenarios:
        validation = validate_downstream_state_guardrail(state)

        decision_correct = validation.is_valid == expected_valid
        result_label = "PASS" if decision_correct else "FAIL"

        print(
            f"[{result_label}] {name}: "
            f"is_valid={validation.is_valid}, "
            f"rollback_required={validation.rollback_required}"
        )

        if validation.invariant_errors:
            for error in validation.invariant_errors:
                print(f"  - {error}")

        if expected_valid:
            valid_total += 1

            if validation.is_valid:
                valid_accepted += 1
            else:
                false_positives += 1
        else:
            invalid_total += 1

            if validation.is_valid:
                false_negatives += 1
            else:
                invalid_blocked += 1

            if validation.rollback_required:
                rollback_count += 1

    return {
        "valid_total": valid_total,
        "valid_accepted": valid_accepted,
        "invalid_total": invalid_total,
        "invalid_blocked": invalid_blocked,
        "false_positives": false_positives,
        "false_negatives": false_negatives,
        "rollback_count": rollback_count,
    }


def print_metrics(
    baseline: dict[str, int],
    guarded: dict[str, int],
) -> None:
    """Print deterministic before-and-after guardrail metrics."""

    total_cases = guarded["valid_total"] + guarded["invalid_total"]
    correct_decisions = (
        guarded["valid_accepted"]
        + guarded["invalid_blocked"]
    )

    validation_accuracy = (
        correct_decisions / total_cases * 100
        if total_cases
        else 0.0
    )

    valid_pass_rate = (
        guarded["valid_accepted"]
        / guarded["valid_total"]
        * 100
        if guarded["valid_total"]
        else 0.0
    )

    invalid_block_rate = (
        guarded["invalid_blocked"]
        / guarded["invalid_total"]
        * 100
        if guarded["invalid_total"]
        else 0.0
    )

    baseline_admission_rate = (
        baseline["invalid_reached_downstream"]
        / baseline["invalid_total"]
        * 100
        if baseline["invalid_total"]
        else 0.0
    )

    print("\n" + "=" * 70)
    print("STUDENT 4 QUANTITATIVE METRICS")
    print("=" * 70)

    print(
        "Invalid states reaching downstream: "
        f"{baseline['invalid_reached_downstream']}/"
        f"{baseline['invalid_total']} "
        f"({baseline_admission_rate:.1f}%) -> 0/"
        f"{guarded['invalid_total']} (0.0%)"
    )

    print(
        "Downstream runtime crashes: "
        f"{baseline['downstream_crashes']} -> 0"
    )

    print(
        "Silent corrupted-state propagations: "
        f"{baseline['silent_corruptions']} -> 0"
    )

    print(
        "Invalid states blocked by guardrail: "
        f"{guarded['invalid_blocked']}/"
        f"{guarded['invalid_total']} "
        f"({invalid_block_rate:.1f}%)"
    )

    print(
        "Valid-state pass rate: "
        f"{guarded['valid_accepted']}/"
        f"{guarded['valid_total']} "
        f"({valid_pass_rate:.1f}%)"
    )

    print(
        f"False negatives: {guarded['false_negatives']}"
    )

    print(
        f"False positives: {guarded['false_positives']}"
    )

    print(
        "Safe mock rollbacks triggered: "
        f"{guarded['rollback_count']}"
    )

    print(
        f"Overall validation accuracy: {validation_accuracy:.1f}%"
    )

    print("=" * 70)

    assert guarded["false_negatives"] == 0
    assert guarded["false_positives"] == 0
    assert guarded["invalid_blocked"] == guarded["invalid_total"]
    assert guarded["valid_accepted"] == guarded["valid_total"]


def main() -> None:
    """Execute failure reproduction and guardrail comparison."""

    scenarios = build_test_scenarios()

    baseline_metrics = run_unguarded_baseline(scenarios)
    guarded_metrics = run_guarded_validation(scenarios)

    print_metrics(
        baseline=baseline_metrics,
        guarded=guarded_metrics,
    )

    print(
        "\nAll Student 4 deterministic guardrail assertions passed."
    )


if __name__ == "__main__":
    main()