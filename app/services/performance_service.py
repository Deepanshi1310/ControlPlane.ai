class PerformanceService:

    @staticmethod
    def calculate_quality(
        relevance: float,
        factuality: float,
        completeness: float,
        clarity: float
    ):

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
    ):

        # Critical failures override weighted score

        if factuality < 0.30:
            return "HIGH"

        if relevance < 0.20:
            return "HIGH"

        if score >= 0.90:
            return "LOW"

        if score >= 0.70:
            return "MEDIUM"

        return "HIGH"