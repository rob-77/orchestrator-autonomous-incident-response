"""
Student 1 - Infinite Loop Failure Demonstration

This script demonstrates:
1. Failure WITHOUT the guardrail (infinite loop)
2. Success WITH the guardrail (stops after 5 rounds)

Run this file independently for your assignment demonstration.
"""

from dataclasses import dataclass, field


@dataclass
class AgentState:
    round_number: int = 0
    error_log: list = field(default_factory=list)


# ---------------------------------------------------
# Version 1: Coordinator WITHOUT Guardrail
# ---------------------------------------------------
def coordinator_without_guardrail(state: AgentState):
    state.round_number += 1
    print(f"Round {state.round_number}")

    # Always routes back to itself
    return "coordinator"


# ---------------------------------------------------
# Version 2: Coordinator WITH Guardrail
# ---------------------------------------------------
MAX_ROUNDS = 5


def coordinator_with_guardrail(state: AgentState):
    state.round_number += 1

    print(f"Round {state.round_number}")

    if state.round_number >= MAX_ROUNDS:
        state.error_log.append(
            "Maximum iterations reached."
        )

        print("\nLoop Guardrail Activated!")
        print("Maximum iterations reached.")
        print("Generating partial report...\n")

        return "reporter"

    return "coordinator"


# ---------------------------------------------------
# Failure Demonstration
# ---------------------------------------------------
def demonstrate_failure():
    print("=" * 50)
    print("FAILURE DEMONSTRATION (WITHOUT GUARDRAIL)")
    print("=" * 50)

    state = AgentState()

    # Stop manually after 10 rounds so the demo doesn't
    # actually run forever.
    for _ in range(10):
        coordinator_without_guardrail(state)

    print("\nThe coordinator would continue forever...")
    print("Infinite loop detected.\n")


# ---------------------------------------------------
# Guardrail Demonstration
# ---------------------------------------------------
def demonstrate_guardrail():
    print("=" * 50)
    print("SUCCESS DEMONSTRATION (WITH GUARDRAIL)")
    print("=" * 50)

    state = AgentState()

    while True:
        next_node = coordinator_with_guardrail(state)

        if next_node == "reporter":
            break

    print("Graph exited safely.")
    print("Error Log:", state.error_log)


# ---------------------------------------------------
# Main
# ---------------------------------------------------
if __name__ == "__main__":

    demonstrate_failure()

    print("\n")

    demonstrate_guardrail()