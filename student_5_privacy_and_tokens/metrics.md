# Student 5 & 6 — Privacy Redaction & Context Token Guardrails: Metrics

## Test Environment
- Script: `student_5_privacy_and_tokens/test_failure.py`
- Domain: Autonomous Incident Response telemetry + multi-turn message windows
- Token estimate: `len(json.dumps(message)) // 4` (deterministic; no live LLM required)
- Cost model: `$0.00003` per estimated input token (illustrative)
- Latency model: `6 ms` per estimated input token (illustrative prefill stand-in)
- Context prune threshold: `MAX_TOKEN_THRESHOLD = 300` (shared with `main_system.py`)

## Results — Section 5: Telemetry Privacy Leak

| Metric | Guardrail Disabled (Baseline) | Guardrail Enabled (Optimized) | Delta / Impact |
|---|---|---|---|
| **Leaked secrets / PII markers** | 4 | 0 | **-100% leak risk** |
| **Primary classes scrubbed** | 0 (raw stream) | 4 (`db_creds`, `api_key`, `ssn`, `bearer_token`) | Full interceptor coverage |
| **Telemetry privacy compliance** | 0% | 100% | Export-safe spans only |

**Headline metric: Leaked secrets 4 → 0.**

Baseline leak markers intentionally planted in the incident payload:
1. DB password (`SuperSecretPassword123`)
2. API key (`secret_api_key_9988776655443322`)
3. SSN (`123-45-6789`)
4. Bearer/JWT fragment (`eyJhbGciOiJIUzI1NiIn…`)

## Results — Section 6: Context Window Explosion

| Metric | Guardrail Disabled (Baseline) | Guardrail Enabled (Optimized) | Delta / Impact |
|---|---|---|---|
| **Message window size** | 12 messages | 4 messages | History condensed |
| **Estimated tokens / turn** | 1,073 | 240 | **-77.6% token spend** |
| **Estimated cost / turn** | $0.0322 | $0.0072 | **-77.6% cost** |
| **Estimated turn latency** | 6.44 s | 1.44 s | **-77.6% latency** |

**Headline metric: Tokens per turn 1,073 → 240 (−77.6%).**

## Notes on Methodology
- Privacy and token figures above are produced by the deterministic reproduction script — they are not pulled from a live LangSmith invoice. Swap in real LangSmith token/cost numbers for the team demo video if available.
- Latency is a proportional estimate from token count (`tokens × 6 ms`), chosen so before/after comparisons stay reproducible without network calls.
- IP addresses are also scrubbed as an auxiliary pattern but are **not** counted in the 4 → 0 primary-secret metric.
- Operational `AgentState.raw_input` retains the original incident text for diagnosis; only telemetry export payloads are redacted before leaving the graph.

## How to Reproduce
```bash
python student_5_privacy_and_tokens/test_failure.py
```
Both failure (guardrail off) and mitigation (guardrail on) runs execute automatically and print a side-by-side summary table at the end.
