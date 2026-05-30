# Deep Interview Transcript: Requester AI Keywords

Metadata:
- Profile: standard
- Context type: brownfield
- Final ambiguity: 18%
- Threshold: 20%
- Context snapshot: `.omx/context/requester-ai-keywords-20260521T213048Z.md`

## Initial Request

Improve the server so requester keyword extraction can use AI over the requester's publication titles. The AI should be invoked through Codex CLI because no API key is available. The user initially expected a Python script plus prompt file, with one Codex CLI call over the publication title list. Candidate keyword extraction should remain heuristic because AI on candidates is too costly.

## Codebase Findings

[from-code][auto-confirmed]
- `collaborator_agent.py` currently extracts topic keywords with `keyword_set()` / `ranked_topic_keywords()` using tokenization over title, abstract, and fields.
- `collaborator_agent.py` currently extracts method keywords with `method_keyword_set()` / `ranked_method_keywords()` using phrase/token heuristics.
- `requester_debug_payload()` displays requester topic and method keywords.
- `build_candidate_list()` uses requester keyword/method sets for topic fit and method similarity scoring.
- `fallback_search_query()` uses requester keyword/method sets when the recommendation endpoint is unavailable.
- Candidate keyword extraction also uses the same heuristic functions and should remain unchanged for first pass.
- `tests/test_collaborator_agent.py` currently asserts requester debug includes heuristic-derived demo keywords.

## Rounds

### Round 1

Target: Scope

Question: Where should requester AI-extracted keywords be used in the first implementation?

Answer: All requester paths.

Captured meaning: The first answer favored AI requester keywords affecting all requester-side behavior, including scoring/debug and fallback discovery query generation, while candidates stay heuristic.

### Round 2

Target: Constraints

Question: If Codex CLI extraction cannot produce valid keywords during a request, what should the server do?

Answer: Fallback to heuristics. The user then clarified the desired UX: create a separate requester-debug button named like `AI-assisted keyword extraction`.

Captured meaning: Failure should not break normal matching. The AI path is an explicit action surfaced in Requester debug.

### Round 3

Target: Outcome

Question: When the new button runs, should its result only update visible debug keywords, or also become active requester keywords used for candidate scoring/search?

Answer: Apply to reranking.

Captured meaning: AI extraction should not be display-only. After the user triggers AI extraction, results should be recalculated/reranked using AI requester keywords.

### Round 4

Target: Non-goals

Question: Should AI extraction never run automatically during initial search, and only run after the requester-debug button?

Answer: Auto optional.

Captured meaning: AI should not be the default behavior, but the backend may support an explicit request flag so the UI button can request AI-assisted extraction and reranking.

### Round 5

Target: Decision Boundaries

Question: May implementation choose the Codex CLI details, as long as they are local, testable, and fall back to heuristics on failure?

Answer: Yes.

Captured meaning: Implementation may choose prompt path, JSON schema, timeout, subprocess wrapper, temp-file handling, parsing strategy, and whether to use `/api/match` with an AI flag or a separate endpoint.

## Pressure Pass

The original assumption that AI requester keywords should affect all requester paths was pressure-tested after Round 2. The clarification changed the behavior from automatic AI extraction during normal matching to an explicit requester-debug action or explicit backend flag. This materially reduces cost and latency risk while preserving the desired reranking behavior when AI is requested.

## Clarity Breakdown

| Dimension | Score | Evidence |
| --- | ---: | --- |
| Intent | 0.90 | Improve semantic quality of requester keywords beyond simple token heuristics. |
| Outcome | 0.88 | Add AI-assisted requester keyword extraction that reranks results when triggered. |
| Scope | 0.86 | Requester only; candidates remain heuristic; backend may support explicit AI flag. |
| Constraints | 0.84 | No API key; use local Codex CLI; fallback to heuristics on failure. |
| Success Criteria | 0.78 | Button/flag works, reranking uses AI terms, normal matching remains responsive. |
| Context | 0.88 | Relevant functions and tests identified in `collaborator_agent.py` and `tests/test_collaborator_agent.py`. |

Weighted ambiguity: 18%

## Readiness Gates

- Non-goals: explicit.
- Decision boundaries: explicit.
- Pressure pass: complete.
- Closure audit: further questions would refine implementation taste more than change the execution path.

