# Student 5: Global Graph Layer — Telemetry Privacy & Context Token Pruner

*(Combined Sections 5 & 6 under Student 5 for the 5-student team structure)*

## Role

**Global Graph Layer** — privacy redaction (Section 5) + context/token management (Section 6)

## Failure Mode Overview

1. **Data Privacy Leak via Telemetry (Section 5):** Streaming graph executions to cloud observability (LangSmith) can leak API keys, DB credentials, bearer tokens, and SSNs into third-party storage.
2. **Context Window Explosion (Section 6):** Multi-turn coordinator loops accumulate redundant tool/debug messages in `state.messages`, driving token cost and latency up.

## Guardrail Implementation

- `redact_telemetry_payload` **/** `build_scrubbed_telemetry_span`**:** Centralized regex interceptor. Scrubs the four primary secret classes (DB creds, API keys, SSN, Bearer) plus auxiliary IPs **before** any telemetry span is appended.
- `prune_context_window` **/** `apply_context_guardrail`**:** Runs at coordinator loop transitions. If estimated tokens exceed `MAX_TOKEN_THRESHOLD` (300), keeps the first + last two messages and inserts a compact summary for the middle history.

Both helpers are imported by `main_system.py` so the isolated snippet and the integrated graph cannot drift.

## Files

```text
student_5_privacy_and_tokens/
|-- snippet.py       # Isolated guardrail implementations
|-- test_failure.py  # Unguarded vs guarded reproduction + summary table
|-- metrics.md       # Before/after quantitative baselines
`-- README.md
```



## Quantitative Metrics

See `[metrics.md](./metrics.md)` for full methodology and tables.


| Metric | Baseline (Off) | Guardrail (On) | Impact |
| --- | --- | --- | --- |
| Leaked secrets | 4 secrets | 0 secrets | −100% |
| Tokens / turn | 1,073 tokens | 240 tokens | −77.6% |
| Est. latency / turn | 6.44 s | 1.44 s | −77.6% |
| Est. cost / turn | $0.0322 | $0.0072 | −77.6% |




## How to Run Reproduction Test

From the repository root:

```bash
python student_5_privacy_and_tokens/test_failure.py
```

Run the full integrated graph (privacy + token guardrails active):

```bash
python main_system.py
```

