# 5-Minute Team Demo Script

**Record with:** `python main_system.py --video-all --step`  
**Press ENTER** when the terminal prompts you — finish the line you're on, then hit ENTER.

Say the quoted lines out loud. Stage directions in *(italics)* are for you, not the mic.

---

## 0:00–1:00 — Use case & architecture

*(Banner is on screen. Do **not** press ENTER yet.)*

> Hi — this is EDS 6397 Team 1.
>
> We built a task orchestrator for autonomous incident response. The flow is monitor, diagnose, patch, validate, and report on enterprise server outages.
>
> Stakes are high here. A bad agent action can wipe production data, leak secrets, or burn unbounded API spend. That's what we're trying to prevent with this architecture.
>
> We have one coordinator that dynamically routes between worker agents — an analyzer, an actor, a validator, and a reporter — over a frozen Pydantic contract in contract.py.
>
> We also built six code-based guardrails — not soft prompts — for loop limits, schema retries, tool whitelists, cascade validation, privacy redaction, and context pruning.
>
> And just to be clear: every infrastructure call in this demo is a safe mock. Nothing touches real systems.

*(Press ENTER → Segment 1 starts)*

---

## 1:00–2:00 — Happy path

> First, we'll show a happy path.
>
> Here's a clean alert on auth-service-v2. Watch the graph move: coordinator to analyzer, to actor, to validator, to reporter.
>
> The analyzer structures the incident, the actor runs an approved restart_service mock, the validator passes the invariants, and we get a final report. Status is success. Zero external side effects.

*(Press ENTER → Segment 2 starts)*

---

## 2:00–3:30 — Combined pressure

*(The terminal will pause on each punchline. Say the matching line, then press ENTER.)*

> Next, a pressure scenario. Same system, but now the alert is under attack — secrets in the payload, a corrupted schema, and a rogue tool request, all at once.
>
> First, privacy. You can see the bearer token, database credentials, API key, and SSN get scrubbed before anything goes to telemetry. Four sensitive categories — zero leaks.
>
*(ENTER)*
>
> Next, context. The message history was bloated, so our context guardrail pruned it — roughly thirteen hundred tokens down to about two hundred — so loops stay cheap.
>
*(ENTER)*
>
> Next, schema. The structured output comes back invalid. We catch that, retry once, and recover a valid incident analysis.
>
*(ENTER)*
>
> And finally, rogue tools. The model asks for delete_database. Our permission matrix blocks it. Nothing destructive runs. We fail safe and route straight to the reporter.

*(Press ENTER → Segment 3 starts)*

---

## 3:30–4:30 — Recovery loop

> Last scenario: a recovery loop. This is where you really see dynamic routing under persistent failure — a LOOP_STORM.
>
> The validator rejects bad downstream state, triggers a safe mock rollback, and sends us back to the coordinator. No crash, no corrupt report.
>
*(ENTER)*
>
> That reject-and-reroute cycle keeps repeating. Context stays pruned as we go.
>
*(ENTER)*
>
> Then the loop guardrail kicks in. Once we hit round number five, the coordinator short-circuits to the reporter with a timeout safeguard. Bounded spend, graceful degrade, no deadlock.

---

## 4:30–5:00 — Close on metrics

*(Metrics snapshot is on screen.)*

> So, quick before and after: unbounded loops become five rounds max. Invalid schema gets one retry and recovers. Rogue tools go from executed to zero. Cascade crashes go to zero with mock rollback. Secrets go to zero leaks. And context drops by about seventy-eight percent.
>
> One integrated LangGraph state machine, six active guardrails, contract-first design. That's the system.

**End recording.**
