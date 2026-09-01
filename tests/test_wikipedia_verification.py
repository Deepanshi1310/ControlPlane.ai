# pyrefly: ignore [missing-import]
import pytest
from unittest.mock import AsyncMock, patch
from app.services.wikipedia_service import WikipediaService
from app.services.fact_verification_service import (
    FactVerificationService,
    ClaimVerification,
    FactualClaim
)
from app.services.performance_service import PerformanceService
from app.models.evaluation import FactualityVerificationResult


class TestWikipediaSynchronousHelpers:
    """Synchronous helper tests for entity and keyword extraction."""

    def test_extract_entities(self):
        """Test extracting named entities and capitalized sequences."""
        text = "The World Health Organization was founded in Geneva."
        entities = WikipediaService.extract_entities(text)
        assert any("World Health Organization" in e for e in entities)
        assert any("Geneva" in e for e in entities)

    def test_extract_keywords(self):
        """Test keyword extraction filters stopwords and preserves numbers."""
        text = "Apollo 11 landed on the Moon in July 1969."
        kws = WikipediaService.extract_keywords(text)
        assert "apollo" in kws
        assert "11" in kws
        assert "moon" in kws
        assert "1969" in kws
        assert "the" not in kws
        assert "on" not in kws


@pytest.mark.asyncio
class TestWikipediaServiceSearch:
    """Tests for generalized Wikipedia search and disambiguation filtering."""

    async def test_search_wikipedia_success(self):
        """Test standard search returns cleaned snippets."""
        with patch('aiohttp.ClientSession.get') as mock_get:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value={
                "query": {
                    "search": [
                        {
                            "title": "Photosynthesis",
                            "snippet": "<b>Photosynthesis</b> is a biological process used by plants."
                        }
                    ]
                }
            })
            mock_get.return_value.__aenter__.return_value = mock_response

            results = await WikipediaService.search_wikipedia("Photosynthesis")
            assert len(results) == 1
            assert results[0]["title"] == "Photosynthesis"
            assert "<b>" not in results[0]["snippet"]

    async def test_search_wikipedia_filters_disambiguation(self):
        """Test that disambiguation pages are filtered from search results."""
        with patch('aiohttp.ClientSession.get') as mock_get:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value={
                "query": {
                    "search": [
                        {"title": "Mercury (disambiguation)", "snippet": "Disambiguation page"},
                        {"title": "Mercury (planet)", "snippet": "The smallest planet in the Solar System"}
                    ]
                }
            })
            mock_get.return_value.__aenter__.return_value = mock_response

            results = await WikipediaService.search_wikipedia("Mercury")
            assert len(results) == 1
            assert results[0]["title"] == "Mercury (planet)"

    async def test_search_wikipedia_empty_and_invalid(self):
        """Test search with empty or too-short queries."""
        assert await WikipediaService.search_wikipedia("") == []
        assert await WikipediaService.search_wikipedia(" ") == []
        assert await WikipediaService.search_wikipedia("a") == []

    async def test_search_wikipedia_network_error(self):
        """Test graceful fallback on network error."""
        with patch('aiohttp.ClientSession.get', side_effect=Exception("Network unreachable")):
            results = await WikipediaService.search_wikipedia("Albert Einstein")
            assert results == []



@pytest.mark.asyncio
class TestWikipediaArticleRetrieval:
    """Tests for article fetching and content extraction."""

    async def test_get_wikipedia_article_success(self):
        """Test successfully retrieving a full article."""
        with patch('aiohttp.ClientSession.get') as mock_get:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value={
                "query": {
                    "pages": {
                        "42": {
                            "title": "Jupiter",
                            "extract": "Jupiter is the fifth planet from the Sun and the largest in the Solar System."
                        }
                    }
                }
            })
            mock_get.return_value.__aenter__.return_value = mock_response

            article = await WikipediaService.get_wikipedia_article("Jupiter")
            assert article is not None
            assert article["title"] == "Jupiter"
            assert "fifth planet" in article["content"]
            assert article["url"] == "https://en.wikipedia.org/wiki/Jupiter"

    async def test_get_wikipedia_article_skips_disambiguation_content(self):
        """Test that articles with disambiguation text are skipped."""
        with patch('aiohttp.ClientSession.get') as mock_get:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value={
                "query": {
                    "pages": {
                        "10": {
                            "title": "Java",
                            "extract": "Java may refer to: Java (island), Java (programming language), or Java coffee."
                        }
                    }
                }
            })
            mock_get.return_value.__aenter__.return_value = mock_response

            article = await WikipediaService.get_wikipedia_article("Java")
            assert article is None

    async def test_get_wikipedia_article_missing(self):
        """Test handling missing articles."""
        with patch('aiohttp.ClientSession.get') as mock_get:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value={
                "query": {"pages": {"-1": {"missing": ""}}}
            })
            mock_get.return_value.__aenter__.return_value = mock_response

            article = await WikipediaService.get_wikipedia_article("TotallyFakeArticleXYZ999")
            assert article is None


@pytest.mark.asyncio
class TestFactVerificationExtraction:
    """Tests for claim extraction across diverse formatting styles."""

    async def test_extract_claims_numbered_list(self):
        """Test extracting claims from numbered lists."""
        service = FactVerificationService()
        response = """
        1. Water boils at 100 degrees Celsius at standard atmospheric pressure.
        2. Liquid water freezes at 0 degrees Celsius.
        """
        claims = await service.extract_claims(response)
        assert len(claims) == 2
        assert "100 degrees" in claims[0].claim
        assert "0 degrees" in claims[1].claim

    async def test_extract_claims_bullet_points(self):
        """Test extracting claims from bulleted lists."""
        service = FactVerificationService()
        response = """
        * The Pacific Ocean is the largest and deepest ocean on Earth.
        * Mount Everest is the highest mountain peak above sea level.
        """
        claims = await service.extract_claims(response)
        assert len(claims) == 2
        assert "Pacific Ocean" in claims[0].claim
        assert "Mount Everest" in claims[1].claim

    async def test_extract_claims_filters_pleasantries(self):
        """Test filtering out conversational prefixes."""
        service = FactVerificationService()
        response = "Hello! Sure, I can help with that. The speed of light is approximately 300,000 km per second. Let me know if you need more info!"
        claims = await service.extract_claims(response)
        assert len(claims) == 1
        assert "speed of light" in claims[0].claim


@pytest.mark.asyncio
class TestFactVerificationEvaluation:
    """Tests for 3-state evaluation: SUPPORTED, CONTRADICTED, INSUFFICIENT_EVIDENCE."""

    async def test_scientific_fact_supported(self):
        """Test supported scientific claim."""
        service = FactVerificationService()
        with patch.object(service.wikipedia, 'search_and_get_article') as mock_wiki:
            mock_wiki.return_value = {
                "title": "DNA",
                "content": "Deoxyribonucleic acid is a polymer composed of two polynucleotide chains that coil around each other to form a double helix.",
                "url": "https://en.wikipedia.org/wiki/DNA"
            }
            res = await service.verify_claim("DNA has a double helix structure composed of polynucleotide chains.")
            assert res.status == "SUPPORTED"
            assert res.confidence >= 0.85
            assert res.wikipedia_title == "DNA"

    async def test_historical_date_contradicted(self):
        """Test contradiction on conflicting historical dates/years."""
        service = FactVerificationService()
        with patch.object(service.wikipedia, 'search_and_get_article') as mock_wiki:
            mock_wiki.return_value = {
                "title": "Apollo 11",
                "content": "Apollo 11 was the American spaceflight that first landed humans on the Moon in July 1969.",
                "url": "https://en.wikipedia.org/wiki/Apollo_11"
            }
            # Falsely claiming Apollo 11 landed in 1999
            res = await service.verify_claim("Apollo 11 was the first human mission that landed on the Moon in 1999.")
            assert res.status == "CONTRADICTED"
            assert res.confidence >= 0.90

    async def test_geographic_fact_contradicted(self):
        """Test contradiction on conflicting geographical entity."""
        service = FactVerificationService()
        with patch.object(service.wikipedia, 'search_and_get_article') as mock_wiki:
            mock_wiki.return_value = {
                "title": "Eiffel Tower",
                "content": "The Eiffel Tower is a wrought-iron lattice tower on the Champ de Mars in Paris, France.",
                "url": "https://en.wikipedia.org/wiki/Eiffel_Tower"
            }
            # Falsely claiming Eiffel Tower is in Berlin, Germany
            res = await service.verify_claim("The Eiffel Tower is located in Berlin, Germany.")
            assert res.status == "CONTRADICTED"

    async def test_unsupported_obscure_claim_insufficient_evidence(self):
        """Test obscure/unfound claim returns INSUFFICIENT_EVIDENCE without penalizing."""
        service = FactVerificationService()
        with patch.object(service.wikipedia, 'search_and_get_article', return_value=None):
            res = await service.verify_claim("A small private bakery in 1984 served blueberry muffins to 12 customers.")
            assert res.status == "INSUFFICIENT_EVIDENCE"
            assert res.confidence == 0.0

    async def test_multiple_mixed_claims_evaluation(self):
        """Test multi-claim response with supported, contradicted, and unverified facts."""
        service = FactVerificationService()

        # Mock claim verification directly
        claims = [
            ClaimVerification(claim="Earth orbits the Sun", status="SUPPORTED", confidence=0.98),
            ClaimVerification(claim="Mars was built by aliens in 2020", status="CONTRADICTED", confidence=0.95),
            ClaimVerification(claim="An unknown cat meowed three times", status="INSUFFICIENT_EVIDENCE", confidence=0.0)
        ]

        result = FactVerificationService._calculate_factuality_score(claims)
        assert result.total_claims == 3
        assert result.supported_claims == 1
        assert result.contradicted_claims == 1
        assert result.insufficient_evidence_claims == 1
        # Score = supported / (supported + contradicted) = 1 / 2 = 0.5
        assert result.factuality_score == 0.5

    async def test_all_insufficient_evidence_returns_none(self):
        """Test that if all claims have insufficient evidence, factuality score is None (neutral)."""
        claims = [
            ClaimVerification(claim="Fact A", status="INSUFFICIENT_EVIDENCE", confidence=0.0),
            ClaimVerification(claim="Fact B", status="INSUFFICIENT_EVIDENCE", confidence=0.0)
        ]
        result = FactVerificationService._calculate_factuality_score(claims)
        assert result.total_claims == 2
        assert result.factuality_score is None
        assert result.insufficient_evidence_claims == 2
