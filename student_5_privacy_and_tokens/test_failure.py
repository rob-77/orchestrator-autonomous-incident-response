"""
student_5_privacy_and_tokens/test_failure.py
Reproduction script for Student 5/6:
  - Telemetry Privacy Leak vs Redaction Guardrail
  - Context Token Explosion vs Pruner Guardrail
"""

import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from student_5_privacy_and_tokens.snippet import (
    MAX_TOKEN_THRESHOLD,
    count_remaining_leaks,
    estimate_cost_usd,
    estimate_latency_seconds,
    estimate_message_tokens,
    prune_context_window,
    redact_telemetry_payload,
)


SENSITIVE_LOG = (
    "INCIDENT ALERT: Database postgres://admin:SuperSecretPassword123@10.0.0.15:5432/prod_db timeout. "
    "API Key: secret_api_key_9988776655443322. User SSN: 123-45-6789. "
    "Auth Token: Bearer eyJhbGciOiJIUzI1NiIn..."
)


def build_bloated_messages():
    messages = [{"role": "user", "content": "Initial incident alert description..."}]
    for i in range(1, 12):
        messages.append({
            "role": "assistant",
            "content": (
                f"Intermediate step {i} execution log with verbose debug outputs "
                f"and detailed tool response payloads: {'x' * 250}"
            ),
        })
    return messages


def test_telemetry_privacy(enable_guardrail: bool) -> dict:
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
        return {"leaked": baseline_leaks, "redacted_labels": []}

    print("\nPassing payload through Student 5 Telemetry Privacy Redactor...")
    scrubbed_log, count, labels = redact_telemetry_payload(SENSITIVE_LOG)
    remaining = count_remaining_leaks(scrubbed_log)

    print(f"\nSUCCESSFUL GUARDRAIL INTERCEPT: Redacted {count} secret patterns ({labels})!")
    print(f"Scrubbed Payload Output:\n{scrubbed_log}")
    print(f"METRIC (guardrail ON): Leaked Secrets = {remaining} (was {baseline_leaks})")

    assert count == 4, f"Expected 4 primary redactions, got {count}"
    assert remaining == 0, f"Expected 0 remaining leaks, found {remaining} in: {scrubbed_log}"
    print("ASSERT OK: metrics match — leaked secrets 4 → 0")
    return {"leaked": remaining, "redacted_labels": labels}


def test_context_token_explosion(enable_guardrail: bool) -> dict:
    print(f"\n--- PART 2: Context Window Token Explosion Test (Guardrail: {enable_guardrail}) ---")
    bloated_messages = build_bloated_messages()
    before_tokens = estimate_message_tokens(bloated_messages)

    if not enable_guardrail:
        cost = estimate_cost_usd(before_tokens)
        latency = estimate_latency_seconds(before_tokens)
        print(f"Unguarded Chat History Length: {len(bloated_messages)} messages")
        print(f"Total Token Count: {before_tokens} tokens")
        print(f"Estimated Cost per Turn: ${cost:.4f}")
        print(f"Estimated Turn Latency: {latency:.2f}s")
        print(
            "\n[FAILURE DEMONSTRATION]: Context Window Explosion! "
            "High token count driving up latency and cost."
        )
        return {
            "messages": len(bloated_messages),
            "tokens": before_tokens,
            "cost": cost,
            "latency": latency,
        }

    pruned_msgs, before_t, after_t = prune_context_window(
        bloated_messages, max_token_threshold=MAX_TOKEN_THRESHOLD
    )
    savings_pct = ((before_t - after_t) / before_t) * 100
    cost = estimate_cost_usd(after_t)
    latency = estimate_latency_seconds(after_t)

    print("\nSUCCESSFUL GUARDRAIL INTERCEPT: Pruned Chat History!")
    print(f"Original Messages: {len(bloated_messages)} ({before_t} tokens)")
    print(f"Pruned Messages: {len(pruned_msgs)} ({after_t} tokens)")
    print(f"Token Reduction: -{savings_pct:.1f}%")
    print(f"Estimated Cost per Turn: ${cost:.4f}")
    print(f"Estimated Turn Latency: {latency:.2f}s")

    assert before_t > MAX_TOKEN_THRESHOLD
    assert after_t < before_t
    assert after_t <= 220, f"Expected post-prune <= 220 target, got {after_t}"
    assert 3 <= len(pruned_msgs) <= 4
    return {
        "messages": len(pruned_msgs),
        "tokens": after_t,
        "tokens_before": before_t,
        "cost": cost,
        "latency": latency,
        "savings_pct": savings_pct,
    }


def print_summary(privacy_off, privacy_on, tokens_off, tokens_on):
    savings = tokens_on["savings_pct"]
    savings_label = f"-{savings:.1f}%"
    print("\n==================================================")
    print("  SUMMARY TABLE (see metrics.md)")
    print("==================================================")
    print(
        f"{'Metric':<32} {'Baseline (OFF)':>16} {'Guardrail (ON)':>16} {'Delta':>14}"
    )
    print("-" * 82)
    print(
        f"{'Leaked secrets':<32} {privacy_off['leaked']:>16} "
        f"{privacy_on['leaked']:>16} {'4 → 0':>14}"
    )
    print(
        f"{'Messages in window':<32} {tokens_off['messages']:>16} "
        f"{tokens_on['messages']:>16} "
        f"{str(tokens_off['messages']) + ' → ' + str(tokens_on['messages']):>14}"
    )
    print(
        f"{'Estimated tokens / turn':<32} {tokens_off['tokens']:>16} "
        f"{tokens_on['tokens']:>16} {savings_label:>14}"
    )
    print(
        f"{'Estimated cost / turn':<32} ${tokens_off['cost']:>15.4f} "
        f"${tokens_on['cost']:>15.4f} {savings_label:>14}"
    )
    print(
        f"{'Estimated latency / turn':<32} {tokens_off['latency']:>15.2f}s "
        f"{tokens_on['latency']:>15.2f}s {savings_label:>14}"
    )
    print(f"\nMETRIC -> Leaked secrets: {privacy_off['leaked']} -> {privacy_on['leaked']}")
    print(
        f"METRIC -> Tokens per turn: {tokens_off['tokens']} -> {tokens_on['tokens']} "
        f"({savings_label})"
    )


if __name__ == "__main__":
    print("==================================================")
    print("  1. TESTING FAILURE MODES (Guardrails DISABLED)")
    print("==================================================")
    privacy_off = test_telemetry_privacy(enable_guardrail=False)
    tokens_off = test_context_token_explosion(enable_guardrail=False)

    print("\n==================================================")
    print("  2. TESTING GUARDRAIL MITIGATIONS (Guardrails ENABLED)")
    print("==================================================")
    privacy_on = test_telemetry_privacy(enable_guardrail=True)
    tokens_on = test_context_token_explosion(enable_guardrail=True)

    print_summary(privacy_off, privacy_on, tokens_off, tokens_on)
