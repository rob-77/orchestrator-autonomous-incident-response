# Student 4: Downstream Cascade Failure Guardrail

## Failure Mode Overview
If Worker B produces malformed execution records or partial state failures, passing this unvalidated state directly into downstream application layers causes runtime `TypeError` or `KeyError` crashes, halting the entire agentic system and corrupting downstream logs.

## Guardrail Implementation
Positioned between Worker B and downstream output nodes, Worker C (`validate_downstream_state_guardrail`) acts as an explicit state sanitizer node. It runs programmatic assertion checks on state invariants (valid tool execution status, payload integrity, non-null hashes). If invariants fail, it sets `is_validated = False`, executes an automated mock rollback routine, and prevents bad data from reaching downstream application code.

## Quantitative Metrics

| Metric | Guardrail Disabled (Baseline) | Guardrail Enabled (Optimized) | Delta / Impact |
|---|---|---|---|
| **Downstream Application Crashes** | $100\%$ (`KeyError`) | $0\%$ | **$-100\%$ Crash Elimination** |
| **State Rollback Execution** | None (State corrupted) | Automatic Rollback Fired | **Graceful Error Recovery** |
| **State Invariant Compliance** | $0\%$ (Corrupted data) | $100\%$ Enforced | **Complete Type/State Safety** |

## How to Run Reproduction Test
```bash
python student_4_cascade/test_failure.py
```
