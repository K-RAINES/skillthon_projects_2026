# TIPA US Academic Collaborator Finder

A small Python demo server for Korean SMEs/researchers who want to identify US
academic collaborators from public scholarly metadata.

The app accepts a requester/researcher identity, lets the user tune filters in a
browser form, and returns a sorted list of visible collaborator candidates with
score breakdowns, evidence snippets, regional tags, coauthor-neighbor heuristics,
and ready-to-send outreach email drafts.

## What this demo does

- Uses **Semantic Scholar** as the primary live data source for authors,
  publications, citations, and related/recommended papers.
- Optionally uses **OpenAlex** as a best-effort fallback for US institution/region
  metadata.
- Accepts a Google Scholar link as an optional identity hint, but **does not
  scrape Google Scholar**.
- Hides low-relevance candidates by default with a user-adjustable
  `min_relevance` filter.
- Returns a sorted, filterable list; it is **not fixed to exactly 5 matches**.

## Out of scope

This first demo intentionally does **not** perform patent/IP overlap analysis,
industry contact matching, grant/funding matching, CRM/email sending, or
production-grade author disambiguation.

## Requirements

- Python 3.10+ recommended.
- No required Python packages beyond the standard library.
- Optional: `SEMANTIC_SCHOLAR_API_KEY` for more reliable Semantic Scholar API
  access.

## Run locally

```bash
cd tipa_us_academic_collaborator_agent
python server.py
```

Then open:

```text
http://127.0.0.1:8000
```

To change the host or port:

```bash
cd tipa_us_academic_collaborator_agent
TIPA_HOST=0.0.0.0 TIPA_PORT=8080 python server.py
```

On Windows PowerShell:

```powershell
cd tipa_us_academic_collaborator_agent
$env:TIPA_PORT = "8080"
python server.py
```

## Browser inputs

The web UI includes a **Run** button and manual inputs for:

- requester name (required),
- Semantic Scholar author URL/ID (preferred for live data),
- ORCID (optional identity hint),
- Google Scholar link (optional visible hint only),
- desired region, such as `Boston area`,
- `min_relevance`,
- `max_neighbor`,
- candidate/result limit,
- built-in demo data toggle.

Normal demo tuning does not require editing a config file or restarting the
server.

After a normal run, Requester debug includes an **AI-assisted keyword
extraction** button. That action asks the local Codex CLI to extract requester
topic/method keywords from publication titles and reruns the match with those
requester keywords. It is explicit and requester-only; candidate keyword
extraction remains heuristic. If Codex is unavailable or returns unusable
output, the server falls back to heuristic requester keywords.

The AI button uses a per-process page token and same-origin browser flow to
avoid casual cross-site triggering of local Codex work. This is a local demo
guard, not a full authentication system for hostile local software or browser
extensions.

## API usage

POST JSON to `/api/match`:

```bash
curl -X POST http://127.0.0.1:8000/api/match \
  -H "Content-Type: application/json" \
  -d '{
    "requester_name": "Demo Researcher",
    "semantic_scholar_author": "",
    "orcid": "",
    "google_scholar_url": "",
    "region": "Boston",
    "min_relevance": 0.55,
    "max_neighbor": 5,
    "max_results": 20,
    "use_demo_data": true
  }'
```

Set `"use_demo_data": false` and provide a Semantic Scholar author URL/ID for
live API data.

## Scoring model

Default weights:

| Signal | Weight | Note |
|---|---:|---|
| Topic / technical fit | 35% | Keyword and field overlap, plus Semantic Scholar related-paper signal. |
| Method similarity | 25% | Heuristic extraction from title, abstract, fields, and method-like keywords. |
| Citation-stage similarity | 15% | Career-stage proxy; not a quality score. |
| Region fit | 15% | Best-effort institution/affiliation matching. |
| Coauthor neighbor | 10% | Shallow fetched-graph heuristic, not exhaustive shortest path. |

`max_neighbor` interpretation:

- `1`: direct fetched coauthor,
- `2`: shared fetched coauthor bridge,
- `5`: no shallow bridge found, treated as a distant heuristic neighbor.

## Run tests

```bash
cd tipa_us_academic_collaborator_agent
python -m unittest discover -s tests
```

The tests use the built-in fixture dataset and do not require network access.

## Data-source caveats

- Semantic Scholar author affiliations and paper metadata can be sparse.
- Region and coauthor-neighbor values are intentionally labeled as heuristics.
- Google Scholar has no official backend dependency in this demo; links are
  accepted only as user-supplied context.
