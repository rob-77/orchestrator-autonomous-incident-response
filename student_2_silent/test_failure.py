"""
student_2_silent/test_failure.py
Reproduction script for Student 2: Silent Hallucination & Structural Failure vs Guardrail
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from contract import AgentState
from student_2_silent.snippet import parse_incident_with_schema_guardrail


def run_simulation(enable_guardrail: bool):
    print(f"\n==================================================")
    print(f"  RUNNING SILENT HALLUCINATION SIMULATION (Guardrail: {enable_guardrail})")
    print(f"==================================================")

    malformed_input = "MALFORMED ALERT: Server down, please check logs."

    if not enable_guardrail:
        # UNGUARDRAILED NAIVE PARSING: Returns unvalidated dict missing critical fields
        raw_output = {"service_id": "auth-service-v2", "notes": "Server down"}
        print(f"Worker A Raw Output: {raw_output}")

        try:
            # Simulate downstream code attempting to read error_code
            error_code = raw_output["error_code"]
            action = raw_output["recommended_action"]
            print(f"Downstream Action Executed: {action}")
        except KeyError as e:
            print(f"\n[FAILURE DEMONSTRATION]: Silent Hallucination / Missing Schema Field!")
            print(f"CRASH LOG: KeyError: {e}. Worker A produced unvalidated text that broke downstream logic.")

    else:
        # GUARDRAILED PARSING: Enforces schema validation and self-correcting retry loop
        retry = 0
        max_retries = 3

        while retry <= max_retries:
            try:
                print(f"Attempt {retry + 1}: Executing Worker A with Schema Guardrail...")
                # On retry > 0, simulate self-corrected prompt payload
                payload = malformed_input if retry == 0 else "CORRECTED ALERT: ERR_MEM_LEAK_503 on auth-service-v2"
                
                analysis = parse_incident_with_schema_guardrail(payload, current_retry=retry, max_retries=max_retries)
                print(f"\nSUCCESSFUL RECOVERY: Schema Validated!")
                print(f"Structured Analysis: Service={analysis.service_id}, Code={analysis.error_code}, Action={analysis.recommended_action}")
                break

            except ValueError as exc:
                print(f" -> Guardrail Intercepted Error: {exc}")
                retry += 1
                print(f" -> Self-Healing Graph Routing: Retrying Worker A with error context (Retry {retry}/{max_retries})...")


if __name__ == "__main__":
    print("--- 1. Testing Failure Mode (Guardrail DISABLED) ---")
    run_simulation(enable_guardrail=False)

    print("\n--- 2. Testing Guardrail Mitigated Execution (Guardrail ENABLED) ---")
    run_simulation(enable_guardrail=True)
