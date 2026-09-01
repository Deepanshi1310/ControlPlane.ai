# Wikipedia-Based Factual Verification System

## Overview

The ControlPlane.ai system has been enhanced with automatic factual verification using Wikipedia. Instead of requiring users to provide ground-truth facts manually, the system now:

1. **Extracts factual claims** from AI responses using Gemini
2. **Searches Wikipedia** for relevant articles via the MediaWiki API
3. **Retrieves evidence** from Wikipedia articles
4. **Compares claims against evidence** using Gemini
5. **Calculates an accuracy score** based on verification results
6. **Integrates the score** into the existing evaluation pipeline

## Architecture

### New Components

#### 1. Wikipedia Service (`app/services/wikipedia_service.py`)

Handles all Wikipedia API interactions using the official MediaWiki API.

**Key Methods:**

```python
async search_wikipedia(query: str, limit: int = 5) -> List[Dict]
```
- Searches Wikipedia for articles related to a query
- Returns list of results with title and snippet
- Handles timeouts and errors gracefully

```python
async get_wikipedia_article(title: str, sections: bool = True) -> Optional[Dict]
```
- Retrieves the full content of a Wikipedia article
- Returns dict with title, content, url, extract
- Handles redirects and missing articles

```python
async get_relevant_evidence(article_content: str, claim: str, max_length: int = 1000) -> Optional[str]
```
- Extracts the most relevant excerpt from an article for a claim
- Uses keyword matching and paragraph scoring
- Returns excerpts up to max_length characters

```python
async search_and_get_article(query: str) -> Optional[Dict]
```
- Convenience method that searches and retrieves article in one call
- Tries top 3 search results

#### 2. Fact Verification Service (`app/services/fact_verification_service.py`)

Orchestrates the fact-checking pipeline using Wikipedia evidence.

**Key Methods:**

```python
async extract_claims(response: str) -> List[FactualClaim]
```
- Extracts discrete factual claims from AI response
- Uses Gemini LLM to identify verifiable statements
- Filters out opinions, advice, and hypothetical scenarios
- Returns list of FactualClaim objects

```python
async verify_claim(claim: str) -> ClaimVerification
```
- Verifies a single claim against Wikipedia
- Returns ClaimVerification with status (SUPPORTED/CONTRADICTED/INSUFFICIENT_EVIDENCE)
- Includes evidence, Wikipedia title, URL, and confidence

```python
async verify_response(response: str) -> FactVerificationResult
```
- Main entry point for complete response fact-checking
- Extracts all claims and verifies each one
- Calculates overall factuality score
- Returns FactVerificationResult with all details

### Key Models

#### ClaimVerificationResult (in `app/models/evaluation.py`)

```python
class ClaimVerificationResult(BaseModel):
    claim: str
    status: ClaimStatus  # SUPPORTED | CONTRADICTED | INSUFFICIENT_EVIDENCE
    evidence: Optional[str]  # Relevant Wikipedia excerpt
    wikipedia_title: Optional[str]  # Article title used
    wikipedia_url: Optional[str]  # Article URL
    confidence: float  # 0.0 to 1.0
```

#### FactualityVerificationResult

```python
class FactualityVerificationResult(BaseModel):
    verified_claims: List[ClaimVerificationResult]
    factuality_score: Optional[float]  # 0.0 to 1.0 (None if no verifiable claims)
    total_claims: int
    supported_claims: int
    contradicted_claims: int
    insufficient_evidence_claims: int
    verification_method: str = "wikipedia_api"
```

### Integration Points

#### Updated PerformanceResult

```python
class PerformanceResult(BaseModel):
    relevance: float
    factuality: float
    completeness: float
    clarity: float
    quality_score: float
    confidence: float
    risk: RiskLevel
    latency_ms: float
    
    # NEW: Detailed fact verification results
    factual_verification: Optional[FactualityVerificationResult] = None
```

#### Updated ControlPlaneService

The evaluation pipeline now includes Wikipedia fact verification:

```
1. FACT VERIFICATION (Wikipedia) ← NEW
   └─ Extract claims → Search Wikipedia → Compare claims → Calculate score

2. PERFORMANCE (existing)
   └─ Gemini evaluation + Wikipedia factuality override

3. COST (existing)
   └─ Calculate token costs

4. RESPONSIBILITY (existing)
   └─ PII detection + safety/bias evaluation

5. DECISION (existing)
   └─ Combine all results for action recommendation
```

## Factuality Score Calculation

The factuality score is calculated using the following logic:

### Scoring Rules

- **SUPPORTED**: Claim is verified against Wikipedia evidence → counts as 1.0
- **CONTRADICTED**: Claim contradicts Wikipedia evidence → counts as 0.0
- **INSUFFICIENT_EVIDENCE**: Not enough Wikipedia information to judge → excluded

### Formula

```
Supported claims = number of SUPPORTED claims
Contradicted claims = number of CONTRADICTED claims

If (Supported + Contradicted) == 0:
    factuality_score = None (cannot calculate)
Else:
    factuality_score = Supported / (Supported + Contradicted)
```

### Examples

**Example 1: Partially Correct**
```
3 claims:
- Claim 1: SUPPORTED
- Claim 2: SUPPORTED
- Claim 2: CONTRADICTED

Factuality = 2 / (2 + 1) = 0.667 (66.7%)
```

**Example 2: All Insufficient**
```
2 claims:
- Claim 1: INSUFFICIENT_EVIDENCE
- Claim 2: INSUFFICIENT_EVIDENCE

Factuality = None (falls back to Gemini score)
```

**Example 3: All Supported**
```
3 claims:
- Claim 1: SUPPORTED
- Claim 2: SUPPORTED
- Claim 3: SUPPORTED

Factuality = 3 / (3 + 0) = 1.0 (100%)
```

## Data Flow

### Request

```json
{
  "request_id": "req-123",
  "query": "When was the Eiffel Tower completed?",
  "response": "The Eiffel Tower was completed in 1889. It is 330 metres tall.",
  "model": "some-model",
  "input_tokens": 50,
  "output_tokens": 25,
  "total_tokens": 75,
  "latency_ms": 450,
  "tool_calls": 0,
  "context": null,
  "expected_cost": 0.001
}
```

### Internal Processing

**Step 1: Claim Extraction**
```python
# Gemini extracts claims from response
Claims extracted:
[
  {"claim": "The Eiffel Tower was completed in 1889"},
  {"claim": "The Eiffel Tower is 330 metres tall"}
]
```

**Step 2: Wikipedia Search & Evidence Retrieval**
```
Claim 1 → Search: "Eiffel Tower completed 1889"
          → Wikipedia Article Found: "Eiffel Tower"
          → Evidence: "The Eiffel Tower was completed in 1889"

Claim 2 → Search: "Eiffel Tower height 330 metres"
          → Wikipedia Article Found: "Eiffel Tower"
          → Evidence: "...330 m (1,083 ft 1 in) tall"
```

**Step 3: Claim Verification Against Evidence**
```python
# Gemini compares each claim against Wikipedia evidence
Claim 1 vs Evidence:
{
  "status": "SUPPORTED",
  "confidence": 0.98,
  "reasoning": "Wikipedia confirms completion date of 1889"
}

Claim 2 vs Evidence:
{
  "status": "SUPPORTED",
  "confidence": 0.95,
  "reasoning": "Wikipedia confirms height of 330 meters"
}
```

**Step 4: Score Calculation**
```python
supported_claims = 2
contradicted_claims = 0
factuality_score = 2 / (2 + 0) = 1.0 (100%)
```

### Response

```json
{
  "request_id": "req-123",
  "performance": {
    "relevance": 0.95,
    "factuality": 1.0,           // ← UPDATED with Wikipedia score
    "completeness": 0.85,
    "clarity": 0.90,
    "quality_score": 0.9125,
    "confidence": 0.92,
    "risk": "LOW",
    "latency_ms": 450,
    
    // NEW: Detailed fact verification results
    "factual_verification": {
      "verified_claims": [
        {
          "claim": "The Eiffel Tower was completed in 1889",
          "status": "SUPPORTED",
          "evidence": "The Eiffel Tower was completed in 1889",
          "wikipedia_title": "Eiffel Tower",
          "wikipedia_url": "https://en.wikipedia.org/wiki/Eiffel_Tower",
          "confidence": 0.98
        },
        {
          "claim": "The Eiffel Tower is 330 metres tall",
          "status": "SUPPORTED",
          "evidence": "...330 m (1,083 ft 1 in) tall...",
          "wikipedia_title": "Eiffel Tower",
          "wikipedia_url": "https://en.wikipedia.org/wiki/Eiffel_Tower",
          "confidence": 0.95
        }
      ],
      "factuality_score": 1.0,
      "total_claims": 2,
      "supported_claims": 2,
      "contradicted_claims": 0,
      "insufficient_evidence_claims": 0,
      "verification_method": "wikipedia_api"
    }
  },
  "cost": {...},
  "responsibility": {...},
  "decision": {...}
}
```

## Example: Contradicted Claim

### Input

```json
{
  "request_id": "req-456",
  "query": "When was the Eiffel Tower completed?",
  "response": "The Eiffel Tower was completed in 1888."
}
```

### Processing

**Claim Extracted:**
```
"The Eiffel Tower was completed in 1888."
```

**Wikipedia Evidence:**
```
"The Eiffel Tower was completed in 1889."
```

**Gemini Comparison:**
```json
{
  "status": "CONTRADICTED",
  "confidence": 0.99,
  "reasoning": "Wikipedia clearly states completion was in 1889, not 1888"
}
```

### Response (Partial)

```json
{
  "performance": {
    "factuality": 0.0,  // 0 supported / (0 + 1) = 0%
    "factual_verification": {
      "verified_claims": [
        {
          "claim": "The Eiffel Tower was completed in 1888.",
          "status": "CONTRADICTED",
          "evidence": "The Eiffel Tower was completed in 1889",
          "wikipedia_title": "Eiffel Tower",
          "wikipedia_url": "https://en.wikipedia.org/wiki/Eiffel_Tower",
          "confidence": 0.99
        }
      ],
      "factuality_score": 0.0,
      "total_claims": 1,
      "supported_claims": 0,
      "contradicted_claims": 1,
      "insufficient_evidence_claims": 0
    }
  },
  "decision": {
    "risk_level": "HIGH",
    "action": "HUMAN_REVIEW",
    "reason": "Critical factuality failure detected."
  }
}
```

## Modified Files

### New Files Created

1. **`app/services/wikipedia_service.py`** (275 lines)
   - Wikipedia API integration
   - Search, retrieve, and extract evidence
   - Error handling and timeouts

2. **`app/services/fact_verification_service.py`** (400+ lines)
   - Claim extraction using Gemini
   - Claim verification against Wikipedia
   - Score calculation and result aggregation

3. **`tests/test_wikipedia_verification.py`** (500+ lines)
   - 40+ test cases
   - Covers Wikipedia service, fact verification, and integration
   - Tests for success, error, and edge cases

4. **`tests/__init__.py`**
   - Package initialization file

### Modified Files

1. **`app/models/evaluation.py`**
   - Added `ClaimStatus` type
   - Added `ClaimVerificationResult` model
   - Added `FactualityVerificationResult` model
   - Enhanced `PerformanceResult` with optional `factual_verification` field

2. **`app/services/gemini_service.py`**
   - Added `call_gemini()` method for generic JSON responses
   - Supports claim extraction and verification prompts
   - Added logging for debugging

3. **`app/services/controlplane_service.py`**
   - Added `FactVerificationService` initialization
   - Integrated Wikipedia fact verification into evaluation pipeline
   - Overrides Gemini factuality with Wikipedia score
   - Attaches verification results to performance object

4. **`app/services/performance_service.py`**
   - Added `override_factuality_with_wikipedia()` static method
   - Implements intelligent score blending logic
   - Handles edge cases (no claims, all insufficient, etc.)

5. **`requirements.txt`**
   - Added `aiohttp` for async HTTP requests to Wikipedia API
   - Added `pytest` for testing
   - Added `pytest-asyncio` for async test support

### Unchanged Files

- `main.py` - No changes needed
- `app/routers/evaluation.py` - API contract unchanged
- `app/services/responsibility_service.py` - No changes
- `app/services/decision_service.py` - No changes needed (works with updated scores)
- `app/services/cost_service.py` - No changes
- `app/config.py` - No changes
- All other files remain unchanged

## Dependencies

### New Dependencies

```
aiohttp>=3.8.0     # Async HTTP requests to Wikipedia API
pytest>=7.0.0      # Testing framework
pytest-asyncio>=0.20.0  # Async test support
```

### Existing Dependencies (Unchanged)

```
fastapi
uvicorn[standard]
google-genai        # Gemini LLM for claim extraction and comparison
pydantic
pydantic-settings
python-dotenv
```

## Wikipedia API Details

The system uses the official **MediaWiki API** (Wikipedia's API), not HTML scraping.

### Endpoints Used

1. **Search Endpoint**
   ```
   https://en.wikipedia.org/w/api.php?action=query&list=search&srsearch=<query>
   ```
   - Searches Wikipedia articles
   - Returns 3-5 most relevant results
   - Used for claim-based article discovery

2. **Article Content Endpoint**
   ```
   https://en.wikipedia.org/w/api.php?action=query&titles=<title>&prop=extracts
   ```
   - Retrieves full plain-text article content
   - Handles redirects automatically
   - Extracts up to ~6000 characters by default

### Response Format

All responses are JSON, structured as:
```json
{
  "query": {
    "pages": {
      "page_id": {
        "title": "Article Title",
        "extract": "Plain text content..."
      }
    }
  }
}
```

### Error Handling

- **Network timeouts** (10 seconds) → Return INSUFFICIENT_EVIDENCE
- **API errors** (4xx, 5xx) → Return INSUFFICIENT_EVIDENCE
- **Missing articles** → Return INSUFFICIENT_EVIDENCE
- **Empty content** → Return INSUFFICIENT_EVIDENCE
- **No relevant evidence** → Return INSUFFICIENT_EVIDENCE

The system **fails gracefully** - no claim is marked as false due to Wikipedia unavailability.

## LLM Usage

The system uses Gemini LLM for two specific tasks:

### 1. Claim Extraction

**Prompt:**
- Asks Gemini to extract discrete factual claims from the AI response
- Filters out opinions, advice, and hypothetical scenarios
- Returns JSON array of claims

**Why LLM?**
- Natural language understanding needed to distinguish facts from opinions
- Humans can do this; machines need semantic understanding

### 2. Claim-Evidence Comparison

**Prompt:**
- Provides claim + Wikipedia evidence excerpt
- Asks Gemini to determine: SUPPORTED, CONTRADICTED, or INSUFFICIENT_EVIDENCE
- Returns status + confidence + reasoning

**Why LLM?**
- Semantic matching needed (claim may rephrase fact)
- Handles implicit contradictions
- Provides confidence scores and reasoning

### Important Constraints

- ✅ Gemini receives Wikipedia evidence as explicit context
- ✅ Gemini does NOT invent ground truth independently
- ✅ Wikipedia is the authority, not Gemini
- ✅ No circular verification (response not used as its own evidence)

## Performance Considerations

### Request Processing Time

```
Wikipedia fact verification adds approximately:
- Claim extraction: ~500-800ms (1 Gemini API call)
- Per claim:
  - Wikipedia search: ~300-500ms (1 HTTP request)
  - Article retrieval: ~200-400ms (1 HTTP request)
  - Evidence comparison: ~400-600ms (1 Gemini API call)
  Total per claim: ~1-2 seconds

Example: 3 claims = +4-6 seconds overhead
```

### Optimization Tips

1. **Caching**: Consider caching Wikipedia articles for frequently-discussed topics
2. **Parallel Processing**: Multiple claims can be verified in parallel (already asynchronous)
3. **Timeouts**: Wikipedia searches have 10-second timeout; adjust if needed
4. **Batch Size**: Extract claims in batches to reduce Gemini API calls

### Memory Usage

- Minimal (Wikipedia articles stored temporarily during verification)
- Async processing prevents memory accumulation

## Testing

### Test Coverage

The test suite includes 40+ test cases covering:

**Wikipedia Service Tests:**
- Successful searches and article retrieval
- Empty/invalid queries
- API errors and network failures
- Evidence extraction with/without keywords
- Search and get article combined flow

**Fact Verification Service Tests:**
- Claim extraction success
- Empty/short responses
- Claim verification with SUPPORTED status
- Claim verification with CONTRADICTED status
- Claim verification with INSUFFICIENT_EVIDENCE status
- Multiple claims verification
- Factuality score calculation (mixed results)
- Edge cases (all insufficient, all supported, all contradicted)

**Integration Tests:**
- PerformanceService factuality override logic
- Handling of None/empty Wikipedia results
- Gemini score fallback when Wikipedia has no verifiable claims

### Running Tests

```bash
# Install test dependencies
pip install pytest pytest-asyncio

# Run all tests
pytest tests/

# Run specific test file
pytest tests/test_wikipedia_verification.py

# Run with verbose output
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=app
```

## Backward Compatibility

### API Contract

- ✅ Input schema (`EvaluationRequest`) unchanged
- ✅ Output structure (`EvaluationResponse`) backward compatible
- ✅ Existing fields remain in same positions
- ⚠️ `PerformanceResult.factuality` may now have different value (from Wikipedia)
- ➕ New optional field: `PerformanceResult.factual_verification`

### Existing Workflows

- ✅ Decision logic works with updated factuality scores
- ✅ Responsibility/safety evaluation independent of Wikipedia facts
- ✅ Cost calculations unchanged
- ✅ Response actions still correct (may be more conservative if factuality ↓)

### Migration

No migration needed:
1. Existing clients will receive new `factual_verification` data (optional field)
2. Existing clients can ignore the new field
3. Factuality scores will be more accurate (better for clients)
4. No API breaking changes

## Limitations and Considerations

### Known Limitations

1. **Wikipedia Availability**
   - Only works for topics covered in Wikipedia
   - Obscure or new topics won't be verifiable
   - Fails gracefully (returns INSUFFICIENT_EVIDENCE)

2. **Temporal Accuracy**
   - Wikipedia may have outdated information
   - Recent events may not be reflected immediately
   - Historical facts more reliable than current events

3. **Evidence Extraction**
   - Simple keyword-based extraction (no NLP)
   - May miss context-dependent evidence
   - LLM-based extraction would be more sophisticated but slower

4. **Claim Extraction**
   - May not extract implicit factual claims
   - Subjective claims may be incorrectly flagged as factual
   - Compound claims split into separate verification

### Best Use Cases

✅ **Good for:**
- Historical facts
- Geographical information
- Scientific/medical facts
- Notable people and events
- Measurements and statistics
- Published facts with Wikipedia coverage

❌ **Not ideal for:**
- Personal opinions
- Future predictions
- Subjective evaluations
- Very recent events
- Niche/specialized topics
- Fictional or hypothetical scenarios

## Future Enhancements

Possible improvements:

1. **Better Evidence Extraction**: Use NLP/semantic search instead of keyword matching
2. **Fact Checking Sources**: Integrate with Snopes, FactCheck.org, etc.
3. **Multilingual Support**: Extend beyond English Wikipedia
4. **Caching**: Cache Wikipedia articles and search results
5. **Confidence Calibration**: Improve confidence scoring with ML model
6. **Real-time Updates**: Monitor Wikipedia for fact changes
7. **Citation Tracking**: Return Wikipedia citations for evidence
8. **Fact Databases**: Integrate Wikidata for structured facts

## Troubleshooting

### Wikipedia API Returns Empty Results

**Cause**: Query too specific or article doesn't exist
**Solution**: 
- System returns INSUFFICIENT_EVIDENCE (correct behavior)
- Fallback to Gemini's original score
- No false negatives introduced

### Claim Extraction Returns No Claims

**Cause**: Response too vague/non-factual
**Solution**:
- No claims to verify
- Factuality score set to None
- Fallback to Gemini score

### Gemini API Fails During Verification

**Cause**: API timeout or rate limit
**Solution**:
- Caught in exception handler
- Returns INSUFFICIENT_EVIDENCE
- Full fact verification result returned with error state

### Wikipedia Access Blocked (Rate Limiting)

**Cause**: Too many requests to Wikipedia
**Solution**:
- Implement caching (store articles locally)
- Increase timeouts and retry logic
- Use Wikipedia's User-Agent header

## Configuration

### Environment Variables

No new environment variables required. Uses existing:
- `GEMINI_API_KEY`: For claim extraction and comparison

### Tunable Parameters

In `wikipedia_service.py`:
```python
BASE_URL = "https://en.wikipedia.org/w/api.php"
TIMEOUT = 10  # seconds for Wikipedia requests
MAX_RETRIES = 2  # retry attempts (currently unused, can be implemented)
```

In `fact_verification_service.py`:
```python
max_length = 1000  # Maximum evidence excerpt length
limit = 5  # Maximum Wikipedia search results to return
limit = 3  # Maximum search results to try for articles
```

## Summary

The Wikipedia-based fact verification system provides:

✅ **Automatic factual verification** without user-provided ground truth
✅ **Transparent evidence** showing what Wikipedia says
✅ **Per-claim tracking** of SUPPORTED/CONTRADICTED/INSUFFICIENT_EVIDENCE
✅ **Accurate accuracy scores** based on verifiable facts
✅ **Graceful degradation** if Wikipedia unavailable
✅ **Full backward compatibility** with existing API
✅ **Comprehensive testing** with 40+ test cases
✅ **Production-ready** with proper error handling and logging
✅ **Responsible separation** of Wikipedia facts from responsibility/safety evaluations
✅ **Clean architecture** with modular, reusable services

