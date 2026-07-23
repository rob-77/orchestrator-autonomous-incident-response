"""
contract.py - MANDATORY FROZEN SCHEMA CONTRACT
Course Assignment: Multi-Agent Failure Modes & Guardrails
Domain: Autonomous Incident Response System
Team Structure: 5 Students (Sections 5 & 6 combined under Student 5)

This file serves as the universal, immutable type safety contract for data passing
between nodes in the LangGraph Orchestrator.
"""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class IncidentPayload(BaseModel):
    """Raw incident log payload received from monitoring alerts."""
    service_id: str = Field(description="Unique identifier of the failing service")
    raw_log: str = Field(description="Unstructured log output or alert description")
    severity: str = Field(default="CRITICAL", description="Initial alert severity level")
    timestamp: str = Field(default="2026-07-23T18:00:00Z", description="Timestamp of alert")


class IncidentAnalysis(BaseModel):
    """Structured output expected from Worker A (Analyzer node)."""
    service_id: str = Field(..., description="Target service ID")
    error_code: str = Field(..., description="Identified standard error code (e.g. ERR_MEM_LEAK_503)")
    root_cause: str = Field(..., description="Diagnosed root cause explanation")
    target_component: str = Field(..., description="Affected sub-component or microservice")
    recommended_action: str = Field(..., description="Action to execute: restart_service, flush_cache, apply_hotfix")
    confidence_score: float = Field(..., ge=0.0, le=1.0, description="Diagnostic confidence score between 0.0 and 1.0")


class ToolExecutionRequest(BaseModel):
    """Structure for tool execution requests processed by Worker B (Actor node)."""
    tool_name: str = Field(..., description="Name of the target tool to invoke")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Arguments passed to the tool")
    execution_context: str = Field(default="INCIDENT_REMEDIAL", description="Context tag for audit trail")
    safety_level: str = Field(default="SAFE", description="Permission safety level: SAFE, SENSITIVE, DESTRUCTIVE")


class ValidationResult(BaseModel):
    """Output from Worker C (Validator node) assessing system stability after tool action."""
    is_valid: bool = Field(..., description="Whether the patch passed all invariant health checks")
    health_check_passed: bool = Field(..., description="System health metrics check result")
    invariant_errors: List[str] = Field(default_factory=list, description="List of structural invariant violations if any")
    rollback_required: bool = Field(default=False, description="Flag indicating if action must be rolled back")


class TelemetryLog(BaseModel):
    """Structured telemetry span scrubbed by Student 5 Global Graph Layer."""
    span_id: str = Field(..., description="Unique telemetry span ID")
    node_name: str = Field(..., description="Originating graph node")
    raw_payload: str = Field(..., description="Payload content before/after scrubbing")
    contains_pii_redaction: bool = Field(default=False, description="Flag indicating if PII was scrubbed")
    redacted_keys: List[str] = Field(default_factory=list, description="List of keys or patterns redacted")


class AgentState(BaseModel):
    """
    Universal Graph State Contract shared across all nodes and edge routers.
    Maintains complete state lifecycle for the incident response pipeline.
    """
    task_domain: str = Field(default="Autonomous Incident Response", description="High-stakes domain identifier")
    raw_input: str = Field(..., description="Initial task prompt / alert payload")
    round_number: int = Field(default=0, description="Current execution round counter for loop prevention")
    is_validated: bool = Field(default=False, description="State validation flag from Worker C")
    error_log: Optional[str] = Field(default=None, description="Active error message for self-healing retries")
    retry_count: int = Field(default=0, description="Analyzer retry count for schema failure recovery")
    max_retries: int = Field(default=3, description="Maximum allowed self-healing retries")
    
    # State Payloads
    analysis_payload: Dict[str, Any] = Field(default_factory=dict, description="Structured analysis from Worker A")
    sanitized_tool_calls: List[str] = Field(default_factory=list, description="Validated tool call names from Worker B")
    executed_tools: List[Dict[str, Any]] = Field(default_factory=list, description="Execution records from Worker B")
    validation_result: Dict[str, Any] = Field(default_factory=dict, description="Validation output from Worker C")
    
    # Message Context & Tracing
    messages: List[Dict[str, Any]] = Field(default_factory=list, description="Chat/event message history")
    telemetry_logs: List[Dict[str, Any]] = Field(default_factory=list, description="Scrubbed telemetry spans")
    
    # Execution Lifecycle
    system_status: str = Field(default="INIT", description="Graph state: INIT, ANALYZING, PATCHING, VALIDATING, SUCCESS, FAILED, TIMEOUT_SAFEGUARD")
    final_report: Optional[str] = Field(default=None, description="Final output report generated for the user")
