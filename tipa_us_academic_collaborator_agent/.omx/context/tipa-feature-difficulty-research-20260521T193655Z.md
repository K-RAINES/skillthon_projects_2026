# Best-Practice Research: TIPA collaborator-matching feature difficulty

Date: 2026-05-21

Direct recommendation: For the 2-hour demo, fully implement source researcher resolution, candidate generation, topic/method similarity heuristics, citation-stage similarity, and ranked output/email drafts. Implement region as structured tag/filter with best-effort data (Semantic Scholar affiliation plus optional OpenAlex institution geo fallback). Implement coauthor bridge as an approximation over fetched papers, not exhaustive global network distance.

Evidence used:
- Semantic Scholar API overview/tutorial: Academic Graph includes authors/papers/citations/SPECTER2 embeddings; recommendations returns related papers from seed papers; author batch fields include name/url/paperCount/hIndex/papers; use batch endpoints and limited fields.
- Semantic Scholar FAQ: field-of-study classification derives from title/abstract and has limitations; h-index/citations should not be used as comprehensive comparative assessment; author disambiguation can have errors.
- OpenAlex docs: author last_known_institutions and institution geo include city/region/country/lat/long, useful for regional filtering.
- ORCID docs: ORCID is a source of researcher identity/connections and minimal metadata, not abstracts/full-text.

Feature difficulty:
- Seed author resolution: Medium (ORCID easiest; name-only ambiguous; Google Scholar URL should not be scraped in v1).
- Candidate generation from Semantic Scholar recommendations: Medium/easy.
- Topic fit: Easy/medium using recommendations, title/abstract, S2 fields.
- Method similarity: Medium; easy heuristic with title/abstract keyword/phrase overlap, robust method extraction is harder.
- Citation similarity: Easy; use log-scaled citationCount/hIndex closeness, label as career-stage proxy.
- Regional tag/filter: Medium with OpenAlex, hard with Semantic Scholar only for city/metro accuracy.
- Coauthor bridge distance: Medium for direct/shared coauthors in fetched graph, hard for global shortest paths.
- Outreach email: Easy once evidence snippets exist.

Boundary note: This research does not decide approved v1 scope; user review/approval still needed.
