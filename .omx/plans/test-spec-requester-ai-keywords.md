# Test Spec: Requester AI-Assisted Keyword Extraction

## Unit Tests

- `parse_match_request` accepts truthy `ai_keywords`.
- AI keyword parser accepts valid JSON with topic and method keyword arrays.
- AI keyword parser rejects invalid JSON and empty keyword output.
- Codex wrapper failure paths return fallback metadata rather than raising into match flow.
- Mocked AI extraction populates requester debug with `keyword_source: "ai"` and reranks using AI requester keywords.
- Normal non-AI matching has `keyword_source: "heuristic"`.

## Integration / Smoke Tests

- `/api/match` normal demo POST returns requester debug and heuristic source.
- `/api/match` demo POST with `ai_keywords: true` and mocked extractor returns requester debug with AI source.
- Homepage contains `AI-assisted keyword extraction` UI affordance.

## Adversarial QA

- Malformed Codex output does not break the request.
- Missing Codex executable does not break the request.
- Prompt-injection-like publication title text is treated as data in the prompt payload and does not change local control flow.
- Empty requester publications fall back cleanly.
- Repeated AI button requests remain bounded to one backend extraction attempt per request.

## Verification Commands

- `python -m unittest`
- Focused temporary smoke script if needed for API payload behavior.

