"""
student_4_cascade/test_failure.py
Reproduction script for Student 4: Downstream Cascade Failure vs Guardrail
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from contract import AgentState
from student_4_cascade.snippet import validate_downstream_state_guardrail


def run_simulation(enable_guardrail: bool):
    print(f"\n==================================================")
    print(f"  RUNNING CASCADE FAILURE SIMULATION (Guardrail: {enable_guardrail})")
    print(f"==================================================")

    # Corrupted state payload with failed execution status
    corrupted_state = AgentState(
        raw_input="CASCADE_FAIL prompt",
        analysis_payload={"service_id": "auth-service-v2"},
        executed_tools=[{"tool": "apply_hotfix", "status": "FAILED_500", "error": "Internal Error"}]
    )

    if not enable_guardrail:
        # UNGUARDRAILED FLOW: Passes bad state data directly into downstream reporting code
        print("Passing unvalidated state directly to downstream reporter...")
        try:
            # Downstream code assumes status is SUCCESS and performs metric string formatting
            last_tool = corrupted_state.executed_tools[-1]
            output_msg = "SUCCESSFUL_PATCH:" + last_tool["output_hash"] # Missing key -> Crash
            print(f"Downstream Output: {output_msg}")
        except KeyError as exc:
            print(f"\n[FAILURE DEMONSTRATION]: Downstream Cascade Crash Occurred!")
            print(f"CRASH LOG: KeyError: {exc}. Corrupted state propagated into downstream layer.")

    else:
        # GUARDRAILED FLOW: Evaluates state invariants through Worker C before routing
        print("Evaluating state invariants through Worker C Validator...")
        val_result = validate_downstream_state_guardrail(corrupted_state)

        if not val_result.is_valid:
            print(f"\nSUCCESSFUL GUARDRAIL INTERCEPT: Invariants Failed!")
            print(f"Errors Caught: {val_result.invariant_errors}")
            print(f"Rollback Triggered: {val_result.rollback_required}")
            print("Action: Safe mock rollback executed. State statefully isolated without crashing downstream code.")


if __name__ == "__main__":
    print("--- 1. Testing Failure Mode (Guardrail DISABLED) ---")
    run_simulation(enable_guardrail=False)

    print("\n--- 2. Testing Guardrail Mitigated Execution (Guardrail ENABLED) ---")
    run_simulation(enable_guardrail=True)
