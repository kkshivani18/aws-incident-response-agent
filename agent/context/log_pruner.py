import os
import re
import json
from typing import List, Tuple, Dict, Any, Optional
from agent.context.budget import estimate_tokens, TokenBudget

# Routine endpoints that provide no root cause value during incidents
HEALTH_CHECK_PATTERNS = [
    re.compile(r"GET\s+/(health|healthz|live|ready|ping|metrics|status)\b", re.IGNORECASE),
    re.compile(r"ELB-HealthChecker", re.IGNORECASE),
    re.compile(r"kube-probe", re.IGNORECASE),
    re.compile(r"Amazon-Route53-Health-Check-Service", re.IGNORECASE),
    re.compile(r"status\s*[:=]\s*200\b", re.IGNORECASE),
    re.compile(r"\"statusCode\"\s*:\s*200\b", re.IGNORECASE),
]

# Signatures of prompt injection attempts inside untrusted logs
INJECTION_SIGNATURES = [
    re.compile(r"ignore\s+(all\s+)?(previous|prior)\s+instructions", re.IGNORECASE),
    re.compile(r"system\s*override", re.IGNORECASE),
    re.compile(r"disregard\s+(system|prior|all)\b", re.IGNORECASE),
    re.compile(r"output\s+proposed_action\s+as", re.IGNORECASE),
    re.compile(r"admin\s+override", re.IGNORECASE),
    re.compile(r"print\s+secret\s+keys?", re.IGNORECASE),
    re.compile(r"</raw_logs>", re.IGNORECASE),
    re.compile(r"</alert_payload>", re.IGNORECASE),
    re.compile(r"</runbook_context>", re.IGNORECASE),
    re.compile(r"</deployment_history>", re.IGNORECASE),
]

def sanitize_delimiters(text: str) -> str:
    """
    Prevents prompt breakout attacks by neutralizing XML tags commonly used as boundary delimiters.
    """
    if not text:
        return ""
    return text.replace("<", "&lt;").replace(">", "&gt;")

def detect_injection_indicators(text: str) -> List[str]:
    """Scans untrusted logs for explicit adversarial prompt injection attempts."""
    found = []
    for pattern in INJECTION_SIGNATURES:
        match = pattern.search(text)
        if match:
            found.append(match.group(0))
    return found

def is_noise_line(line: str) -> bool:
    """Identifies routine heartbeat / health-check lines that clutter the incident context."""
    stripped = line.strip()
    if not stripped:
        return True
    # If line is an explicit error or warning, do NOT treat it as noise
    if re.search(r"\b(ERROR|FATAL|CRITICAL|FAIL|PANIC|EXCEPTION|WARN|137|5\d\d|TIMEOUT)\b", stripped, re.IGNORECASE):
        return False
    return any(p.search(stripped) for p in HEALTH_CHECK_PATTERNS)

def normalize_cloudwatch_line(line: str) -> str:
    """
    Extracts the meaningful payload from raw production CloudWatch log formats
    """
    stripped = line.strip()
    if stripped.startswith("{") and stripped.endswith("}"):
        try:
            data = json.loads(stripped)
            # Standard CloudWatch Insights / JSON log field preference
            for key in ("@message", "message", "log", "msg", "error"):
                if key in data and isinstance(data[key], str):
                    return data[key].strip()
        except Exception:
            pass
    return stripped

def deduplicate_repetitive_lines(lines: List[str]) -> List[str]:
    """
    Collapses repeated log spam into a single line with an occurrence counter.
    """
    if not lines:
        return []

    deduped: List[str] = []
    prev_sig: str = ""
    count: int = 0
    sample_line: str = ""

    def make_signature(text: str) -> str:
        # Strip timestamps, UUIDs, hex addresses, and ephemeral numbers
        s = re.sub(r"\d{4}-\d{2}-\d{2}[T\s]\d{2}:\d{2}:\d{2}(\.\d+)?Z?", "[TIME]", text)
        s = re.sub(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}", "[UUID]", s)
        s = re.sub(r"0x[0-9a-fA-F]+", "[ADDR]", s)
        s = re.sub(r"\b\d+\b", "[NUM]", s)
        return s.strip()

    for line in lines:
        norm = normalize_cloudwatch_line(line)
        sig = make_signature(norm)
        if sig == prev_sig:
            count += 1
        else:
            if count > 1:
                deduped.append(f"[x{count} repeated occurrences] {sample_line}")
            elif count == 1:
                deduped.append(sample_line)
            prev_sig = sig
            count = 1
            sample_line = norm

    if count > 1:
        deduped.append(f"[x{count} repeated occurrences] {sample_line}")
    elif count == 1:
        deduped.append(sample_line)

    return deduped

def prune_logs(
    raw_logs: str,
    max_token_budget: Optional[int] = None,
    preserve_head_ratio: Optional[float] = None,
    severity: Optional[str] = None
) -> Tuple[str, Dict[str, Any]]:
    """
    Cleans, deduplicates, and bounds untrusted incident logs dynamically.
    
    If max_token_budget is None: dynamically derived from live TokenBudget policy for the severity.
    If preserve_head_ratio is None: dynamically read from LOG_PRUNER_HEAD_RATIO env.
    """
    if max_token_budget is None:
        budget = TokenBudget.from_env(severity=severity)
        max_token_budget = budget.logs_budget

    if preserve_head_ratio is None:
        try:
            preserve_head_ratio = float(os.getenv("LOG_PRUNER_HEAD_RATIO", "0.35"))
        except ValueError:
            preserve_head_ratio = 0.35

    stats = {
        "original_chars": len(raw_logs) if raw_logs else 0,
        "original_lines": 0,
        "pruned_lines": 0,
        "injections_flagged": [],
        "truncated": False,
        "estimated_tokens": 0,
        "budget_limit": max_token_budget
    }

    if not raw_logs or not raw_logs.strip():
        stats["estimated_tokens"] = 0
        return "", stats

    # 1. Sanitize XML boundary delimiters to prevent prompt jailbreak escapes
    sanitized = sanitize_delimiters(raw_logs)

    # 2. Check for adversarial injection signatures
    injections = detect_injection_indicators(raw_logs)
    stats["injections_flagged"] = injections

    # 3. Filter noise (health checks, heartbeats)
    raw_lines = [l for l in sanitized.splitlines() if l.strip()]
    stats["original_lines"] = len(raw_lines)
    
    meaningful_lines = [l for l in raw_lines if not is_noise_line(l)]
    if not meaningful_lines and raw_lines:
        meaningful_lines = raw_lines[:5]

    # 4. Collapse repetitive spam and normalize CloudWatch lines
    deduped_lines = deduplicate_repetitive_lines(meaningful_lines)

    # 5. Token budget check
    joined = "\n".join(deduped_lines)
    current_tokens = estimate_tokens(joined)

    if current_tokens <= max_token_budget:
        stats["pruned_lines"] = len(deduped_lines)
        stats["estimated_tokens"] = current_tokens
        return joined, stats

    # 6. Priority retention: In large production logs, preserve ERROR/CRITICAL lines
    error_pattern = re.compile(r"\b(ERROR|FATAL|CRITICAL|PANIC|EXCEPTION|137|5\d\d)\b", re.IGNORECASE)
    high_priority = [l for l in deduped_lines if error_pattern.search(l)]
    
    # If high priority alone fits the budget, use high priority plus boundary lines
    if high_priority and estimate_tokens("\n".join(high_priority)) <= max_token_budget:
        candidate_lines = high_priority
    else:
        candidate_lines = deduped_lines

    # 7. Apply dynamic sliding window (Head/Tail)
    stats["truncated"] = True
    head_token_cap = int(max_token_budget * preserve_head_ratio)
    tail_token_cap = max_token_budget - head_token_cap

    head_lines: List[str] = []
    head_tok_acc = 0
    for l in candidate_lines:
        tok = estimate_tokens(l)
        if head_tok_acc + tok > head_token_cap:
            break
        head_lines.append(l)
        head_tok_acc += tok

    tail_lines: List[str] = []
    tail_tok_acc = 0
    for l in reversed(candidate_lines[len(head_lines):]):
        tok = estimate_tokens(l)
        if tail_tok_acc + tok > tail_token_cap:
            break
        tail_lines.insert(0, l)
        tail_tok_acc += tok

    omitted_count = max(0, len(raw_lines) - len(head_lines) - len(tail_lines))
    separator = [f"\n [{omitted_count} lines truncated to enforce dynamic token budget of {max_token_budget}] \n"]
    
    final_lines = head_lines + separator + tail_lines
    final_text = "\n".join(final_lines)

    stats["pruned_lines"] = len(final_lines)
    stats["estimated_tokens"] = estimate_tokens(final_text)
    return final_text, stats
