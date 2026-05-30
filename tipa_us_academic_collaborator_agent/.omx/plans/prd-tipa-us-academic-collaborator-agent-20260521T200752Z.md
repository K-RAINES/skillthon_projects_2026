# PRD: TIPA US Academic Collaborator Agent

## Source of truth
- Deep-interview spec: `.omx/specs/deep-interview-tipa-us-academic-collaborator-agent.md`
- Research artifact: `.omx/context/tipa-feature-difficulty-research-20260521T193655Z.md`

## RALPLAN-DR Summary

### Principles
1. Demo-first: small, local, easy to run, and useful in a live TIPA session.
2. Transparent scoring: every visible candidate must explain why they appear.
3. Public-source honesty: label heuristics and sparse metadata limitations.
4. User-controlled filters: no config-file edits for normal demo tuning.
5. Academic-only boundary: do not drift into IP, grants, industry, or CRM.

### Decision drivers
1. Time-to-working-demo and low dependency friction.
2. Reliability of official/public APIs over brittle Scholar scraping.
3. Clear score breakdown and low-relevance suppression.

### Viable options
- Option A: Standard-library Python HTTP server + small HTML/JS UI + urllib API client.
  - Pros: no dependency install required, fast to verify, easy README.
  - Cons: less ergonomic than FastAPI; no automatic API docs.
- Option B: FastAPI + templates/static assets.
  - Pros: clean API, modern developer experience.
  - Cons: new dependencies, install friction, heavier for 2-hour demo.
- Option C: CLI-only script.
  - Pros: fastest backend implementation.
  - Cons: violates Run-button/browser-input requirement.

### Decision
Use Option A: a standard-library Python server. It best satisfies the demo, README, and no-config-change constraints.

### Alternatives rejected
- FastAPI: rejected to avoid dependency install friction for a short demo.
- Google Scholar scraping: rejected because it is brittle and outside the clarified data-source boundary.
- Fixed top-5 shortlist: rejected because user requested a sorted, filterable list.

### ADR
- Decision: Build a dependency-light Python web demo with `/` UI and `/api/match` JSON endpoint.
- Drivers: 2-hour deliverable, browser Run button, transparent scoring, minimal setup.
- Consequences: Region/coauthor/method matching are documented heuristics; API quality depends on Semantic Scholar availability.
- Follow-ups: If productionized, add robust author confirmation, caching, richer geo normalization, API-key config, and test fixtures with recorded API responses.

## Product requirements

### Inputs
- Required: `requester_name`.
- Optional identity hints: `semantic_scholar_author`, `orcid`, `google_scholar_url`.
- Optional filters: `region`, `min_relevance`, `max_neighbor`, `max_results`.
- Optional weighting controls may be added if time permits but are not required.

### Outputs
- Sorted collaborator list, not fixed to 5.
- Low-relevance candidates hidden by default.
- For each candidate: name, affiliation, region tag, profile URL, total score, score breakdown, coauthor-neighbor estimate, evidence snippets, rationale, personalized email draft.
- Show applied filters and filtered/hidden counts.

### Data-source policy
- Primary backend: Semantic Scholar official/public endpoints.
- Optional fallback: OpenAlex for institution/region metadata if simple to integrate.
- Google Scholar link is accepted only as optional visible hint; no required scraping.

### Scoring model
Default weighted score:
- Topic/technical fit: 35%
- Method similarity: 25%
- Citation-stage similarity: 15%
- Region fit/tag confidence: 15%
- Coauthor neighbor distance: 10%

Score signals may be adjusted in implementation if documented.

### Non-goals
- IP/patent overlap, industry contacts, grant/funding matching, market-entry connectors.
- Email sending/CRM.
- Production-grade disambiguation/auth/deployment.
- Exhaustive global coauthor shortest paths.

## Implementation plan
1. Create standard-library server entry point (`server.py`) and README.
2. Implement Semantic Scholar client with optional API key via environment variable.
3. Implement author resolution, seed paper retrieval, candidate paper/author collection, and safe fallback demo behavior when API is unavailable.
4. Implement scoring/filtering heuristics and explainability helpers.
5. Build minimal UI with manual parameter form and Run button.
6. Add unit tests for parsing, scoring, filtering, and email drafting.
7. Run smoke tests and adversarial request checks.

## Available agent-types roster
- executor: implementation/refactoring.
- test-engineer/verifier: test coverage and smoke validation.
- code-reviewer/architect: post-implementation review.
No parallel team required for this small greenfield demo.

## Handoff
Proceed to `$ultragoal` / direct implementation from this PRD and the paired test spec.
