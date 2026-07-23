from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional


class AgentState(BaseModel):
    task_domain: str = "Autonomous Incident Response"

    raw_input: str

    incident_id: Optional[str] = None

    incident_type: Optional[str] = None

    severity: Optional[str] = None

    analysis_payload: Dict[str, Any] = Field(default_factory=dict)

    validated: bool = False

    report: Optional[str] = None

    round_number: int = 0

    error_log: List[str] = Field(default_factory=list)

    messages: List[str] = Field(default_factory=list)

    telemetry: Dict[str, Any] = Field(default_factory=dict)

    tool_calls: List[Dict[str, Any]] = Field(default_factory=list)
              # raw, as requested by LLM
    sanitized_tool_calls: List[Dict[str, Any]] = Field(default_factory=list) # post-guardrail, approved only

    affected_service: Optional[str] = None

    patch_action: Optional[str] = None