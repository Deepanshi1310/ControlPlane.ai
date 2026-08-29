from typing import Optional, List, Literal
from pydantic import BaseModel, Field


RiskLevel = Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]

DecisionAction = Literal[
    "ALLOW",
    "EDIT",
    "REDACT",
    "BLOCK",
    "HUMAN_REVIEW"
]


class EvaluationRequest(BaseModel):
    request_id: str

    query: str
    response: str

    model: str

    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: Optional[int] = None

    latency_ms: float = 0

    tool_calls: int = 0

    context: Optional[str] = None

    expected_cost: Optional[float] = None


class PerformanceResult(BaseModel):
    relevance: float = Field(ge=0, le=1)
    factuality: float = Field(ge=0, le=1)
    completeness: float = Field(ge=0, le=1)
    clarity: float = Field(ge=0, le=1)

    quality_score: float = Field(ge=0, le=1)

    confidence: float = Field(ge=0, le=1)

    risk: RiskLevel

    latency_ms: float


class CostResult(BaseModel):
    input_tokens: int
    output_tokens: int
    total_tokens: int

    estimated_cost: float
    expected_cost: float

    ratio: float

    risk: RiskLevel

    tool_calls: int


class ResponsibilityResult(BaseModel):
    pii_detected: bool

    pii_types: List[str] = []

    safety_score: float = Field(ge=0, le=1)

    bias_score: float = Field(ge=0, le=1)

    policy_violation: bool

    policy_issues: List[str] = []

    risk: RiskLevel


class DecisionResult(BaseModel):
    risk_level: RiskLevel

    action: DecisionAction

    reason: str


class EvaluationResponse(BaseModel):
    request_id: str

    performance: PerformanceResult
    cost: CostResult
    responsibility: ResponsibilityResult

    decision: DecisionResult