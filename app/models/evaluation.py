from typing import Optional, List, Literal
from pydantic import BaseModel, Field


import uuid


RiskLevel = Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]

DecisionAction = Literal[
    "ALLOW",
    "EDIT",
    "REDACT",
    "BLOCK",
    "HUMAN_REVIEW"
]

ClaimStatus = Literal[
    "SUPPORTED",
    "CONTRADICTED",
    "INSUFFICIENT_EVIDENCE"
]


class EvaluationRequest(BaseModel):
    """
    Evaluation request for an AI response.
    Requires only query and response.
    """
    query: str
    response: str

    # Optional metadata with safe defaults
    request_id: Optional[str] = Field(default_factory=lambda: f"req-{uuid.uuid4().hex[:8]}")
    model: Optional[str] = "gemini-2.5-flash"
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: Optional[int] = 0
    latency_ms: float = 0.0
    tool_calls: int = 0
    context: Optional[str] = None
    expected_cost: Optional[float] = None

    model_config = {
        "json_schema_extra": {
            "example": {
                "query": "Who founded Microsoft?",
                "response": "Microsoft was founded by Bill Gates and Paul Allen on April 4, 1975."
            }
        }
    }


class ClaimVerificationResult(BaseModel):
    """Result of verifying a single factual claim against Wikipedia."""
    claim: str
    status: ClaimStatus
    evidence: Optional[str] = None
    wikipedia_title: Optional[str] = None
    wikipedia_url: Optional[str] = None
    confidence: float = Field(ge=0, le=1)


class FactualityVerificationResult(BaseModel):
    """Overall factual verification result using Wikipedia."""
    verified_claims: List[ClaimVerificationResult] = []
    factuality_score: Optional[float] = Field(
        None,
        ge=0,
        le=1
    )
    total_claims: int = 0
    supported_claims: int = 0
    contradicted_claims: int = 0
    insufficient_evidence_claims: int = 0
    verification_method: str = "wikipedia_api"


class PerformanceResult(BaseModel):
    relevance: float = Field(ge=0, le=1)
    factuality: float = Field(ge=0, le=1)
    completeness: float = Field(ge=0, le=1)
    clarity: float = Field(ge=0, le=1)

    quality_score: float = Field(ge=0, le=1)

    confidence: float = Field(ge=0, le=1)

    risk: RiskLevel

    latency_ms: float

    # Optional: factual verification results from Wikipedia
    factual_verification: Optional[FactualityVerificationResult] = None


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


class SourceOfTruth(BaseModel):
    """Ground-truth reference source verifying the claim."""
    title: str
    url: str
    snippet: str
    status: ClaimStatus = "SUPPORTED"
    claim: Optional[str] = None
    confidence: float = Field(default=1.0, ge=0, le=1)


class DecisionResult(BaseModel):
    risk_level: RiskLevel

    action: DecisionAction

    reason: str

    source_of_truth: str = "Wikipedia"
    supporting_url: Optional[str] = None
    supporting_evidence: Optional[str] = None
    sources_of_truth: List[SourceOfTruth] = []


class EvaluationResponse(BaseModel):
    request_id: str

    decision: DecisionResult
    sources_of_truth: List[SourceOfTruth] = []

    performance: PerformanceResult
    cost: CostResult
    responsibility: ResponsibilityResult