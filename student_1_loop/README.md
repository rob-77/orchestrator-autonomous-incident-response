# Student 1: Infinite Graph Loops Guardrail

## Role

**Coordinator Node**

## 🏛️ System Architecture & Dynamic Routing Topology

```
                         ┌─────────────────────────────────────────┐
                         ▼                                         │ (Loop / Self-Correction)
               [ 0. Coordinator Node ] ────────────────────────────┼──────────────────┐
                  │ (Student 1)  ▲                                 │                  │
                  │ (Route A)    │ (Error Flag)                    │ (Route B)        │ (Route C)
                  ▼              │                                 ▼                  ▼
     [ 1. Worker A: Analyzer ] ──┘                      [ 2. Worker B: Actor ]   [ 4. Worker D: Reporter ]
        (Student 2)                                        (Student 3)                (Final Output)
                  │                                                │
                  │ (Valid Schema)                                 │ (Execution State)
                  ▼                                                ▼
     [ 5. Worker C: Validator Node ] ◄─────────────────────────────┘
        (Student 4)
                  │
                  └─► [ Global Graph Interceptors: Privacy & Tokens ] (Student 5)
```


Coordinator Node is positioned at the top before Worker A (Analyzer) and Worker D (Reporter); however, it also received loop/self-correction from Worker B (Actor) and error flag from Worder A (Analyzer). Its responsibility is to state routing, round tracking & loop control.

## Failure Mode Overview
In dynamic multi-agent architectures, non-deterministic LLM outputs or ambiguous validation criteria can cause the Coordinator node to re-route execution back to upstream worker nodes continuously. Without hard bounds, the graph enters an adversarial infinite loop, consuming massive token budgets and causing system deadlocks.

## Guardrail Implementation
The guardrail introduces a deterministic `round_number` counter bound directly into the LangGraph routing edge (`coordinator_route_guardrail`). When `state.round_number >= 5`, the edge short-circuits the normal routing topology and immediately routes to the `reporter` node with a `TIMEOUT_SAFEGUARD` status.

## Files

```text
student_1_loop/
|-- snippet.py
|-- test_failure.py
|-- metrics.md
`-- README.md
```

- `snippet.py`: Isolated structural and semantic invariant guardrail.
- `test_failure.py`: Deterministic unguarded-versus-guarded reproduction and metrics.
- `README.md`: Failure analysis, metrics, integration description, and video guide.
- `metrics.md`: Failure analysis, metrics, integration description, and video guide.


## Quantitative Metrics

| Metric | Guardrail Disabled (Baseline) | Guardrail Enabled (Optimized) | Delta / Impact |
|---|---|---|---|
| **Max Iterations Executed** | $\infty$ (Aborted at 20) | 5 Iterations | **100% Loop Bound Guaranteed** |
| **API Token Cost per Event** | $\$4.40$ (Runaway) | $\$0.11$ | **$-97.5\%$ Cost Reduction** |
| **Execution Latency** | $> 45.0\text{s}$ (Timeout) | $1.2\text{s}$ | **$-97.3\%$ Latency Drop** |
| **Graph Deadlock Risk** | HIGH (100% failure) | ZERO (0% failure) | **System Reliability Restored** |

## How to Run Reproduction Test

From the repository root:

```bash
python student_1_loop/test_failure.py
```
Run the full integrated graph:

```bash
python main_system.py
```

## Expected Test Summary

## Individual Demonstration Video

**Multi-Agent Failure Modes & Guardrails**

**Student:** Roberto Gomez  
**Demonstration:** Infinite Graph Loop Guardrail

[Watch the Combined Individual Demonstration Video] 

(https://drive.google.com/drive/folders/1FsxzfFzjbOi8PZ3ev-DDAVsS2ykiWZsp?usp=drive_link)
