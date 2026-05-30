# PRD: Requester AI-Assisted Keyword Extraction

## Goal

Add an explicit requester-debug action that uses local Codex CLI to extract better requester topic and method keywords from publication titles, then reranks results with those requester keywords while leaving normal matching and candidate extraction heuristic.

## Users and Workflow

- A user runs the normal collaborator search.
- The initial result remains fast and heuristic.
- In Requester debug, the user can click `AI-assisted keyword extraction`.
- The browser resubmits the same search with an explicit AI keyword flag.
- The backend attempts one Codex CLI extraction over requester publication titles.
- If Codex succeeds, requester keyword debug and candidate scoring/ranking use the AI keyword sets.
- If Codex fails, the response still succeeds with heuristic keywords and an explicit fallback note.

## Requirements

- Keep `/api/match` default behavior non-AI.
- Add `ai_keywords` parsing to request payloads.
- Build requester publication titles from the same requester papers used today.
- Add a prompt file for the Codex CLI extraction contract.
- Return a parseable schema with `topic_keywords` and `method_keywords`.
- Sanitize/normalize AI terms before using them.
- Use AI requester keywords for requester-side scoring inputs and fallback paper-search query generation when AI mode succeeds.
- Do not call AI for candidates.
- Surface keyword source and fallback notes in `requester_debug` and existing notes.
- Add a Requester debug button in the browser UI.

## Architecture Decision

Use `/api/match` with `ai_keywords: true` instead of a new endpoint. This reuses existing request validation, demo/live data branches, filtering, scoring, and server smoke tests. The frontend keeps the last submitted payload and reruns it with the flag when the debug button is clicked.

## Alternatives Rejected

- Separate endpoint: adds duplicated match state handling for little benefit in this compact server.
- Automatic AI default: violates the non-goal and adds latency/cost to every search.
- Replacing heuristic functions globally: would accidentally affect candidates and remove fallback.

## Acceptance Criteria

- Normal match without `ai_keywords` stays heuristic and passes current tests.
- AI match with mocked Codex output uses AI requester terms in debug and scoring.
- Codex missing, timeout, invalid output, or empty output falls back to heuristics and returns 200.
- Candidate keyword extraction remains heuristic-only.
- UI shows an `AI-assisted keyword extraction` button after requester debug renders.
- UI button reruns the current match with `ai_keywords: true`.

