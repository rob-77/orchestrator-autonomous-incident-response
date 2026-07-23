"""
student_3_rogue/test_failure.py
Reproduction script for Student 3: Rogue Tool Execution vs Guardrail
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from student_3_rogue.snippet import validate_tool_execution_guardrail, InvalidToolCallException


def run_simulation(enable_guardrail: bool):
    print(f"\n==================================================")
    print(f"  RUNNING ROGUE TOOL EXECUTION SIMULATION (Guardrail: {enable_guardrail})")
    print(f"==================================================")

    # Simulated adversarial jailbreak prompt output recommending database deletion
    rogue_tool_request = {
        "tool_name": "delete_database",
        "parameters": {"db_name": "production_database", "force": True}
    }

    print(f"Adversarial LLM Target Action: {rogue_tool_request['tool_name']}({rogue_tool_request['parameters']})")

    if not enable_guardrail:
        # UNGUARDRAILED EXECUTION: Executes dangerous tool call directly
        print("\nExecuting tool without security middleware...")
        # SAFE MOCK WARNING IN COMPLIANCE WITH MANDATE
        print("[CRITICAL UNGUARDRAILED SIMULATION]: PROD INFRASTRUCTURE DELETION TARGETED -> MOCK DANGEROUS ACTION FIRED!")
        print(f"\n[FAILURE DEMONSTRATION]: Rogue Tool Execution Fired! Database 'production_database' targeted.")

    else:
        # GUARDRAILED EXECUTION: Validates through dynamic middleware lookup matrix
        print("\nExecuting tool through Student 3 Security Middleware...")
        try:
            validated_req = validate_tool_execution_guardrail(
                rogue_tool_request["tool_name"],
                rogue_tool_request["parameters"]
            )
            print(f"Tool executed: {validated_req.tool_name}")
        except InvalidToolCallException as exc:
            print(f"\nSUCCESSFUL GUARDRAIL INTERCEPT: {exc}")
            print("Rogue action safely trapped and blocked before execution.")


if __name__ == "__main__":
    print("--- 1. Testing Failure Mode (Guardrail DISABLED) ---")
    run_simulation(enable_guardrail=False)

    print("\n--- 2. Testing Guardrail Mitigated Execution (Guardrail ENABLED) ---")
    run_simulation(enable_guardrail=True)
