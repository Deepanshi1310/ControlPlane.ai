class CostService:

    def __init__(
        self,
        input_price_per_million: float,
        output_price_per_million: float
    ):
        self.input_price = input_price_per_million
        self.output_price = output_price_per_million

    def calculate(
        self,
        input_tokens: int,
        output_tokens: int,
        expected_cost: float | None = None,
        tool_calls: int = 0
    ):

        input_cost = (
            input_tokens / 1_000_000
        ) * self.input_price

        output_cost = (
            output_tokens / 1_000_000
        ) * self.output_price

        total_cost = input_cost + output_cost

        expected = expected_cost or total_cost

        if expected > 0:
            ratio = total_cost / expected
        else:
            ratio = 1.0

        if ratio <= 1.5:
            risk = "LOW"
        elif ratio <= 3:
            risk = "MEDIUM"
        else:
            risk = "HIGH"

        return {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens,
            "estimated_cost": round(total_cost, 8),
            "expected_cost": expected,
            "ratio": round(ratio, 4),
            "risk": risk,
            "tool_calls": tool_calls
        }