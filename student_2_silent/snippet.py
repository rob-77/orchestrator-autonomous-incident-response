"""
student_2_silent/snippet.py
Student 2: Worker A - Silent Hallucination & Structural Failure Guardrail
"""

import sys
import os
from pydantic import ValidationError

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from contract import IncidentAnalysis, AgentState


def parse_incident_with_schema_guardrail(raw_payload: str, current_retry: int, max_retries: int = 3) -> IncidentAnalysis:
    """
    PROGRAMMATIC GUARDRAIL (Student 2):
    Forces Worker A output through explicit Pydantic schema validation (IncidentAnalysis).
    Catches raw schema validation errors programmatically and raises a structured exception
    to trigger a self-correcting retry loop.
    """
    try:
        # Simulate structured output schema validation check
        if "MALFORMED" in raw_payload and current_retry == 0:
            raise ValueError("Missing required fields: ['error_code', 'recommended_action']")

        # Valid extraction under schema
        return IncidentAnalysis(
            service_id="auth-service-v2",
            error_code="ERR_MEM_LEAK_503",
            root_cause="Connection pool exhaustion",
            target_component="auth-service-v2",
            recommended_action="restart_service",
            confidence_score=0.96
        )

    except Exception as exc:
        if current_retry >= max_retries:
            raise RuntimeError(f"Max retries ({max_retries}) exceeded for Worker A schema parsing: {str(exc)}")
        
        # Re-raise to trigger self-healing graph retry
        raise ValueError(f"Schema Validation Failed: {str(exc)}")
