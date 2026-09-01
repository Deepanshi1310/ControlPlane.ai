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
    Handles dynamic search, candidate scoring, disambiguation filtering,
    article retrieval, and evidence extraction across arbitrary topics.
    """

    BASE_URL = "https://en.wikipedia.org/w/api.php"
    TIMEOUT = 10
    HEADERS = {
        "User-Agent": "ControlPlaneAI/1.0 (https://controlplane.ai; contact@controlplane.ai)"
    }

    # Stopwords to filter out when tokenizing queries & claims
    STOPWORDS = {
        "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
        "have", "has", "had", "do", "does", "did", "will", "would", "could",
        "should", "may", "might", "must", "can", "it", "its", "of", "in", "to",
        "for", "and", "or", "if", "not", "no", "yes", "on", "at", "by", "with",
        "from", "about", "into", "over", "after", "who", "whom", "which", "what",
        "where", "when", "why", "how", "that", "this", "these", "those", "also",
        "such", "other", "than", "then", "very", "much", "more", "most", "some"
    }

    @staticmethod
    def extract_keywords(text: str) -> List[str]:
        """
        Extract meaningful alphanumeric keywords filtering out stopwords and punctuation.
        Preserves numbers, years, and significant terms.
        """
        if not text:
            return []
        words = re.findall(r"\b[a-zA-Z0-9_\-\.]{2,}\b", text.lower())
        return [w for w in words if w not in WikipediaService.STOPWORDS]

    @staticmethod
    def extract_entities(text: str) -> List[str]:
        """
        Extract potential entity phrases (capitalized sequences, numbers, quoted terms)
        to form targeted Wikipedia search queries.
        """
        if not text:
            return []

        # Find capitalized words or multi-word phrases (e.g. "Eiffel Tower", "World Health Organization")
        capitalized_phrases = re.findall(r"\b[A-Z][a-z0-9]*(?:\s+[A-Z][a-z0-9]*)*\b", text)

        # Filter out capitalized sentence starters that are stopwords
        filtered_phrases = []
        for phrase in capitalized_phrases:
            words = phrase.split()
            if len(words) == 1 and words[0].lower() in WikipediaService.STOPWORDS:
                continue
            filtered_phrases.append(phrase)

        return filtered_phrases

    @staticmethod
    async def search_wikipedia(
        query: str,
        limit: int = 5
    ) -> List[Dict[str, str]]:
        """
        Search Wikipedia for articles related to the query.

        Args:
            query: Search query string
            limit: Maximum number of candidate results

        Returns:
            List of dicts with 'title' and 'snippet' keys
        """
        if not query or len(query.strip()) < 2:
            return []

        clean_query = re.sub(r"[^\w\s]", " ", query).strip()
        if not clean_query:
            return []

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
                        logger.error(f"Wikipedia search failed with HTTP {response.status}")
                        return []

                    data = await response.json()
                    results = data.get("query", {}).get("search", [])

                    candidates = []
                    for result in results:
                        title = result.get("title", "")
                        # Filter out obvious disambiguation or meta pages
                        if title.lower().endswith("(disambiguation)") or "list of" in title.lower():
                            continue

                        raw_snippet = result.get("snippet", "")
                        clean_snippet = re.sub(r"<[^>]+>", "", raw_snippet)

                        candidates.append({
                            "title": title,
                            "snippet": clean_snippet
                        })

                    return candidates

        except asyncio.TimeoutError:
            logger.error(f"Wikipedia search timeout for query: {query}")
            return []
        except Exception as e:
            logger.error(f"Wikipedia search error for query '{query}': {str(e)}")
            return []

    @staticmethod
    async def get_wikipedia_article(
        title: str,
        intro_only: bool = False
    ) -> Optional[Dict[str, Any]]:
        """
        Retrieve the content of a specific Wikipedia article.

        Args:
            title: Wikipedia article title
            intro_only: If True, fetches only the introductory summary

        Returns:
            Dict with 'title', 'content', 'url', 'extract' keys or None
        """
        if not title or len(title.strip()) < 1:
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
                        logger.error(f"Wikipedia article fetch failed: HTTP {response.status}")
                        return None

                    data = await response.json()
                    pages = data.get("query", {}).get("pages", {})

                    if not pages:
                        return None

                    page = list(pages.values())[0]

                    if "missing" in page:
                        logger.info(f"Article not found on Wikipedia: {title}")
                        return None

                    article_title = page.get("title", title)
                    content = page.get("extract", "")

                    if not content or len(content.strip()) < 20:
                        logger.warning(f"No usable content in Wikipedia article: {title}")
                        return None

                    # Detect disambiguation page content
                    if "may refer to:" in content[:300].lower() or "can refer to:" in content[:300].lower():
                        logger.info(f"Article '{article_title}' is a disambiguation page. Skipping.")
                        return None

                    wikipedia_url = f"https://en.wikipedia.org/wiki/{quote(article_title.replace(' ', '_'))}"

                    return {
                        "title": article_title,
                        "content": content,
                        "url": wikipedia_url,
                        "extract": content[:600]
                    }

        except asyncio.TimeoutError:
            logger.error(f"Wikipedia article fetch timeout for: {title}")
            return None
        except Exception as e:
            logger.error(f"Wikipedia article fetch error for '{title}': {str(e)}")
            return None

    @staticmethod
    def get_relevant_evidence(
        article_content: str,
        claim: str,
        max_length: int = 800
    ) -> Optional[Dict[str, Any]]:
        """
        Extract the most relevant evidence sentences and context from article content for a claim.

        Args:
            article_content: Full text of the Wikipedia article
            claim: Factual claim string
            max_length: Maximum character length for evidence snippet

        Returns:
            Dict with 'evidence', 'score' (match ratio 0.0-1.0), 'matched_keywords'
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

        # Split into distinct paragraphs
        paragraphs = [p.strip() for p in article_content.split("\n") if len(p.strip()) > 30]
        if not paragraphs:
            paragraphs = [article_content.strip()]

        keywords_set = set(keywords)
        scored_paragraphs = []

        for idx, para in enumerate(paragraphs):
            para_lower = para.lower()
            matched = [kw for kw in keywords_set if kw in para_lower]
            if matched:
                score = len(matched) / len(keywords_set)
                # Boost intro paragraphs slightly
                if idx == 0:
                    score += 0.15
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

        # Extract specific sentences containing matched keywords
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
        claim: str,
        query: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Dynamically search and select the best matching Wikipedia article for a claim.
        Uses entity recognition, claim keywords, and contextual relevance scoring.

        Args:
            claim: Factual statement to verify
            query: Optional original user query for context

        Returns:
            Dict with 'title', 'content', 'url', 'extract' or None
        """
        if not claim or len(claim.strip()) < 3:
            return None

        # Build candidate search queries:
        # 1. Extracted named entities / capitalized phrases (e.g. "Eiffel Tower", "World Health Organization")
        # 2. Entire claim
        # 3. Query + Claim if available
        search_queries = []

        entities = WikipediaService.extract_entities(claim)
        for entity in entities:
            if entity not in search_queries:
                search_queries.append(entity)

        clean_claim = re.sub(r"[^\w\s]", " ", claim).strip()
        if clean_claim and clean_claim not in search_queries:
            search_queries.append(clean_claim)

        if query:
            clean_user_query = re.sub(r"[^\w\s]", " ", query).strip()
            if clean_user_query and clean_user_query not in search_queries:
                search_queries.append(clean_user_query)

        # Execute searches and collect candidate articles
        all_candidates: List[Dict[str, str]] = []
        seen_titles = set()

        for sq in search_queries[:3]:
            results = await WikipediaService.search_wikipedia(sq, limit=4)
            for res in results:
                t = res["title"]
                if t.lower() not in seen_titles:
                    seen_titles.add(t.lower())
                    all_candidates.append(res)

        if not all_candidates:
            return None

        # Score candidates against claim keywords
        claim_keywords = set(WikipediaService.extract_keywords(claim))
        scored_candidates = []

        for cand in all_candidates:
            title_lower = cand["title"].lower()
            snippet_lower = cand["snippet"].lower()

            # Count keyword matches in title (weighted x2) and snippet
            title_matches = sum(1 for kw in claim_keywords if kw in title_lower)
            snippet_matches = sum(1 for kw in claim_keywords if kw in snippet_lower)

            cand_score = (title_matches * 2.0) + snippet_matches
            scored_candidates.append((cand_score, cand))

        # Sort candidates by relevance score
        scored_candidates.sort(key=lambda x: x[0], reverse=True)

        # Retrieve full article for top candidates until a valid one is found
        for score, cand in scored_candidates[:3]:
            article = await WikipediaService.get_wikipedia_article(cand["title"])
            if article and article.get("content"):
                return article

        return None

