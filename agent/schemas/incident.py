from typing import List, Literal
from pydantic import BaseModel, Field

class IncidentTriageReport(BaseModel):
    severity: Literal["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"] = Field(
        ..., description="Severity level based on impact and blast radius"
    )
    suspected_service: str = Field(
        ..., description="Name of the service emitting errors or suffering degradation"
    )
    root_cause_hypothesis: str = Field(
        ..., description="Technical explanation of the underlying failure"
    )
    evidence: List[str] = Field(
        ..., min_length=1, description="Specific log lines or signals supporting the hypothesis"
    )
    confidence_score: float = Field(
        ..., ge=0.0, le=1.0, description="Confidence in the diagnosis from 0.0 to 1.0"
    )
    proposed_action: Literal["ROLLBACK", "SCALE_UP", "RESTART", "INVESTIGATE", "NO_ACTION"] = Field(
        ..., description="Recommended remediation strictly from allow-listed safe actions"
    )
    is_injection_detected: bool = Field(
        default=False, description="Flag set true if adversarial instructions were detected in logs"
    )