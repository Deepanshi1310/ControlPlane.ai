import logging
import re
from typing import List, Dict, Optional, Any, Tuple
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
    status: ClaimStatus  # SUPPORTED, CONTRADICTED, INSUFFICIENT_EVIDENCE
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
    Works across arbitrary domains, people, places, dates, and science concepts.

    Pipeline:
    1. Extract discrete factual claims from response (NLP / rule-based segmentation)
    2. Dynamically search Wikipedia for candidate articles
    3. Retrieve relevant evidence excerpts
    4. Classify each claim into exactly one of: SUPPORTED, CONTRADICTED, INSUFFICIENT_EVIDENCE
    5. Calculate overall factuality score
    """

    def __init__(self, gemini_service=None):
        self.gemini = gemini_service
        self.wikipedia = WikipediaService()

    async def extract_claims(self, response: str) -> List[FactualClaim]:
        """
        Extract individual factual claims from the AI response.
        Handles multi-line lists, bullet points, numbered items, and complex sentences.
        Works deterministically on arbitrary topics.
        """
        if not response or len(response.strip()) < 5:
            return []

        raw_text = response.strip()

        # Step 1: Split by newlines first to preserve list structures
        lines = [line.strip() for line in raw_text.split("\n") if line.strip()]

        candidate_segments: List[str] = []

        for line in lines:
            # Strip list prefixes like "1. ", "* ", "- ", "• "
            cleaned_line = re.sub(r"^(\d+[\.\)]|\*|\-|•)\s+", "", line).strip()
            if not cleaned_line:
                continue

            # Split sentences on standard punctuation boundaries or semicolons
            sentences = re.split(r"(?<=[.!?])\s+|;\s+", cleaned_line)
            for s in sentences:
                s_clean = s.strip()
                if len(s_clean) >= 10:
                    candidate_segments.append(s_clean)

        # Step 2: Filter out conversational filler, disclaimers, and pleasantries
        non_factual_patterns = [
            r"^(hello|hi|hey|greetings|welcome)\b",
            r"^(thanks|thank you|sure|certainly|of course|please|alright)\b",
            r"^(let me know|feel free|hope this helps|i hope|here is|here are)\b",
            r"^(as an ai|note that|in summary|in conclusion|overall)\b"
        ]

        claims: List[FactualClaim] = []
        seen_claims = set()

        for segment in candidate_segments:
            # Check for non-factual pleasantries
            if any(re.search(pat, segment, re.IGNORECASE) for pat in non_factual_patterns):
                continue

            # Clean trailing punctuation
            norm = segment.strip().rstrip(".")
            if norm.lower() not in seen_claims:
                seen_claims.add(norm.lower())
                claims.append(FactualClaim(claim=segment, claim_id=len(claims)))

        if not claims and len(raw_text) >= 10:
            claims.append(FactualClaim(claim=raw_text, claim_id=0))

        logger.info(f"Extracted {len(claims)} factual claims for evaluation")
        return claims

    async def verify_claim(
        self,
        claim: str,
        query: Optional[str] = None
    ) -> ClaimVerification:
        """
        Verify a single claim against Wikipedia.
        Classifies status into SUPPORTED, CONTRADICTED, or INSUFFICIENT_EVIDENCE.
        """
        try:
            # Search Wikipedia dynamically using claim and optional query context
            article = await self.wikipedia.search_and_get_article(claim=claim, query=query)

            if not article:
                logger.info(f"No Wikipedia article found for claim: {claim}")
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

            # Evaluate 3-state classification
            status, confidence = self._evaluate_evidence_match(
                claim=claim,
                evidence=evidence_text,
                match_score=match_score,
                article_title=article["title"]
            )

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
        match_score: float,
        article_title: Optional[str] = None
    ) -> Tuple[ClaimStatus, float]:
        """
        Compare a factual claim against Wikipedia evidence text.
        Distinguishes SUPPORTED, CONTRADICTED, and INSUFFICIENT_EVIDENCE.

        Critical Rule: No evidence != contradiction.
        """
        full_text = f"{article_title or ''} {evidence}".strip()
        full_text_lower = full_text.lower()

        claim_keywords = WikipediaService.extract_keywords(claim)
        if not claim_keywords:
            return ("INSUFFICIENT_EVIDENCE", 0.0)

        matched_kw = [kw for kw in claim_keywords if kw in full_text_lower]
        unmatched_kw = [kw for kw in claim_keywords if kw not in full_text_lower]
        kw_ratio = len(matched_kw) / len(claim_keywords) if claim_keywords else 0.0

        # Check 1: Conflicting numbers and years (e.g. "1889" vs "2015", "1969" vs "1999")
        claim_numbers = set(re.findall(r"\b\d+(?:\.\d+)?\b", claim))
        evidence_numbers = set(re.findall(r"\b\d+(?:\.\d+)?\b", full_text))

        if claim_numbers:
            claim_years = {n for n in claim_numbers if len(n) == 4 and (n.startswith("1") or n.startswith("2"))}
            evidence_years = {n for n in evidence_numbers if len(n) == 4 and (n.startswith("1") or n.startswith("2"))}

            if claim_years and evidence_years and not (claim_years & evidence_years):
                # Asserted year conflicts with verified years in evidence
                return ("CONTRADICTED", 0.95)

        # Check 2: Strong factual support (High keyword overlap >= 65% or strong core match)
        if kw_ratio >= 0.65 or (len(matched_kw) >= 3 and len(unmatched_kw) <= 1):
            confidence = 0.98 if kw_ratio >= 0.85 else 0.88
            return ("SUPPORTED", confidence)

        # Check 3: Named entity contradiction (e.g. asserting Eiffel Tower is in Berlin / Germany)
        claim_entities = WikipediaService.extract_entities(claim)
        if claim_entities and article_title:
            title_lower = article_title.lower()
            subject_matched = any(e.lower() in title_lower or title_lower in e.lower() for e in claim_entities)
            if subject_matched:
                unmatched_entities = [
                    e for e in claim_entities
                    if e.lower() not in full_text_lower and e.lower() not in title_lower
                ]
                if unmatched_entities and len(unmatched_entities) >= 1 and kw_ratio < 0.60:
                    # Specific asserted entity conflicts with the ground truth
                    return ("CONTRADICTED", 0.92)

        # Check 4: Moderate support if key entities and core predicates match
        if kw_ratio >= 0.50 and len(matched_kw) >= 3:
            return ("SUPPORTED", 0.80)

        # Check 5: Neutral insufficient evidence
        return ("INSUFFICIENT_EVIDENCE", 0.50)



    async def verify_response(
        self,
        response: str,
        query: Optional[str] = None
    ) -> FactVerificationResult:
        """
        Perform complete factual verification of an AI response against Wikipedia.
        Evaluates multiple claims independently.
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
            verification = await self.verify_claim(claim=claim.claim, query=query)
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
        - SUPPORTED = correct (1.0)
        - CONTRADICTED = incorrect (0.0)
        - INSUFFICIENT_EVIDENCE = unknown (neutral, not counted as false)
        """
        total = len(verified_claims)
        supported = sum(1 for c in verified_claims if c.status == "SUPPORTED")
        contradicted = sum(1 for c in verified_claims if c.status == "CONTRADICTED")
        insufficient = sum(1 for c in verified_claims if c.status == "INSUFFICIENT_EVIDENCE")

        verifiable_count = supported + contradicted

        if verifiable_count == 0:
            # All claims are unknown / insufficient evidence -> neutral
            factuality_score = None
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
