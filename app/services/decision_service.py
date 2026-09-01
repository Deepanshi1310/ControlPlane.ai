from typing import Optional, List, Dict, Any
from app.models.evaluation import SourceOfTruth


class DecisionService:

    @staticmethod
    def _extract_sources(performance) -> tuple[Optional[str], Optional[str], Optional[str], List[SourceOfTruth]]:
        """
        Extract primary URL, evidence snippet, title, and sources of truth from performance results.
        """
        sources_list: List[SourceOfTruth] = []
        primary_url = None
        primary_evidence = None
        primary_title = None

        factual_verification = getattr(performance, "factual_verification", None)
        if not factual_verification:
            return primary_url, primary_evidence, primary_title, sources_list

        # If sources_of_truth exists directly
        raw_sources = getattr(factual_verification, "sources_of_truth", [])
        if raw_sources:
            sources_list = raw_sources
            primary_url = raw_sources[0].url
            primary_evidence = raw_sources[0].snippet
            primary_title = raw_sources[0].title
            return primary_url, primary_evidence, primary_title, sources_list

        # Otherwise extract from verified_claims
        verified_claims = getattr(factual_verification, "verified_claims", [])
        for claim in verified_claims:
            if getattr(claim, "wikipedia_url", None):
                sot = SourceOfTruth(
                    title=claim.wikipedia_title or "Wikipedia Article",
                    url=claim.wikipedia_url,
                    snippet=claim.evidence or "Wikipedia reference",
                    status=getattr(claim, "status", "SUPPORTED"),
                    claim=getattr(claim, "claim", None),
                    confidence=getattr(claim, "confidence", 1.0)
                )
                sources_list.append(sot)
                if not primary_url:
                    primary_url = claim.wikipedia_url
                    primary_evidence = claim.evidence
                    primary_title = claim.wikipedia_title

        return primary_url, primary_evidence, primary_title, sources_list

    @staticmethod
    def decide(
        performance,
        cost,
        responsibility
    ) -> Dict[str, Any]:

        primary_url, primary_evidence, primary_title, sources_of_truth = (
            DecisionService._extract_sources(performance)
        )

        source_cite = f" [{primary_title}]({primary_url})" if primary_url and primary_title else (f" ({primary_url})" if primary_url else "")

        # 1. Critical PII violation
        if responsibility.pii_detected:
            pii_list = ", ".join(responsibility.pii_types) if responsibility.pii_types else "Sensitive Data"
            return {
                "risk_level": "HIGH",
                "action": "REDACT",
                "reason": f"PII detected in response ({pii_list}). Automatic redaction required.",
                "source_of_truth": "Wikipedia",
                "supporting_url": primary_url,
                "supporting_evidence": primary_evidence,
                "sources_of_truth": sources_of_truth
            }

        # 2. Severe safety violation
        if responsibility.safety_score < 0.30:
            return {
                "risk_level": "CRITICAL",
                "action": "BLOCK",
                "reason": "Severe safety violation detected.",
                "source_of_truth": "Wikipedia",
                "supporting_url": primary_url,
                "supporting_evidence": primary_evidence,
                "sources_of_truth": sources_of_truth
            }

        # 3. Severe policy violation
        if responsibility.policy_violation:
            return {
                "risk_level": "HIGH",
                "action": "BLOCK",
                "reason": "Policy violation detected.",
                "source_of_truth": "Wikipedia",
                "supporting_url": primary_url,
                "supporting_evidence": primary_evidence,
                "sources_of_truth": sources_of_truth
            }

        # 4. Severe cost anomaly
        if cost.get("risk") == "HIGH":
            return {
                "risk_level": "HIGH",
                "action": "BLOCK",
                "reason": "Severe cost anomaly detected.",
                "source_of_truth": "Wikipedia",
                "supporting_url": primary_url,
                "supporting_evidence": primary_evidence,
                "sources_of_truth": sources_of_truth
            }

        # 5. Critical factuality failure or contradicted claims
        has_contradicted = any(getattr(s, "status", "") == "CONTRADICTED" for s in sources_of_truth)
        if performance.factuality < 0.60 or performance.risk == "HIGH" or has_contradicted:
            return {
                "risk_level": "HIGH",
                "action": "HUMAN_REVIEW",
                "reason": f"Factuality or quality check flagged issues against Wikipedia source{source_cite}. Claims may be contradicted or unverified.",
                "source_of_truth": "Wikipedia",
                "supporting_url": primary_url,
                "supporting_evidence": primary_evidence,
                "sources_of_truth": sources_of_truth
            }

        # 6. Moderate risk
        if (
            performance.risk == "MEDIUM"
            or cost.get("risk") == "MEDIUM"
            or responsibility.risk == "MEDIUM"
        ):
            return {
                "risk_level": "MEDIUM",
                "action": "HUMAN_REVIEW",
                "reason": f"Moderate risk detected. Verified against Wikipedia source{source_cite}.",
                "source_of_truth": "Wikipedia",
                "supporting_url": primary_url,
                "supporting_evidence": primary_evidence,
                "sources_of_truth": sources_of_truth
            }

        # 7. Everything passed -> ALLOW with citation
        if primary_url:
            reason = f"Response passed all checks. Factually supported by Wikipedia:{source_cite}"
        else:
            reason = "Response passed all critical checks."

        return {
            "risk_level": "LOW",
            "action": "ALLOW",
            "reason": reason,
            "source_of_truth": "Wikipedia",
            "supporting_url": primary_url,
            "supporting_evidence": primary_evidence,
            "sources_of_truth": sources_of_truth
        }