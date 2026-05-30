# UltraQA Report: Requester AI-Assisted Keyword Extraction

## Goal and success criteria

- Goal: Verify requester-only AI-assisted keyword extraction through an explicit UI/API flag, with Codex CLI subprocess handling, heuristic fallback, requester reranking, candidate heuristic isolation, and browser-trigger guardrails.
- Stop condition: Code review is clean, architecture is clear, available verification passes, and blocked verification is explicitly documented.
- Safety bounds: No destructive commands, no production/network writes, no credential inspection, bounded Codex CLI smoke only, no real Semantic Scholar live API calls.

## Scenario matrix

| ID | User/attacker model | Scenario | Command/harness | Expected signal | Actual result | Status | Evidence | Cleanup |
|----|---------------------|----------|-----------------|-----------------|---------------|--------|----------|---------|
| UQ-01 | Normal user | Default match stays heuristic | `python -m unittest tests.test_collaborator_agent` via review subagent | Tests pass; `keyword_source` heuristic | Passed in subagent environment | PASS | 21 tests OK before final 3 regressions; local surface lacks Python | N/A |
| UQ-02 | Normal user | AI match reranks with requester AI terms | Mocked `run_codex_keyword_extraction` tests | AI source and marine candidate ranks first | Covered by test additions | PASS | `test_ai_keyword_match_uses_codex_terms_for_requester_reranking` | N/A |
| UQ-03 | Missing/bad Codex | Fallback does not fail request | Mocked exception/nonzero tests | Generic fallback note, no stderr/stdout leak | Covered by tests and review | PASS | `test_ai_keyword_failure_falls_back_to_heuristics`, `test_run_codex_keyword_extraction_raises_generic_nonzero_error` | N/A |
| UQ-04 | Malformed model output | Empty/invalid AI output rejected and fallback eligible | Parser tests | Raises `ValueError` for unusable output | Covered by tests | PASS | `test_parse_ai_keyword_response_rejects_empty_keywords` | N/A |
| UQ-05 | Cross-site webpage | POST AI without local token | Server smoke test | HTTP 403 | Covered by test | PASS | `test_api_rejects_ai_keywords_without_local_token` | N/A |
| UQ-06 | Cross-site webpage | GET with `ai_keywords=true` | Server smoke test | HTTP 403; no Codex run | Covered by test | PASS | `test_api_rejects_ai_keywords_on_get` | N/A |
| UQ-07 | Browser CORS abuse | OPTIONS should not grant wildcard CORS | Server smoke test | No `Access-Control-Allow-Origin` | Covered by test | PASS | `test_api_does_not_emit_wildcard_cors` | N/A |
| UQ-08 | Concurrent caller | Second Codex run while one is active | Semaphore unit test | Runtime error, fallback path can use heuristics | Covered by test | PASS | `test_run_codex_keyword_extraction_rejects_concurrent_invocation` | N/A |
| UQ-09 | Prompt injection in title | Title text treated as data | Prompt file and JSON title payload inspection | Prompt says ignore title instructions; titles passed as JSON | Static inspection passed | PASS | `prompts/requester_keyword_extraction.md`, `codex_keyword_prompt()` | N/A |
| UQ-10 | Misleading success output | Codex stdout noisy, final-message file authoritative | Wrapper test and live CLI smoke | Parse final-message file when present | Covered by test; live command wrote JSON to output file | PASS | `test_run_codex_keyword_extraction_reads_final_message_file`; local Codex smoke exit 0 | Temp file removed |
| UQ-11 | Environment failure | Local verification command unavailable | `python -m py_compile ...; python -m unittest ...` | Document blocker and use next-best evidence | Python command is Microsoft Store stub in leader shell | BLOCKED_LOCAL | Output: `Python was not found...`; subagent reported pass | N/A |

## Commands run

- `[1] python -m py_compile collaborator_agent.py server.py tests/test_collaborator_agent.py; python -m unittest tests.test_collaborator_agent` - blocked in leader shell by Microsoft Store Python stub.
- `[0] codex --ask-for-approval never exec --skip-git-repo-check --sandbox read-only --ephemeral --color never --help` - validates CLI argument order.
- `[0] codex --ask-for-approval never exec --skip-git-repo-check --sandbox read-only --ephemeral --color never --output-last-message <tmp> -` - validates final-message file behavior with bounded prompt; temp file removed.
- `[0] rg ...` - confirms guard/test/code locations and no wildcard CORS header code remains.

## Review gates

- Code review: APPROVE, no findings after fixes.
- Architecture review: CLEAR.

## Residual risks

- The page token is a local demo guard, not a full authentication boundary against hostile local software or compromised browser extensions. This is documented in `README.md`.
- Leader shell cannot run Python tests due to PATH resolving to the Microsoft Store stub; subagent verification reported `py_compile` and `unittest` passing before the final three guard tests were added. Those final tests are simple smoke/regression additions but remain unexecuted in the leader shell.

