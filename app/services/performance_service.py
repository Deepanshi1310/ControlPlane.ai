import logging
import re
from app.models.evaluation import PerformanceResult

logger = logging.getLogger(__name__)


class PerformanceService:

    @staticmethod
    def calculate_quality(
        relevance: float,
        factuality: float,
        completeness: float,
        clarity: float
    ) -> float:

        score = (
            0.25 * relevance
            + 0.40 * factuality
            + 0.20 * completeness
            + 0.15 * clarity
        )

        return round(score, 4)

    @staticmethod
    def determine_risk(
        score: float,
        factuality: float,
        relevance: float
    ) -> str:

        # Critical failures override weighted score
        if factuality < 0.30:
            return "HIGH"

        if relevance < 0.20:
            return "HIGH"

        if score >= 0.85:
            return "LOW"

        if score >= 0.65:
            return "MEDIUM"

        return "HIGH"

    @staticmethod
    def create_standalone_performance_result(
        query: str,
        response: str,
        factuality: float,
        context: str = None
    ) -> PerformanceResult:
        """
        Compute performance metrics deterministically without requiring external LLMs.
        Uses text similarity for relevance and Wikipedia grounding for factuality.
        """
        query_words = set(re.findall(r"\b\w{3,}\b", (query or "").lower()))
        response_words = set(re.findall(r"\b\w{3,}\b", (response or "").lower()))

        # Relevance based on keyword overlap
        if query_words:
            overlap = len(query_words.intersection(response_words))
            relevance = min(max(overlap / len(query_words), 0.3), 1.0)
            if overlap >= 2:
                relevance = max(relevance, 0.90)
        else:
            relevance = 0.90

        # Completeness based on response length and substance
        char_count = len((response or "").strip())
        if char_count > 60:
            completeness = 0.95
        elif char_count > 20:
            completeness = 0.85
        else:
            completeness = 0.60

        # Clarity
        clarity = 0.95

        factuality_val = round(max(min(factuality, 1.0), 0.0), 4)

        quality_score = PerformanceService.calculate_quality(
            relevance=relevance,
            factuality=factuality_val,
            completeness=completeness,
            clarity=clarity
        )

        risk = PerformanceService.determine_risk(
            score=quality_score,
            factuality=factuality_val,
            relevance=relevance
        )

        return PerformanceResult(
            relevance=round(relevance, 4),
            factuality=factuality_val,
            completeness=round(completeness, 4),
            clarity=round(clarity, 4),
            quality_score=quality_score,
            confidence=0.95,
            risk=risk,
            latency_ms=0.0
        )

    @staticmethod
    def override_factuality_with_wikipedia(
        gemini_factuality: float,
        wikipedia_verification
    ) -> float:
        if not wikipedia_verification:
            return gemini_factuality

        if wikipedia_verification.total_claims == 0:
            return gemini_factuality

        wikipedia_score = wikipedia_verification.factuality_score
        if wikipedia_score is None:
            return gemini_factuality

        return round(wikipedia_score, 4)