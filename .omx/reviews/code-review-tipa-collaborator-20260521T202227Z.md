# Code Review Report: TIPA US Academic Collaborator Agent

Files reviewed: 4 implementation/doc/test files
- `collaborator_agent.py`
- `server.py`
- `tests/test_collaborator_agent.py`
- `README.md`

## Review categories

### Security
- PASS: Browser rendering uses `textContent` for untrusted result data; no `eval`/dynamic script execution.
- PASS: POST body size capped at 200 KB.
- PASS: Malformed JSON receives 400 response.
- PASS: Google Scholar link is never scraped.
- PASS: No hardcoded API keys or secrets.

### Code quality / maintainability
- PASS: Core matching logic is separated from HTTP/UI server.
- PASS: Tests cover parser, scoring/filtering, server smoke, malformed JSON, and optional Scholar behavior by implication.
- FIXED during review: Semantic Scholar author URL parsing now supports both `/author/name-id` and `/author/name/id` URL shapes.
- FIXED during review: OpenAlex fallback lookups are capped to avoid slow live-demo behavior when affiliations are sparse.

### Performance
- PASS: Candidate author detail batching is used for Semantic Scholar.
- PASS: OpenAlex fallback has a lookup budget.
- WATCH: Live Semantic Scholar/OpenAlex latency and rate limits are still external constraints; demo data path is available for reliable presentation.

### Spec compliance
- PASS: Runnable Python server with browser UI and Run button.
- PASS: Manual inputs include requester, Semantic Scholar/ORCID/Scholar hints, region, min relevance, max neighbor, result limit.
- PASS: Returns sorted filterable list, not fixed top-5.
- PASS: Low-relevance candidates hidden by threshold.
- PASS: Candidate output includes score breakdown, evidence, rationale, region tag, coauthor heuristic, and outreach email.

## Issues by severity

CRITICAL: none
HIGH: none
MEDIUM: none unresolved
LOW: none unresolved

## Architectural status

CLEAR. The standard-library server is appropriate for the clarified 2-hour demo scope and avoids dependency friction. Heuristic data limitations are documented rather than hidden.

## Verification reviewed

- `python -m unittest discover -s tests -v`: 9 tests passed.
- `python -m compileall collaborator_agent.py server.py tests`: passed.

## Final synthesis

- code-reviewer recommendation: APPROVE
- architect status: CLEAR
- final recommendation: APPROVE

RECOMMENDATION: APPROVE

## Post-UltraQA addendum

UltraQA found an oversized-body response stability issue. Fix reviewed: server.py now drains bounded oversized bodies before returning 400, and 	ests/test_collaborator_agent.py includes a regression test. Rerun verification: 10 unittest cases passed; compileall passed. Verdict remains APPROVE / CLEAR.

## Final verification addendum
- Final tests after QA fix and cleanup: python -B -m unittest discover -s tests -v passed 10 tests.
- Final syntax check: python -B -m py_compile collaborator_agent.py server.py tests/test_collaborator_agent.py passed.
- Final verdict remains APPROVE / CLEAR.
