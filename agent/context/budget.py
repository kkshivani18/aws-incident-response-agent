import os
from dataclasses import dataclass, field
from typing import Dict, Any, Optional

def estimate_tokens(text: str) -> int:
    """
    Fast, reliable token estimation for LLM context management.
    Uses ~3.8 chars per token for typical English/code/log text.
    """
    if not text:
        return 0
    char_based = len(text) / 3.8
    word_based = len(text.split()) * 1.3
    return max(1, int((char_based + word_based) / 2))

def get_model_context_window() -> int:
    """
    Pattern 1: Model-Aware Ceiling.
    Discovers context window limit from env config.
    """
    # Check specific model context windows, then fallback to general
    for key in ("NOVA_PRO_CONTEXT_WINDOW", "NOVA_LITE_CONTEXT_WINDOW", "LLM_CONTEXT_WINDOW"):
        val = os.getenv(key)
        if val:
            try:
                return int(val)
            except ValueError:
                pass
    return 300_000

def get_total_budget() -> int:
    """
    Derives total incident turn budget dynamically.
    Priority:
    1. Explicit LLM_MAX_CONTEXT_TOKENS (e.g. 4000 for strict cost/turn budgeting).
    2. Fractional model window: LLM_CONTEXT_WINDOW * LLM_MAX_CONTEXT_BUDGET_FRACTION (e.g. 70%).
    """
    explicit_cap = os.getenv("LLM_MAX_CONTEXT_TOKENS")
    if explicit_cap:
        try:
            return max(500, int(explicit_cap))
        except ValueError:
            pass

    window = get_model_context_window()
    try:
        fraction = float(os.getenv("LLM_MAX_CONTEXT_BUDGET_FRACTION", "0.70"))
    except ValueError:
        fraction = 0.70

    calculated = int(window * fraction)
    # Ensure sane operational boundaries
    return max(1_000, calculated)

@dataclass
class TokenBudget:
    """
    Enforces dynamic token ceilings per incident analysis turn.
    Protects against context window blowout, needle-in-haystack degradation,
    and unpredictable API spend on huge production CloudWatch streams.
    """
    total_budget: int = 4000
    system_prompt_budget: int = 500
    alert_budget: int = 400
    deploy_history_budget: int = 400
    runbook_budget: int = 1000
    logs_budget: int = 1700

    def allocated_sum(self) -> int:
        return (
            self.system_prompt_budget
            + self.alert_budget
            + self.deploy_history_budget
            + self.runbook_budget
            + self.logs_budget
        )

    def validate_budget(self) -> bool:
        return self.allocated_sum() <= self.total_budget

    @classmethod
    def from_env(cls, severity: Optional[str] = None) -> "TokenBudget":
        """
        Derives an active TokenBudget dynamically from env vars
        """
        return get_budget_for_severity(severity=severity)

@dataclass
class BudgetPolicy:
    """
    Pattern 2: Proportional Slice Allocation.
    Defines the proportion of the total budget each context slice gets.
    Ratios can be adjusted via environment variables or severity tiers.
    """
    system_ratio: float = 0.10     # System prompt stays relatively constant
    alert_ratio: float = 0.08      # CloudWatch Alarm payload
    deploy_ratio: float = 0.08     # CI/CD deployment history
    runbook_ratio: float = 0.24    # Retrieved runbook instructions / RAG
    logs_ratio: float = 0.50       # Production CloudWatch logs take the lion's share

    def normalize(self) -> "BudgetPolicy":
        """Ensures the sum of slice ratios equals 1.0."""
        total = self.system_ratio + self.alert_ratio + self.deploy_ratio + self.runbook_ratio + self.logs_ratio
        if total <= 0:
            return BudgetPolicy()
        return BudgetPolicy(
            system_ratio=self.system_ratio / total,
            alert_ratio=self.alert_ratio / total,
            deploy_ratio=self.deploy_ratio / total,
            runbook_ratio=self.runbook_ratio / total,
            logs_ratio=self.logs_ratio / total,
        )

    def to_budget(self, total_tokens: int) -> TokenBudget:
        norm = self.normalize()
        return TokenBudget(
            total_budget=total_tokens,
            system_prompt_budget=max(100, int(total_tokens * norm.system_ratio)),
            alert_budget=max(100, int(total_tokens * norm.alert_ratio)),
            deploy_history_budget=max(100, int(total_tokens * norm.deploy_ratio)),
            runbook_budget=max(200, int(total_tokens * norm.runbook_ratio)),
            logs_budget=max(300, int(total_tokens * norm.logs_ratio)),
        )

# Pattern 3: Severity-Adaptive Policy
# During CRITICAL / HIGH incidents: telemetry and logs dominate (investigate live outage).
# During LOW / INFO incidents: runbooks, triage checklists, and guidance take priority.
SEVERITY_POLICIES: Dict[str, BudgetPolicy] = {
    "CRITICAL": BudgetPolicy(system_ratio=0.08, alert_ratio=0.07, deploy_ratio=0.10, runbook_ratio=0.20, logs_ratio=0.55),
    "HIGH":     BudgetPolicy(system_ratio=0.09, alert_ratio=0.08, deploy_ratio=0.09, runbook_ratio=0.24, logs_ratio=0.50),
    "MEDIUM":   BudgetPolicy(system_ratio=0.10, alert_ratio=0.09, deploy_ratio=0.08, runbook_ratio=0.28, logs_ratio=0.45),
    "LOW":      BudgetPolicy(system_ratio=0.12, alert_ratio=0.10, deploy_ratio=0.08, runbook_ratio=0.35, logs_ratio=0.35),
    "INFO":     BudgetPolicy(system_ratio=0.15, alert_ratio=0.10, deploy_ratio=0.05, runbook_ratio=0.40, logs_ratio=0.30),
}

def get_budget_for_severity(
    severity: Optional[str] = None,
    total_tokens: Optional[int] = None
) -> TokenBudget:
    """
    Returns a dynamically configured TokenBudget adapted to incident severity
    and environment configuration.
    """
    total = total_tokens or get_total_budget()
    sev_key = (severity or "MEDIUM").strip().upper()
    policy = SEVERITY_POLICIES.get(sev_key, SEVERITY_POLICIES["MEDIUM"])
    return policy.to_budget(total)

@dataclass
class ContextUsage:
    alert_tokens: int = 0
    logs_tokens: int = 0
    deploy_tokens: int = 0
    runbook_tokens: int = 0
    system_tokens: int = 0
    total_tokens: int = 0
    budget_exceeded: bool = False
    truncation_applied: bool = False
    details: Dict[str, Any] = field(default_factory=dict)