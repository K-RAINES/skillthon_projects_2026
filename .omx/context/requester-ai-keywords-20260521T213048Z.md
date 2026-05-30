# Deep Interview Context Snapshot: requester-ai-keywords

Task statement: Improve the server by replacing requester-side keyword extraction with an AI-assisted extraction flow.

Desired outcome: The server reads the requester's publication titles, calls Codex CLI once with a prompt file and title list, and uses the returned keywords to improve requester topic/method extraction.

Stated solution: Add a Python script that runs Codex CLI with a prompt text/markdown file because no API key is available. Use this only for the requester, not candidates, to control cost.

Probable intent hypothesis: The current heuristic token extraction is too shallow for requester publications, so AI should infer better domain and method keywords from publication titles while preserving candidate-side cheap heuristics.

Known facts/evidence:
- `collaborator_agent.py` has `tokenize`, `keyword_set`, `ranked_topic_keywords`, `method_keywords_from_text`, `method_keyword_set`, and `ranked_method_keywords` as heuristic extraction functions.
- `requester_debug_payload()` calls `ranked_topic_keywords(papers)` and `ranked_method_keywords(papers)` for the requester debug panel.
- `build_candidate_list()` computes `requester_keywords = keyword_set(requester_papers)` and `requester_methods = method_keyword_set(requester_papers)`, then compares them to candidate heuristic sets.
- `fallback_search_query()` also derives search terms from requester keyword/method sets.
- Candidate keyword extraction currently uses heuristic `keyword_set` and `method_keyword_set` over candidate papers.
- Tests in `tests/test_collaborator_agent.py` assert demo requester debug includes heuristic-derived terms such as `biomedical` and `deep learning`.

Constraints:
- No API key is available.
- AI should be invoked through Codex CLI rather than an API.
- Avoid AI extraction for candidates because it is too costly.
- Initial user belief: a single Codex CLI call should be enough when supplied with an appropriate prompt and publication title list.

Unknowns/open questions:
- Whether AI keywords should replace requester keywords everywhere or only the requester debug display.
- Whether Codex CLI failures should fall back silently to heuristics, fail the request, or surface a warning.
- Exact output schema expected from the CLI prompt.
- Whether only titles should be used, or whether abstracts/fields may still be included as a fallback or prompt context.
- Whether this should run for demo data, live data, or both.
- Performance expectations and acceptable request latency.

Decision-boundary unknowns:
- OMX may likely choose implementation details such as prompt-file path, temp-file handling, parsing, and fallback code structure, but user confirmation is needed for behavioral boundaries that affect scoring, runtime failures, and external CLI execution.

Likely codebase touchpoints:
- `collaborator_agent.py`: requester keyword extraction, scoring inputs, fallback query, debug payload.
- `tests/test_collaborator_agent.py`: requester debug and scoring expectations, new fallback/CLI parsing tests.
- Potential new prompt file such as `prompts/requester_keywords.md` or repo-root prompt file.
- Potential helper script such as `extract_requester_keywords.py` if retained as a separate CLI wrapper.

Prompt-safe initial-context summary status: not_needed
