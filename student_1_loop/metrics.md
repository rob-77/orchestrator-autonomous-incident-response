# Student 1 — Infinite Graph Loop Guardrail: Metrics

## Test Environment
- Script: `student_1_loop/test_failure.py`
- Simulated per-round cost: $0.22/round (illustrative API token cost estimate)
- Simulated per-round processing delay: 0.06s (stand-in for an LLM call + tool round trip)
- Artificial hard stop for the unguarded run: 20 rounds (so the failure demo terminates instead of hanging forever)

## Results

| Metric | Guardrail Disabled (Baseline) | Guardrail Enabled (Optimized) | Delta / Impact |
|---|---|---|---|
| **Rounds executed** | 20 (artificially capped; unbounded in production) | 5 | **100% loop bound guaranteed** |
| **Terminated cleanly** | No — hit artificial cutoff, never reached `reporter` | Yes — routed to `reporter` at round 5 | Guardrail is the only path to clean termination |
| **Final `system_status`** | Stuck at `ANALYZING` | `TIMEOUT_SAFEGUARD` | State correctly reflects the safeguard fired |
| **Measured wall-clock latency** | 1.21s (to hit the 20-round artificial cutoff) | 0.30s | **-75% latency** |
| **Estimated token cost** | $4.40 (20 rounds × $0.22) | $1.10 (5 rounds × $0.22) | **-75% cost** |

## Notes on Methodology
- The $0.22/round figure and the 0.06s per-round delay are simulated stand-ins, not pulled from a live LLM API — this keeps the reproduction deterministic and mockable per the assignment's safety mandate. If your team's `main_system.py` logs real LangSmith trace costs/latencies, swap those in here for the team demo video to make the numbers fully authentic.
- In a real unguarded production run, rounds would continue indefinitely (no natural upper bound) — the 20-round cutoff here exists only so the demo script terminates and produces comparable numbers.
- The corrected guardrail-enabled cost is **$1.10**, not the $0.11 previously listed in the README (5 rounds × $0.22 = $1.10). The README's metrics table should be updated to match.

## How to Reproduce
```bash
python student_1_loop/test_failure.py
```
Both simulations run automatically and print a side-by-side summary table at the end.
