"""
student_3_rogue/snippet.py
Student 3: Worker B (Actor) - Rogue Tool Execution Guardrail

Programmatic tool-execution middleware. Intercepts every proposed tool call
BEFORE execution and validates it against a strict permission matrix. Raises
InvalidToolCallException if the tool is forbidden, unknown, missing required
arguments, or carries an out-of-range argument value.

Runs standalone (self-tests at bottom): python student_3_rogue/test_failure.py
Wires into the graph via validate_tool_execution_guardrail (name kept for
main_system.py compatibility).
"""

from typing import Dict, Any
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from contract import ToolExecutionRequest


class InvalidToolCallException(Exception):
    """Raised when a tool request breaches the permission matrix."""
    pass


# --- PERMISSION MATRIX -------------------------------------------------------
# Tool names match the frozen contract's IncidentAnalysis.recommended_action
# vocabulary (restart_service, flush_cache, apply_hotfix). Each tool declares
# its required args AND value-level rules so the guardrail checks not just
# "is this arg allowed" but "is this VALUE safe."
PERMISSION_MATRIX: Dict[str, Dict[str, Any]] = {
    "restart_service": {
        "required_args": {"service_id"},
        "optional_args": {"delay_sec"},
        "max_delay_sec": 300,          # no absurd multi-hour delays
    },
    "flush_cache": {
        "required_args": {"service_id"},
        "optional_args": {"cache_tier"},
        "allowed_cache_tier": {"L1", "L2", "edge"},
    },
    "apply_hotfix": {
        "required_args": {"service_id", "patch_version"},
        "optional_args": set(),
    },
    "fetch_metrics": {
        "required_args": {"service_id"},
        "optional_args": set(),
    },
}

# Explicit blacklist: destructive tools that must NEVER run, even if some
# upstream bug adds them to the matrix. Checked first, fail-closed.
FORBIDDEN_TOOLS = {"delete_database", "drop_tables", "wipe_disk",
                   "unauthorized_shell_exec"}


def validate_tool_execution_guardrail(tool_name: str,
                                      parameters: Dict[str, Any]
                                      ) -> ToolExecutionRequest:
    """
    Inspect ONE tool call before it executes.
    Returns a validated ToolExecutionRequest if allowed.
    Raises InvalidToolCallException on any violation.
    """
    # Rule 1: hard blacklist (fail-closed on known-destructive tools)
    if tool_name in FORBIDDEN_TOOLS:
        raise InvalidToolCallException(
            f"GUARDRAIL INTERCEPT: forbidden tool '{tool_name}' BLOCKED."
        )

    # Rule 2: tool must be on the whitelist
    if tool_name not in PERMISSION_MATRIX:
        raise InvalidToolCallException(
            f"GUARDRAIL INTERCEPT: tool '{tool_name}' not in approved whitelist."
        )

    rules = PERMISSION_MATRIX[tool_name]
    allowed = rules["required_args"] | rules.get("optional_args", set())

    # Rule 3: no unexpected arguments
    for arg in parameters:
        if arg not in allowed:
            raise InvalidToolCallException(
                f"GUARDRAIL INTERCEPT: unauthorized arg '{arg}' for '{tool_name}'."
            )

    # Rule 4: all required arguments present
    missing = rules["required_args"] - set(parameters.keys())
    if missing:
        raise InvalidToolCallException(
            f"GUARDRAIL INTERCEPT: '{tool_name}' missing required args {missing}."
        )

    # Rule 5: tool-specific VALUE checks (the argument-level validation)
    if tool_name == "restart_service" and "delay_sec" in parameters:
        delay = parameters["delay_sec"]
        if not isinstance(delay, int) or delay < 0 or delay > rules["max_delay_sec"]:
            raise InvalidToolCallException(
                f"GUARDRAIL INTERCEPT: delay_sec {delay} out of range "
                f"(0..{rules['max_delay_sec']})."
            )

    if tool_name == "flush_cache" and "cache_tier" in parameters:
        tier = parameters["cache_tier"]
        if tier not in rules["allowed_cache_tier"]:
            raise InvalidToolCallException(
                f"GUARDRAIL INTERCEPT: cache_tier '{tier}' not allowed."
            )

    return ToolExecutionRequest(
        tool_name=tool_name,
        parameters=parameters,
        safety_level="SAFE",
    )
