import asyncio
# pyrefly: ignore [missing-import]
import aiohttp
import logging
import re
from typing import Optional, List, Dict, Any
from urllib.parse import quote

logger = logging.getLogger(__name__)


class WikipediaService:
    """
    Service for retrieving factual evidence from Wikipedia via MediaWiki API.
    Handles search, article retrieval, and evidence extraction without requiring LLMs.
    """

    BASE_URL = "https://en.wikipedia.org/w/api.php"
    TIMEOUT = 10
    HEADERS = {
        "User-Agent": "ControlPlaneAI/1.0 (https://controlplane.ai; contact@controlplane.ai)"
    }

    @staticmethod
    async def search_wikipedia(
        query: str,
        limit: int = 5
    ) -> List[Dict[str, str]]:
        """
        Search Wikipedia for articles related to the query.

        Args:
            query: Search query string
            limit: Maximum number of results to return

        Returns:
            List of dicts with 'title' and 'snippet' keys
        """
        if not query or len(query.strip()) < 2:
            logger.warning(f"Invalid search query: {query}")
            return []

        # Clean query of noise
        clean_query = re.sub(r"[^\w\s]", " ", query).strip()

        params = {
            "action": "query",
            "format": "json",
            "list": "search",
            "srsearch": clean_query,
            "srlimit": str(limit),
            "srinfo": "totalhits"
        }

        try:
            async with aiohttp.ClientSession(headers=WikipediaService.HEADERS) as session:
                async with session.get(
                    WikipediaService.BASE_URL,
                    params=params,
                    timeout=aiohttp.ClientTimeout(total=WikipediaService.TIMEOUT)
                ) as response:
                    if response.status != 200:
                        logger.error(f"Wikipedia search failed: {response.status}")
                        return []

                    data = await response.json()
                    results = data.get("query", {}).get("search", [])

                    return [
                        {
                            "title": result["title"],
                            "snippet": re.sub(r"<[^>]+>", "", result.get("snippet", ""))
                        }
                        for result in results
                    ]

        except asyncio.TimeoutError:
            logger.error(f"Wikipedia search timeout for: {query}")
            return []
        except Exception as e:
            logger.error(f"Wikipedia search error: {str(e)}")
            return []

    @staticmethod
    async def get_wikipedia_article(
        title: str,
        intro_only: bool = False
    ) -> Optional[Dict[str, Any]]:
        """
        Retrieve the content of a Wikipedia article.

        Args:
            title: Wikipedia article title
            intro_only: If True, fetches only the introductory summary

        Returns:
            Dict with 'title', 'content', 'url', 'extract' keys
        """
        if not title or len(title.strip()) < 1:
            logger.warning(f"Invalid article title: {title}")
            return None

        params = {
            "action": "query",
            "format": "json",
            "titles": title,
            "prop": "extracts|info",
            "explaintext": "1",
            "exintro": "1" if intro_only else "0",
            "redirects": "1"
        }

        try:
            async with aiohttp.ClientSession(headers=WikipediaService.HEADERS) as session:
                async with session.get(
                    WikipediaService.BASE_URL,
                    params=params,
                    timeout=aiohttp.ClientTimeout(total=WikipediaService.TIMEOUT)
                ) as response:
                    if response.status != 200:
                        logger.error(f"Wikipedia article fetch failed: {response.status}")
                        return None

                    data = await response.json()
                    pages = data.get("query", {}).get("pages", {})

                    if not pages:
                        return None

                    page = list(pages.values())[0]

                    if "missing" in page:
                        logger.info(f"Article not found: {title}")
                        return None

                    article_title = page.get("title", title)
                    content = page.get("extract", "")

                    if not content:
                        logger.warning(f"No content retrieved for: {title}")
                        return None

                    wikipedia_url = f"https://en.wikipedia.org/wiki/{quote(article_title.replace(' ', '_'))}"

                    return {
                        "title": article_title,
                        "content": content,
                        "url": wikipedia_url,
                        "extract": content[:500]
                    }

        except asyncio.TimeoutError:
            logger.error(f"Wikipedia article fetch timeout for: {title}")
            return None
        except Exception as e:
            logger.error(f"Wikipedia article fetch error for {title}: {str(e)}")
            return None

    @staticmethod
    def extract_keywords(text: str) -> List[str]:
        """Extract meaningful alphanumeric keywords filtering out stopwords."""
        stopwords = {
            "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
            "have", "has", "had", "do", "does", "did", "will", "would", "could",
            "should", "may", "might", "must", "can", "it", "its", "of", "in", "to",
            "for", "and", "or", "if", "not", "no", "yes", "on", "at", "by", "with",
            "from", "about", "into", "over", "after", "who", "whom", "which", "what",
            "where", "when", "why", "how", "that", "this", "these", "those"
        }
        words = re.findall(r"\b[a-zA-Z0-9_-]+\b", text.lower())
        return [w for w in words if len(w) > 2 and w not in stopwords]

    @staticmethod
    def get_relevant_evidence(
        article_content: str,
        claim: str,
        max_length: int = 600
    ) -> Optional[Dict[str, Any]]:
        """
        Extract the most relevant excerpt and sentences from article content for a claim.

        Returns:
            Dict with 'evidence', 'score' (match ratio), 'matched_keywords'
        """
        if not article_content or not claim:
            return None

        keywords = WikipediaService.extract_keywords(claim)
        if not keywords:
            snippet = article_content[:max_length].strip()
            return {
                "evidence": snippet,
                "score": 0.5,
                "matched_keywords": []
            }

        # Break article into sentences and paragraphs
        paragraphs = [p.strip() for p in article_content.split("\n\n") if p.strip()]
        scored_paragraphs = []

        keywords_set = set(keywords)

        for para in paragraphs:
            para_lower = para.lower()
            matched = [kw for kw in keywords_set if kw in para_lower]
            if matched:
                score = len(matched) / len(keywords_set)
                scored_paragraphs.append((score, len(matched), para, matched))

        if not scored_paragraphs:
            # Fallback to introductory paragraph
            first_para = paragraphs[0] if paragraphs else article_content[:max_length]
            return {
                "evidence": first_para[:max_length],
                "score": 0.2,
                "matched_keywords": []
            }

        # Sort by score descending
        scored_paragraphs.sort(key=lambda x: (x[0], x[1]), reverse=True)
        top_score, _, best_para, matched = scored_paragraphs[0]

        # Extract the specific sentences containing the keywords within the best paragraph
        sentences = re.split(r"(?<=[.!?])\s+", best_para)
        relevant_sentences = []
        for s in sentences:
            s_lower = s.lower()
            if any(kw in s_lower for kw in matched):
                relevant_sentences.append(s.strip())

        if relevant_sentences:
            evidence = " ".join(relevant_sentences)
        else:
            evidence = best_para

        if len(evidence) > max_length:
            evidence = evidence[:max_length].rstrip() + "..."

        return {
            "evidence": evidence,
            "score": round(min(top_score, 1.0), 3),
            "matched_keywords": matched
        }

    @staticmethod
    async def search_and_get_article(
        query: str
    ) -> Optional[Dict[str, Any]]:
        """
        Search for an article and return its full content with URL.
        """
        search_results = await WikipediaService.search_wikipedia(query, limit=3)
        if not search_results:
            return None

        for result in search_results:
            article = await WikipediaService.get_wikipedia_article(result["title"])
            if article and article.get("content"):
                return article

        return None
