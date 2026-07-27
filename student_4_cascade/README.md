# Student 4: Downstream Cascade Failure Guardrail

## Role

**Worker C: Validator Node**

Worker C is positioned between Worker B (Actor) and all downstream reporting or application layers. Its responsibility is to verify that the execution result matches the Analyzer's original intent before the incident can be marked as resolved.

## Failure Mode

Worker B may produce malformed, incomplete, contradictory, or unauthorized execution state. Without a validation layer, downstream code may assume that required fields exist and that an action succeeded.

The deterministic baseline demonstrates two types of downstream cascade failure:

1. **Runtime crashes** caused by missing fields such as `output` or `executed_params`.
2. **Silent corruption** where failed, unauthorized, or mismatched execution records reach downstream code without raising an exception.

In the unguarded baseline, all 9 invalid states reached the downstream consumer. Three caused runtime crashes, while six silently propagated incorrect state.

## Programmatic Guardrail

The function `validate_downstream_state_guardrail()` implements a code-based Validation and Sanitization Node using the frozen `AgentState` and `ValidationResult` Pydantic contracts.

The Validator checks the following structural and semantic invariants:

1. `analysis_payload` must contain a non-empty `service_id`.
2. `analysis_payload` must contain a non-empty `recommended_action`.
3. At least one Actor execution record must exist.
4. The execution record must contain all required fields.
5. The execution status must equal `SUCCESS`.
6. The executed tool must match the recommended action.
7. The recommended action must exist in `sanitized_tool_calls`.
8. `executed_params` must be a dictionary.
9. The executed service must match the analyzed service.
10. Execution output must be a non-empty string.
11. The safety level must be either `SAFE` or `SENSITIVE`.

If any invariant fails, the Validator:

- returns `is_valid=False`;
- returns `health_check_passed=False`;
- records all invariant violations;
- sets `rollback_required=True`;
- prevents the corrupted state from reaching downstream reporting;
- triggers only a **safe mocked rollback**;
- routes the graph back through the Coordinator for recovery.

No real infrastructure rollback, file modification, database action, or destructive command is executed.

## Quantitative Metrics

The metrics below were produced by 10 deterministic scenarios: one valid Actor state and nine invalid Actor states.

| Metric | Guardrail Disabled | Guardrail Enabled | Impact |
|---|---:|---:|---:|
| Invalid states reaching downstream | 9/9 (100.0%) | 0/9 (0.0%) | 100% invalid-state isolation |
| Downstream runtime crashes | 3 | 0 | 100% crash elimination |
| Silent corrupted-state propagations | 6 | 0 | 100% silent-failure elimination |
| Invalid states correctly blocked | 0/9 | 9/9 (100.0%) | 100% rejection coverage |
| Valid states correctly accepted | Not validated | 1/1 (100.0%) | Valid execution preserved |
| False negatives | Not measured | 0 | Team target achieved |
| False positives | Not measured | 0 | No valid-state rejection |
| Safe mock rollbacks | 0 | 9 | Graceful recovery enabled |
| Overall validation accuracy | Not applicable | 100.0% | Exceeds 95% target |

## Integrated LangGraph Behavior

The isolated guardrail is imported into `main_system.py` and executed inside `worker_c_validator_node()`.

The integrated cascade scenario follows this routing path:

```text
Coordinator
    |
    v
Analyzer
    |
    v
Actor
    |
    v
Validator detects downstream health failure
    |
    v
Safe mock rollback
    |
    v
Coordinator re-analysis
    |
    v
Actor retry
    |
    v
Validator passes
    |
    v
Reporter
```

Observed integrated result:

```text
system_status: SUCCESS
is_validated: True
round_number: 2
rollback_count: 1
```

This confirms that the graph handles corrupted or failed downstream state without crashing or deadlocking.

## Files

```text
student_4_cascade/
|-- snippet.py
|-- test_failure.py
`-- README.md
```

- `snippet.py`: Isolated structural and semantic invariant guardrail.
- `test_failure.py`: Deterministic unguarded-versus-guarded reproduction and metrics.
- `README.md`: Failure analysis, metrics, integration description, and video guide.

## How to Run

From the repository root:

```bash
python student_4_cascade/test_failure.py
```

Run the full integrated graph:

```bash
python main_system.py
```

## Expected Test Summary

```text
Invalid states reaching downstream: 9/9 (100.0%) -> 0/9 (0.0%)
Downstream runtime crashes: 3 -> 0
Silent corrupted-state propagations: 6 -> 0
Invalid states blocked by guardrail: 9/9 (100.0%)
Valid-state pass rate: 1/1 (100.0%)
False negatives: 0
False positives: 0
Safe mock rollbacks triggered: 9
Overall validation accuracy: 100.0%

All Student 4 deterministic guardrail assertions passed.
```
