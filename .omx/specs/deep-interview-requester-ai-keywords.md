# Execution Spec: Requester AI-Assisted Keyword Extraction

## Metadata

- Source workflow: `$deep-interview`
- Profile: standard
- Context type: brownfield
- Final ambiguity: 18%
- Threshold: 20%
- Context snapshot: `.omx/context/requester-ai-keywords-20260521T213048Z.md`
- Transcript: `.omx/interviews/requester-ai-keywords-20260521T213839Z.md`

## Intent

Improve requester keyword quality by using AI to infer topic and method keywords from the requester's publication titles, because the current token/phrase heuristics miss higher-level semantic concepts.

## Desired Outcome

Add a user-triggered `AI-assisted keyword extraction` capability in the Requester debug area. When triggered, the server should call local Codex CLI once with an appropriate prompt and the requester's publication title list, parse structured keyword output, and rerun/recalculate candidate results using those AI requester keywords.

Normal matching should continue to work without AI. Candidate-side keyword extraction remains heuristic.

## In Scope

- Add requester-only AI keyword extraction based on the requester publication title list.
- Invoke Codex CLI locally rather than an external API.
- Provide a prompt file, likely markdown or text, that instructs Codex to return structured topic and method keywords.
- Add a local Python subprocess wrapper or equivalent helper for the Codex CLI invocation.
- Add an explicit UI control in Requester debug, named like `AI-assisted keyword extraction`.
- Add backend support for explicit AI extraction, either through an `ai_keywords` request flag on `/api/match` or a separate endpoint, at implementer discretion.
- When AI extraction is requested and succeeds, use AI requester keywords for reranking/scoring and requester debug keyword display.
- If an AI-assisted request reaches fallback paper-search query generation, use AI requester keywords for that requester-side query where practical.
- Fall back to existing heuristic requester keywords when Codex CLI is unavailable, times out, exits nonzero, or returns invalid/unusable output.
- Add tests that verify success parsing, fallback behavior, and that candidate keyword extraction remains heuristic.

## Out of Scope / Non-goals

- Do not call any paid or API-key-based LLM service.
- Do not run AI extraction over candidate publication lists.
- Do not make AI extraction the default behavior for normal initial searches.
- Do not require Codex CLI to be present for the app or tests to pass.
- Do not remove existing heuristic keyword extraction; it is the fallback and remains the candidate path.
- Do not block or fail normal matching solely because AI keyword extraction fails.

## Decision Boundaries

Implementation may choose without further confirmation:

- Prompt file path and exact file extension.
- JSON output schema for Codex keyword extraction.
- Subprocess wrapper structure.
- Timeout value, if reasonable and testable.
- Temporary file/stdin strategy for passing title lists.
- Whether the UI calls `/api/match` with an explicit AI flag or uses a separate endpoint.
- How to surface fallback notes in the response, as long as failure is not silent to developers/users inspecting debug notes.
- Internal data structures for carrying AI topic/method keyword sets into scoring and fallback query generation.

Implementation should ask before:

- Making AI extraction automatic by default.
- Adding new external dependencies.
- Changing candidate extraction to AI.
- Removing existing heuristic extraction or fallback behavior.
- Requiring a specific Codex account/login workflow beyond local CLI availability.

## Constraints

- No API key is available.
- AI invocation must be through local Codex CLI.
- The first pass should use one Codex CLI call per requested AI extraction.
- Publication titles are the intended input to the AI prompt.
- Existing demo and non-AI flows must remain responsive and deterministic enough for tests.
- The project is a compact Python server with tests in `tests/test_collaborator_agent.py`.

## Brownfield Technical Context

- `collaborator_agent.py` contains current heuristic functions:
  - `tokenize`
  - `keyword_set`
  - `ranked_topic_keywords`
  - `method_keywords_from_text`
  - `method_keyword_set`
  - `ranked_method_keywords`
- `requester_debug_payload()` currently displays heuristic requester keywords.
- `build_candidate_list()` currently computes requester keyword/method sets and candidate keyword/method sets with the same heuristic functions.
- `fallback_search_query()` currently derives terms from requester heuristic sets.
- `tests/test_collaborator_agent.py` has demo tests that assert requester debug keywords and match behavior.

## Acceptance Criteria

- Normal `/api/match` without an AI flag still returns results using heuristic requester and candidate keywords.
- Requester debug includes an `AI-assisted keyword extraction` control or equivalent UI affordance.
- Triggering AI extraction sends an explicit AI request to the backend.
- The backend builds a title list from requester publications and invokes Codex CLI once for the AI extraction attempt.
- A valid Codex result produces structured topic and method keywords.
- Successful AI extraction causes candidate results to be recalculated/reranked using AI requester keywords while candidate keywords remain heuristic.
- The response/debug payload indicates whether requester keywords came from AI or heuristic fallback.
- Codex CLI missing, timeout, invalid JSON, empty keywords, or nonzero exit falls back to heuristic requester keywords and still returns a successful match response.
- Tests cover the subprocess wrapper by mocking it rather than requiring real Codex CLI.
- Existing tests for demo matching and server smoke behavior continue to pass, adjusted only where the response schema gains explicit keyword-source metadata.

## Assumptions Exposed + Resolutions

- Initial assumption: AI requester keywords should affect all requester-side paths automatically.
  - Resolution: AI should be explicit, either via a Requester debug button or backend flag, not default.
- Initial assumption: fallback could be a pure backend behavior detail.
  - Resolution: fallback to heuristics is required and should be visible in debug/notes.
- Initial assumption: UI result might be display-only.
  - Resolution: user wants AI extraction to apply to reranking.

## Verification Plan

- Unit-test the AI keyword parser with valid JSON, malformed JSON, empty lists, and extra text around JSON if supported.
- Unit-test the Codex wrapper failure paths: executable missing, timeout, nonzero exit, invalid output.
- Unit-test matching with AI keyword extraction enabled by injecting/mocking AI keywords and asserting scoring/reranking uses requester AI sets.
- Unit-test that candidate keyword functions are still called/used heuristically and no candidate AI extraction is attempted.
- Smoke-test `/api/match` normal behavior and AI-flag behavior.
- Run the repository test suite after implementation.

## Recommended Handoff

Use `$ralplan` next if you want architecture/test-shape review before edits:

`$plan --consensus --direct .omx/specs/deep-interview-requester-ai-keywords.md`

Use `$autopilot` or `$ultragoal` if you want to proceed into implementation from this spec.

