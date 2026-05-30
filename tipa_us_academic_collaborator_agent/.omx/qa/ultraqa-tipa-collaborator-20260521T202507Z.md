# UltraQA Report

## Goal and success criteria
- Goal: Verify the TIPA collaborator demo server/UI behavior after implementation.
- Stop condition: Baseline tests pass and adversarial local HTTP scenarios pass after fixes.
- Safety bounds applied: local server only; no live external API calls; no secrets printed; no destructive commands; bounded request sizes/timeouts.

## Scenario matrix

| ID | User/attacker model | Scenario | Command/harness | Expected signal | Actual result | Status | Evidence | Cleanup |
|----|---------------------|----------|-----------------|-----------------|---------------|--------|----------|---------|
| ADV-UI-001 | Normal user / XSS reviewer | GET homepage, inspect Run button and safe rendering pattern | Inline Python HTTP harness | 200, Run present, uses `textContent`, no `eval` | 200, HTML length 10533 | PASS | Harness output | Server shutdown |
| ADV-API-001 | Normal demo user | POST demo request | Inline Python HTTP harness | Sorted visible candidates | 4 visible, sorted scores `[0.733, 0.659, 0.641, 0.586]` | PASS | Harness output | Server shutdown |
| ADV-API-002 | User tuning filters repeatedly | Rerun with `region=Boston`, `max_results=1` | Inline Python HTTP harness | Filter applied without restart | 1 visible, region filter echoed | PASS | Harness output | Server shutdown |
| ADV-MAL-001 | Malformed client | POST invalid JSON | Inline Python HTTP harness | 400 safe JSON error | 400 `invalid JSON body` | PASS | Harness output | Server shutdown |
| ADV-MAL-002 | Missing-field client | POST missing requester | Inline Python HTTP harness | 400 safe validation error | 400 `requester_name is required` | PASS | Harness output | Server shutdown |
| ADV-INJ-001 | Prompt-injection/XSS-like user | Requester name contains `<script>` and instruction override text | Inline Python HTTP harness | API treats as data, no secret leakage | 200; requester text preserved as JSON data; no API key leakage | PASS | Harness output | Server shutdown |
| ADV-FILTER-001 | Hostile parameter user | Extreme filter values | Inline Python HTTP harness | Values clamped safely | min=1.0, max_neighbor=1, max_results=100 | PASS | Harness output | Server shutdown |
| ADV-MAL-003 | Oversized-body client | POST 210KB body | Inline Python HTTP harness | Stable 400 response | Initially failed via connection abort; fixed; rerun returned 400 `request body too large` | PASS after fix | Harness output | Server shutdown |

## Commands run
- `[0] python -m unittest discover -s tests -v` — 10 tests passed after fixes.
- `[0] python -m compileall collaborator_agent.py server.py tests` — syntax compile passed.
- `[1 -> 0] inline UltraQA HTTP harness` — first run found oversized-body abort; second run passed 8 scenarios.

## Failures found
- ADV-MAL-003: oversized body response could abort on Windows because the server returned 400 without draining the request body.
  - User impact: hostile/large client could see a dropped connection instead of a useful JSON error.
  - Safety impact: bounded to local server request handling; no data leak.

## Fixes applied
- `server.py`: added `drain_request_body()` and call it before returning oversized-body 400.
- `tests/test_collaborator_agent.py`: added regression test for oversized-body response stability.

## Cleanup and rollback
- Inline harness generated no tracked temporary script.
- Local test server was shut down after each harness run.
- No rollback needed; all fixes are intentional.

## Residual risks
- Live Semantic Scholar/OpenAlex API behavior was not exercised in UltraQA to avoid external network/rate-limit dependency; demo-data path and API client error handling are covered locally.
- Region/coauthor-neighbor remain documented heuristics as required.

## Evidence
- Unit/smoke tests: 10 passed.
- Compile check: passed.
- Adversarial local HTTP harness: 8/8 scenarios passed after one fix cycle.

ULTRAQA COMPLETE: Goal met after 2 cycles.

## Final post-cleanup verification addendum
- python -B -m unittest discover -s tests -v: 10 tests passed.
- python -B -m py_compile collaborator_agent.py server.py tests/test_collaborator_agent.py: passed.
- Generated __pycache__ directories were removed after verification.
