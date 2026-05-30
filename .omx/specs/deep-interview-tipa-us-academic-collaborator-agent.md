# Execution-Ready Spec: TIPA US Academic Collaborator Agent

## Metadata

- Profile: standard deep-interview
- Context type: greenfield
- Final ambiguity: ~8%
- Threshold: <=20%
- Context snapshot: `.omx/context/tipa-us-researcher-commercialization-agent-20260521T191556Z.md`
- Transcript: see `.omx/interviews/`
- Research artifact: `.omx/context/tipa-feature-difficulty-research-20260521T193655Z.md`

## Clarity Breakdown

| Dimension | Score | Notes |
|---|---:|---|
| Intent | 0.96 | Help Korean SMEs/researchers identify US academic research collaborators for commercialization-adjacent collaboration. |
| Outcome | 0.95 | Runnable demo server with UI, ranked/filterable collaborator list, evidence, and outreach drafts. |
| Scope | 0.92 | Academic collaborator matching only; no IP, industry, or grant/funding matching. |
| Constraints | 0.88 | 2-hour demo orientation; use reliable public data sources; Google Scholar optional only. |
| Success criteria | 0.86 | Server runs, UI has manual inputs + Run button, candidates are sorted and low-relevance candidates hidden. |

## Intent

Create a live-demo-ready agent for TIPA-style users: a Korean SME or researcher who already knows their own researcher identity and wants to find US academic collaborators worth contacting.

## Desired Outcome

A small Python server with a minimal web UI. The user can enter researcher identity and filter/scoring parameters, click **Run**, and receive a sorted visible list of relevant US academic collaborator candidates. Each candidate should include rationale, score breakdown, region tag, evidence snippets, and a personalized outreach email draft.

## In Scope

1. **Python server**
   - Serves a minimal browser UI.
   - Provides an endpoint/form action that runs matching from manual inputs.
   - Includes README instructions for setup and running.

2. **Manual-input UI with Run button**
   - No normal demo workflow should require editing a config file or restarting the server.
   - UI should expose requester identity and filters/scoring parameters.

3. **Requester identity input**
   - Required: requester/researcher name.
   - Preferred: Semantic Scholar author URL/ID or ORCID.
   - Optional: Google Scholar link as a human-visible identity hint only.
   - Do not rely on Google Scholar scraping as the data source.

4. **Candidate matching**
   - Use Semantic Scholar as the primary publication/candidate data source.
   - OpenAlex may be used as a best-effort fallback for institution/region metadata if needed.
   - Generate US academic collaborator candidates from related/recommended publications and author profiles.

5. **Scoring/filtering signals**
   - Technical/topic fit.
   - Method similarity, inferred heuristically from titles/abstracts/fields/keywords where available.
   - Citation-stage similarity, treated as a career-stage proxy rather than quality judgment.
   - Region tag/filter, best effort from affiliation/institution metadata.
   - Coauthor bridge / neighbor distance, implemented as a shallow heuristic over fetched papers rather than exhaustive global shortest path.

6. **Output**
   - Return a sorted list, not a fixed top-5-only list.
   - Hide low-relevance candidates by default using a configurable relevance threshold.
   - Show applied filters and hidden/filtered counts when feasible.
   - For each visible candidate, show:
     - name,
     - affiliation/institution if available,
     - region tag if available,
     - profile/source links,
     - score and score breakdown,
     - reason for match,
     - supporting publication snippets,
     - coauthor bridge estimate,
     - personalized outreach email draft.

## Out of Scope / Non-goals

- Patent/IP overlap analysis.
- Non-academic industry contact matching.
- Grant/funding opportunity matching.
- Commercialization consultant / market-entry connector matching.
- Exhaustive coauthor-network shortest-path computation.
- Google Scholar scraping as a required backend dependency.
- Full production-grade author disambiguation.
- Production authentication, persistence, billing, deployment hardening, or CRM/email sending.

## Decision Boundaries

OMX / the implementation lane may decide without further confirmation:

- Practical default values for filters such as `min_relevance`, `max_neighbor`, `max_results`, region optionality, and citation-similarity weighting, as long as the UI lets users override them.
- Exact score weights, as long as they are documented and visible in output/README.
- Whether a feature is labeled as heuristic when reliable source data is sparse.
- Minimal server/UI structure, with preference for a small, demo-friendly implementation over a large framework.
- Whether to include OpenAlex fallback for region metadata if it can be done quickly and safely.

Implementation should not decide without confirmation:

- Adding Google Scholar scraping as a required data source.
- Expanding into IP, funding, industry, or market-entry contact matching.
- Hiding score rationale from users.
- Replacing academic collaborators with non-academic contacts.

## Constraints

- Demo should be runnable locally from README instructions.
- The normal user flow must be browser-based with manual inputs and a Run button.
- Low-relevance candidates should not be visible by default.
- Scoring must be transparent enough for demo users to understand why a candidate appears.
- Public-data limitations must be surfaced honestly in README/output labels.
- Prefer minimal dependencies; if dependencies are introduced, document them clearly.

## Testable Acceptance Criteria

1. `README.md` explains how to run the Python server locally.
2. Starting the server exposes a web page with a form and **Run** button.
3. The form accepts at least:
   - requester name,
   - optional Semantic Scholar author URL/ID,
   - optional ORCID,
   - optional Google Scholar link,
   - optional desired region,
   - `min_relevance`,
   - `max_neighbor`,
   - candidate/result limit.
4. Clicking **Run** returns a sorted list of visible collaborator candidates without editing a config file or restarting.
5. Output is not limited to exactly 5 candidates; count depends on filters and available data.
6. Candidates below `min_relevance` are hidden or clearly filtered out.
7. Each visible candidate includes a score breakdown and rationale.
8. Each visible candidate includes at least one supporting publication/evidence snippet when available.
9. Each visible candidate includes an outreach email draft personalized to the requester/candidate evidence.
10. Region and coauthor-neighbor features are labeled as best-effort/heuristic if source data is incomplete.
11. Google Scholar link is accepted as optional metadata/hint but not required for backend retrieval.
12. The system avoids IP, industry, and funding recommendations.

## Assumptions Exposed + Resolutions

- Assumption: The output should always be exactly 5 matches.
  - Resolution: No. Return a sorted, filterable list; hide low relevance by threshold.
- Assumption: Google Scholar link should be required and scraped.
  - Resolution: No. It is optional identity context only; use Semantic Scholar/ORCID/OpenAlex-compatible data instead.
- Assumption: Region and coauthor distance must be exact.
  - Resolution: Not for V1. They can be best-effort heuristics if labeled and user-configurable.

## Pressure-Pass Findings

The first scope sounded like a fixed shortlist generator. Pressure testing changed it into a filterable collaborator-discovery UI with transparent scoring, manual parameter control, and explicit suppression of weak candidates.

## Brownfield Evidence vs Inference Notes

- Evidence: Project root inspection found no existing app/server scaffold or root README; this is effectively greenfield.
- Tool note: `omx explore` was unavailable on this Windows surface due to POSIX allowlist runtime; a read-only PowerShell listing was used instead.

## Technical Context Findings

- Semantic Scholar is the preferred primary source for author/paper/citation/recommendation data.
- OpenAlex can help with institution/region metadata if needed.
- ORCID can help with identity, but not full method/publication abstract retrieval by itself.
- Google Scholar should not be a required backend source.

## Handoff Recommendation

Recommended next step: `$ralplan` or `$autopilot` using this spec.

- Use `$ralplan` if you want an architecture/test plan before implementation.
- Use `$autopilot` if you want direct plan → build → QA from this clarified spec.
- Use `$ultragoal` after planning if durable goal tracking is desired.
