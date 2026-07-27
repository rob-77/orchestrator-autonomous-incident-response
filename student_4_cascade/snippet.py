"""
student_4_cascade/snippet.py

Student 4: Worker C - Downstream Cascade Failure Guardrail

This module validates Actor output before the state is allowed to reach
downstream reporting or additional application layers.
"""

import os
import sys
from typing import Any

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from contract import AgentState, ValidationResult


SUCCESS_STATUS = "SUCCESS"
ALLOWED_SAFETY_LEVELS = {"SAFE", "SENSITIVE"}


def _is_non_empty_string(value: Any) -> bool:
    """Return True only when value is a non-empty string."""
    return isinstance(value, str) and bool(value.strip())


def validate_downstream_state_guardrail(
    state: AgentState,
) -> ValidationResult:
    """
    Validate the state produced by Worker B before downstream processing.

    The guardrail checks both structural and semantic invariants:

    1. The analysis payload contains a valid service ID.
    2. The analysis payload contains a requested action.
    3. At least one execution record exists.
    4. The execution record contains all required fields.
    5. The execution status is SUCCESS.
    6. The executed tool matches the Analyzer recommendation.
    7. The tool appears in the sanitized tool-call list.
    8. The executed service matches the analyzed service.
    9. The execution output is a non-empty string.
    10. The execution safety level is recognized.

    Any invariant violation produces a rejected ValidationResult and
    requires a safe mocked rollback.
    """
    invariant_errors: list[str] = []

    # ------------------------------------------------------------------
    # Invariants for Worker A analysis output
    # ------------------------------------------------------------------
    analysis = state.analysis_payload
    expected_service_id: Any = None
    expected_action: Any = None

    if not isinstance(analysis, dict):
        invariant_errors.append(
            "Invariant Error: analysis_payload must be a dictionary."
        )
    else:
        expected_service_id = analysis.get("service_id")
        expected_action = analysis.get("recommended_action")

        if not _is_non_empty_string(expected_service_id):
            invariant_errors.append(
                "Invariant Error: Missing or invalid service_id "
                "in analysis payload."
            )

        if not _is_non_empty_string(expected_action):
            invariant_errors.append(
                "Invariant Error: Missing or invalid recommended_action "
                "in analysis payload."
            )

    # ------------------------------------------------------------------
    # Invariants for Worker B execution output
    # ------------------------------------------------------------------
    executed_tools = state.executed_tools

    if not isinstance(executed_tools, list) or not executed_tools:
        invariant_errors.append(
            "Invariant Error: Executed tools array is empty or invalid."
        )
    else:
        last_action = executed_tools[-1]

        if not isinstance(last_action, dict):
            invariant_errors.append(
                "Invariant Error: Last execution record must be a dictionary."
            )
        else:
            required_fields = {
                "tool",
                "status",
                "executed_params",
                "safety_level",
                "output",
            }

            missing_fields = sorted(
                field
                for field in required_fields
                if field not in last_action
            )

            if missing_fields:
                invariant_errors.append(
                    "Invariant Error: Execution record is missing required "
                    f"fields: {', '.join(missing_fields)}."
                )

            executed_tool = last_action.get("tool")
            execution_status = last_action.get("status")
            executed_params = last_action.get("executed_params")
            safety_level = last_action.get("safety_level")
            execution_output = last_action.get("output")

            if not _is_non_empty_string(executed_tool):
                invariant_errors.append(
                    "Invariant Error: Executed tool name is missing or invalid."
                )

            if execution_status != SUCCESS_STATUS:
                invariant_errors.append(
                    "Invariant Error: Last action status is "
                    f"'{execution_status}', expected '{SUCCESS_STATUS}'."
                )

            if (
                _is_non_empty_string(expected_action)
                and _is_non_empty_string(executed_tool)
                and executed_tool != expected_action
            ):
                invariant_errors.append(
                    "Invariant Error: Executed tool does not match the "
                    f"recommended action. Expected '{expected_action}', "
                    f"received '{executed_tool}'."
                )

            if (
                _is_non_empty_string(expected_action)
                and expected_action not in state.sanitized_tool_calls
            ):
                invariant_errors.append(
                    "Invariant Error: Recommended action is absent from "
                    "sanitized_tool_calls."
                )

            if not isinstance(executed_params, dict):
                invariant_errors.append(
                    "Invariant Error: executed_params must be a dictionary."
                )
            elif (
                _is_non_empty_string(expected_service_id)
                and executed_params.get("service_id")
                != expected_service_id
            ):
                invariant_errors.append(
                    "Invariant Error: Executed service does not match the "
                    f"analyzed service. Expected '{expected_service_id}', "
                    f"received '{executed_params.get('service_id')}'."
                )

            if not _is_non_empty_string(execution_output):
                invariant_errors.append(
                    "Invariant Error: Execution output is missing or invalid."
                )

            if safety_level not in ALLOWED_SAFETY_LEVELS:
                invariant_errors.append(
                    "Invariant Error: Unrecognized safety level "
                    f"'{safety_level}'."
                )

    # ------------------------------------------------------------------
    # Rejection or approval result
    # ------------------------------------------------------------------
    if invariant_errors:
        return ValidationResult(
            is_valid=False,
            health_check_passed=False,
            invariant_errors=invariant_errors,
            rollback_required=True,
        )

    return ValidationResult(
        is_valid=True,
        health_check_passed=True,
        invariant_errors=[],
        rollback_required=False,
    )