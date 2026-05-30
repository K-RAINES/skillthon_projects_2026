"""Minimal browser server for the TIPA collaborator matching demo."""

from __future__ import annotations

import json
import os
import secrets
import urllib.parse
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from collaborator_agent import ApiError, match_collaborators

AI_KEYWORD_TOKEN = secrets.token_urlsafe(24)

APP_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>TIPA US Academic Collaborator Finder</title>
  <style>
    :root { color-scheme: light; font-family: Inter, Segoe UI, Arial, sans-serif; }
    body { margin: 0; background: #f6f8fb; color: #172033; }
    header { background: #0f2a55; color: white; padding: 28px max(24px, 8vw); }
    main { max-width: 1180px; margin: 0 auto; padding: 28px 24px 60px; }
    h1 { margin: 0 0 8px; font-size: clamp(28px, 4vw, 44px); }
    h2 { margin-top: 0; }
    .subtitle { max-width: 840px; opacity: 0.9; line-height: 1.5; }
    .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(230px, 1fr)); gap: 16px; }
    .panel, .candidate { background: white; border: 1px solid #d8e0ec; border-radius: 14px; box-shadow: 0 10px 30px rgba(15, 42, 85, .08); }
    .panel { padding: 20px; margin-bottom: 22px; }
    label { display: grid; gap: 6px; font-weight: 700; color: #24334d; }
    input { border: 1px solid #c7d1df; border-radius: 10px; padding: 10px 12px; font: inherit; }
    input[type="checkbox"] { width: 18px; height: 18px; }
    .checkbox { display: flex; align-items: center; gap: 10px; font-weight: 600; }
    .hint { color: #60718c; font-size: 13px; font-weight: 500; }
    button { cursor: pointer; border: 0; border-radius: 999px; padding: 13px 24px; font-weight: 800; font-size: 16px; color: white; background: #2364d2; }
    button:disabled { opacity: 0.65; cursor: progress; }
    .actions { margin-top: 18px; display: flex; align-items: center; gap: 14px; flex-wrap: wrap; }
    .status { color: #43536c; }
    .error { color: #a20d0d; font-weight: 700; }
    .summary { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; margin: 18px 0; }
    .metric { background: #eaf1ff; border-radius: 12px; padding: 14px; }
    .metric strong { display: block; font-size: 24px; color: #0f2a55; }
    .debug-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 18px; }
    .debug-block { background: #f8fafc; border: 1px solid #e0e7f0; border-radius: 12px; padding: 14px; }
    .debug-block h3 { margin: 0 0 10px; color: #0f2a55; }
    .keyword-list { display: flex; flex-wrap: wrap; gap: 8px; margin: 0; padding: 0; list-style: none; }
    .publication-list { margin: 0; padding-left: 22px; }
    .publication-list li { margin-bottom: 12px; }
    .meta { color: #60718c; font-size: 13px; }
    .empty { color: #60718c; font-style: italic; }
    .candidate { padding: 18px; margin-bottom: 16px; }
    .candidate h3 { margin: 0 0 4px; color: #0f2a55; }
    .score { font-size: 28px; font-weight: 900; color: #2364d2; }
    .pill-row { display: flex; flex-wrap: wrap; gap: 8px; margin: 10px 0; }
    .pill { background: #edf3fb; border: 1px solid #d5e2f0; border-radius: 999px; padding: 5px 10px; font-size: 13px; }
    .breakdown { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 8px; }
    .breakdown div { background: #f7f9fc; border-radius: 10px; padding: 8px; }
    pre { white-space: pre-wrap; background: #f8fafc; border: 1px solid #d8e0ec; border-radius: 12px; padding: 12px; }
    a { color: #195bbf; }
  </style>
</head>
<body>
  <header>
    <h1>TIPA US Academic Collaborator Finder</h1>
    <p class="subtitle">Enter a researcher identity and tune filters directly in the browser. The demo ranks US academic collaborator candidates from public scholarly metadata and explains every visible score.</p>
  </header>
  <main>
    <section class="panel">
      <h2>Run a collaborator search</h2>
      <form id="matchForm">
        <div class="grid">
          <label>Requester name *
            <input name="requester_name" value="Demo Researcher" required>
            <span class="hint">Required. Used for identity lookup and email drafts.</span>
          </label>
          <label>Semantic Scholar author URL/ID
            <input name="semantic_scholar_author" placeholder="https://www.semanticscholar.org/author/...">
            <span class="hint">Preferred for live data; avoids name ambiguity.</span>
          </label>
          <label>ORCID
            <input name="orcid" placeholder="0000-0002-1825-0097">
            <span class="hint">Optional identity hint.</span>
          </label>
          <label>Google Scholar link
            <input name="google_scholar_url" placeholder="Optional; not scraped">
            <span class="hint">Optional visible hint only. The backend does not scrape Scholar.</span>
          </label>
          <label>Desired region
            <input name="region" placeholder="e.g. Boston area">
            <span class="hint">Optional. Region matching is best-effort from institution metadata.</span>
          </label>
          <label>Minimum relevance
            <input name="min_relevance" type="number" value="0.55" min="0" max="1" step="0.01">
            <span class="hint">Candidates below this score are hidden.</span>
          </label>
          <label>Max coauthor neighbor
            <input name="max_neighbor" type="number" value="5" min="1" max="99" step="1">
            <span class="hint">1=direct coauthor, 2=shared coauthor, 5=no shallow bridge found.</span>
          </label>
          <label>Candidate/result limit
            <input name="max_results" type="number" value="20" min="1" max="100" step="1">
            <span class="hint">This is a limit, not a fixed top-5 shortlist.</span>
          </label>
        </div>
        <div class="actions">
          <label class="checkbox"><input name="use_demo_data" type="checkbox" checked> Use demo data</label>
          <button id="runButton" type="submit">Run</button>
          <span id="status" class="status"></span>
        </div>
      </form>
    </section>

    <section id="results"></section>
  </main>

  <script>
    const form = document.getElementById('matchForm');
    const button = document.getElementById('runButton');
    const statusEl = document.getElementById('status');
    const resultsEl = document.getElementById('results');
    const aiKeywordToken = '__AI_KEYWORD_TOKEN__';
    let lastPayload = null;

    const text = (value) => String(value ?? '');
    function el(tag, textValue, className) {
      const node = document.createElement(tag);
      if (className) node.className = className;
      if (textValue !== undefined) node.textContent = text(textValue);
      return node;
    }
    function fieldsetToPayload(formData) {
      return {
        requester_name: formData.get('requester_name'),
        semantic_scholar_author: formData.get('semantic_scholar_author'),
        orcid: formData.get('orcid'),
        google_scholar_url: formData.get('google_scholar_url'),
        region: formData.get('region'),
        min_relevance: formData.get('min_relevance'),
        max_neighbor: formData.get('max_neighbor'),
        max_results: formData.get('max_results'),
        use_demo_data: formData.get('use_demo_data') === 'on',
        ai_keywords: false
      };
    }
    function renderSummary(data) {
      const summary = el('div', undefined, 'summary');
      const metrics = [
        ['Visible candidates', data.visible_count],
        ['Below threshold', data.hidden_counts?.below_min_relevance ?? 0],
        ['Region-filtered', data.hidden_counts?.region_filter ?? 0],
        ['Neighbor-filtered', data.hidden_counts?.neighbor_filter ?? 0]
      ];
      for (const [label, value] of metrics) {
        const box = el('div', undefined, 'metric');
        box.appendChild(el('strong', value));
        box.appendChild(el('span', label));
        summary.appendChild(box);
      }
      return summary;
    }
    function keywordLabel(item) {
      if (typeof item === 'string') return item;
      const term = item?.term ?? '';
      const count = item?.count;
      return count ? `${term} x${count}` : term;
    }
    function renderKeywordBlock(title, keywords) {
      const block = el('section', undefined, 'debug-block');
      block.appendChild(el('h3', title));
      if (!keywords || keywords.length === 0) {
        block.appendChild(el('p', 'No keywords extracted from the listed requester publications.', 'empty'));
        return block;
      }
      const list = el('ul', undefined, 'keyword-list');
      keywords.forEach(item => {
        const label = keywordLabel(item);
        if (!label) return;
        list.appendChild(el('li', label, 'pill'));
      });
      block.appendChild(list);
      return block;
    }
    function renderPublicationBlock(debug) {
      const block = el('section', undefined, 'debug-block');
      block.appendChild(el('h3', 'Requester publications used'));
      const publications = debug?.publications || [];
      const total = debug?.publication_count ?? publications.length;
      const limit = debug?.listed_publication_limit ?? publications.length;
      block.appendChild(el('p', `Showing ${publications.length} of ${total} fetched requester publications; list is sorted by citations/year and capped at ${limit}.`, 'meta'));
      if (publications.length === 0) {
        block.appendChild(el('p', 'No requester publications were available from the selected source.', 'empty'));
        return block;
      }
      const list = el('ol', undefined, 'publication-list');
      publications.forEach(pub => {
        const row = el('li');
        const title = pub?.title || 'Untitled paper';
        if (pub?.url) {
          const link = el('a', title);
          link.href = pub.url;
          link.target = '_blank';
          link.rel = 'noopener noreferrer';
          row.appendChild(link);
        } else {
          row.appendChild(el('strong', title));
        }
        const metaParts = [];
        if (pub?.year) metaParts.push(String(pub.year));
        if (pub?.citation_count !== undefined) metaParts.push(`${pub.citation_count} citations`);
        if (pub?.paper_id) metaParts.push(`ID ${pub.paper_id}`);
        if (metaParts.length) row.appendChild(el('div', metaParts.join(' - '), 'meta'));
        if (pub?.snippet) row.appendChild(el('div', pub.snippet, 'meta'));
        list.appendChild(row);
      });
      block.appendChild(list);
      return block;
    }
    function renderRequesterDebug(debug) {
      if (!debug) return undefined;
      const panel = el('section', undefined, 'panel');
      panel.appendChild(el('h2', 'Requester debug'));
      panel.appendChild(el('p', 'These are the requester-side publications and extracted terms used to seed candidate discovery and scoring.', 'meta'));
      const source = debug.keyword_source || 'heuristic';
      panel.appendChild(el('p', `Keyword source: ${source}`, 'meta'));
      const actions = el('div', undefined, 'actions');
      const aiButton = el('button', 'AI-assisted keyword extraction');
      aiButton.type = 'button';
      aiButton.addEventListener('click', () => {
        if (!lastPayload) return;
        runMatch({...lastPayload, ai_keywords: true}, 'Extracting AI keywords...');
      });
      actions.appendChild(aiButton);
      panel.appendChild(actions);
      const grid = el('div', undefined, 'debug-grid');
      grid.appendChild(renderKeywordBlock('Extracted topic keywords', debug.topic_keywords || []));
      grid.appendChild(renderKeywordBlock('Extracted method keywords', debug.method_keywords || []));
      grid.appendChild(renderPublicationBlock(debug));
      panel.appendChild(grid);
      return panel;
    }
    function renderCandidate(candidate, index) {
      const card = el('article', undefined, 'candidate');
      const title = el('h3', `${index + 1}. ${candidate.name}`);
      card.appendChild(title);
      const meta = el('p', `${candidate.affiliation} - Region: ${candidate.region_tag}`);
      card.appendChild(meta);
      const score = el('div', `Score ${candidate.score}`, 'score');
      card.appendChild(score);
      const pills = el('div', undefined, 'pill-row');
      pills.appendChild(el('span', `Neighbor ${candidate.coauthor_neighbor_distance}`, 'pill'));
      if (candidate.profile_url) {
        const link = el('a', 'Semantic Scholar profile', 'pill');
        link.href = candidate.profile_url;
        link.target = '_blank';
        link.rel = 'noopener noreferrer';
        pills.appendChild(link);
      }
      card.appendChild(pills);
      card.appendChild(el('p', candidate.rationale));
      const breakdown = el('div', undefined, 'breakdown');
      Object.entries(candidate.score_breakdown || {}).forEach(([key, value]) => {
        breakdown.appendChild(el('div', `${key.replaceAll('_', ' ')}: ${value}`));
      });
      card.appendChild(breakdown);
      card.appendChild(el('h4', 'Evidence'));
      const list = el('ul');
      (candidate.evidence || []).forEach(item => {
        const row = el('li');
        row.appendChild(el('strong', `${item.title}${item.year ? ' (' + item.year + ')' : ''}: `));
        row.appendChild(el('span', item.snippet));
        list.appendChild(row);
      });
      card.appendChild(list);
      card.appendChild(el('h4', 'Personalized outreach draft'));
      card.appendChild(el('pre', candidate.outreach_email));
      return card;
    }
    function renderResults(data) {
      resultsEl.innerHTML = '';
      const panel = el('section', undefined, 'panel');
      panel.appendChild(el('h2', 'Results'));
      panel.appendChild(renderSummary(data));
      const notes = el('ul');
      [...(data.heuristic_notes || []), ...(data.data_notes || [])].forEach(note => {
        notes.appendChild(el('li', note));
      });
      panel.appendChild(notes);
      resultsEl.appendChild(panel);
      const requesterDebug = renderRequesterDebug(data.requester_debug);
      if (requesterDebug) resultsEl.appendChild(requesterDebug);
      (data.candidates || []).forEach((candidate, index) => {
        resultsEl.appendChild(renderCandidate(candidate, index));
      });
      if (!data.candidates || data.candidates.length === 0) {
        resultsEl.appendChild(el('p', 'No candidates met the current filters. Lower min_relevance, widen region, or increase max_neighbor.'));
      }
    }
    form.addEventListener('submit', async (event) => {
      event.preventDefault();
      const payload = fieldsetToPayload(new FormData(form));
      runMatch(payload, 'Running...');
    });
    async function runMatch(payload, pendingText) {
      lastPayload = {...payload};
      button.disabled = true;
      statusEl.textContent = pendingText;
      resultsEl.innerHTML = '';
      try {
        const response = await fetch('/api/match', {
          method: 'POST',
          headers: {'Content-Type': 'application/json', 'X-TIPA-AI-Token': aiKeywordToken},
          body: JSON.stringify(payload)
        });
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || 'Request failed');
        renderResults(data);
        statusEl.textContent = 'Done';
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        const node = el('p', message, 'error');
        resultsEl.appendChild(node);
        statusEl.textContent = 'Error';
      } finally {
        button.disabled = false;
      }
    }
  </script>
</body>
</html>
"""


class CollaboratorHandler(BaseHTTPRequestHandler):
    server_version = "TIPACollaboratorDemo/0.1"

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002 - inherited API name
        if os.environ.get("TIPA_SERVER_QUIET") == "1":
            return
        super().log_message(format, *args)

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path in {"/", "/index.html"}:
            html = APP_HTML.replace("__AI_KEYWORD_TOKEN__", AI_KEYWORD_TOKEN)
            self.write_bytes(HTTPStatus.OK, html.encode("utf-8"), "text/html; charset=utf-8")
            return
        if parsed.path == "/healthz":
            self.write_json(HTTPStatus.OK, {"status": "ok"})
            return
        if parsed.path == "/api/match":
            params = {key: values[-1] for key, values in urllib.parse.parse_qs(parsed.query).items()}
            if self.ai_keywords_requested(params):
                self.write_json(HTTPStatus.FORBIDDEN, {"error": "AI-assisted keyword extraction requires a POST from the local page"})
                return
            self.handle_match(params)
            return
        self.write_json(HTTPStatus.NOT_FOUND, {"error": "not found"})

    def do_OPTIONS(self) -> None:
        self.send_response(HTTPStatus.NO_CONTENT)
        self.end_headers()

    def do_POST(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path != "/api/match":
            self.write_json(HTTPStatus.NOT_FOUND, {"error": "not found"})
            return
        content_length = int(self.headers.get("Content-Length") or 0)
        if content_length > 200_000:
            self.drain_request_body(content_length)
            self.write_json(HTTPStatus.BAD_REQUEST, {"error": "request body too large"})
            return
        raw = self.rfile.read(content_length)
        try:
            payload = json.loads(raw.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            self.write_json(HTTPStatus.BAD_REQUEST, {"error": "invalid JSON body"})
            return
        if not isinstance(payload, dict):
            self.write_json(HTTPStatus.BAD_REQUEST, {"error": "JSON body must be an object"})
            return
        if self.ai_keywords_requested(payload) and self.headers.get("X-TIPA-AI-Token") != AI_KEYWORD_TOKEN:
            self.write_json(HTTPStatus.FORBIDDEN, {"error": "AI-assisted keyword extraction requires the local page token"})
            return
        self.handle_match(payload)

    def handle_match(self, payload: dict[str, Any]) -> None:
        try:
            result = match_collaborators(payload)
            self.write_json(HTTPStatus.OK, result)
        except ValueError as exc:
            self.write_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
        except ApiError as exc:
            self.write_json(
                HTTPStatus.BAD_GATEWAY,
                {
                    "error": str(exc),
                    "hint": "Try again later, provide a Semantic Scholar author ID, or enable 'Use demo data'.",
                },
            )

    def ai_keywords_requested(self, payload: dict[str, Any]) -> bool:
        value = payload.get("ai_keywords")
        if isinstance(value, bool):
            return value
        if value is None:
            return False
        return str(value).strip().lower() in {"1", "true", "yes", "on"}

    def drain_request_body(self, content_length: int) -> None:
        """Drain bounded oversized bodies so clients can still read the 400 response."""

        remaining = min(content_length, 1_000_000)
        while remaining > 0:
            chunk = self.rfile.read(min(65_536, remaining))
            if not chunk:
                break
            remaining -= len(chunk)

    def write_json(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self.write_bytes(status, body, "application/json; charset=utf-8")

    def write_bytes(self, status: HTTPStatus, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def create_server(host: str = "127.0.0.1", port: int = 8000) -> ThreadingHTTPServer:
    return ThreadingHTTPServer((host, port), CollaboratorHandler)


def main() -> None:
    host = os.environ.get("TIPA_HOST", "127.0.0.1")
    port = int(os.environ.get("TIPA_PORT", "8000"))
    server = create_server(host, port)
    print(f"TIPA collaborator demo running at http://{host}:{port}")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping server.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
