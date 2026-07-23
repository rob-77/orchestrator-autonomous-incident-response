"""
student_3_rogue/snippet.py
Student 3: Worker B - Rogue Tool Execution Guardrail
"""

from typing import Dict, Any, List
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from contract import ToolExecutionRequest


class InvalidToolCallException(Exception):
    """Custom exception thrown when a tool request breaches permission matrix."""
    pass


# PERMISSION LOOKUP MATRIX
TOOL_PERMISSION_MATRIX = {
    "restart_service": ["service_id", "delay_sec"],
    "flush_cache": ["service_id", "cache_tier"],
    "apply_hotfix": ["service_id", "patch_version"],
    "fetch_metrics": ["service_id"]
}

FORBIDDEN_TOOLS = ["delete_database", "drop_tables", "unauthorized_shell_exec", "wipe_disk"]


def validate_tool_execution_guardrail(tool_name: str, parameters: Dict[str, Any]) -> ToolExecutionRequest:
    """
    PROGRAMMATIC GUARDRAIL (Student 3):
    Dynamic tool runtime execution middleware. Intercepts proposed tool calls
    and validates them against a strict lookup configuration matrix.
    Throws InvalidToolCallException if tool or parameters breach authorization boundaries.
    """
    if tool_name in FORBIDDEN_TOOLS:
        raise InvalidToolCallException(
            f"SECURITY GUARDRAIL INTERCEPT: Forbidden rogue tool '{tool_name}' execution BLOCKED!"
        )

    if tool_name not in TOOL_PERMISSION_MATRIX:
        raise InvalidToolCallException(
            f"SECURITY GUARDRAIL INTERCEPT: Tool '{tool_name}' is not in approved execution whitelist."
        )

    allowed_params = TOOL_PERMISSION_MATRIX[tool_name]
    for param_name in parameters:
        if param_name not in allowed_params:
            raise InvalidToolCallException(
                f"SECURITY GUARDRAIL INTERCEPT: Unauthorized parameter '{param_name}' for tool '{tool_name}'."
            )

    return ToolExecutionRequest(
        tool_name=tool_name,
        parameters=parameters,
        safety_level="SAFE"
    )
