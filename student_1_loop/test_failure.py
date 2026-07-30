"""
student_1_loop/test_failure.py
Reproduction script for Student 1: Infinite Graph Loop Failure Mode vs Guardrail
"""

import sys
import os
import time
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from contract import AgentState
from student_1_loop.snippet import coordinator_route_guardrail

# Simulated per-round API token cost, used only to illustrate cumulative waste
COST_PER_ROUND = 0.22


def run_simulation(enable_guardrail: bool):
    print(f"\n==================================================")
    print(f"  RUNNING LOOP SIMULATION (Guardrail Enabled: {enable_guardrail})")
    print(f"==================================================")

    state = AgentState(
        raw_input="ALERT: Unstable cluster state causing non-terminating retry loops.",
        system_status="ANALYZING"
    )

    iterations = 0
    max_test_steps = 20  # Artificial hard stop for unguardrailed test, so the demo terminates

    start_time = time.perf_counter()

    while True:
        iterations += 1
        state.round_number += 1
        print(f"Step {iterations}: Round = {state.round_number}, Status = {state.system_status}")

        # Simulate per-round processing time (LLM call + tool round trip)
        time.sleep(0.06)

        if enable_guardrail:
            next_node = coordinator_route_guardrail(state, max_allowed_rounds=5)
        else:
            # UNGUARDRAILED NAIVE ROUTING: Continuously loops back to analyzer
            next_node = "analyzer"

        print(f" -> Routed to: {next_node}")

        if next_node == "reporter":
            elapsed = time.perf_counter() - start_time
            print(f"\nSUCCESSFUL TERMINATION: Graph safely routed to reporter after {state.round_number} rounds.")
            print(f"Final system_status: {state.system_status}")
            print(f"Measured wall-clock latency: {elapsed:.2f}s")
            return {
                "rounds": state.round_number,
                "latency_s": elapsed,
                "token_cost": state.round_number * COST_PER_ROUND,
                "terminated": True,
            }

        if not enable_guardrail and iterations >= max_test_steps:
            elapsed = time.perf_counter() - start_time
            print(f"\n[FAILURE DEMONSTRATION]: Infinite graph loop detected! "
                  f"Executed {iterations} rounds without terminating.")
            print(f"Estimated Token Cost Wasted: ${iterations * COST_PER_ROUND:.2f}")
            print(f"Measured wall-clock latency before artificial cutoff: {elapsed:.2f}s")
            return {
                "rounds": iterations,
                "latency_s": elapsed,
                "token_cost": iterations * COST_PER_ROUND,
                "terminated": False,
            }


if __name__ == "__main__":
    print("--- 1. Testing Failure Mode (Guardrail DISABLED) ---")
    unguarded = run_simulation(enable_guardrail=False)

    print("\n--- 2. Testing Guardrail Mitigated Execution (Guardrail ENABLED) ---")
    guarded = run_simulation(enable_guardrail=True)

    print("\n==================================================")
    print("  SUMMARY: BASELINE vs GUARDRAILED")
    print("==================================================")
    print(f"{'Metric':<28}{'Guardrail Disabled':<22}{'Guardrail Enabled':<20}")
    print(f"{'Rounds executed':<28}{unguarded['rounds']:<22}{guarded['rounds']:<20}")
    print(f"{'Terminated cleanly':<28}{str(unguarded['terminated']):<22}{str(guarded['terminated']):<20}")
    print(f"{'Wall-clock latency (s)':<28}{unguarded['latency_s']:<22.2f}{guarded['latency_s']:<20.2f}")
    print(f"{'Est. token cost ($)':<28}{unguarded['token_cost']:<22.2f}{guarded['token_cost']:<20.2f}")
