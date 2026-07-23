"""
student_1_loop/test_failure.py
Reproduction script for Student 1: Infinite Graph Loop Failure Mode vs Guardrail
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from contract import AgentState
from student_1_loop.snippet import coordinator_route_guardrail


def run_simulation(enable_guardrail: bool):
    print(f"\n==================================================")
    print(f"  RUNNING LOOP SIMULATION (Guardrail Enabled: {enable_guardrail})")
    print(f"==================================================")

    state = AgentState(
        raw_input="ALERT: Unstable cluster state causing non-terminating retry loops.",
        system_status="ANALYZING"
    )

    iterations = 0
    max_test_steps = 20 # Artificial hard stop for unguardrailed test

    while True:
        iterations += 1
        state.round_number += 1
        print(f"Step {iterations}: Round = {state.round_number}, Status = {state.system_status}")

        if enable_guardrail:
            next_node = coordinator_route_guardrail(state, max_allowed_rounds=5)
        else:
            # UNGUARDRAILED NAIVE ROUTING: Continuously loops back to analyzer
            next_node = "analyzer"

        print(f" -> Routed to: {next_node}")

        if next_node == "reporter":
            print(f"\nSUCCESSFUL TERMINATION: Graph safely routed to reporter after {state.round_number} rounds.")
            break

        if not enable_guardrail and iterations >= max_test_steps:
            print(f"\n[FAILURE DEMONSTRATION]: Infinite graph loop detected! Executed {iterations} rounds without terminating.")
            print(f"Estimated Token Cost Wasted: ${iterations * 0.22:.2f}")
            break


if __name__ == "__main__":
    print("--- 1. Testing Failure Mode (Guardrail DISABLED) ---")
    run_simulation(enable_guardrail=False)

    print("\n--- 2. Testing Guardrail Mitigated Execution (Guardrail ENABLED) ---")
    run_simulation(enable_guardrail=True)
