"""
student_5_privacy_and_tokens/snippet.py
Student 5: Global Graph Layer - Telemetry Privacy & Context Token Pruning Guardrails
(Combined Section 5 & 6 for 5-Student Team Structure)
"""

import re
import json
from typing import List, Dict, Any, Tuple


# ============================================================================
# PART 1: TELEMETRY DATA PRIVACY REDACTION INTERCEPTOR (SECTION 5)
# ============================================================================

PII_PATTERNS = [
    (r'(?i)(api[_-]?key|secret|token|password)\s*[:=]\s*["\']?([a-zA-Z0-9_\-\.]{12,})["\']?', r'\1: [REDACTED_SECRET]'),
    (r'bearer\s+[a-zA-Z0-9_\-\.]{12,}', r'Bearer [REDACTED_TOKEN]'),
    (r'\b\d{3}-\d{2}-\d{4}\b', r'[REDACTED_SSN]'),
    (r'postgres://[^:]+:[^@]+@', r'postgres://[REDACTED_CREDS]@'),
    (r'\b(?:1\d{2}|2[0-4]\d|25[0-5]|\d{1,2})\.(?:1\d{2}|2[0-4]\d|25[0-5]|\d{1,2})\.(?:1\d{2}|2[0-4]\d|25[0-5]|\d{1,2})\.(?:1\d{2}|2[0-4]\d|25[0-5]|\d{1,2})\b', r'[REDACTED_IP]')
]

def redact_telemetry_payload(raw_text: str) -> Tuple[str, int]:
    """
    PROGRAMMATIC GUARDRAIL (Section 5):
    Intercepts metadata and state payloads prior to streaming to external
    observability platforms (e.g. LangSmith). Scrubs API keys, passwords,
    DB credentials, IP addresses, and SSNs.
    """
    redacted_text = raw_text
    redactions_count = 0

    for pattern, replacement in PII_PATTERNS:
        matches = re.findall(pattern, redacted_text)
        if matches:
            redactions_count += len(matches)
            redacted_text = re.sub(pattern, replacement, redacted_text)

    return redacted_text, redactions_count


# ============================================================================
# PART 2: CONTEXT WINDOW EXPLOSION & TOKEN PRUNER INTERCEPTOR (SECTION 6)
# ============================================================================

def prune_context_window(messages: List[Dict[str, Any]], max_token_threshold: int = 300) -> Tuple[List[Dict[str, Any]], int, int]:
    """
    PROGRAMMATIC GUARDRAIL (Section 6):
    Monitors message list token length before routing turns.
    If total tokens exceed max_token_threshold, prunes intermediate execution logs
    and condenses message chain while retaining initial prompt and latest context.
    """
    before_tokens = sum(len(json.dumps(m)) for m in messages) // 4

    if before_tokens <= max_token_threshold or len(messages) <= 3:
        return messages, before_tokens, before_tokens

    # Condense history
    first_msg = messages[0]
    last_two = messages[-2:]
    condensed = [
        first_msg,
        {
            "role": "system",
            "content": f"[STUDENT 5 GUARDRAIL]: Summarized {len(messages) - 3} intermediate message steps to preserve token budget."
        }
    ] + last_two

    after_tokens = sum(len(json.dumps(m)) for m in condensed) // 4
    return condensed, before_tokens, after_tokens
