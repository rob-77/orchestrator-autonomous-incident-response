"""
student_1_loop/snippet.py
Student 1: Coordinator Node - Infinite Graph Loops Guardrail
"""

from typing import Dict, Any
import sys
import os

# Add parent directory to path to import contract
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from contract import AgentState


def coordinator_route_guardrail(state: AgentState, max_allowed_rounds: int = 5) -> str:
    """
    PROGRAMMATIC GUARDRAIL (Student 1):
    Enforces a strict, deterministic round counter check directly in the routing edge logic.
    If round_number >= max_allowed_rounds, short-circuits execution and forces graceful routing
    to the final output/reporter node.
    """
    if state.round_number >= max_allowed_rounds:
        print(f"[GUARDRAIL ACTIVATED] Round limit reached ({state.round_number}/{max_allowed_rounds}). Short-circuiting loop flow.")
        return "reporter"
    
    # Standard routing logic
    if state.system_status == "ANALYZING":
        return "analyzer"
    elif state.system_status == "PATCHING":
        return "actor"
    elif state.system_status == "VALIDATING":
        return "validator"
    return "reporter"
