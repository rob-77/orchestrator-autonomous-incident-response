from contract import AgentState

MAX_ROUNDS = 5

def coordinator(state: AgentState) -> str:
    # Increment the loop counter every time the coordinator runs
    state.round_number += 1

    # ===== Loop Guardrail (YOUR ASSIGNMENT) =====
    if state.round_number >= MAX_ROUNDS:
        state.error_log.append(
            f"Loop guardrail activated after {MAX_ROUNDS} rounds."
        )
        return "reporter"   # Route to the reporter instead of looping again

    # ===== Routing Logic =====
    if not state.analysis_payload:
        return "analyzer"

    if not state.tool_calls:
        return "actor"

    if not state.validated:
        return "validator"

    return "reporter"