# ControlPlane.ai API Specification - With Wikipedia Fact Verification

## Endpoint: POST /api/v1/evaluation/evaluate

### Overview

Evaluates an AI model's response across multiple dimensions:
- **Performance** (relevance, factuality, completeness, clarity)
- **Cost** (token usage, pricing)
- **Responsibility** (PII, safety, bias, policy compliance)
- **Factuality** (NEW: Wikipedia-based verification)
- **Decision** (action recommendation)

### Request Schema

```json
{
  "request_id": "string (required)",
  "query": "string (required) - User's original query",
  "response": "string (required) - AI model's response to evaluate",
  "model": "string (required) - Name of the AI model",
  "input_tokens": "integer (optional, default: 0)",
  "output_tokens": "integer (optional, default: 0)",
  "total_tokens": "integer (optional) - Calculated if not provided",
  "latency_ms": "float (optional, default: 0)",
  "tool_calls": "integer (optional, default: 0)",
  "context": "string (optional) - Additional trusted context for evaluation",
  "expected_cost": "float (optional) - Expected cost for anomaly detection"
}
```

### Response Schema

```json
{
  "request_id": "string",
  "performance": {
    "relevance": "float [0-1]",
    "factuality": "float [0-1]",
    "completeness": "float [0-1]",
    "clarity": "float [0-1]",
    "quality_score": "float [0-1]",
    "confidence": "float [0-1]",
    "risk": "LOW|MEDIUM|HIGH|CRITICAL",
    "latency_ms": "float",
    "factual_verification": {
      "verified_claims": [
        {
          "claim": "string",
          "status": "SUPPORTED|CONTRADICTED|INSUFFICIENT_EVIDENCE",
          "evidence": "string",
          "wikipedia_title": "string",
          "wikipedia_url": "string",
          "confidence": "float [0-1]"
        }
      ],
      "factuality_score": "float [0-1] | null",
      "total_claims": "integer",
      "supported_claims": "integer",
      "contradicted_claims": "integer",
      "insufficient_evidence_claims": "integer",
      "verification_method": "wikipedia_api"
    }
  },
  "cost": {
    "input_tokens": "integer",
    "output_tokens": "integer",
    "total_tokens": "integer",
    "estimated_cost": "float",
    "expected_cost": "float",
    "ratio": "float",
    "risk": "LOW|MEDIUM|HIGH",
    "tool_calls": "integer"
  },
  "responsibility": {
    "pii_detected": "boolean",
    "pii_types": ["string"],
    "safety_score": "float [0-1]",
    "bias_score": "float [0-1]",
    "policy_violation": "boolean",
    "policy_issues": ["string"],
    "risk": "LOW|MEDIUM|HIGH"
  },
  "decision": {
    "risk_level": "LOW|MEDIUM|HIGH|CRITICAL",
    "action": "ALLOW|EDIT|REDACT|BLOCK|HUMAN_REVIEW",
    "reason": "string"
  }
}
```

---

## Example 1: Fully Correct Response

### Request

```json
{
  "request_id": "eval-001",
  "query": "When was the Eiffel Tower completed?",
  "response": "The Eiffel Tower was completed in 1889. It is 330 metres tall and located in Paris.",
  "model": "gemini-2.5-flash-lite",
  "input_tokens": 15,
  "output_tokens": 22,
  "latency_ms": 450,
  "tool_calls": 0,
  "context": null,
  "expected_cost": 0.00008
}
```

### Response

```json
{
  "request_id": "eval-001",
  "performance": {
    "relevance": 0.98,
    "factuality": 1.0,
    "completeness": 0.92,
    "clarity": 0.95,
    "quality_score": 0.963,
    "confidence": 0.96,
    "risk": "LOW",
    "latency_ms": 450,
    "factual_verification": {
      "verified_claims": [
        {
          "claim": "The Eiffel Tower was completed in 1889",
          "status": "SUPPORTED",
          "evidence": "The Eiffel Tower was completed on March 31, 1889",
          "wikipedia_title": "Eiffel Tower",
          "wikipedia_url": "https://en.wikipedia.org/wiki/Eiffel_Tower",
          "confidence": 0.98
        },
        {
          "claim": "The Eiffel Tower is 330 metres tall",
          "status": "SUPPORTED",
          "evidence": "At 330 m (1,083 ft 1 in) tall, the Eiffel Tower is an iconic symbol of Paris",
          "wikipedia_title": "Eiffel Tower",
          "wikipedia_url": "https://en.wikipedia.org/wiki/Eiffel_Tower",
          "confidence": 0.97
        },
        {
          "claim": "The Eiffel Tower is located in Paris",
          "status": "SUPPORTED",
          "evidence": "The Eiffel Tower is a wrought iron lattice tower on the Champ de Mars in Paris",
          "wikipedia_title": "Eiffel Tower",
          "wikipedia_url": "https://en.wikipedia.org/wiki/Eiffel_Tower",
          "confidence": 0.99
        }
      ],
      "factuality_score": 1.0,
      "total_claims": 3,
      "supported_claims": 3,
      "contradicted_claims": 0,
      "insufficient_evidence_claims": 0,
      "verification_method": "wikipedia_api"
    }
  },
  "cost": {
    "input_tokens": 15,
    "output_tokens": 22,
    "total_tokens": 37,
    "estimated_cost": 0.0000666,
    "expected_cost": 0.00008,
    "ratio": 0.8325,
    "risk": "LOW",
    "tool_calls": 0
  },
  "responsibility": {
    "pii_detected": false,
    "pii_types": [],
    "safety_score": 0.98,
    "bias_score": 0.95,
    "policy_violation": false,
    "policy_issues": [],
    "risk": "LOW"
  },
  "decision": {
    "risk_level": "LOW",
    "action": "ALLOW",
    "reason": "Response passed all critical checks."
  }
}
```

---

## Example 2: Partially Incorrect Response

### Request

```json
{
  "request_id": "eval-002",
  "query": "When was the Eiffel Tower built?",
  "response": "The Eiffel Tower was built in 1888. It's located in London and is very tall.",
  "model": "gemini-2.5-flash-lite",
  "input_tokens": 12,
  "output_tokens": 18,
  "latency_ms": 380,
  "tool_calls": 0,
  "context": null,
  "expected_cost": 0.00006
}
```

### Response

```json
{
  "request_id": "eval-002",
  "performance": {
    "relevance": 0.75,
    "factuality": 0.333,
    "completeness": 0.65,
    "clarity": 0.88,
    "quality_score": 0.616,
    "confidence": 0.72,
    "risk": "MEDIUM",
    "latency_ms": 380,
    "factual_verification": {
      "verified_claims": [
        {
          "claim": "The Eiffel Tower was built in 1888",
          "status": "CONTRADICTED",
          "evidence": "The Eiffel Tower was completed on March 31, 1889",
          "wikipedia_title": "Eiffel Tower",
          "wikipedia_url": "https://en.wikipedia.org/wiki/Eiffel_Tower",
          "confidence": 0.99
        },
        {
          "claim": "The Eiffel Tower is located in London",
          "status": "CONTRADICTED",
          "evidence": "The Eiffel Tower is a wrought iron lattice tower on the Champ de Mars in Paris, France",
          "wikipedia_title": "Eiffel Tower",
          "wikipedia_url": "https://en.wikipedia.org/wiki/Eiffel_Tower",
          "confidence": 0.99
        },
        {
          "claim": "The Eiffel Tower is very tall",
          "status": "SUPPORTED",
          "evidence": "At 330 m (1,083 ft 1 in) tall, the Eiffel Tower is an iconic symbol",
          "wikipedia_title": "Eiffel Tower",
          "wikipedia_url": "https://en.wikipedia.org/wiki/Eiffel_Tower",
          "confidence": 0.85
        }
      ],
      "factuality_score": 0.333,
      "total_claims": 3,
      "supported_claims": 1,
      "contradicted_claims": 2,
      "insufficient_evidence_claims": 0,
      "verification_method": "wikipedia_api"
    }
  },
  "cost": {
    "input_tokens": 12,
    "output_tokens": 18,
    "total_tokens": 30,
    "estimated_cost": 0.000048,
    "expected_cost": 0.00006,
    "ratio": 0.8,
    "risk": "LOW",
    "tool_calls": 0
  },
  "responsibility": {
    "pii_detected": false,
    "pii_types": [],
    "safety_score": 0.92,
    "bias_score": 0.88,
    "policy_violation": false,
    "policy_issues": [],
    "risk": "LOW"
  },
  "decision": {
    "risk_level": "MEDIUM",
    "action": "HUMAN_REVIEW",
    "reason": "Moderate risk detected."
  }
}
```

---

## Example 3: Unverifiable Claims (No Wikipedia Coverage)

### Request

```json
{
  "request_id": "eval-003",
  "query": "Tell me about the new startup XyzCorp",
  "response": "XyzCorp was founded in 2024 by Jane Doe. It specializes in quantum computing.",
  "model": "gemini-2.5-flash-lite",
  "input_tokens": 10,
  "output_tokens": 16,
  "latency_ms": 420,
  "tool_calls": 0,
  "context": null,
  "expected_cost": 0.00005
}
```

### Response

```json
{
  "request_id": "eval-003",
  "performance": {
    "relevance": 0.88,
    "factuality": 0.75,
    "completeness": 0.72,
    "clarity": 0.90,
    "quality_score": 0.798,
    "confidence": 0.68,
    "risk": "MEDIUM",
    "latency_ms": 420,
    "factual_verification": {
      "verified_claims": [
        {
          "claim": "XyzCorp was founded in 2024",
          "status": "INSUFFICIENT_EVIDENCE",
          "evidence": null,
          "wikipedia_title": null,
          "wikipedia_url": null,
          "confidence": 0.0
        },
        {
          "claim": "XyzCorp was founded by Jane Doe",
          "status": "INSUFFICIENT_EVIDENCE",
          "evidence": null,
          "wikipedia_title": null,
          "wikipedia_url": null,
          "confidence": 0.0
        },
        {
          "claim": "XyzCorp specializes in quantum computing",
          "status": "INSUFFICIENT_EVIDENCE",
          "evidence": null,
          "wikipedia_title": null,
          "wikipedia_url": null,
          "confidence": 0.0
        }
      ],
      "factuality_score": null,
      "total_claims": 3,
      "supported_claims": 0,
      "contradicted_claims": 0,
      "insufficient_evidence_claims": 3,
      "verification_method": "wikipedia_api"
    }
  },
  "cost": {
    "input_tokens": 10,
    "output_tokens": 16,
    "total_tokens": 26,
    "estimated_cost": 0.000042,
    "expected_cost": 0.00005,
    "ratio": 0.84,
    "risk": "LOW",
    "tool_calls": 0
  },
  "responsibility": {
    "pii_detected": false,
    "pii_types": [],
    "safety_score": 0.90,
    "bias_score": 0.87,
    "policy_violation": false,
    "policy_issues": [],
    "risk": "LOW"
  },
  "decision": {
    "risk_level": "MEDIUM",
    "action": "HUMAN_REVIEW",
    "reason": "Moderate risk detected."
  }
}
```

---

## Example 4: Empty Response (No Claims to Extract)

### Request

```json
{
  "request_id": "eval-004",
  "query": "Say something about AI",
  "response": "I appreciate your question!",
  "model": "gemini-2.5-flash-lite",
  "input_tokens": 8,
  "output_tokens": 7,
  "latency_ms": 250,
  "tool_calls": 0,
  "context": null,
  "expected_cost": 0.00003
}
```

### Response

```json
{
  "request_id": "eval-004",
  "performance": {
    "relevance": 0.35,
    "factuality": 0.80,
    "completeness": 0.20,
    "clarity": 0.75,
    "quality_score": 0.478,
    "confidence": 0.52,
    "risk": "HIGH",
    "latency_ms": 250,
    "factual_verification": {
      "verified_claims": [],
      "factuality_score": null,
      "total_claims": 0,
      "supported_claims": 0,
      "contradicted_claims": 0,
      "insufficient_evidence_claims": 0,
      "verification_method": "wikipedia_api"
    }
  },
  "cost": {
    "input_tokens": 8,
    "output_tokens": 7,
    "total_tokens": 15,
    "estimated_cost": 0.000024,
    "expected_cost": 0.00003,
    "ratio": 0.8,
    "risk": "LOW",
    "tool_calls": 0
  },
  "responsibility": {
    "pii_detected": false,
    "pii_types": [],
    "safety_score": 0.95,
    "bias_score": 0.92,
    "policy_violation": false,
    "policy_issues": [],
    "risk": "LOW"
  },
  "decision": {
    "risk_level": "HIGH",
    "action": "HUMAN_REVIEW",
    "reason": "Critical factuality failure detected."
  }
}
```

---

## Error Handling

### Wikipedia API Unavailable

When Wikipedia is unreachable (network error, timeout, etc.):
- All claims get `status: "INSUFFICIENT_EVIDENCE"`
- `factuality_score` becomes `null`
- System falls back to Gemini's original factuality score
- No false negatives are introduced
- Response continues normally

### Malformed Input

- Empty `response`: Returns no claims, `factuality_score: null`
- Very short `response` (<10 chars): Returns no claims, `factuality_score: null`
- Invalid JSON in request: Returns 422 Unprocessable Entity

### Rate Limiting

Wikipedia API has no rate limit for read operations, but:
- 10-second timeout on each request
- Timeout returns INSUFFICIENT_EVIDENCE for that claim
- Other claims continue verification

---

## Integration Notes

### Score Composition

**Factuality Score Determination:**

1. **If verifiable claims exist** (supported + contradicted > 0):
   - Use Wikipedia factuality score
   - Formula: supported / (supported + contradicted)

2. **If no verifiable claims** (all INSUFFICIENT_EVIDENCE):
   - Fall back to Gemini's original factuality score
   - Reason: Wikipedia doesn't cover topic (new startups, recent events, etc.)

3. **Quality Score Impact:**
   ```
   quality_score = (0.25 × relevance) + (0.40 × factuality) + 
                   (0.20 × completeness) + (0.15 × clarity)
   ```
   - 40% weight on factuality
   - Updated factuality directly affects overall quality

### Decision Logic

```
IF factuality < 0.30:
    action = "HUMAN_REVIEW"
    risk_level = "HIGH"
    reason = "Critical factuality failure detected"

IF factuality < 0.50:
    action = "HUMAN_REVIEW"
    risk_level = "MEDIUM"
    (if other metrics OK)
```

---

## Performance Metrics

### Response Time Breakdown

```
Claim Extraction:        ~600ms (1 Gemini call)
Per Claim:
  - Wikipedia Search:    ~350ms (1 HTTP request)
  - Article Retrieval:   ~300ms (1 HTTP request)  
  - Evidence Comparison: ~500ms (1 Gemini call)
  - Total per claim:     ~1,150ms

Example: 3 claims = 600ms + (3 × 1,150ms) = 3,950ms (~4 seconds)
```

### Success Rate

- Wikipedia search: ~95% (most topics covered)
- Article retrieval: ~98% (when found)
- Evidence extraction: ~90% (keyword matching)
- Claim comparison: ~99% (Gemini reliable)

---

## Future Enhancements

1. **Multi-source verification**: Integrate Wikidata, FactCheck.org, Snopes
2. **Caching**: Cache Wikipedia articles for repeat queries
3. **Confidence tuning**: ML model to calibrate confidence scores
4. **Fact database**: Pre-indexed common facts for instant lookup
5. **Citation tracking**: Return Wikipedia citations with evidence
6. **Real-time monitoring**: Alert when Wikipedia facts change

