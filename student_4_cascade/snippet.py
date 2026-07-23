"""
student_4_cascade/snippet.py
Student 4: Worker C - Downstream Cascade Failure Guardrail
"""

from typing import Dict, Any, List
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from contract import AgentState, ValidationResult


def validate_downstream_state_guardrail(state: AgentState) -> ValidationResult:
    """
    PROGRAMMATIC GUARDRAIL (Student 4):
    Validation/Sanitization node positioned between Worker B (Actor) and downstream code.
    Evaluates incoming state against explicit invariant assertions. If structural
    invariants fail, triggers a rollback routine and sets rejection flag.
    """
    executed_tools = state.executed_tools
    invariant_errors = []

    # Assertion 1: Tool execution list must exist and contain at least one tool
    if not executed_tools:
        invariant_errors.append("Invariant Error: Executed tools array is empty.")
    else:
        last_action = executed_tools[-1]
        # Assertion 2: Tool execution status must be SUCCESS
        if last_action.get("status") != "SUCCESS":
            invariant_errors.append(f"Invariant Error: Last action status is '{last_action.get('status')}'.")

    # Assertion 3: Verify target service matches analysis payload
    target_service = state.analysis_payload.get("service_id")
    if not target_service:
        invariant_errors.append("Invariant Error: Missing target service_id in analysis payload.")

    if invariant_errors:
        return ValidationResult(
            is_valid=False,
            health_check_passed=False,
            invariant_errors=invariant_errors,
            rollback_required=True
        )

    return ValidationResult(
        is_valid=True,
        health_check_passed=True,
        invariant_errors=[],
        rollback_required=False
    )
