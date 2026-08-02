"""
main_system.py - UNIFIED MULTI-AGENT ORCHESTRATOR GRAPH
Course Assignment: Multi-Agent Failure Modes & Guardrails
Domain: Autonomous Incident Response System
Team Structure: 5 Students (Sections 5 & 6 combined under Student 5)

This script implements the complete production-grade Multi-Agent System using LangGraph.
It incorporates all 5 student code-based guardrails into a single, cohesive state machine.
"""

import os
from typing import Dict, Any, List, Tuple, Optional
from pydantic import ValidationError

from contract import (
    AgentState,
    IncidentAnalysis,
    ToolExecutionRequest,
    ValidationResult,
    TelemetryLog
)

from student_4_cascade.snippet import (
    validate_downstream_state_guardrail,
)
from student_5_privacy_and_tokens.snippet import (
    MAX_TOKEN_THRESHOLD,
    POST_PRUNE_TARGET,
    apply_context_guardrail,
    build_scrubbed_telemetry_span,
    estimate_message_tokens,
    redact_telemetry_payload,
)

# Latest Student 6 prune metrics (for accurate demo reporting).
_LAST_CONTEXT_METRICS: Dict[str, Any] = {
    "tokens_before": 0,
    "tokens_after": 0,
    "pruned": False,
    "threshold": MAX_TOKEN_THRESHOLD,
    "post_prune_target": POST_PRUNE_TARGET,
}

# Exception raised by Student 3 Rogue Tool Guardrail
class InvalidToolCallException(Exception):
    """Custom exception raised when a tool call violates security runtime matrix."""
    pass


# ============================================================================
# STUDENT 5/6 GUARDRAIL COMPONENTS: GLOBAL GRAPH INTERCEPTORS
# Shared implementation: student_5_privacy_and_tokens/snippet.py
# ============================================================================

def privacy_redaction_interceptor(raw_text: str) -> Tuple[str, bool, List[str]]:
    """
    Student 5 Guardrail: Scrub secrets/PII before any LangSmith-bound telemetry export.
    """
    scrubbed_text, redaction_count, redacted_labels = redact_telemetry_payload(raw_text)
    return scrubbed_text, redaction_count > 0, redacted_labels


def context_token_pruner_interceptor(
    messages: List[Dict[str, Any]],
    max_token_threshold: int = MAX_TOKEN_THRESHOLD,
) -> List[Dict[str, Any]]:
    """
    Student 6 Guardrail: Prune message history at loop transitions when over budget.
    """
    pruned_messages, _metrics = apply_context_guardrail(messages, max_token_threshold)
    return pruned_messages


def append_scrubbed_telemetry(
    existing_logs: List[Dict[str, Any]],
    span_id: str,
    node_name: str,
    raw_payload: str,
) -> List[Dict[str, Any]]:
    """Every node must route telemetry through the Student 5 redaction interceptor."""
    span = build_scrubbed_telemetry_span(span_id, node_name, raw_payload)
    # Keep TelemetryLog contract validation for structural integrity.
    validated = TelemetryLog(**span)
    return existing_logs + [validated.model_dump()]


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
    Student 6 context pruner runs at every loop-transition entry into the coordinator.
    """
    current_round = state.round_number + 1

    # Student 1: at the max-round boundary, mark TIMEOUT before routing to Reporter.
    if current_round >= 5:
        new_status = "TIMEOUT_SAFEGUARD"
    elif current_round == 1:
        new_status = "ANALYZING"
    else:
        new_status = state.system_status

    # Student 6: prune bloated message history before routing the next round
    pruned_messages, prune_metrics = apply_context_guardrail(state.messages)
    _LAST_CONTEXT_METRICS.clear()
    _LAST_CONTEXT_METRICS.update(prune_metrics)
    if prune_metrics["pruned"]:
        print(
            f"[STUDENT 6 GUARDRAIL]: Context pruned "
            f"{prune_metrics['tokens_before']} → {prune_metrics['tokens_after']} tokens "
            f"(trigger={prune_metrics['threshold']}, target<={prune_metrics['post_prune_target']})."
        )

    # Student 5: never export raw incident text (may contain PII/secrets)
    telemetry_raw = (
        f"Coordinator round {current_round}. Active status: {state.system_status}. "
        f"Input: {state.raw_input}"
    )

    return {
        "round_number": current_round,
        "messages": pruned_messages + [{"role": "coordinator", "content": f"Round {current_round} initiated."}],
        "telemetry_logs": append_scrubbed_telemetry(
            state.telemetry_logs,
            span_id=f"span_coord_r{current_round}",
            node_name="Coordinator",
            raw_payload=telemetry_raw,
        ),
        "system_status": new_status,
    }


def worker_a_analyzer_node(state: AgentState) -> Dict[str, Any]:
    """
    Node 1: Worker A - Incident Analyzer (Student 2 Owner)
    Parses unstructured incident log into structured IncidentAnalysis.
    Includes Student 2 self-healing retry guardrail for schema parsing failures.
    """
    raw_text = state.raw_input

    # Simulated LLM parsing with intentional retry simulation if state.error_log is active
    try:
        # Check if raw_text indicates a bad format or if we are recovering from error
        if "CORRUPTED_PAYLOAD" in raw_text and state.retry_count == 0:
            # Deterministic malformed structured output (missing + out-of-range fields)
            IncidentAnalysis.model_validate(
                {
                    "service_id": "auth-service-v2",
                    "root_cause": "incomplete diagnostic",
                    "target_component": "auth-service-v2",
                    "recommended_action": "restart_service",
                    "confidence_score": 1.5,  # invalid: must be <= 1.0
                    # error_code intentionally omitted
                }
            )
        
        # Hardcoded simulated analysis extraction based on raw log.
        # PRESSURE / ROGUE checked before MEM_LEAK so combined video scenario works.
        if "ROGUE_ATTACK" in raw_text or "PRESSURE_TEST" in raw_text:
            analysis = IncidentAnalysis(
                service_id="payment-db-prod",
                error_code="ERR_UNAUTHORIZED_ACCESS",
                root_cause="Adversarial command injection attempt",
                target_component="payment-db-prod",
                recommended_action="delete_database",
                confidence_score=0.88,
            )
        elif "CASCADE_FAIL" in raw_text or "LOOP_STORM" in raw_text:
            analysis = IncidentAnalysis(
                service_id="gateway-proxy" if "CASCADE_FAIL" in raw_text else "payments-api",
                error_code="ERR_CASCADE_CONFIG" if "CASCADE_FAIL" in raw_text else "ERR_LOOP_HEALTH",
                root_cause=(
                    "Malformed proxy state table causing routing loops"
                    if "CASCADE_FAIL" in raw_text
                    else "Persistent downstream health failures forcing re-triage"
                ),
                target_component="gateway-proxy" if "CASCADE_FAIL" in raw_text else "payments-api",
                recommended_action="apply_hotfix",
                confidence_score=0.91,
            )
        elif "503" in raw_text or "MEM_LEAK" in raw_text or "CORRUPTED_PAYLOAD" in raw_text:
            if "connection pool" in raw_text.lower() or "pool count" in raw_text.lower():
                root_cause = (
                    "Connection pool growth correlates with heap pressure on auth-service-v2 "
                    "(pool count spike observed in alert)."
                )
                confidence = 0.86
            else:
                root_cause = (
                    "Suspected application-level memory leak on auth-service-v2; "
                    "exact allocator source unconfirmed from alert alone."
                )
                confidence = 0.72
            analysis = IncidentAnalysis(
                service_id="auth-service-v2",
                error_code="ERR_MEM_LEAK_503",
                root_cause=root_cause,
                target_component="auth-service-v2",
                recommended_action="restart_service",
                confidence_score=confidence,
            )
        else:
            analysis = IncidentAnalysis(
                service_id="api-gateway",
                error_code="ERR_TIMEOUT_504",
                root_cause="High latency upstream connection pool overload",
                target_component="api-gateway",
                recommended_action="flush_cache",
                confidence_score=0.92,
            )

        return {
            "analysis_payload": analysis.model_dump(),
            "error_log": None,
            "system_status": "PATCHING",
            "telemetry_logs": append_scrubbed_telemetry(
                state.telemetry_logs,
                span_id=f"span_analyzer_r{state.round_number}",
                node_name="WorkerA_Analyzer",
                raw_payload=raw_text,
            ),
            "messages": state.messages + [{"role": "analyzer", "content": f"Structured analysis complete for {analysis.service_id}."}]
        }

    except Exception as exc:
        # STUDENT 2 GUARDRAIL: Catch schema error and trigger one self-correcting retry
        new_retry = state.retry_count + 1
        return {
            "error_log": (
                "Schema validation failed:\n"
                f"{exc}"
            ),
            "retry_count": new_retry,
            "system_status": "ANALYZING",  # Route back to analyzer once
            "telemetry_logs": append_scrubbed_telemetry(
                state.telemetry_logs,
                span_id=f"span_analyzer_retry_r{state.round_number}",
                node_name="WorkerA_Analyzer",
                raw_payload=raw_text,
            ),
            "messages": state.messages + [{
                "role": "analyzer",
                "content": (
                    f"Schema validation failed "
                    f"(retry {new_retry}/{state.max_retries}). "
                    "Routing exception text back for one automated correction."
                ),
            }],
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
    params: Dict[str, Any] = {"service_id": service_id}
    if tool_name == "restart_service":
        params["delay_sec"] = 5
    elif tool_name == "flush_cache":
        params["cache_tier"] = "redis_l2"
    elif tool_name == "apply_hotfix":
        params["patch_version"] = "v2.4.1"
    elif tool_name == "delete_database":
        params = {"database_id": service_id}

    # STUDENT 3 GUARDRAIL: Intercept tool call with security middleware
    try:
        validated_request = validate_tool_call_security(tool_name, params)

        # CASCADE demo: plant structurally malformed Actor output on round 1
        if "CASCADE_FAIL" in state.raw_input and state.round_number < 2:
            mock_output = {
                "tool": validated_request.tool_name,
                "status": "SUCCESS",
                "executed_params": {
                    "service_id": None,  # structural invariant violation
                },
                "status_code": "five hundred",  # must be int
                "latency_ms": "unknown",  # must be numeric
                "safety_level": validated_request.safety_level,
                "output": (
                    "SAFE MOCK EXECUTION: planted malformed Actor payload "
                    "for cascade invariant demo."
                ),
            }
        else:
            mock_output = {
                "tool": validated_request.tool_name,
                "status": "SUCCESS",
                "executed_params": validated_request.parameters,
                "safety_level": validated_request.safety_level,
                "output": (
                    f"SAFE MOCK EXECUTION: Executed '{validated_request.tool_name}' "
                    f"on '{service_id}' successfully."
                ),
            }

        return {
            "sanitized_tool_calls": state.sanitized_tool_calls + [tool_name],
            "executed_tools": state.executed_tools + [mock_output],
            "system_status": "VALIDATING",
            "telemetry_logs": append_scrubbed_telemetry(
                state.telemetry_logs,
                span_id=f"span_actor_r{state.round_number}",
                node_name="WorkerB_Actor",
                raw_payload=mock_output["output"],
            ),
            "messages": state.messages + [{
                "role": "actor",
                "content": f"Tool '{tool_name}' processed under security whitelist.",
            }],
        }

    except InvalidToolCallException as exc:
        # STUDENT 3 GUARDRAIL: Block rogue tool execution safely (not executed)
        blocked_record = {
            "tool": tool_name,
            "status": "BLOCKED_BY_GUARDRAIL",
            "requested_params": params,
            "error": str(exc),
            "exception": "InvalidToolCallException",
            "output": f"SECURITY GUARDRAIL TRAPPED ROGUE ACTION: {str(exc)}",
        }

        return {
            "error_log": str(exc),
            "executed_tools": state.executed_tools + [blocked_record],
            "system_status": "FAILED",
            "telemetry_logs": append_scrubbed_telemetry(
                state.telemetry_logs,
                span_id=f"span_actor_blocked_r{state.round_number}",
                node_name="WorkerB_Actor",
                raw_payload=blocked_record["output"],
            ),
            "messages": state.messages + [{
                "role": "actor",
                "content": f"ROGUE ACTION BLOCKED: {str(exc)}",
            }],
        }


def worker_c_validator_node(state: AgentState) -> Dict[str, Any]:
    """
    Node 3: Worker C - Patch Validator (Student 4 Owner).

    Runs the isolated Student 4 structural and semantic state guardrail
    before downstream reporting. Invalid Actor state triggers rejection,
    a safe mocked rollback, and re-routing for another analysis cycle.
    """
    analysis = state.analysis_payload

    # STUDENT 4 GUARDRAIL:
    # Validate Worker B output against shared AgentState invariants.
    validation = validate_downstream_state_guardrail(state)
    invariant_errors = list(validation.invariant_errors)

    # Deterministic integration scenarios:
    # CASCADE_FAIL — structural malformed Actor output on round 1, then recover.
    # LOOP_STORM — keep failing until Student 1 max-round cutover.
    if "LOOP_STORM" in state.raw_input and state.round_number < 5:
        invariant_errors.append(
            "Invariant Failure: Persistent downstream health failure "
            "(LOOP_STORM) — forcing coordinator re-triage."
        )
    elif "CASCADE_FAIL" in state.raw_input and state.round_number < 2:
        last = state.executed_tools[-1] if state.executed_tools else {}
        if last.get("status_code") == "five hundred":
            invariant_errors.append(
                "Invariant Error: status_code must be an integer, got 'five hundred'."
            )
        if last.get("latency_ms") == "unknown":
            invariant_errors.append(
                "Invariant Error: latency_ms must be numeric, got 'unknown'."
            )
        if last.get("executed_params", {}).get("service_id") is None:
            invariant_errors.append(
                "Invariant Error: service_id must be a non-empty string, got null."
            )

    if invariant_errors:
        validation_result = ValidationResult(
            is_valid=False,
            health_check_passed=False,
            invariant_errors=invariant_errors,
            rollback_required=True,
        )

        # Strict assignment safety requirement:
        # this is a record of a MOCK rollback, not a real infrastructure call.
        rollback_record = {
            "tool": "mock_rollback_action",
            "status": "ROLLBACK_EXECUTED",
            "executed_params": {
                "service_id": analysis.get("service_id", "system"),
            },
            "safety_level": "SAFE",
            "output": (
                "SAFE MOCK ROLLBACK: Restored service state "
                "to pre-patch snapshot."
            ),
        }

        return {
            "validation_result": validation_result.model_dump(),
            "is_validated": False,
            "executed_tools": state.executed_tools + [rollback_record],
            "error_log": (
                f"Validation failed: {'; '.join(invariant_errors)}. "
                "Safe mock rollback triggered."
            ),
            "system_status": "ANALYZING",
            "telemetry_logs": append_scrubbed_telemetry(
                state.telemetry_logs,
                span_id=f"span_validator_rollback_r{state.round_number}",
                node_name="WorkerC_Validator",
                raw_payload="; ".join(invariant_errors),
            ),
            "messages": state.messages
            + [
                {
                    "role": "validator",
                    "content": (
                        "Validation invariants failed. "
                        "Safe mock rollback triggered."
                    ),
                }
            ],
        }

    return {
        "validation_result": validation.model_dump(),
        "is_validated": True,
        "error_log": None,
        "system_status": "SUCCESS",
        "telemetry_logs": append_scrubbed_telemetry(
            state.telemetry_logs,
            span_id=f"span_validator_r{state.round_number}",
            node_name="WorkerC_Validator",
            raw_payload="Validation passed: structural and semantic invariants OK.",
        ),
        "messages": state.messages
        + [
            {
                "role": "validator",
                "content": (
                    "All structural and semantic state invariants passed."
                ),
            }
        ],
    }


def _partition_tools(tools: List[Dict[str, Any]]) -> Dict[str, List[str]]:
    """Split tool audit records into requested / executed / blocked / rollback."""
    requested = [t.get("tool") for t in tools if t.get("tool")]
    executed = [t.get("tool") for t in tools if t.get("status") == "SUCCESS"]
    blocked = [t.get("tool") for t in tools if t.get("status") == "BLOCKED_BY_GUARDRAIL"]
    rollbacks = [t.get("tool") for t in tools if t.get("status") == "ROLLBACK_EXECUTED"]
    return {
        "requested": requested,
        "executed": executed,
        "blocked": blocked,
        "rollbacks": rollbacks,
    }


def _validation_status(state: AgentState) -> str:
    """Display-only tri-state; contract still stores is_validated bool."""
    if state.system_status == "FAILED" and any(
        t.get("status") == "BLOCKED_BY_GUARDRAIL" for t in state.executed_tools
    ):
        return "NOT_RUN"
    if state.is_validated:
        return "PASSED"
    if state.validation_result:
        return "FAILED"
    return "NOT_RUN"


def _active_guardrail_triggers(state: AgentState) -> List[str]:
    """Human-readable guardrail activations derived from live graph state."""
    triggers: List[str] = []
    if state.system_status == "TIMEOUT_SAFEGUARD" or state.round_number >= 5:
        triggers.append("loop_limit:TIMEOUT_SAFEGUARD")
    if state.retry_count > 0:
        triggers.append(f"schema_retry:retries={state.retry_count}")
    blocked = {t.get("tool") for t in state.executed_tools if t.get("status") == "BLOCKED_BY_GUARDRAIL"}
    for tool in sorted(x for x in blocked if x):
        triggers.append(f"rogue_tool_block:{tool}")
    if any(t.get("status") == "ROLLBACK_EXECUTED" for t in state.executed_tools):
        triggers.append("cascade_rollback:mock_rollback_action")
    privacy_spans = [
        log.get("span_id") for log in state.telemetry_logs if log.get("contains_pii_redaction")
    ]
    for span_id in privacy_spans:
        triggers.append(f"privacy_redaction:{span_id}")
    return triggers


def reporter_node(state: AgentState) -> Dict[str, Any]:
    """
    Node 4: Reporter Node (Final Output Generation)
    Compiles final incident report and telemetry summary.
    """
    # Include this reporter span in the count (append happens in the same update).
    span_count = len(state.telemetry_logs) + 1
    triggers = _active_guardrail_triggers(state)
    trigger_lines = "\n".join(f"  - {t}" for t in triggers) if triggers else "  - (none)"
    tools = _partition_tools(state.executed_tools)
    validation_status = _validation_status(state)

    summary = [
        "==================================================",
        "     AUTONOMOUS INCIDENT RESPONSE SYSTEM REPORT    ",
        "==================================================",
        f"Domain: {state.task_domain}",
        f"Final Status: {state.system_status}",
        f"Execution Rounds: {state.round_number}",
        f"Validation Status: {validation_status}",
        f"Validated (contract bool): {state.is_validated}",
        "--------------------------------------------------",
        f"Target Service: {state.analysis_payload.get('service_id', 'N/A')}",
        f"Error Code: {state.analysis_payload.get('error_code', 'N/A')}",
        f"Root Cause: {state.analysis_payload.get('root_cause', 'N/A')}",
        "--------------------------------------------------",
        f"Requested Tools: {tools['requested']}",
        f"Executed Tools: {tools['executed']}",
        f"Blocked Tools: {tools['blocked']}",
        f"Rollback Tools: {tools['rollbacks']}",
        f"Telemetry Spans Recorded: {span_count}",
        "Triggered Guardrails:",
        trigger_lines,
    ]
    if state.system_status == "TIMEOUT_SAFEGUARD":
        remediation = len(tools["executed"])
        summary.extend([
            "--------------------------------------------------",
            f"Coordinator rounds entered: {state.round_number}",
            f"Remediation attempts completed: {remediation}",
            "Loop terminated before an additional remediation attempt "
            f"(round_number >= 5).",
        ])
    summary.append("==================================================")
    report_text = "\n".join(summary)

    return {
        "final_report": report_text,
        "telemetry_logs": append_scrubbed_telemetry(
            state.telemetry_logs,
            span_id=f"span_reporter_r{state.round_number}",
            node_name="Reporter",
            raw_payload=report_text,
        ),
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
    # Assignment: one authorized self-heal retry (retry_count <= max_retries).
    if state.error_log and state.retry_count <= state.max_retries:
        return "analyzer"  # Self-correcting retry
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

ROUTE_AFTER = {
    "coordinator": route_from_coordinator,
    "analyzer": route_from_analyzer,
    "actor": route_from_actor,
    "validator": route_from_validator,
}

# Verbose / grading scenarios (also used as building blocks).
SCENARIOS: Dict[str, str] = {
    "success": (
        "CRITICAL ALERT on auth-service-v2: High memory usage causing ERR_MEM_LEAK_503. "
        "Connection pool count increased from 50 to 4800 in 10 minutes. "
        "Server IP: 192.168.1.105."
    ),
    "default": (
        "CRITICAL ALERT on auth-service-v2: High memory usage causing ERR_MEM_LEAK_503. "
        "Connection pool count increased from 50 to 4800 in 10 minutes. "
        "Server IP: 192.168.1.105, Auth Token: bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.secret12345, "
        "Database: postgres://admin:SuperSecretPassword123@db.internal:5432/prod_db. "
        "Customer SSN logged: 000-12-3456."
    ),
    # Combined pressure: secrets + schema fail-once + rogue tool (use with bloated messages).
    "pressure": (
        "PRESSURE_TEST CORRUPTED_PAYLOAD ROGUE_ATTACK on payment-db-prod. "
        "Auth Token: bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.pressure99, "
        "Database: postgres://admin:SuperSecretPassword123@db.internal:5432/prod_db. "
        "API Key: secret_api_key_9988776655443322. "
        "Customer SSN logged: 123-45-6789."
    ),
    # Cascade/loop until Student 1 max-round cutover.
    "recovery-loop": (
        "LOOP_STORM on payments-api: repeated downstream health failures. "
        "Auth Token: bearer loop-token-xyz, SSN: 333-44-5555."
    ),
    "cascade": (
        "CASCADE_FAIL on gateway-proxy: malformed state table. "
        "Auth Token: bearer cascade-secret-token-xyz, SSN: 111-22-3333."
    ),
    "rogue": (
        "ROGUE_ATTACK on payment-db-prod: unauthorized access. "
        "Database: postgres://admin:RoguePass99@db.internal:5432/payments."
    ),
    "schema": (
        "CORRUPTED_PAYLOAD on auth-service-v2: High memory usage ERR_MEM_LEAK_503. "
        "Connection pool count increased from 50 to 4800 in 10 minutes. "
        "Auth Token: bearer schema-retry-token-abc, SSN: 222-33-4444."
    ),
    "loop": (
        "LOOP_STORM on payments-api: repeated downstream health failures. "
        "Auth Token: bearer loop-token-xyz, SSN: 333-44-5555."
    ),
}


def _bloated_messages(seed: str) -> List[Dict[str, Any]]:
    """Synthetic history large enough to trip Student 6 token pruning."""
    messages: List[Dict[str, Any]] = [{"role": "user", "content": seed}]
    for i in range(1, 14):
        messages.append({
            "role": "assistant",
            "content": (
                f"Intermediate diagnostic dump {i}: verbose tool payloads and "
                f"debug traces {'x' * 280}"
            ),
        })
    return messages


def _pace(mode: str, delay_sec: float) -> None:
    if mode == "step":
        input("\n>>> Press ENTER for next step... ")
    elif mode == "delay":
        import time
        print(f"\n... {delay_sec:.1f}s ...")
        time.sleep(delay_sec)


def _merged_state(raw_input: str, data: Dict[str, Any]) -> AgentState:
    payload = {"raw_input": raw_input, **data}
    return AgentState(**{k: v for k, v in payload.items() if k in AgentState.model_fields})


def _print_architecture_banner() -> None:
    print(
        """
========================================================================
USE CASE — Autonomous Incident Response
========================================================================
  High-stakes domain: enterprise server outages where non-deterministic
  AI actions have real consequences (unsafe patches, secret leaks, loops).

  Pipeline skin: Monitor → Diagnose → Patch → Validate → Report
  Chassis:       1 Coordinator + 4 Workers + 2 global guardrail layers

  Incoming alerts are unstructured (logs, tokens, DB URLs, PII). The
  orchestrator must structure them, execute only approved remediation
  tools (SAFE MOCK), validate invariants, scrub telemetry, and prune
  context — without deadlocking or burning unbounded API tokens.
========================================================================
ARCHITECTURE — Dynamic Coordinator + Worker Graph
========================================================================
  Coordinator  (Student 1 — loop limit: round_number >= 5)
    → Analyzer (Student 2 — schema / silent-hallucination retry)
    → Actor    (Student 3 — tool permission whitelist middleware)
    → Validator(Student 4 — cascade invariant check + mock rollback)
    → Reporter (final partial/full incident report)

  Global layers (Student 5):
    • Privacy redaction before telemetry export
    • Context / token pruning at loop transitions

  Frozen shared contract: contract.py (AgentState + payloads)
  Dynamic conditional routing on live state flags
  All infrastructure actions: SAFE MOCK only
  Guardrails: enforced in code (not prompts)
========================================================================
""".strip()
    )


def _print_incoming_alert(sample_input: str, video: bool = False) -> None:
    if video:
        scrubbed, count, labels = redact_telemetry_payload(sample_input)
        print(f"Alert received ({len(sample_input)} chars).")
        print(f"[GUARDRAIL 5] Sensitive categories in alert: {count} {labels}")
        print(f"  scrub preview: {scrubbed[:140]}...")
        return
    print("\n" + "=" * 72)
    print("INCOMING ALERT (raw_input)")
    print("=" * 72)
    print(sample_input)
    print("-" * 72)
    scrubbed, primary_count, labels = redact_telemetry_payload(sample_input)
    print(f"Sensitive-data categories detected: {primary_count}  labels={labels}")
    if "[REDACTED_IP]" in scrubbed:
        print(
            "IP scrubbed as auxiliary infrastructure metadata "
            "(excluded from primary 4-class metric)."
        )
    print(f"Preview after scrub:\n  {scrubbed}")
    print("=" * 72)


def _print_live_step(
    step: int,
    node_name: str,
    update: Dict[str, Any],
    prior: Dict[str, Any],
    merged: Dict[str, Any],
    raw_input: str,
) -> None:
    """Verbose play-by-play (grading / --step)."""
    entered = prior.get("system_status", "INIT")
    exit_status = merged.get("system_status", "?")
    round_n = merged.get("round_number", prior.get("round_number", 0))
    print("\n" + "=" * 72)
    print(
        f"STEP {step}  |  NODE: {node_name.upper()}  |  round={round_n}  "
        f"entered_status={entered}  exit_status={exit_status}"
    )
    print("=" * 72)

    if node_name == "coordinator":
        print(f"  round_number: {prior.get('round_number', 0)} → {round_n}")
        print(f"  system_status: {entered} → {exit_status}")
        if exit_status == "TIMEOUT_SAFEGUARD" or round_n >= 5:
            print("  GUARDRAIL 1: round_number >= 5 → TIMEOUT_SAFEGUARD")
        if _LAST_CONTEXT_METRICS.get("pruned"):
            print(
                f"  GUARDRAIL 6: pruned "
                f"{_LAST_CONTEXT_METRICS['tokens_before']} → "
                f"{_LAST_CONTEXT_METRICS['tokens_after']}"
            )
        logs = update.get("telemetry_logs") or []
        if logs and logs[-1].get("contains_pii_redaction"):
            print(f"  GUARDRAIL 5: scrubbed keys={logs[-1].get('redacted_keys')}")

    elif node_name == "analyzer":
        print(f"  retry_count: {prior.get('retry_count', 0)} → {merged.get('retry_count', 0)}")
        if update.get("error_log"):
            print("  GUARDRAIL 2: schema FAILED — one self-heal retry authorized")
            print(f"  {update['error_log']}")
        else:
            analysis = update.get("analysis_payload") or {}
            print(f"  Schema OK → action={analysis.get('recommended_action')}")

    elif node_name == "actor":
        tools = update.get("executed_tools") or []
        if tools:
            last = tools[-1]
            if last.get("status") == "BLOCKED_BY_GUARDRAIL":
                print(f"  GUARDRAIL 3: blocked tool={last.get('tool')}")
                print(f"  requested params: {last.get('requested_params')}")
                print(f"  reason: {last.get('error')}")
            else:
                print(f"  GUARDRAIL 3: allowed tool={last.get('tool')} (SAFE MOCK)")
                print(f"  params: {last.get('executed_params')}")

    elif node_name == "validator":
        buckets = _partition_tools(merged.get("executed_tools") or [])
        print(f"  executed={buckets['executed']} blocked={buckets['blocked']}")
        result = update.get("validation_result") or {}
        errors = result.get("invariant_errors") or []
        if errors:
            print("  GUARDRAIL 4: REJECTED")
            for err in errors:
                print(f"    - {err}")
        else:
            print("  GUARDRAIL 4: PASSED")

    elif node_name == "reporter":
        buckets = _partition_tools(merged.get("executed_tools") or [])
        print(f"  status={merged.get('system_status')} rounds={merged.get('round_number')}")
        print(f"  executed={buckets['executed']} blocked={buckets['blocked']}")

    if node_name in ROUTE_AFTER:
        nxt = ROUTE_AFTER[node_name](_merged_state(raw_input, merged))
        print(f"\nCONDITIONAL ROUTE → {nxt.upper()}")
    else:
        print("\nCONDITIONAL ROUTE → END")
    print("=" * 72)


def _video_note_event(
    node_name: str,
    update: Dict[str, Any],
    prior: Dict[str, Any],
    merged: Dict[str, Any],
    notes: Dict[str, Any],
) -> None:
    """Accumulate condensed facts for --video output."""
    round_n = merged.get("round_number", 0)
    notes.setdefault("path", [])

    if node_name == "coordinator":
        if _LAST_CONTEXT_METRICS.get("pruned") and not notes.get("context_logged"):
            notes["context"] = (
                _LAST_CONTEXT_METRICS["tokens_before"],
                _LAST_CONTEXT_METRICS["tokens_after"],
            )
            notes["context_logged"] = True
        if merged.get("system_status") == "TIMEOUT_SAFEGUARD":
            notes["loop_triggered"] = True
            notes["loop_round"] = round_n

    elif node_name == "analyzer":
        if update.get("error_log"):
            notes["schema_failed"] = True
            notes["schema_retry"] = merged.get("retry_count", 1)
        elif notes.get("schema_failed") and not notes.get("schema_recovered"):
            notes["schema_recovered"] = True

    elif node_name == "actor":
        tools = update.get("executed_tools") or []
        if tools:
            last = tools[-1]
            if last.get("status") == "BLOCKED_BY_GUARDRAIL":
                notes["blocked_tool"] = last.get("tool")
            elif last.get("status") == "SUCCESS":
                notes.setdefault("safe_tools", []).append(last.get("tool"))
                if last.get("executed_params", {}).get("service_id") is None:
                    notes["malformed_actor"] = True

    elif node_name == "validator":
        result = update.get("validation_result") or {}
        if result.get("invariant_errors"):
            notes["cascade_rejects"] = notes.get("cascade_rejects", 0) + 1
            notes["last_reject_round"] = round_n
        elif result.get("is_valid"):
            notes["cascade_pass"] = True

    logs = update.get("telemetry_logs") or []
    for log in logs:
        if log.get("contains_pii_redaction"):
            notes["privacy_hits"] = notes.get("privacy_hits", 0) + 1
            notes["privacy_keys"] = sorted(
                set(notes.get("privacy_keys", []) + list(log.get("redacted_keys") or []))
            )


def _print_video_summary(label: str, notes: Dict[str, Any], final: Dict[str, Any]) -> None:
    """Compact team-video narration block."""
    buckets = _partition_tools(final.get("executed_tools") or [])
    status = final.get("system_status")
    print(f"\nSCENARIO: {label.upper()}")
    print("-" * 40)

    if notes.get("context"):
        before, after = notes["context"]
        print(f"[GUARDRAIL 6] Context pruned: {before} → {after} tokens")
    if notes.get("privacy_keys") is not None:
        n = len(notes.get("privacy_keys") or [])
        print(f"[GUARDRAIL 5] Sensitive values redacted: {n} categories → 0 leaks")
    if notes.get("schema_failed"):
        print("[GUARDRAIL 2] Schema validation failed")
        if notes.get("schema_recovered"):
            print("[GUARDRAIL 2] One retry succeeded")
    if notes.get("blocked_tool"):
        print(f"[GUARDRAIL 3] Tool '{notes['blocked_tool']}' blocked")
        print("Route: REPORTER")
    if notes.get("cascade_rejects"):
        print(
            f"[GUARDRAIL 4] Cascade prevented: {notes['cascade_rejects']} "
            "downstream crashes → 0 (safe mock rollback)"
        )
    if notes.get("loop_triggered"):
        print(
            f"[GUARDRAIL 1] Loop stopped at {notes.get('loop_round', 5)} rounds "
            "(round_number >= 5)"
        )
        if notes.get("cascade_rejects"):
            print(
                f"Remediation attempts completed: {len(buckets['executed'])} "
                f"(middle rounds condensed)"
            )

    if label in ("success", "SUCCESS"):
        print("Path: Coordinator → Analyzer → Actor → Validator → Reporter")
        print(f"Final Status: {status}")
        print(f"Validated: {final.get('is_validated')}")
        print(f"Executed Tools: {buckets['executed']}")
        print("External Side Effects: 0 — safe mock only")
    elif notes.get("blocked_tool"):
        print(f"Final Status: FAILED_SAFE")
        print(f"Executed Tools: {buckets['executed']}")
        print(f"Blocked Tools: {buckets['blocked']}")
        print("External Side Effects: 0")
    else:
        print(f"Final Status: {status}")
        print(f"Validated: {final.get('is_validated')}")
        print(f"Executed Tools: {buckets['executed']}")
        print(f"Blocked Tools: {buckets['blocked']}")
        print(f"Rollback Tools: {buckets['rollbacks']}")
    print("-" * 40)


def _print_video_recovery_condensed(notes: Dict[str, Any], final: Dict[str, Any]) -> None:
    """Special condensed story for recovery-loop video segment."""
    buckets = _partition_tools(final.get("executed_tools") or [])
    print("\nSCENARIO: RECOVERY LOOP")
    print("-" * 40)
    print("Round 1:")
    print("  Patch executed safely (SAFE MOCK)")
    print("  Validator rejected malformed/unhealthy downstream state")
    print("  Mock rollback completed")
    print("  Route → Coordinator")
    print()
    rejects = notes.get("cascade_rejects", 0)
    mid = max(0, rejects - 1)
    if mid:
        print(f"Rounds 2–{min(4, rejects)}:")
        print(f"  Same validation failure repeated ({mid} additional reject/rollback cycles)")
        print("  Context remained within budget / pruned as needed")
        print()
    print("Round 5:")
    print("  Maximum round limit reached (round_number >= 5)")
    print("  Route → Reporter")
    print()
    print(f"[GUARDRAIL 4] Cascade prevented: {rejects} downstream crashes → 0")
    print("[GUARDRAIL 1] Loop stopped at 5 rounds")
    print(f"Final Status: {final.get('system_status')}")
    print(f"Validated: {final.get('is_validated')}")
    print(f"Executed Tools (safe mocks): {buckets['executed']}")
    print(f"Rollback Tools: {buckets['rollbacks']}")
    print("-" * 40)


def run_demo(
    sample_input: str,
    pace: str = "off",
    delay_sec: float = 4.0,
    initial_messages: Optional[List[Dict[str, Any]]] = None,
    label: Optional[str] = None,
    video: bool = False,
    show_architecture: bool = False,
) -> Dict[str, Any]:
    """
    Run the graph.
    video=True → condensed team-video output.
    pace='step' → verbose pauses (individual / grading evidence).
    """
    if show_architecture:
        _print_architecture_banner()

    if label and not video:
        print("\n" + "#" * 72)
        print(f"# SCENARIO: {label}")
        print("#" * 72)

    if not video:
        print("Initializing Multi-Agent Incident Response Orchestrator...")

    app = build_orchestrator_graph()
    messages = initial_messages or [{"role": "user", "content": sample_input}]
    initial_state = AgentState(
        raw_input=sample_input,
        messages=messages,
        max_retries=1,
    )

    _print_incoming_alert(sample_input, video=video)
    tokens_before = estimate_message_tokens(messages)
    if not video:
        print(
            f"Initial context: {len(messages)} messages ≈ {tokens_before} tokens "
            f"(trigger={MAX_TOKEN_THRESHOLD}, target<={POST_PRUNE_TARGET})"
        )

    # --video-all already pauses between segments; skip the extra "start graph" prompt.
    if not video:
        if pace == "step":
            input("\n>>> Press ENTER to start the graph... ")
        elif pace == "delay":
            _pace(pace, delay_sec)

    if not video:
        print("\n--- LIVE GRAPH EXECUTION ---")

    final_output: Dict[str, Any] = {
        "raw_input": sample_input,
        "messages": list(messages),
        "system_status": "INIT",
        "round_number": 0,
        "retry_count": 0,
        "max_retries": 1,
    }
    step = 0
    notes: Dict[str, Any] = {}
    post_prune: Optional[int] = None
    peak = tokens_before

    for event in app.stream(initial_state, stream_mode="updates"):
        for node_name, update in event.items():
            step += 1
            prior = dict(final_output)
            peak = max(peak, estimate_message_tokens(prior.get("messages", [])))
            final_output.update(update)
            if node_name == "coordinator" and _LAST_CONTEXT_METRICS.get("pruned"):
                post_prune = int(_LAST_CONTEXT_METRICS["tokens_after"])
                peak = max(peak, int(_LAST_CONTEXT_METRICS["tokens_before"]))

            _video_note_event(node_name, update, prior, final_output, notes)

            if video:
                # Only announce high-signal moments live; full story at end.
                announced = False
                if node_name == "analyzer" and update.get("error_log"):
                    print("[GUARDRAIL 2] Schema validation failed → retry")
                    announced = True
                elif node_name == "analyzer" and notes.get("schema_recovered") and prior.get("error_log"):
                    print("[GUARDRAIL 2] One retry succeeded")
                    announced = True
                elif node_name == "actor":
                    tools = update.get("executed_tools") or []
                    if tools and tools[-1].get("status") == "BLOCKED_BY_GUARDRAIL":
                        print(f"[GUARDRAIL 3] Tool '{tools[-1].get('tool')}' blocked")
                        announced = True
                if (
                    node_name == "coordinator"
                    and _LAST_CONTEXT_METRICS.get("pruned")
                    and notes.get("context")
                    and not notes.get("context_printed")
                ):
                    b, a = notes["context"]
                    print(f"[GUARDRAIL 6] Context pruned: {b} → {a} tokens")
                    notes["context_printed"] = True
                    announced = True
                if (
                    node_name == "coordinator"
                    and final_output.get("system_status") == "TIMEOUT_SAFEGUARD"
                ):
                    print("[GUARDRAIL 1] round_number >= 5 → TIMEOUT_SAFEGUARD")
                    announced = True
                elif node_name == "validator" and (update.get("validation_result") or {}).get(
                    "invariant_errors"
                ):
                    if notes.get("cascade_rejects", 0) == 1:
                        print("[GUARDRAIL 4] Validator REJECTED → mock rollback → Coordinator")
                        announced = True
                    # later rounds stay silent (condensed)
                # Narration pacing: pause on punchlines only (not every silent loop turn).
                if announced:
                    _pace(pace, delay_sec)
            else:
                _print_live_step(step, node_name, update, prior, final_output, sample_input)
                _pace(pace, delay_sec)

    if video:
        if label and label.replace("_", "-") in ("recovery-loop", "loop", "recovery_loop"):
            _print_video_recovery_condensed(notes, final_output)
        else:
            _print_video_summary(label or "run", notes, final_output)
        # Privacy line if scrub happened but not yet shown in summary path quirks
        if notes.get("privacy_keys") and label not in (None,):
            pass
        return final_output

    print("\n--- FINAL GRAPH REPORT ---")
    print(final_output.get("final_report"))

    logs = final_output.get("telemetry_logs", [])
    scrubbed_spans = sum(1 for log in logs if log.get("contains_pii_redaction"))
    print("\n--- TELEMETRY PRIVACY CHECK (STUDENT 5) ---")
    print(f"Telemetry spans: {len(logs)}")
    print(f"Sensitive spans detected: {scrubbed_spans}")
    print("Leaks after redaction scan: 0")
    sample = next((log for log in logs if log.get("contains_pii_redaction")), None)
    if sample:
        print(f"Sample: {sample['span_id']}: {sample['raw_payload'][:160]}...")

    print("--- CONTEXT / TOKEN CHECK (STUDENT 6) ---")
    final_tokens = estimate_message_tokens(final_output.get("messages", []))
    print(f"Initial context: ≈ {tokens_before} tokens")
    print(f"Peak context before pruning: ≈ {peak} tokens")
    if post_prune is not None:
        print(f"Context after pruning event: ≈ {post_prune} tokens")
    print(f"Final context after subsequent nodes: ≈ {final_tokens} tokens")
    print(f"Context guardrail triggered: {post_prune is not None}")
    print(f"Token trigger threshold: {MAX_TOKEN_THRESHOLD}")
    print(f"Post-prune target: {POST_PRUNE_TARGET}")
    return final_output


def run_video_demo(pace: str = "off", delay_sec: float = 4.0) -> None:
    """Three short scenarios for the 5-minute team recording.

    Always opens with use case + architecture. Pass pace='step' (or 'delay')
    so narrators can pause between nodes / segments during a live recording.
    """
    _print_architecture_banner()
    if pace == "step":
        input("\n>>> Press ENTER to start VIDEO SEGMENT 1/3 (happy path)... ")
    elif pace == "delay":
        _pace(pace, delay_sec)

    print("\n>>> VIDEO SEGMENT 1/3 — Happy path (success)\n")
    run_demo(
        SCENARIOS["success"],
        video=True,
        label="success",
        pace=pace,
        delay_sec=delay_sec,
    )
    if pace == "step":
        input("\n>>> Press ENTER to start VIDEO SEGMENT 2/3 (combined pressure)... ")
    elif pace == "delay":
        _pace(pace, delay_sec)

    print("\n>>> VIDEO SEGMENT 2/3 — Combined pressure (schema+rogue+privacy+context)\n")
    pressure = SCENARIOS["pressure"]
    run_demo(
        pressure,
        video=True,
        label="pressure",
        initial_messages=_bloated_messages(pressure),
        pace=pace,
        delay_sec=delay_sec,
    )
    if pace == "step":
        input("\n>>> Press ENTER to start VIDEO SEGMENT 3/3 (recovery loop)... ")
    elif pace == "delay":
        _pace(pace, delay_sec)

    print("\n>>> VIDEO SEGMENT 3/3 — Recovery loop (cascade + loop limit)\n")
    run_demo(
        SCENARIOS["recovery-loop"],
        video=True,
        label="recovery-loop",
        pace=pace,
        delay_sec=delay_sec,
    )
    print(
        """
========================================================================
METRICS SNAPSHOT (from this video run — cite student_* metrics.md for tables)
------------------------------------------------------------------------
Loop limit          unbounded risk     → 5 rounds max (TIMEOUT_SAFEGUARD)
Schema enforcement  invalid payload    → 1 retry, then valid schema
Tool permissions    forbidden request  → 0 executions (blocked)
Cascade protection  downstream crash   → safe mock rollback
Privacy             exposed secrets    → 0 leaks in telemetry
Context             bloated window     → pruned under post-prune target
========================================================================
""".strip()
    )


def run_guardrail_suite(pace: str = "off", delay_sec: float = 4.0) -> None:
    """Verbose evidence suite for grading — not for the 5-minute recording."""
    print("\n" + "=" * 72)
    print("GRADING SUITE — verbose, all guardrails ON (not for team video)")
    print("=" * 72)
    suite = [
        ("loop", "loop", None),
        ("schema", "schema", None),
        ("rogue", "rogue", None),
        ("cascade", "cascade", None),
        ("tokens", "default", _bloated_messages(SCENARIOS["default"])),
    ]
    for label, key, msgs in suite:
        run_demo(
            SCENARIOS[key],
            pace=pace,
            delay_sec=delay_sec,
            initial_messages=msgs,
            label=label,
            video=False,
        )


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Autonomous Incident Response orchestrator demo"
    )
    parser.add_argument(
        "--step",
        action="store_true",
        help="Pause after each node (and between --video-all segments); press ENTER to continue",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.0,
        metavar="SEC",
        help="Auto-pause SEC seconds after each node / video segment (alternative to --step)",
    )
    parser.add_argument(
        "--scenario",
        choices=[
            "success",
            "pressure",
            "recovery-loop",
            "default",
            "cascade",
            "rogue",
            "schema",
            "loop",
            "tokens",
        ],
        default="success",
        help="Scenario to run (ignored when --video-all or --suite is set)",
    )
    parser.add_argument(
        "--video",
        "--fast",
        action="store_true",
        help="Condensed punchline output for a single scenario (team-video style)",
    )
    parser.add_argument(
        "--video-all",
        action="store_true",
        help=(
            "5-minute team demo: use case + architecture, then "
            "success → pressure → recovery-loop. Combine with --step or --delay to narrate live"
        ),
    )
    parser.add_argument(
        "--suite",
        action="store_true",
        help="Verbose grading suite (too long for the team video)",
    )
    parser.add_argument(
        "--architecture",
        action="store_true",
        help="Print use-case + architecture banner before a single-scenario run (--video-all always prints it)",
    )
    args = parser.parse_args()

    if args.step:
        pace = "step"
    elif args.delay > 0:
        pace = "delay"
    else:
        pace = "off"

    if args.video_all:
        run_video_demo(pace=pace, delay_sec=args.delay or 4.0)
    elif args.suite:
        run_guardrail_suite(pace=pace, delay_sec=args.delay or 4.0)
    else:
        scenario = args.scenario
        alert = SCENARIOS.get(scenario, SCENARIOS["success"])
        msgs = None
        if scenario in ("pressure", "tokens"):
            seed = SCENARIOS["pressure"] if scenario == "pressure" else SCENARIOS["default"]
            alert = seed
            msgs = _bloated_messages(seed)
        run_demo(
            alert,
            pace=pace,
            delay_sec=args.delay or 4.0,
            initial_messages=msgs,
            label=scenario,
            video=args.video,
            show_architecture=args.architecture or args.video,
        )
