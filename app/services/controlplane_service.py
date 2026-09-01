import logging
import uuid
from app.services.performance_service import PerformanceService
from app.services.responsibility_service import ResponsibilityService
from app.services.cost_service import CostService
from app.services.decision_service import DecisionService
from app.services.fact_verification_service import FactVerificationService

logger = logging.getLogger(__name__)


class ControlPlaneService:

    def __init__(self, gemini_service=None):
        self.gemini = gemini_service

        self.responsibility_service = ResponsibilityService(
            gemini_service
        )

        self.fact_verification_service = FactVerificationService(
            gemini_service
        )

        self.cost_service = CostService(
            input_price_per_million=1.0,
            output_price_per_million=2.0
        )

    async def evaluate(self, request):

        # -----------------------------
        # 1. FACT VERIFICATION (Wikipedia Source of Truth)
        # -----------------------------

        fact_verification = await self.fact_verification_service.verify_response(
            response=request.response
        )

        logger.info(
            f"Wikipedia Source of Truth verification complete: "
            f"{fact_verification.total_claims} claims, "
            f"score: {fact_verification.factuality_score}"
        )

        # -----------------------------
        # 2. PERFORMANCE EVALUATION
        # -----------------------------

        factuality_score = fact_verification.factuality_score if fact_verification.factuality_score is not None else 0.85

        # Evaluate performance grounded in Wikipedia factuality
        performance = PerformanceService.create_standalone_performance_result(
            query=request.query,
            response=request.response,
            factuality=factuality_score,
            context=request.context
        )

        # Attach full verification result
        performance.factual_verification = fact_verification
        performance.latency_ms = request.latency_ms or 0.0

        # -----------------------------
        # 3. COST
        # -----------------------------

        cost = self.cost_service.calculate(
            input_tokens=request.input_tokens or 0,
            output_tokens=request.output_tokens or 0,
            expected_cost=request.expected_cost,
            tool_calls=request.tool_calls or 0
        )

        # -----------------------------
        # 4. RESPONSIBILITY
        # -----------------------------

        responsibility = await self.responsibility_service.evaluate(
            query=request.query,
            response=request.response
        )

        # -----------------------------
        # 5. DECISION WITH CITATIONS
        # -----------------------------

        decision = DecisionService.decide(
            performance=performance,
            cost=cost,
            responsibility=responsibility
        )

        req_id = request.request_id or f"req-{uuid.uuid4().hex[:8]}"

        return {
            "request_id": req_id,
            "decision": decision,
            "sources_of_truth": getattr(fact_verification, "sources_of_truth", []),
            "performance": performance,
            "cost": cost,
            "responsibility": responsibility
        }