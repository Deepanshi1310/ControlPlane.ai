from app.services.performance_service import PerformanceService
from app.services.responsibility_service import ResponsibilityService
from app.services.cost_service import CostService
from app.services.decision_service import DecisionService


class ControlPlaneService:

    def __init__(self, gemini_service):
        self.gemini = gemini_service

        self.responsibility_service = ResponsibilityService(
            gemini_service
        )

        self.cost_service = CostService(
            input_price_per_million=1.0,
            output_price_per_million=2.0
        )

    async def evaluate(self, request):

        # -----------------------------
        # PERFORMANCE
        # -----------------------------

        performance = await self.gemini.evaluate_performance(
            query=request.query,
            response=request.response,
            context=request.context
        )

        quality_score = PerformanceService.calculate_quality(
            relevance=performance.relevance,
            factuality=performance.factuality,
            completeness=performance.completeness,
            clarity=performance.clarity
        )

        performance.quality_score = quality_score

        performance.risk = PerformanceService.determine_risk(
            score=quality_score,
            factuality=performance.factuality,
            relevance=performance.relevance
        )

        performance.latency_ms = request.latency_ms

        # -----------------------------
        # COST
        # -----------------------------

        cost = self.cost_service.calculate(
            input_tokens=request.input_tokens,
            output_tokens=request.output_tokens,
            expected_cost=request.expected_cost,
            tool_calls=request.tool_calls
        )

        # -----------------------------
        # RESPONSIBILITY
        # -----------------------------

        responsibility = await self.responsibility_service.evaluate(
            query=request.query,
            response=request.response
        )

        # -----------------------------
        # DECISION
        # -----------------------------

        decision = DecisionService.decide(
            performance=performance,
            cost=cost,
            responsibility=responsibility
        )

        return {
            "request_id": request.request_id,
            "performance": performance,
            "cost": cost,
            "responsibility": responsibility,
            "decision": decision
        }