"""
student_5_privacy_and_tokens/snippet.py
Student 5: Global Graph Layer - Telemetry Privacy & Context Token Pruning Guardrails
(Combined Section 5 & 6 for 5-Student Team Structure)
"""

import re
import json
from typing import List, Dict, Any, Tuple


# ============================================================================
# SHARED GUARDRAIL CONSTANTS (used by snippet tests + main_system)
# ============================================================================

# Assignment: prune when message-window token estimate exceeds this threshold.
MAX_TOKEN_THRESHOLD = 300

# Illustrative cost model for deterministic metrics (not a live LLM bill).
COST_PER_TOKEN_USD = 0.00003

# Latency model: ~6 ms per input token as a stand-in for LLM prefill cost.
LATENCY_MS_PER_TOKEN = 6.0


# ============================================================================
# PART 1: TELEMETRY DATA PRIVACY REDACTION INTERCEPTOR (SECTION 5)
# ============================================================================

# Four primary secret classes counted toward the 4 → 0 leak metric.
# Order matters: redact credentials/tokens before residual host identifiers.
PRIMARY_PII_PATTERNS: List[Tuple[str, str, str]] = [
    # 1. Database connection credentials
    (
        r"(?i)(postgres|mysql|mongodb)://[^:\s]+:[^@\s]+@",
        r"\1://[REDACTED_CREDS]@",
        "db_creds",
    ),
    # 2. API keys / labeled secrets ("API Key:", "api_key=", "password:", …)
    #    Allows whitespace in labels: "API Key" — previously leaked.
    (
        r"(?i)(api\s*[_-]?\s*key|secret|password)\s*[:=]\s*[\"']?[A-Za-z0-9_\-.]{12,}[\"']?",
        r"\1: [REDACTED_SECRET]",
        "api_key",
    ),
    # 3. Social Security Numbers
    (
        r"\b\d{3}-\d{2}-\d{4}\b",
        r"[REDACTED_SSN]",
        "ssn",
    ),
    # 4. Bearer / JWT auth tokens (case-insensitive — previously leaked)
    (
        r"(?i)bearer\s+[A-Za-z0-9_\-.=]+",
        r"Bearer [REDACTED_TOKEN]",
        "bearer_token",
    ),
]

# Auxiliary scrubbers (still applied; not counted toward the 4-secret metric)
AUX_PII_PATTERNS: List[Tuple[str, str]] = [
    (
        r"\b(?:(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\b",
        r"[REDACTED_IP]",
    ),
]

# Canonical leak substrings used by tests to prove residual exposure
KNOWN_LEAK_MARKERS = [
    "SuperSecretPassword123",
    "secret_api_key_9988776655443322",
    "123-45-6789",
    "eyJhbGciOiJIUzI1NiIn",
]


def count_remaining_leaks(text: str) -> int:
    """Return how many of the known secret markers are still present in text."""
    return sum(1 for marker in KNOWN_LEAK_MARKERS if marker in text)


def redact_telemetry_payload(raw_text: str) -> Tuple[str, int, List[str]]:
    """
    PROGRAMMATIC GUARDRAIL (Section 5):
    Intercepts metadata and state payloads prior to streaming to external
    observability platforms (e.g. LangSmith). Scrubs API keys, passwords,
    DB credentials, bearer tokens, IP addresses, and SSNs.

    Returns:
        (scrubbed_text, primary_redaction_count, redacted_labels)
        primary_redaction_count is the 4-class metric (db/api/ssn/bearer).
    """
    redacted_text = raw_text
    redacted_labels: List[str] = []

    for pattern, replacement, label in PRIMARY_PII_PATTERNS:
        if re.search(pattern, redacted_text):
            redacted_text = re.sub(pattern, replacement, redacted_text)
            redacted_labels.append(label)

    for pattern, replacement in AUX_PII_PATTERNS:
        redacted_text = re.sub(pattern, replacement, redacted_text)

    return redacted_text, len(redacted_labels), redacted_labels


def build_scrubbed_telemetry_span(
    span_id: str,
    node_name: str,
    raw_payload: str,
) -> Dict[str, Any]:
    """
    Centralized telemetry interceptor used by every graph node before any
    external observability export. Always stores the scrubbed payload only.
    """
    scrubbed_text, count, labels = redact_telemetry_payload(raw_payload)
    return {
        "span_id": span_id,
        "node_name": node_name,
        "raw_payload": scrubbed_text,
        "contains_pii_redaction": count > 0,
        "redacted_keys": labels,
    }


# ============================================================================
# PART 2: CONTEXT WINDOW EXPLOSION & TOKEN PRUNER INTERCEPTOR (SECTION 6)
# ============================================================================

def estimate_message_tokens(messages: List[Dict[str, Any]]) -> int:
    """Deterministic token estimate: ~1 token per 4 characters of JSON."""
    return sum(len(json.dumps(m)) for m in messages) // 4


def estimate_cost_usd(token_count: int) -> float:
    return token_count * COST_PER_TOKEN_USD


def estimate_latency_seconds(token_count: int) -> float:
    return (token_count * LATENCY_MS_PER_TOKEN) / 1000.0


def prune_context_window(
    messages: List[Dict[str, Any]],
    max_token_threshold: int = MAX_TOKEN_THRESHOLD,
) -> Tuple[List[Dict[str, Any]], int, int]:
    """
    PROGRAMMATIC GUARDRAIL (Section 6):
    Monitors message list token length before routing turns.
    If total tokens exceed max_token_threshold, prunes intermediate execution logs
    and condenses message chain while retaining initial prompt and latest context.
    """
    before_tokens = estimate_message_tokens(messages)

    if before_tokens <= max_token_threshold or len(messages) <= 3:
        return messages, before_tokens, before_tokens

    first_msg = messages[0]
    last_two = messages[-2:]
    condensed = [
        first_msg,
        {
            "role": "system",
            "content": (
                f"[STUDENT 5/6 GUARDRAIL]: Summarized {len(messages) - 3} "
                "intermediate message steps to preserve token budget."
            ),
        },
    ] + last_two

    after_tokens = estimate_message_tokens(condensed)
    return condensed, before_tokens, after_tokens


def apply_context_guardrail(
    messages: List[Dict[str, Any]],
    max_token_threshold: int = MAX_TOKEN_THRESHOLD,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Loop-transition entrypoint for Student 6. Returns pruned messages plus a
    small metrics dict the graph can optionally log/print.
    """
    pruned, before_t, after_t = prune_context_window(messages, max_token_threshold)
    return pruned, {
        "tokens_before": before_t,
        "tokens_after": after_t,
        "pruned": before_t > after_t,
        "threshold": max_token_threshold,
    }
