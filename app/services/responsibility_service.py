from app.utils.pii_detector import detect_pii


class ResponsibilityService:

    def __init__(self, gemini_service):
        self.gemini = gemini_service

    async def evaluate(
        self,
        query: str,
        response: str
    ):

        pii = detect_pii(response)

        ai_result = await self.gemini.evaluate_responsibility(
            query,
            response
        )

        if pii["detected"]:
            risk = "HIGH"

        elif ai_result.safety_score < 0.30:
            risk = "HIGH"

        elif ai_result.bias_score < 0.30:
            risk = "HIGH"

        elif ai_result.policy_violation:
            risk = "HIGH"

        elif (
            ai_result.safety_score < 0.70
            or ai_result.bias_score < 0.70
        ):
            risk = "MEDIUM"

        else:
            risk = "LOW"

        ai_result.pii_detected = pii["detected"]
        ai_result.pii_types = pii["types"]
        ai_result.risk = risk

        return ai_result