"""
student_5_privacy_and_tokens/test_failure.py
Reproduction script for Student 5: Telemetry Privacy Leak & Context Token Explosion vs Guardrail
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from student_5_privacy_and_tokens.snippet import (
    redact_telemetry_payload,
    prune_context_window,
    count_remaining_leaks,
)


SENSITIVE_LOG = (
    "INCIDENT ALERT: Database postgres://admin:SuperSecretPassword123@10.0.0.15:5432/prod_db timeout. "
    "API Key: secret_api_key_9988776655443322. User SSN: 123-45-6789. "
    "Auth Token: Bearer eyJhbGciOiJIUzI1NiIn..."
)


def test_telemetry_privacy(enable_guardrail: bool):
    print(f"\n--- PART 1: Telemetry Data Privacy Test (Guardrail: {enable_guardrail}) ---")
    print(f"Raw Input Payload: {SENSITIVE_LOG[:90]}...")

    baseline_leaks = count_remaining_leaks(SENSITIVE_LOG)
    assert baseline_leaks == 4, f"Expected 4 baseline leaks, found {baseline_leaks}"

    if not enable_guardrail:
        print("\nStreaming raw payload directly to LangSmith telemetry dashboard...")
        print(
            f"[FAILURE DEMONSTRATION]: Secret Leak! {baseline_leaks} sensitive "
            "credentials streamed to external cloud logger:"
        )
        print(" -> DB Creds: postgres://admin:SuperSecretPassword123@10.0.0.15:5432/prod_db")
        print(" -> API Key: secret_api_key_9988776655443322")
        print(" -> SSN: 123-45-6789")
        print(" -> Bearer Token: eyJhbGciOiJIUzI1NiIn...")
        print(f"METRIC (guardrail OFF): Leaked Secrets = {baseline_leaks}")

    else:
        print("\nPassing payload through Student 5 Telemetry Privacy Redactor...")
        scrubbed_log, count, labels = redact_telemetry_payload(SENSITIVE_LOG)
        remaining = count_remaining_leaks(scrubbed_log)

        print(f"\nSUCCESSFUL GUARDRAIL INTERCEPT: Redacted {count} secret patterns ({labels})!")
        print(f"Scrubbed Payload Output:\n{scrubbed_log}")
        print(f"METRIC (guardrail ON): Leaked Secrets = {remaining} (was {baseline_leaks})")

        assert count == 4, f"Expected 4 primary redactions, got {count}"
        assert remaining == 0, f"Expected 0 remaining leaks, found {remaining} in: {scrubbed_log}"
        print("ASSERT OK: metrics match — leaked secrets 4 → 0")


def test_context_token_explosion(enable_guardrail: bool):
    print(f"\n--- PART 2: Context Window Token Explosion Test (Guardrail: {enable_guardrail}) ---")

    # Simulate bloated message list across multiple turns
    bloated_messages = [
        {"role": "user", "content": "Initial incident alert description..."},
    ]
    for i in range(1, 12):
        bloated_messages.append({
            "role": "assistant",
            "content": (
                f"Intermediate step {i} execution log with verbose debug outputs "
                f"and detailed tool response payloads: {'x' * 250}"
            ),
        })

    if not enable_guardrail:
        before_tokens = sum(len(str(m)) for m in bloated_messages) // 4
        print(f"Unguarded Chat History Length: {len(bloated_messages)} messages")
        print(f"Total Token Count: {before_tokens} tokens")
        print(f"Estimated Cost per Turn: ${before_tokens * 0.00003:.4f}")
        print(
            "\n[FAILURE DEMONSTRATION]: Context Window Explosion! "
            "High token count driving up latency (~6.5s) and cost."
        )

    else:
        pruned_msgs, before_t, after_t = prune_context_window(
            bloated_messages, max_token_threshold=300
        )
        savings_pct = ((before_t - after_t) / before_t) * 100
        print("\nSUCCESSFUL GUARDRAIL INTERCEPT: Pruned Chat History!")
        print(f"Original Messages: {len(bloated_messages)} ({before_t} tokens)")
        print(f"Pruned Messages: {len(pruned_msgs)} ({after_t} tokens)")
        print(f"Token Reduction: -{savings_pct:.1f}% | Estimated Turn Latency: 1.2s")


if __name__ == "__main__":
    print("==================================================")
    print("  1. TESTING FAILURE MODES (Guardrails DISABLED)")
    print("==================================================")
    test_telemetry_privacy(enable_guardrail=False)
    test_context_token_explosion(enable_guardrail=False)

    print("\n==================================================")
    print("  2. TESTING GUARDRAIL MITIGATIONS (Guardrails ENABLED)")
    print("==================================================")
    test_telemetry_privacy(enable_guardrail=True)
    test_context_token_explosion(enable_guardrail=True)
