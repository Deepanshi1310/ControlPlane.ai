import logging
import re
from typing import List, Dict, Optional, Any
from app.services.wikipedia_service import WikipediaService
from app.models.evaluation import SourceOfTruth, ClaimStatus
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class FactualClaim(BaseModel):
    """Represents a single factual claim extracted from a response."""
    claim: str
    claim_id: Optional[int] = None


class ClaimVerification(BaseModel):
    """Result of verifying a single claim against Wikipedia."""
    claim: str
    status: str  # SUPPORTED, CONTRADICTED, INSUFFICIENT_EVIDENCE
    evidence: Optional[str] = None
    wikipedia_title: Optional[str] = None
    wikipedia_url: Optional[str] = None
    confidence: float = 0.0


class FactVerificationResult(BaseModel):
    """Overall factual verification result."""
    verified_claims: List[ClaimVerification] = []
    sources_of_truth: List[SourceOfTruth] = []
    factuality_score: Optional[float] = None
    total_claims: int = 0
    supported_claims: int = 0
    contradicted_claims: int = 0
    insufficient_evidence_claims: int = 0


class FactVerificationService:
    """
    Service for automated factual verification using Wikipedia as the Source of Truth.

    Pipeline:
    1. Extract discrete factual claims from response (NLP / rule-based)
    2. Query Wikipedia MediaWiki API for ground-truth articles
    3. Extract relevant citation excerpts & compare with claim
    4. Provide direct Wikipedia links and verifiable evidence snippets
    """

    def __init__(self, gemini_service=None):
        self.gemini = gemini_service
        self.wikipedia = WikipediaService()

    async def extract_claims(self, response: str) -> List[FactualClaim]:
        """
        Extract individual factual claims from the AI response.
        Works deterministically without requiring Gemini.
        """
        if not response or len(response.strip()) < 5:
            return []

        # Split response into distinct sentences
        raw_sentences = re.split(r"(?<=[.!?])\s+", response.strip())
        claims: List[FactualClaim] = []

        # Common non-factual filler prefixes
        non_factual_patterns = [
            r"^(hello|hi|hey|thanks|thank you|sure|certainly|of course|please)\b",
            r"^(let me know|feel free|hope this helps|i hope|as an ai)\b"
        ]

        for sentence in raw_sentences:
            clean = sentence.strip()
            if len(clean) < 10:
                continue

            # Skip pleasantries and filler
            if any(re.search(pat, clean, re.IGNORECASE) for pat in non_factual_patterns):
                continue

            claims.append(FactualClaim(claim=clean, claim_id=len(claims)))

        if not claims:
            claims.append(FactualClaim(claim=response.strip(), claim_id=0))

        logger.info(f"Extracted {len(claims)} factual claims for Wikipedia verification")
        return claims

    async def verify_claim(self, claim: str) -> ClaimVerification:
        """
        Verify a single claim directly against Wikipedia.
        """
        try:
            # Search Wikipedia for the claim
            article = await self.wikipedia.search_and_get_article(claim)

            if not article:
                logger.info(f"No Wikipedia article found for: {claim}")
                return ClaimVerification(
                    claim=claim,
                    status="INSUFFICIENT_EVIDENCE",
                    evidence=None,
                    confidence=0.0
                )

            # Extract evidence matching the claim
            evidence_result = self.wikipedia.get_relevant_evidence(
                article_content=article["content"],
                claim=claim,
                max_length=800
            )

            if not evidence_result or not evidence_result.get("evidence"):
                return ClaimVerification(
                    claim=claim,
                    status="INSUFFICIENT_EVIDENCE",
                    wikipedia_title=article["title"],
                    wikipedia_url=article["url"],
                    evidence=None,
                    confidence=0.0
                )

            evidence_text = evidence_result["evidence"]
            match_score = evidence_result.get("score", 0.0)

            # Compare claim against evidence
            status, confidence = self._evaluate_evidence_match(claim, evidence_text, match_score)

            return ClaimVerification(
                claim=claim,
                status=status,
                evidence=evidence_text,
                wikipedia_title=article["title"],
                wikipedia_url=article["url"],
                confidence=confidence
            )

        except Exception as e:
            logger.error(f"Error verifying claim '{claim}': {str(e)}")
            return ClaimVerification(
                claim=claim,
                status="INSUFFICIENT_EVIDENCE",
                evidence=None,
                confidence=0.0
            )

    def _evaluate_evidence_match(
        self,
        claim: str,
        evidence: str,
        match_score: float
    ) -> tuple[str, float]:
        """
        Compare a factual claim against Wikipedia evidence text.
        Returns (status, confidence).
        """
        evidence_lower = evidence.lower()

        claim_keywords = WikipediaService.extract_keywords(claim)
        if not claim_keywords:
            return ("INSUFFICIENT_EVIDENCE", 0.0)

        matched_kw = [kw for kw in claim_keywords if kw in evidence_lower]
        unmatched_kw = [kw for kw in claim_keywords if kw not in evidence_lower]
        kw_ratio = len(matched_kw) / len(claim_keywords) if claim_keywords else 0.0

        # 1. Missing keywords/entities in claim (e.g. false location or person)
        if unmatched_kw:
            if len(matched_kw) >= 2:
                # The Wikipedia article covers the topic, but the asserted details are absent/unsupported
                return ("CONTRADICTED", 0.90)
            return ("INSUFFICIENT_EVIDENCE", 0.40)

        # 2. All keywords found in grounding evidence
        if kw_ratio >= 0.90:
            return ("SUPPORTED", 0.98)
        else:
            return ("SUPPORTED", 0.85)

    async def verify_response(self, response: str) -> FactVerificationResult:
        """
        Perform complete fact-checking of an AI response against Wikipedia.
        """
        claims = await self.extract_claims(response)

        if not claims:
            return FactVerificationResult(
                verified_claims=[],
                sources_of_truth=[],
                factuality_score=None,
                total_claims=0,
                supported_claims=0,
                contradicted_claims=0,
                insufficient_evidence_claims=0
            )

        verified_claims: List[ClaimVerification] = []
        sources_of_truth: List[SourceOfTruth] = []

        for claim in claims:
            verification = await self.verify_claim(claim.claim)
            verified_claims.append(verification)

            if verification.wikipedia_title and verification.wikipedia_url:
                sources_of_truth.append(
                    SourceOfTruth(
                        title=verification.wikipedia_title,
                        url=verification.wikipedia_url,
                        snippet=verification.evidence or "Wikipedia article reference",
                        status=verification.status,
                        claim=verification.claim,
                        confidence=verification.confidence
                    )
                )

        result = self._calculate_factuality_score(verified_claims)
        result.verified_claims = verified_claims
        result.sources_of_truth = sources_of_truth

        return result

    @staticmethod
    def _calculate_factuality_score(
        verified_claims: List[ClaimVerification]
    ) -> FactVerificationResult:
        """
        Calculate overall factuality score from verified claims.
        """
        total = len(verified_claims)
        supported = sum(1 for c in verified_claims if c.status == "SUPPORTED")
        contradicted = sum(1 for c in verified_claims if c.status == "CONTRADICTED")
        insufficient = sum(1 for c in verified_claims if c.status == "INSUFFICIENT_EVIDENCE")

        verifiable_count = supported + contradicted

        if verifiable_count == 0:
            factuality_score = 0.85 if total > 0 else None
        else:
            factuality_score = supported / verifiable_count

        return FactVerificationResult(
            verified_claims=[],
            sources_of_truth=[],
            factuality_score=round(factuality_score, 4) if factuality_score is not None else None,
            total_claims=total,
            supported_claims=supported,
            contradicted_claims=contradicted,
            insufficient_evidence_claims=insufficient
        )
