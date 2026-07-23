"""
main_system.py - UNIFIED MULTI-AGENT ORCHESTRATOR GRAPH
Course Assignment: Multi-Agent Failure Modes & Guardrails
Domain: Autonomous Incident Response System
Team Structure: 5 Students (Sections 5 & 6 combined under Student 5)

This script implements the complete production-grade Multi-Agent System using LangGraph.
It incorporates all 5 student code-based guardrails into a single, cohesive state machine.
"""

import os
import re
import json
from typing import Dict, Any, List, Tuple
from pydantic import ValidationError

from contract import (
    AgentState,
    IncidentAnalysis,
    ToolExecutionRequest,
    ValidationResult,
    TelemetryLog
)

# Exception raised by Student 3 Rogue Tool Guardrail
class InvalidToolCallException(Exception):
    """Custom exception raised when a tool call violates security runtime matrix."""
    pass


# ============================================================================
# STUDENT 5 GUARDRAIL COMPONENTS: GLOBAL GRAPH INTERCEPTORS
# (Telemetry Privacy Redaction & Token Context Window Pruner)
# ============================================================================

PII_PATTERNS = [
    (r'(?i)(api[_-]?key|secret|token|password)\s*[:=]\s*["\']?([a-zA-Z0-9_\-\.]{16,})["\']?', r'\1: [REDACTED_SECRET]'),
    (r'bearer\s+[a-zA-Z0-9_\-\.]{16,}', r'Bearer [REDACTED_TOKEN]'),
    (r'\b\d{3}-\d{2}-\d{4}\b', r'[REDACTED_SSN]'),
    (r'postgres://[^:]+:[^@]+@', r'postgres://[REDACTED_CREDS]@'),
    (r'\b(?:1\d{2}|2[0-4]\d|25[0-5]|\d{1,2})\.(?:1\d{2}|2[0-4]\d|25[0-5]|\d{1,2})\.(?:1\d{2}|2[0-4]\d|25[0-5]|\d{1,2})\.(?:1\d{2}|2[0-4]\d|25[0-5]|\d{1,2})\b', r'[REDACTED_IP]')
]

def privacy_redaction_interceptor(raw_text: str) -> Tuple[str, bool, List[str]]:
    """
    Student 5 Guardrail Part 1: Programmatically scrubs secrets, API keys, IP addresses,
    and PII from text payloads before emitting telemetry to external dashboards (LangSmith).
    """
    redacted_text = raw_text
    redacted_keys = []
    contains_pii = False

    for pattern, replacement in PII_PATTERNS:
        matches = re.findall(pattern, redacted_text)
        if matches:
            contains_pii = True
            redacted_keys.append(pattern)
            redacted_text = re.sub(pattern, replacement, redacted_text)

    return redacted_text, contains_pii, redacted_keys


def context_token_pruner_interceptor(messages: List[Dict[str, Any]], max_token_threshold: int = 400) -> List[Dict[str, Any]]:
    """
    Student 5 Guardrail Part 2: Intercepts graph state history right before routing.
    If total estimated token count exceeds max_token_threshold, summarizes past history
    and prunes redundant tool log messages to prevent context window explosion.
    """
    # Rough token estimation (1 token ~ 4 characters)
    total_chars = sum(len(json.dumps(m)) for m in messages)
    estimated_tokens = total_chars // 4

    if estimated_tokens <= max_token_threshold or len(messages) <= 3:
        return messages

    # Keep initial task prompt (index 0) and latest 2 messages, condense middle turns
    system_prompt = messages[0]
    recent_messages = messages[-2:]
    middle_messages = messages[1:-2]

    condensed_summary = {
        "role": "system",
        "content": f"[CONTEXT PRUNED BY STUDENT 5 GUARDRAIL: Condensed {len(middle_messages)} intermediate execution steps to optimize token budget.]"
    }

    return [system_prompt, condensed_summary] + recent_messages


# ============================================================================
# STUDENT 3 GUARDRAIL: TOOL RUNTIME PERMISSION MATRIX
# ============================================================================

ALLOWED_TOOL_PERMISSIONS = {
    "restart_service": {"allowed_params": ["service_id", "delay_sec"], "safety": "SAFE"},
    "flush_cache": {"allowed_params": ["service_id", "cache_tier"], "safety": "SAFE"},
    "apply_hotfix": {"allowed_params": ["service_id", "patch_version"], "safety": "SENSITIVE"},
    "fetch_metrics": {"allowed_params": ["service_id"], "safety": "SAFE"}
}

FORBIDDEN_TOOLS = ["delete_database", "drop_tables", "unauthorized_shell_exec", "wipe_disk"]

def validate_tool_call_security(tool_name: str, params: Dict[str, Any]) -> ToolExecutionRequest:
    """
    Student 3 Guardrail: Validates requested tool calls against security whitelist matrix.
    Throws InvalidToolCallException if tool is blacklisted or params are malformed.
    """
    if tool_name in FORBIDDEN_TOOLS:
        raise InvalidToolCallException(f"CRITICAL SECURITY VIOLATION: Execution of forbidden tool '{tool_name}' BLOCKED!")

    if tool_name not in ALLOWED_TOOL_PERMISSIONS:
        raise InvalidToolCallException(f"UNAUTHORIZED TOOL: Tool '{tool_name}' is not in approved execution matrix.")

    tool_config = ALLOWED_TOOL_PERMISSIONS[tool_name]
    for param_key in params:
        if param_key not in tool_config["allowed_params"]:
            raise InvalidToolCallException(f"UNAUTHORIZED PARAMETER: Parameter '{param_key}' is not allowed for tool '{tool_name}'.")

    return ToolExecutionRequest(
        tool_name=tool_name,
        parameters=params,
        safety_level=tool_config["safety"]
    )


# ============================================================================
# GRAPH NODES
# ============================================================================

def coordinator_node(state: AgentState) -> Dict[str, Any]:
    """
    Node 0: Coordinator Node (Student 1 Owner)
    Evaluates system state and increments round number for deterministic loop prevention.
    """
    current_round = state.round_number + 1
    new_status = state.system_status
    
    # Apply Student 5 Context Token Pruner
    pruned_messages = context_token_pruner_interceptor(state.messages)

    # Telemetry logging with Student 5 Privacy Scrubber
    telemetry_raw = f"Coordinator round {current_round}. Active status: {state.system_status}. Input: {state.raw_input}"
    scrubbed_text, contains_pii, redacted_keys = privacy_redaction_interceptor(telemetry_raw)

    t_log = TelemetryLog(
        span_id=f"span_coord_r{current_round}",
        node_name="Coordinator",
        raw_payload=scrubbed_text,
        contains_pii_redaction=contains_pii,
        redacted_keys=redacted_keys
    )

    return {
        "round_number": current_round,
        "messages": pruned_messages + [{"role": "coordinator", "content": f"Round {current_round} initiated."}],
        "telemetry_logs": state.telemetry_logs + [t_log.model_dump()],
        "system_status": "ANALYZING" if current_round == 1 else new_status
    }


def worker_a_analyzer_node(state: AgentState) -> Dict[str, Any]:
    """
    Node 1: Worker A - Incident Analyzer (Student 2 Owner)
    Parses unstructured incident log into structured IncidentAnalysis.
    Includes Student 2 self-healing retry guardrail for schema parsing failures.
    """
    raw_text = state.raw_input

    # Telemetry scrubber
    scrubbed_log, contains_pii, redacted_keys = privacy_redaction_interceptor(raw_text)

    # Simulated LLM parsing with intentional retry simulation if state.error_log is active
    try:
        # Check if raw_text indicates a bad format or if we are recovering from error
        if "CORRUPTED_PAYLOAD" in raw_text and state.retry_count == 0:
            # Simulate a malformed output to trigger schema validation failure
            raise ValidationError.from_exception_data(
                title="IncidentAnalysis Schema Error",
                line_errors=[]
            )
        
        # Hardcoded simulated analysis extraction based on raw log
        if "503" in raw_text or "MEM_LEAK" in raw_text or "CORRUPTED_PAYLOAD" in raw_text:
            analysis = IncidentAnalysis(
                service_id="auth-service-v2",
                error_code="ERR_MEM_LEAK_503",
                root_cause="Unbounded connection pool causing heap exhaustion on auth-service-v2",
                target_component="auth-service-v2",
                recommended_action="restart_service",
                confidence_score=0.95
            )
        elif "ROGUE_ATTACK" in raw_text:
            analysis = IncidentAnalysis(
                service_id="payment-db-prod",
                error_code="ERR_UNAUTHORIZED_ACCESS",
                root_cause="Adversarial command injection attempt",
                target_component="payment-db-prod",
                recommended_action="delete_database", # Rogue action target
                confidence_score=0.88
            )
        elif "CASCADE_FAIL" in raw_text:
            analysis = IncidentAnalysis(
                service_id="gateway-proxy",
                error_code="ERR_CASCADE_CONFIG",
                root_cause="Malformed proxy state table causing routing loops",
                target_component="gateway-proxy",
                recommended_action="apply_hotfix",
                confidence_score=0.91
            )
        else:
            analysis = IncidentAnalysis(
                service_id="api-gateway",
                error_code="ERR_TIMEOUT_504",
                root_cause="High latency upstream connection pool overload",
                target_component="api-gateway",
                recommended_action="flush_cache",
                confidence_score=0.92
            )

        t_log = TelemetryLog(
            span_id=f"span_analyzer_r{state.round_number}",
            node_name="WorkerA_Analyzer",
            raw_payload=scrubbed_log,
            contains_pii_redaction=contains_pii,
            redacted_keys=redacted_keys
        )

        return {
            "analysis_payload": analysis.model_dump(),
            "error_log": None,
            "system_status": "PATCHING",
            "telemetry_logs": state.telemetry_logs + [t_log.model_dump()],
            "messages": state.messages + [{"role": "analyzer", "content": f"Structured analysis complete for {analysis.service_id}."}]
        }

    except Exception as exc:
        # STUDENT 2 GUARDRAIL: Catch schema error and trigger self-correcting retry
        new_retry = state.retry_count + 1
        return {
            "error_log": f"Schema parsing error: {str(exc)}. Retrying with explicit schema rules.",
            "retry_count": new_retry,
            "system_status": "ANALYZING", # Route back to analyzer
            "messages": state.messages + [{"role": "analyzer", "content": f"Schema validation failed (Attempt {new_retry}/{state.max_retries}). Triggering self-correction."}]
        }


def worker_b_actor_node(state: AgentState) -> Dict[str, Any]:
    """
    Node 2: Worker B - Patch Actor (Student 3 Owner)
    Maps analysis to executable tools through Student 3 Security Middleware.
    """
    analysis = state.analysis_payload
    tool_name = analysis.get("recommended_action", "flush_cache")
    service_id = analysis.get("service_id", "unknown-service")
    
    # Parameters to pass
    params = {"service_id": service_id}
    if tool_name == "restart_service":
        params["delay_sec"] = 5
    elif tool_name == "flush_cache":
        params["cache_tier"] = "redis_l2"
    elif tool_name == "apply_hotfix":
        params["patch_version"] = "v2.4.1"

    # STUDENT 3 GUARDRAIL: Intercept tool call with security middleware
    try:
        validated_request = validate_tool_call_security(tool_name, params)
        
        # MOCK TOOL EXECUTION (Safe Execution)
        mock_output = {
            "tool": validated_request.tool_name,
            "status": "SUCCESS",
            "executed_params": validated_request.parameters,
            "safety_level": validated_request.safety_level,
            "output": f"SAFE MOCK EXECUTION: Executed '{validated_request.tool_name}' on '{service_id}' successfully."
        }

        return {
            "sanitized_tool_calls": state.sanitized_tool_calls + [tool_name],
            "executed_tools": state.executed_tools + [mock_output],
            "system_status": "VALIDATING",
            "messages": state.messages + [{"role": "actor", "content": f"Tool '{tool_name}' executed safely under security whitelist."}]
        }

    except InvalidToolCallException as exc:
        # STUDENT 3 GUARDRAIL: Block rogue tool execution safely
        blocked_record = {
            "tool": tool_name,
            "status": "BLOCKED_BY_GUARDRAIL",
            "error": str(exc),
            "output": f"SECURITY GUARDRAIL TRAPPED ROGUE ACTION: {str(exc)}"
        }

        return {
            "error_log": str(exc),
            "executed_tools": state.executed_tools + [blocked_record],
            "system_status": "FAILED",
            "messages": state.messages + [{"role": "actor", "content": f"ROGUE ACTION BLOCKED: {str(exc)}"}]
        }


def worker_c_validator_node(state: AgentState) -> Dict[str, Any]:
    """
    Node 3: Worker C - Patch Validator (Student 4 Owner)
    Executes programmatic invariant assertions on state prior to reporting.
    Prevents downstream cascade failures through automatic rollback logic.
    """
    analysis = state.analysis_payload
    executed_tools = state.executed_tools

    # STUDENT 4 GUARDRAIL: Invariant assertion checks
    invariant_errors = []

    if not executed_tools:
        invariant_errors.append("Invariant Failure: No tool execution record found in state.")
    else:
        last_tool = executed_tools[-1]
        if last_tool.get("status") != "SUCCESS":
            invariant_errors.append(f"Invariant Failure: Tool execution status is '{last_tool.get('status')}'.")
    
    # Check if cascade failure trigger was set in input prompt
    if "CASCADE_FAIL" in state.raw_input and state.round_number < 2:
        invariant_errors.append("Invariant Failure: Downstream service health check failed post-patch (500 Internal Server Error).")

    if invariant_errors:
        # STUDENT 4 GUARDRAIL: Trigger Rollback Routine
        val_result = ValidationResult(
            is_valid=False,
            health_check_passed=False,
            invariant_errors=invariant_errors,
            rollback_required=True
        )

        rollback_record = {
            "action": "mock_rollback_action",
            "target": analysis.get("service_id", "system"),
            "status": "ROLLBACK_EXECUTED",
            "message": "SAFE MOCK ROLLBACK: Restored service state to pre-patch snapshot."
        }

        return {
            "validation_result": val_result.model_dump(),
            "is_validated": False,
            "executed_tools": state.executed_tools + [rollback_record],
            "error_log": f"Validation failed: {'; '.join(invariant_errors)}. Rollback triggered.",
            "system_status": "ANALYZING", # Route back for self-healing re-triage
            "messages": state.messages + [{"role": "validator", "content": f"Validation invariant failed. Triggered automated rollback."}]
        }

    # Successful validation
    val_result = ValidationResult(
        is_valid=True,
        health_check_passed=True,
        invariant_errors=[],
        rollback_required=False
    )

    return {
        "validation_result": val_result.model_dump(),
        "is_validated": True,
        "system_status": "SUCCESS",
        "messages": state.messages + [{"role": "validator", "content": "All invariant health checks PASSED successfully."}]
    }


def reporter_node(state: AgentState) -> Dict[str, Any]:
    """
    Node 4: Reporter Node (Final Output Generation)
    Compiles final incident report and telemetry summary.
    """
    summary = [
        "==================================================",
        "     AUTONOMOUS INCIDENT RESPONSE SYSTEM REPORT    ",
        "==================================================",
        f"Domain: {state.task_domain}",
        f"Final Status: {state.system_status}",
        f"Execution Rounds: {state.round_number}",
        f"Validated: {state.is_validated}",
        "--------------------------------------------------",
        f"Target Service: {state.analysis_payload.get('service_id', 'N/A')}",
        f"Error Code: {state.analysis_payload.get('error_code', 'N/A')}",
        f"Root Cause: {state.analysis_payload.get('root_cause', 'N/A')}",
        "--------------------------------------------------",
        f"Executed Tools: {[t.get('tool') for t in state.executed_tools]}",
        f"Telemetry Spans Recorded: {len(state.telemetry_logs)}",
        f"Active Guardrail Triggers: {[t.get('span_id') for t in state.telemetry_logs if t.get('contains_pii_redaction')]}",
        "=================================================="
    ]
    report_text = "\n".join(summary)

    return {
        "final_report": report_text,
        "messages": state.messages + [{"role": "reporter", "content": "Final incident summary report generated."}]
    }


# ============================================================================
# CONDITIONAL ROUTING EDGES (STUDENT 1 & GRAPH CONTROL)
# ============================================================================

def route_from_coordinator(state: AgentState) -> str:
    """
    Student 1 Guardrail: Checks round_number limit before routing.
    If round_number >= 5, short-circuits execution loop directly to reporter node.
    """
    if state.round_number >= 5:
        print(f"[STUDENT 1 GUARDRAIL TRIGGERED]: Max round limit (5) breached. Short-circuiting loop to Reporter.")
        return "reporter"

    status = state.system_status
    if status == "ANALYZING":
        return "analyzer"
    elif status == "PATCHING":
        return "actor"
    elif status == "VALIDATING":
        return "validator"
    elif status in ["SUCCESS", "FAILED", "TIMEOUT_SAFEGUARD"]:
        return "reporter"
    else:
        return "analyzer"


def route_from_analyzer(state: AgentState) -> str:
    """Routes from Worker A based on analysis outcome or retry state."""
    if state.error_log and state.retry_count < state.max_retries:
        return "analyzer" # Self-correcting retry
    elif state.system_status == "PATCHING":
        return "actor"
    else:
        return "coordinator"


def route_from_actor(state: AgentState) -> str:
    """Routes from Worker B based on tool execution outcome."""
    if state.system_status == "FAILED":
        return "reporter" # Blocked by rogue guardrail -> report
    return "validator"


def route_from_validator(state: AgentState) -> str:
    """Routes from Worker C based on invariant validation outcome."""
    if not state.is_validated and state.round_number < 5:
        return "coordinator" # Re-route to coordinator for re-triage loop
    return "reporter"


# ============================================================================
# LANGGRAPH STATE MACHINE ASSEMBLY
# ============================================================================

from langgraph.graph import StateGraph, END

def build_orchestrator_graph():
    """Builds and compiles the unified LangGraph state machine."""
    workflow = StateGraph(AgentState)

    # Add Nodes
    workflow.add_node("coordinator", coordinator_node)
    workflow.add_node("analyzer", worker_a_analyzer_node)
    workflow.add_node("actor", worker_b_actor_node)
    workflow.add_node("validator", worker_c_validator_node)
    workflow.add_node("reporter", reporter_node)

    # Set Entry Point
    workflow.set_entry_point("coordinator")

    # Add Conditional Edges
    workflow.add_conditional_edges(
        "coordinator",
        route_from_coordinator,
        {
            "analyzer": "analyzer",
            "actor": "actor",
            "validator": "validator",
            "reporter": "reporter"
        }
    )

    workflow.add_conditional_edges(
        "analyzer",
        route_from_analyzer,
        {
            "analyzer": "analyzer",
            "actor": "actor",
            "coordinator": "coordinator"
        }
    )

    workflow.add_conditional_edges(
        "actor",
        route_from_actor,
        {
            "validator": "validator",
            "reporter": "reporter"
        }
    )

    workflow.add_conditional_edges(
        "validator",
        route_from_validator,
        {
            "coordinator": "coordinator",
            "reporter": "reporter"
        }
    )

    workflow.add_edge("reporter", END)

    return workflow.compile()


# ============================================================================
# MAIN EXECUTION DEMO
# ============================================================================

if __name__ == "__main__":
    print("Initializing Multi-Agent Incident Response Orchestrator...")
    app = build_orchestrator_graph()

    # Sample alert containing PII to test Student 5 Privacy Scrubber
    sample_input = (
        "CRITICAL ALERT on auth-service-v2: High memory usage causing ERR_MEM_LEAK_503. "
        "Server IP: 192.168.1.105, Auth Token: bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.secret12345, "
        "Database: postgres://admin:SuperSecretPassword123@db.internal:5432/prod_db. "
        "Customer SSN logged: 000-12-3456."
    )

    initial_state = AgentState(
        raw_input=sample_input,
        messages=[{"role": "user", "content": sample_input}]
    )

    print("\nExecuting graph flow with sample incident alert...")
    final_output = app.invoke(initial_state)

    print("\n--- FINAL GRAPH REPORT ---")
    print(final_output.get("final_report"))

    print("\n--- TELEMETRY PRIVACY CHECK (STUDENT 5) ---")
    for log in final_output.get("telemetry_logs", []):
        print(f"Span: {log['span_id']} | Scrubbed PII: {log['contains_pii_redaction']}")
        print(f"Scrubbed Payload: {log['raw_payload']}\n")
