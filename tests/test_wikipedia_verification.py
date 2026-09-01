# pyrefly: ignore [missing-import]
import pytest
from unittest.mock import AsyncMock, patch
from app.services.wikipedia_service import WikipediaService
from app.services.fact_verification_service import FactVerificationService, ClaimVerification
from app.services.performance_service import PerformanceService
from app.models.evaluation import FactualityVerificationResult


@pytest.mark.asyncio
class TestWikipediaService:
    """Test cases for WikipediaService"""

    async def test_search_wikipedia_success(self):
        """Test successful Wikipedia search"""
        with patch('aiohttp.ClientSession.get') as mock_get:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value={
                "query": {
                    "search": [
                        {
                            "title": "Eiffel Tower",
                            "snippet": "The Eiffel Tower is located in Paris"
                        }
                    ]
                }
            })
            mock_get.return_value.__aenter__.return_value = mock_response

            results = await WikipediaService.search_wikipedia("Eiffel Tower")
            assert len(results) > 0
            assert results[0]["title"] == "Eiffel Tower"

    async def test_search_wikipedia_empty_query(self):
        """Test search with empty query"""
        results = await WikipediaService.search_wikipedia("")
        assert results == []

    async def test_search_wikipedia_api_error(self):
        """Test search with API error"""
        with patch('aiohttp.ClientSession.get') as mock_get:
            mock_response = AsyncMock()
            mock_response.status = 500
            mock_get.return_value.__aenter__.return_value = mock_response

            results = await WikipediaService.search_wikipedia("test")
            assert results == []

    async def test_get_wikipedia_article_success(self):
        """Test successful article retrieval"""
        with patch('aiohttp.ClientSession.get') as mock_get:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value={
                "query": {
                    "pages": {
                        "123": {
                            "title": "Eiffel Tower",
                            "extract": "The Eiffel Tower is a wrought iron lattice tower..."
                        }
                    }
                }
            })
            mock_get.return_value.__aenter__.return_value = mock_response

            article = await WikipediaService.get_wikipedia_article("Eiffel Tower")
            assert article is not None
            assert article["title"] == "Eiffel Tower"
            assert "Eiffel Tower" in article["content"]

    async def test_get_wikipedia_article_not_found(self):
        """Test article not found"""
        with patch('aiohttp.ClientSession.get') as mock_get:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value={
                "query": {
                    "pages": {
                        "123": {
                            "missing": ""
                        }
                    }
                }
            })
            mock_get.return_value.__aenter__.return_value = mock_response

            article = await WikipediaService.get_wikipedia_article("NonExistentPlace123")
            assert article is None

    def test_get_relevant_evidence_with_keywords(self):
        """Test evidence extraction with keywords"""
        content = """
        The Eiffel Tower is a wrought iron lattice tower.
        It was completed in 1889.
        The height of the Eiffel Tower is 330 metres.
        """
        claim = "The Eiffel Tower was completed in 1889"
        result = WikipediaService.get_relevant_evidence(
            article_content=content,
            claim=claim
        )
        assert result is not None
        assert "1889" in result["evidence"]

    def test_get_relevant_evidence_empty_content(self):
        """Test evidence extraction with empty content"""
        result = WikipediaService.get_relevant_evidence(
            article_content="",
            claim="Some claim"
        )
        assert result is None


@pytest.mark.asyncio
class TestFactVerificationService:
    """Test cases for FactVerificationService"""

    async def test_extract_claims_success(self):
        """Test successful claim extraction"""
        service = FactVerificationService()
        response = "The Eiffel Tower is located in Paris. It was completed in 1889."
        claims = await service.extract_claims(response)
        assert len(claims) == 2
        assert "Eiffel Tower" in claims[0].claim

    async def test_extract_claims_empty_response(self):
        """Test claim extraction with empty response"""
        service = FactVerificationService()
        claims = await service.extract_claims("")
        assert claims == []

    async def test_verify_claim_supported(self):
        """Test claim verification - SUPPORTED status"""
        service = FactVerificationService()

        with patch.object(service.wikipedia, 'search_and_get_article') as mock_wiki:
            mock_wiki.return_value = {
                "title": "Eiffel Tower",
                "content": "The Eiffel Tower is located in Paris and was completed in 1889.",
                "url": "https://en.wikipedia.org/wiki/Eiffel_Tower"
            }

            verification = await service.verify_claim(
                "The Eiffel Tower is located in Paris and was completed in 1889."
            )

            assert verification.status == "SUPPORTED"
            assert verification.wikipedia_title == "Eiffel Tower"
            assert verification.wikipedia_url == "https://en.wikipedia.org/wiki/Eiffel_Tower"

    async def test_verify_claim_contradicted(self):
        """Test claim verification - CONTRADICTED status"""
        service = FactVerificationService()

        with patch.object(service.wikipedia, 'search_and_get_article') as mock_wiki:
            mock_wiki.return_value = {
                "title": "Eiffel Tower",
                "content": "The Eiffel Tower is a wrought-iron lattice tower located in Paris, France.",
                "url": "https://en.wikipedia.org/wiki/Eiffel_Tower"
            }

            verification = await service.verify_claim(
                "The Eiffel Tower was built in 2015 in Berlin."
            )

            assert verification.status == "CONTRADICTED"

    async def test_calculate_factuality_score_mixed_results(self):
        """Test factuality score calculation with mixed verification results"""
        claims = [
            ClaimVerification(claim="Claim 1", status="SUPPORTED", confidence=0.95),
            ClaimVerification(claim="Claim 2", status="SUPPORTED", confidence=0.90),
            ClaimVerification(claim="Claim 3", status="CONTRADICTED", confidence=0.98),
            ClaimVerification(claim="Claim 4", status="INSUFFICIENT_EVIDENCE", confidence=0.0)
        ]

        result = FactVerificationService._calculate_factuality_score(claims)
        assert result.total_claims == 4
        assert result.supported_claims == 2
        assert result.contradicted_claims == 1
        assert result.insufficient_evidence_claims == 1
        assert abs(result.factuality_score - (2 / 3)) < 0.01

    async def test_calculate_factuality_score_all_supported(self):
        """Test factuality score when all claims are supported"""
        claims = [
            ClaimVerification(claim="Claim 1", status="SUPPORTED", confidence=0.95),
            ClaimVerification(claim="Claim 2", status="SUPPORTED", confidence=0.90)
        ]
        result = FactVerificationService._calculate_factuality_score(claims)
        assert result.total_claims == 2
        assert result.factuality_score == 1.0

    async def test_calculate_factuality_score_all_contradicted(self):
        """Test factuality score when all claims are contradicted"""
        claims = [
            ClaimVerification(claim="Claim 1", status="CONTRADICTED", confidence=0.95),
            ClaimVerification(claim="Claim 2", status="CONTRADICTED", confidence=0.90)
        ]
        result = FactVerificationService._calculate_factuality_score(claims)
        assert result.total_claims == 2
        assert result.factuality_score == 0.0


class TestPerformanceServiceIntegration:
    """Test cases for Performance Service with Wikipedia verification"""

    def test_override_factuality_with_wikipedia_uses_wiki_score(self):
        """Test that Wikipedia score overrides Gemini score"""
        wiki_result = FactualityVerificationResult(
            verified_claims=[],
            factuality_score=0.5,
            total_claims=2,
            supported_claims=1,
            contradicted_claims=1,
            insufficient_evidence_claims=0
        )
        gemini_score = 0.9
        result_score = PerformanceService.override_factuality_with_wikipedia(
            gemini_factuality=gemini_score,
            wikipedia_verification=wiki_result
        )
        assert result_score == 0.5

    def test_override_factuality_no_wiki_result(self):
        """Test that Gemini score is used when no Wikipedia result"""
        gemini_score = 0.75
        result_score = PerformanceService.override_factuality_with_wikipedia(
            gemini_factuality=gemini_score,
            wikipedia_verification=None
        )
        assert result_score == 0.75
