"""
main_system.py

Temporary integration for Day 2.

This file connects the Coordinator and all worker nodes
using mock implementations. It will later be replaced
with a LangGraph StateGraph.
"""

from contract import AgentState

from graph.coordinator import coordinator

from workers.analyzer import analyzer
from workers.actor import actor
from workers.validator import validator
from workers.reporter import reporter


def run_system(raw_input: str):

    state = AgentState(
        raw_input=raw_input
    )

    print("=" * 50)
    print("Autonomous Incident Response")
    print("=" * 50)

    while True:

        next_node = coordinator(state)

        print(f"\nCoordinator -> {next_node}")

        if next_node == "analyzer":
            state = analyzer(state)

        elif next_node == "actor":
            state = actor(state)

        elif next_node == "validator":
            state = validator(state)

        elif next_node == "reporter":
            state = reporter(state)
            break

    print("\n========== FINAL STATE ==========")

    print(f"Rounds: {state.round_number}")
    print(f"Validated: {state.validated}")
    print(f"Analysis: {state.analysis_payload}")
    print(f"Tool Calls: {state.tool_calls}")
    print(f"Report: {state.report}")
    print(f"Errors: {state.error_log}")

    return state


if __name__ == "__main__":

    run_system(
        "Production database is down after server update."
    )