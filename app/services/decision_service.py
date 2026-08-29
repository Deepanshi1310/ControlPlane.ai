class DecisionService:

    @staticmethod
    def decide(
        performance,
        cost,
        responsibility
    ):

        # Critical PII violation
        if responsibility.pii_detected:
            return {
                "risk_level": "HIGH",
                "action": "REDACT",
                "reason": "PII detected in AI response."
            }

        # Severe safety violation
        if responsibility.safety_score < 0.30:
            return {
                "risk_level": "CRITICAL",
                "action": "BLOCK",
                "reason": "Severe safety violation detected."
            }

        # Severe policy violation
        if responsibility.policy_violation:
            return {
                "risk_level": "HIGH",
                "action": "BLOCK",
                "reason": "Policy violation detected."
            }

        # Severe cost anomaly
        if cost["risk"] == "HIGH":
            return {
                "risk_level": "HIGH",
                "action": "BLOCK",
                "reason": "Severe cost anomaly detected."
            }

        # Critical factuality failure
        if performance.factuality < 0.30:
            return {
                "risk_level": "HIGH",
                "action": "HUMAN_REVIEW",
                "reason": "Critical factuality failure detected."
            }

        # Moderate risk
        if (
            performance.risk == "MEDIUM"
            or cost["risk"] == "MEDIUM"
            or responsibility.risk == "MEDIUM"
        ):
            return {
                "risk_level": "MEDIUM",
                "action": "HUMAN_REVIEW",
                "reason": "Moderate risk detected."
            }

        # Everything passed
        return {
            "risk_level": "LOW",
            "action": "ALLOW",
            "reason": "Response passed all critical checks."
        }