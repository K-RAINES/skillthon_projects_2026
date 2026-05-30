# Test Spec: TIPA US Academic Collaborator Agent

## Source of truth
- PRD: paired `prd-tipa-us-academic-collaborator-agent-*.md`
- Deep-interview spec: `.omx/specs/deep-interview-tipa-us-academic-collaborator-agent.md`

## Acceptance test matrix

| ID | Requirement | Verification |
|---|---|---|
| AC-01 | README explains local run steps | Inspect README and run documented command. |
| AC-02 | Server exposes browser UI with Run button | HTTP GET `/` contains form fields and Run button. |
| AC-03 | UI accepts required/optional inputs | HTML includes requester, Semantic Scholar/ORCID/Scholar, region, min_relevance, max_neighbor, max_results. |
| AC-04 | API accepts manual params without config edits | POST `/api/match` with JSON body returns JSON result. |
| AC-05 | Output is sorted and not fixed to 5 | Unit test with fixture candidates and variable max_results. |
| AC-06 | Low relevance is hidden | Unit test filters below min_relevance and reports hidden count. |
| AC-07 | Score breakdown and rationale are visible | Unit/API fixture response includes breakdown and reason fields. |
| AC-08 | Evidence snippet included | Unit/API fixture response includes candidate evidence snippets. |
| AC-09 | Personalized outreach draft included | Unit test verifies requester/candidate-specific email text. |
| AC-10 | Region/coauthor features labeled heuristic | UI/README/API notes include heuristic labels. |
| AC-11 | Scholar link optional only | Missing Scholar URL still works; provided Scholar URL is not scraped. |
| AC-12 | Non-goals avoided | README/output never recommend IP/funding/industry contacts. |

## Unit tests
- `extract_author_id` handles URLs, IDs, whitespace, and missing values.
- method keyword extraction is deterministic and excludes noise.
- citation-stage similarity is bounded 0..1 and handles zero citations.
- coauthor neighbor distance maps direct/shared/unknown to configured values.
- filter/sort suppresses low relevance and respects `max_neighbor`, region, and result limit.
- email draft contains requester/candidate names and evidence.

## Integration/smoke tests
- Start server on a local port and GET `/`.
- POST malformed JSON/missing requester; expect safe 400 response.
- POST demo fixture request with `use_demo_data=true`; expect sorted candidates and hidden count.
- Verify candidates below default threshold are not returned.

## Adversarial QA focus
- Malformed JSON and missing fields.
- Oversized or prompt-injection-like user strings are escaped in UI/output and do not alter server behavior.
- Extreme filter values are clamped/safely parsed.
- API unavailable path returns a clear error or demo fallback, not a crash.
- No config-file edit/restart required for normal parameter changes.

## Success criteria
All unit tests pass, server smoke check passes, and adversarial API scenarios pass without crashes or unescaped HTML/script injection.
