"""Core matching logic for the TIPA US academic collaborator demo.

The module is intentionally dependency-light so the demo can run with a stock
Python interpreter.  Semantic Scholar is the primary live data source; OpenAlex
is used only as a best-effort institution/region fallback when enough metadata
is available.  Google Scholar URLs are accepted as identity hints but are never
scraped.
"""

from __future__ import annotations

import json
import math
import os
import re
import shlex
import subprocess
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


SEMANTIC_SCHOLAR_GRAPH = "https://api.semanticscholar.org/graph/v1"
SEMANTIC_SCHOLAR_RECOMMENDATIONS = "https://api.semanticscholar.org/recommendations/v1"
OPENALEX_BASE = "https://api.openalex.org"
REQUESTER_KEYWORD_PROMPT = Path(__file__).with_name("prompts") / "requester_keyword_extraction.md"
CODEX_KEYWORD_SEMAPHORE = threading.BoundedSemaphore(1)

DEFAULT_SCORE_WEIGHTS = {
    "topic_fit": 0.35,
    "method_similarity": 0.25,
    "citation_stage": 0.15,
    "region_fit": 0.15,
    "coauthor_neighbor": 0.10,
}

STOPWORDS = {
    "about",
    "across",
    "after",
    "against",
    "also",
    "among",
    "analysis",
    "approach",
    "based",
    "between",
    "could",
    "data",
    "from",
    "have",
    "into",
    "method",
    "methods",
    "model",
    "models",
    "paper",
    "results",
    "study",
    "that",
    "their",
    "there",
    "these",
    "this",
    "through",
    "using",
    "with",
}

METHOD_PHRASES = {
    "agent-based model",
    "bayesian",
    "clinical trial",
    "computational",
    "cryo-em",
    "deep learning",
    "econometric",
    "finite element",
    "genome-wide",
    "in vitro",
    "in vivo",
    "machine learning",
    "meta-analysis",
    "microscopy",
    "molecular dynamics",
    "monte carlo",
    "natural language processing",
    "neural network",
    "optimization",
    "randomized controlled trial",
    "regression",
    "simulation",
    "single-cell",
    "spectroscopy",
    "statistical",
    "survey",
    "synthesis",
    "transformer",
}

METHOD_TOKENS = {
    "algorithm",
    "bayesian",
    "clinical",
    "computational",
    "deep",
    "econometric",
    "experimental",
    "genomic",
    "learning",
    "microscopy",
    "neural",
    "optimization",
    "qualitative",
    "quantitative",
    "randomized",
    "regression",
    "sequencing",
    "simulation",
    "spectroscopy",
    "statistical",
    "survey",
    "synthesis",
    "transformer",
}

US_REGION_HINTS = {
    "boston": [
        "boston",
        "cambridge",
        "harvard",
        "mit",
        "massachusetts institute",
        "tufts",
        "northeastern",
        "boston university",
        "brigham",
        "mass general",
        "massachusetts general",
        "umass",
        "worcester",
    ],
    "bay area": [
        "stanford",
        "berkeley",
        "ucsf",
        "san francisco",
        "palo alto",
        "san jose",
        "oakland",
        "silicon valley",
    ],
    "new york": [
        "new york",
        "columbia",
        "cornell",
        "nyu",
        "rockefeller",
        "mount sinai",
        "suny",
    ],
    "seattle": ["seattle", "washington", "uw", "fred hutch"],
    "research triangle": ["duke", "chapel hill", "nc state", "raleigh", "durham"],
    "los angeles": ["los angeles", "ucla", "caltech", "usc", "pasadena"],
}

US_AFFILIATION_HINTS = {
    "united states",
    " usa",
    "u.s.",
    "university of california",
    "harvard",
    "mit",
    "massachusetts institute",
    "stanford",
    "berkeley",
    "princeton",
    "columbia",
    "cornell",
    "yale",
    "duke",
    "caltech",
    "ucla",
    "usc",
    "nyu",
    "johns hopkins",
    "carnegie mellon",
    "university of washington",
    "university of michigan",
    "university of texas",
    "university of illinois",
    "university of pennsylvania",
    "northwestern",
}

KNOWN_NON_US_HINTS = {
    "china",
    "japan",
    "korea",
    "singapore",
    "canada",
    "germany",
    "france",
    "italy",
    "spain",
    "united kingdom",
    "uk",
    "australia",
    "netherlands",
    "switzerland",
}


class ApiError(RuntimeError):
    """Raised for live API failures that should be shown clearly to users."""


@dataclass(frozen=True)
class MatchRequest:
    requester_name: str
    semantic_scholar_author: str | None = None
    orcid: str | None = None
    google_scholar_url: str | None = None
    region: str | None = None
    min_relevance: float = 0.55
    max_neighbor: int = 5
    max_results: int = 20
    use_demo_data: bool = False
    ai_keywords: bool = False


@dataclass(frozen=True)
class RequesterKeywordProfile:
    source: str
    topic_terms: set[str]
    method_terms: set[str]
    topic_keywords: list[dict[str, Any]]
    method_keywords: list[dict[str, Any]]
    notes: list[str]


def clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def safe_float(value: Any, default: float, minimum: float, maximum: float) -> float:
    try:
        return clamp(float(value), minimum, maximum)
    except (TypeError, ValueError):
        return default


def safe_int(value: Any, default: int, minimum: int, maximum: int) -> int:
    try:
        return int(clamp(float(value), minimum, maximum))
    except (TypeError, ValueError):
        return default


def parse_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def normalize_space(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def parse_match_request(payload: dict[str, Any]) -> MatchRequest:
    requester_name = normalize_space(
        payload.get("requester_name") or payload.get("name") or payload.get("researcher_name")
    )
    if not requester_name:
        raise ValueError("requester_name is required")

    return MatchRequest(
        requester_name=requester_name,
        semantic_scholar_author=normalize_space(
            payload.get("semantic_scholar_author")
            or payload.get("semantic_scholar_url")
            or payload.get("author_id")
        )
        or None,
        orcid=normalize_space(payload.get("orcid")) or None,
        google_scholar_url=normalize_space(payload.get("google_scholar_url")) or None,
        region=normalize_space(payload.get("region")) or None,
        min_relevance=safe_float(payload.get("min_relevance"), 0.55, 0.0, 1.0),
        max_neighbor=safe_int(payload.get("max_neighbor"), 5, 1, 99),
        max_results=safe_int(payload.get("max_results"), 20, 1, 100),
        use_demo_data=parse_bool(payload.get("use_demo_data")),
        ai_keywords=parse_bool(payload.get("ai_keywords")),
    )


def extract_semantic_scholar_author_id(value: str | None) -> str | None:
    """Extract an author id from a Semantic Scholar URL or raw ID."""

    if not value:
        return None
    raw = value.strip()
    if not raw:
        return None

    nested_url_match = re.search(r"/author/[^/?#]+/([A-Za-z0-9:_-]+)", raw)
    if nested_url_match:
        return nested_url_match.group(1)

    url_match = re.search(r"/author/([^/?#]+)", raw)
    if url_match:
        slug_or_id = urllib.parse.unquote(url_match.group(1))
        return slug_or_id.rsplit("-", 1)[-1] if "-" in slug_or_id else slug_or_id

    query_match = re.search(r"(?:authorId|author_id)=([A-Za-z0-9:_-]+)", raw)
    if query_match:
        return query_match.group(1)

    if re.fullmatch(r"[A-Za-z0-9:_-]+", raw):
        return raw
    return None


def tokenize(text: str) -> set[str]:
    words = re.findall(r"[A-Za-z][A-Za-z0-9+-]{2,}", text.lower())
    return {word for word in words if word not in STOPWORDS}


def paper_text(paper: dict[str, Any]) -> str:
    fields = paper.get("fieldsOfStudy") or []
    s2_fields = paper.get("s2FieldsOfStudy") or []
    s2_names = [
        item.get("category", "") if isinstance(item, dict) else str(item)
        for item in s2_fields
    ]
    return " ".join(
        [
            normalize_space(paper.get("title")),
            normalize_space(paper.get("abstract")),
            " ".join(str(field) for field in fields),
            " ".join(s2_names),
        ]
    )


def keyword_set(papers: Iterable[dict[str, Any]]) -> set[str]:
    result: set[str] = set()
    for paper in papers:
        result.update(tokenize(paper_text(paper)))
    return result


def ranked_term_counts(terms: Iterable[str], limit: int) -> list[dict[str, Any]]:
    counts = Counter(term for term in terms if term)
    ranked = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    return [{"term": term, "count": count} for term, count in ranked[:limit]]


def ranked_topic_keywords(papers: Iterable[dict[str, Any]], limit: int = 30) -> list[dict[str, Any]]:
    terms: list[str] = []
    for paper in papers:
        terms.extend(tokenize(paper_text(paper)))
    return ranked_term_counts(terms, limit)


def method_keywords_from_text(text: str) -> set[str]:
    lower = text.lower()
    methods = {phrase for phrase in METHOD_PHRASES if phrase in lower}
    methods.update(token for token in tokenize(lower) if token in METHOD_TOKENS)
    return methods


def method_keyword_set(papers: Iterable[dict[str, Any]]) -> set[str]:
    result: set[str] = set()
    for paper in papers:
        result.update(method_keywords_from_text(paper_text(paper)))
    return result


def ranked_method_keywords(papers: Iterable[dict[str, Any]], limit: int = 20) -> list[dict[str, Any]]:
    terms: list[str] = []
    for paper in papers:
        terms.extend(method_keywords_from_text(paper_text(paper)))
    return ranked_term_counts(terms, limit)


def normalize_keyword_term(value: Any) -> str:
    term = normalize_space(value).lower()
    term = re.sub(r"[^a-z0-9+ -]", "", term)
    return normalize_space(term)


def keyword_terms_from_ranked(items: Iterable[dict[str, Any]]) -> set[str]:
    return {term for item in items if (term := normalize_keyword_term(item.get("term")))}


def ranked_keywords_from_terms(terms: Iterable[Any], limit: int) -> list[dict[str, Any]]:
    normalized: list[str] = []
    for value in terms:
        if isinstance(value, dict):
            value = value.get("term") or value.get("keyword") or value.get("name")
        term = normalize_keyword_term(value)
        if term:
            normalized.append(term)
    return ranked_term_counts(normalized, limit)


def expand_keyword_terms(terms: Iterable[str]) -> set[str]:
    expanded: set[str] = set()
    for term in terms:
        normalized = normalize_keyword_term(term)
        if not normalized:
            continue
        expanded.add(normalized)
        expanded.update(tokenize(normalized))
    return expanded


def extract_json_object(text: str) -> dict[str, Any]:
    stripped = text.strip()
    if not stripped:
        raise ValueError("empty Codex keyword output")
    try:
        value = json.loads(stripped)
    except json.JSONDecodeError:
        start = stripped.find("{")
        end = stripped.rfind("}")
        if start < 0 or end <= start:
            raise ValueError("Codex keyword output did not contain a JSON object") from None
        value = json.loads(stripped[start : end + 1])
    if not isinstance(value, dict):
        raise ValueError("Codex keyword output must be a JSON object")
    return value


def parse_ai_keyword_response(text: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    payload = extract_json_object(text)
    topic_keywords = ranked_keywords_from_terms(payload.get("topic_keywords") or [], 30)
    method_keywords = ranked_keywords_from_terms(payload.get("method_keywords") or [], 20)
    if not topic_keywords and not method_keywords:
        raise ValueError("Codex keyword output contained no usable keywords")
    return topic_keywords, method_keywords


def publication_titles(papers: Iterable[dict[str, Any]]) -> list[str]:
    titles: list[str] = []
    for paper in papers:
        title = normalize_space(paper.get("title"))
        if title:
            titles.append(title)
    return titles


def codex_keyword_prompt(titles: list[str]) -> str:
    try:
        instructions = REQUESTER_KEYWORD_PROMPT.read_text(encoding="utf-8")
    except OSError:
        instructions = (
            "Extract concise requester topic_keywords and method_keywords from publication titles. "
            "Return only JSON with arrays named topic_keywords and method_keywords."
        )
    return "\n\n".join(
        [
            instructions,
            "Publication titles as JSON:",
            json.dumps(titles, ensure_ascii=False, indent=2),
        ]
    )


def codex_command() -> list[str]:
    base = shlex.split(os.environ.get("TIPA_CODEX_COMMAND", "codex"), posix=os.name != "nt")
    return base + [
        "--ask-for-approval",
        "never",
        "exec",
        "--skip-git-repo-check",
        "--sandbox",
        "read-only",
        "--ephemeral",
        "--color",
        "never",
        "-",
    ]


def run_codex_keyword_extraction(titles: list[str], timeout: float = 60.0) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if not titles:
        raise ValueError("no requester publication titles available")
    if not CODEX_KEYWORD_SEMAPHORE.acquire(blocking=False):
        raise RuntimeError("Codex keyword extraction is already running")
    output_path = ""
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False, suffix=".json") as output_file:
            output_path = output_file.name
        command = codex_command()
        command = command[:-1] + ["--output-last-message", output_path, command[-1]]
        completed = subprocess.run(
            command,
            input=codex_keyword_prompt(titles),
            text=True,
            capture_output=True,
            timeout=timeout,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        if completed.returncode != 0:
            raise RuntimeError("Codex keyword extraction failed")
        try:
            final_message = Path(output_path).read_text(encoding="utf-8")
        except OSError:
            final_message = ""
        return parse_ai_keyword_response(final_message or completed.stdout)
    finally:
        if output_path:
            try:
                Path(output_path).unlink()
            except OSError:
                pass
        CODEX_KEYWORD_SEMAPHORE.release()


def heuristic_requester_keyword_profile(papers: list[dict[str, Any]], notes: list[str] | None = None) -> RequesterKeywordProfile:
    topic_keywords = ranked_topic_keywords(papers)
    method_keywords = ranked_method_keywords(papers)
    return RequesterKeywordProfile(
        source="heuristic",
        topic_terms=keyword_set(papers),
        method_terms=method_keyword_set(papers),
        topic_keywords=topic_keywords,
        method_keywords=method_keywords,
        notes=notes or [],
    )


def requester_keyword_profile(papers: list[dict[str, Any]], use_ai: bool) -> RequesterKeywordProfile:
    if not use_ai:
        return heuristic_requester_keyword_profile(papers)
    titles = publication_titles(papers)
    try:
        topic_keywords, method_keywords = run_codex_keyword_extraction(titles)
    except (OSError, subprocess.SubprocessError, RuntimeError, ValueError):
        return heuristic_requester_keyword_profile(
            papers,
            ["AI-assisted requester keyword extraction fell back to heuristic keywords."],
        )
    return RequesterKeywordProfile(
        source="ai",
        topic_terms=expand_keyword_terms(item["term"] for item in topic_keywords),
        method_terms=expand_keyword_terms(item["term"] for item in method_keywords),
        topic_keywords=topic_keywords,
        method_keywords=method_keywords,
        notes=["AI-assisted requester keyword extraction used Codex CLI publication-title analysis."],
    )


def jaccard(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def bounded_overlap(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    return min(1.0, len(left & right) / max(1, min(len(left), len(right))))


def citation_metric(author: dict[str, Any], papers: Iterable[dict[str, Any]] | None = None) -> float:
    for key in ("citationCount", "hIndex", "paperCount"):
        value = author.get(key)
        if isinstance(value, (int, float)) and value > 0:
            return float(value)
    if papers:
        citations = [paper.get("citationCount", 0) or 0 for paper in papers]
        if citations:
            return sum(citations) / len(citations)
    return 0.0


def citation_stage_similarity(requester_metric: float, candidate_metric: float) -> float:
    """Similarity of career/citation stage, not a quality ranking."""

    left = math.log1p(max(0.0, requester_metric))
    right = math.log1p(max(0.0, candidate_metric))
    if left == 0 and right == 0:
        return 0.5
    distance = abs(left - right)
    scale = max(left, right, 1.0)
    return clamp(1.0 - (distance / scale), 0.0, 1.0)


def authors_from_paper(paper: dict[str, Any]) -> list[dict[str, Any]]:
    authors = paper.get("authors") or []
    return [author for author in authors if isinstance(author, dict)]


def collect_coauthor_ids(papers: Iterable[dict[str, Any]], requester_id: str | None) -> set[str]:
    ids: set[str] = set()
    for paper in papers:
        for author in authors_from_paper(paper):
            author_id = str(author.get("authorId") or "")
            if author_id and author_id != requester_id:
                ids.add(author_id)
    return ids


def estimate_neighbor_distance(
    candidate_id: str | None,
    candidate_papers: Iterable[dict[str, Any]],
    requester_id: str | None,
    requester_coauthor_ids: set[str],
) -> tuple[int, str]:
    if not candidate_id:
        return 5, "unknown author id; treated as distant heuristic neighbor"

    for paper in candidate_papers:
        paper_author_ids = {str(author.get("authorId") or "") for author in authors_from_paper(paper)}
        if requester_id and requester_id in paper_author_ids and candidate_id in paper_author_ids:
            return 1, "direct coauthor on a fetched paper"
        if requester_coauthor_ids & paper_author_ids:
            return 2, "shares at least one fetched coauthor bridge"
    return 5, "no shallow coauthor bridge found in fetched papers"


def infer_region_tag(affiliations: Iterable[str], openalex_geo: dict[str, Any] | None = None) -> str:
    aff_text = " ".join(affiliations).lower()
    if openalex_geo:
        city = normalize_space(openalex_geo.get("city"))
        region = normalize_space(openalex_geo.get("region"))
        country = normalize_space(openalex_geo.get("country_code") or openalex_geo.get("country"))
        parts = [part for part in (city, region, country) if part]
        if parts:
            return ", ".join(parts)

    for label, hints in US_REGION_HINTS.items():
        if any(hint in aff_text for hint in hints):
            return label.title()
    if any(hint in aff_text for hint in US_AFFILIATION_HINTS):
        return "United States"
    return "Unknown (verify)"


def known_non_us_affiliation(affiliations: Iterable[str]) -> bool:
    text = " ".join(affiliations).lower()
    if not text:
        return False
    if any(hint in text for hint in US_AFFILIATION_HINTS):
        return False
    return any(hint in text for hint in KNOWN_NON_US_HINTS)


def region_score(region_filter: str | None, region_tag: str, affiliations: Iterable[str]) -> tuple[float, bool]:
    haystack = " ".join([region_tag, *affiliations]).lower()
    if not region_filter:
        if region_tag != "Unknown (verify)":
            return 0.75, True
        return 0.45, True

    terms = [term for term in tokenize(region_filter) if len(term) >= 3]
    raw = region_filter.lower().strip()
    matched = raw in haystack or any(term in haystack for term in terms)
    return (1.0 if matched else 0.0), matched


def score_from_distance(distance: int) -> float:
    if distance <= 1:
        return 1.0
    if distance == 2:
        return 0.78
    if distance <= 5:
        return 0.45
    return 0.0


def short_snippet(text: str, limit: int = 220) -> str:
    clean = normalize_space(text)
    if len(clean) <= limit:
        return clean
    return clean[: limit - 3].rstrip() + "..."


def candidate_affiliations(author: dict[str, Any]) -> list[str]:
    affiliations = author.get("affiliations") or []
    if isinstance(affiliations, str):
        affiliations = [affiliations]
    return [normalize_space(item) for item in affiliations if normalize_space(item)]


def build_email(
    requester_name: str,
    candidate_name: str,
    candidate_affiliation: str,
    evidence_title: str,
    shared_methods: Iterable[str],
) -> str:
    method_text = ", ".join(sorted(shared_methods)[:3]) or "overlapping research methods"
    affiliation_text = f" at {candidate_affiliation}" if candidate_affiliation else ""
    return (
        f"Subject: Potential academic collaboration on {method_text}\n\n"
        f"Dear {candidate_name},\n\n"
        f"My name is {requester_name}. I am exploring US academic collaborators whose "
        f"recent work aligns technically and methodologically with my research. Your work"
        f"{affiliation_text}, especially \"{evidence_title}\", stood out because it appears "
        f"to overlap on {method_text}.\n\n"
        "Would you be open to a short introductory call to compare research directions and "
        "discuss whether there is a concrete collaboration opportunity?\n\n"
        f"Best,\n{requester_name}"
    )


class JsonApiClient:
    def __init__(self, timeout: float = 12.0, user_agent: str = "tipa-collaborator-demo/0.1"):
        self.timeout = timeout
        self.user_agent = user_agent

    def request_json(
        self,
        method: str,
        url: str,
        params: dict[str, Any] | None = None,
        payload: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> Any:
        if params:
            url = f"{url}?{urllib.parse.urlencode(params)}"
        data = None
        request_headers = {"User-Agent": self.user_agent}
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
            request_headers["Content-Type"] = "application/json"
        if headers:
            request_headers.update(headers)
        request = urllib.request.Request(url, data=data, method=method, headers=request_headers)
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise ApiError(f"{method} {url} failed with HTTP {exc.code}: {detail[:300]}") from exc
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise ApiError(f"{method} {url} failed: {exc}") from exc


class SemanticScholarClient:
    AUTHOR_FIELDS = (
        "authorId,name,url,affiliations,paperCount,citationCount,hIndex,"
        "papers.paperId,papers.title,papers.abstract,papers.year,papers.citationCount,"
        "papers.fieldsOfStudy,papers.s2FieldsOfStudy,papers.authors"
    )
    PAPER_FIELDS = (
        "paperId,title,abstract,year,citationCount,fieldsOfStudy,s2FieldsOfStudy,"
        "authors.authorId,authors.name,authors.url"
    )

    def __init__(self, api_key: str | None = None, timeout: float = 12.0):
        self.api_key = api_key or os.environ.get("SEMANTIC_SCHOLAR_API_KEY")
        self.client = JsonApiClient(timeout=timeout)

    @property
    def headers(self) -> dict[str, str]:
        return {"x-api-key": self.api_key} if self.api_key else {}

    def get_author(self, author_id: str) -> dict[str, Any]:
        return self.client.request_json(
            "GET",
            f"{SEMANTIC_SCHOLAR_GRAPH}/author/{urllib.parse.quote(author_id)}",
            {"fields": self.AUTHOR_FIELDS},
            headers=self.headers,
        )

    def search_authors(self, name: str, limit: int = 5) -> list[dict[str, Any]]:
        data = self.client.request_json(
            "GET",
            f"{SEMANTIC_SCHOLAR_GRAPH}/author/search",
            {"query": name, "limit": limit, "fields": self.AUTHOR_FIELDS},
            headers=self.headers,
        )
        return list(data.get("data") or [])

    def batch_authors(self, author_ids: list[str]) -> dict[str, dict[str, Any]]:
        if not author_ids:
            return {}
        ids = list(dict.fromkeys(author_ids))[:100]
        try:
            data = self.client.request_json(
                "POST",
                f"{SEMANTIC_SCHOLAR_GRAPH}/author/batch",
                {"fields": self.AUTHOR_FIELDS},
                {"ids": ids},
                headers=self.headers,
            )
            authors = data if isinstance(data, list) else data.get("data", [])
            return {
                str(author.get("authorId")): author
                for author in authors
                if isinstance(author, dict) and author.get("authorId")
            }
        except ApiError:
            details: dict[str, dict[str, Any]] = {}
            for author_id in ids[:25]:
                try:
                    author = self.get_author(author_id)
                    if author.get("authorId"):
                        details[str(author["authorId"])] = author
                    time.sleep(0.05)
                except ApiError:
                    continue
            return details

    def recommend_papers(self, seed_paper_ids: list[str], limit: int = 80) -> list[dict[str, Any]]:
        if not seed_paper_ids:
            return []
        data = self.client.request_json(
            "POST",
            f"{SEMANTIC_SCHOLAR_RECOMMENDATIONS}/papers",
            {"fields": self.PAPER_FIELDS, "limit": limit},
            {"positivePaperIds": seed_paper_ids[:10], "negativePaperIds": []},
            headers=self.headers,
        )
        if isinstance(data, list):
            return data
        return list(data.get("recommendedPapers") or data.get("data") or [])

    def search_papers(self, query: str, limit: int = 60) -> list[dict[str, Any]]:
        data = self.client.request_json(
            "GET",
            f"{SEMANTIC_SCHOLAR_GRAPH}/paper/search",
            {"query": query, "limit": limit, "fields": self.PAPER_FIELDS},
            headers=self.headers,
        )
        return list(data.get("data") or [])


class OpenAlexClient:
    def __init__(self, timeout: float = 8.0):
        self.client = JsonApiClient(timeout=timeout)

    def find_us_author_geo(self, name: str) -> dict[str, Any] | None:
        data = self.client.request_json(
            "GET",
            f"{OPENALEX_BASE}/authors",
            {
                "search": name,
                "filter": "last_known_institutions.country_code:US",
                "per-page": 1,
            },
        )
        results = data.get("results") or []
        if not results:
            return None
        institutions = results[0].get("last_known_institutions") or []
        for institution in institutions:
            geo = institution.get("geo") or {}
            if institution.get("country_code") == "US" or geo.get("country_code") == "US":
                return {
                    "institution": institution.get("display_name"),
                    "city": geo.get("city"),
                    "region": geo.get("region"),
                    "country_code": "US",
                }
        return None


def resolve_requester_author(request: MatchRequest, s2: SemanticScholarClient) -> dict[str, Any]:
    author_id = extract_semantic_scholar_author_id(request.semantic_scholar_author)
    if author_id:
        return s2.get_author(author_id)

    # ORCID is preserved as an identity hint, but Semantic Scholar author search
    # is still name-based because ORCID support is not consistently available in
    # the public author search endpoint.
    candidates = s2.search_authors(request.requester_name, limit=5)
    if not candidates:
        raise ApiError(f"No Semantic Scholar author candidates found for {request.requester_name!r}")
    return candidates[0]


def seed_papers_from_author(author: dict[str, Any], max_seed: int = 10) -> list[dict[str, Any]]:
    papers = [paper for paper in author.get("papers") or [] if isinstance(paper, dict)]
    papers.sort(key=lambda paper: (paper.get("citationCount") or 0, paper.get("year") or 0), reverse=True)
    return papers[:max_seed]


def paper_url(paper: dict[str, Any]) -> str | None:
    paper_id = paper.get("paperId")
    if not paper_id:
        return None
    return f"https://www.semanticscholar.org/paper/{paper_id}"


def requester_debug_payload(
    requester_author: dict[str, Any],
    keyword_profile: RequesterKeywordProfile,
    publication_limit: int = 30,
) -> dict[str, Any]:
    papers = seed_papers_from_author(requester_author, max_seed=publication_limit)
    publications = [
        {
            "paper_id": paper.get("paperId"),
            "title": normalize_space(paper.get("title")) or "Untitled paper",
            "year": paper.get("year"),
            "citation_count": paper.get("citationCount") or 0,
            "snippet": short_snippet(paper.get("abstract") or paper.get("title") or ""),
            "url": paper_url(paper),
        }
        for paper in papers
    ]
    return {
        "source": "requester_author.papers",
        "keyword_source": keyword_profile.source,
        "keyword_notes": keyword_profile.notes,
        "publication_count": len([paper for paper in requester_author.get("papers") or [] if isinstance(paper, dict)]),
        "listed_publication_limit": publication_limit,
        "topic_keywords": keyword_profile.topic_keywords,
        "method_keywords": keyword_profile.method_keywords,
        "publications": publications,
    }


def fallback_search_query(
    seed_papers: list[dict[str, Any]],
    keyword_profile: RequesterKeywordProfile | None = None,
) -> str:
    if keyword_profile:
        topic_terms = [item["term"] for item in keyword_profile.topic_keywords]
        method_terms = [item["term"] for item in keyword_profile.method_keywords]
        selected_profile_terms = method_terms[:3] + [term for term in topic_terms if term not in method_terms][:5]
        if selected_profile_terms:
            return " ".join(selected_profile_terms)
    keywords = keyword_set(seed_papers)
    methods = method_keyword_set(seed_papers)
    selected = sorted(methods)[:3] + sorted(keywords - methods)[:5]
    return " ".join(selected) or normalize_space(seed_papers[0].get("title") if seed_papers else "")


def collect_candidate_papers(
    requester_author: dict[str, Any],
    s2: SemanticScholarClient,
    keyword_profile: RequesterKeywordProfile | None = None,
) -> tuple[list[dict[str, Any]], list[str]]:
    notes: list[str] = []
    seeds = seed_papers_from_author(requester_author)
    seed_ids = [str(paper.get("paperId")) for paper in seeds if paper.get("paperId")]
    papers: list[dict[str, Any]] = []
    try:
        papers = s2.recommend_papers(seed_ids)
        notes.append("Candidate papers from Semantic Scholar recommendations.")
    except ApiError as exc:
        notes.append(f"Recommendation endpoint unavailable; used paper search fallback. Detail: {exc}")
    if not papers:
        query = fallback_search_query(seeds, keyword_profile)
        if not query:
            raise ApiError("Requester author has no usable seed papers.")
        papers = s2.search_papers(query)
        notes.append(f"Candidate papers from Semantic Scholar paper search for: {query!r}.")
    return papers, notes


def group_candidates_from_papers(
    papers: Iterable[dict[str, Any]], requester_id: str | None
) -> dict[str, dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for paper in papers:
        for author in authors_from_paper(paper):
            author_id = str(author.get("authorId") or "")
            name = normalize_space(author.get("name"))
            if not author_id or not name or author_id == requester_id:
                continue
            record = grouped.setdefault(
                author_id,
                {
                    "authorId": author_id,
                    "name": name,
                    "url": author.get("url"),
                    "papers": [],
                },
            )
            record["papers"].append(paper)
    return grouped


def build_candidate_list(
    request: MatchRequest,
    requester_author: dict[str, Any],
    candidate_papers: list[dict[str, Any]],
    author_details: dict[str, dict[str, Any]],
    openalex: OpenAlexClient | None = None,
    requester_profile: RequesterKeywordProfile | None = None,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    requester_id = str(requester_author.get("authorId") or "")
    requester_papers = seed_papers_from_author(requester_author, max_seed=30)
    requester_profile = requester_profile or requester_keyword_profile(requester_papers, False)
    requester_keywords = requester_profile.topic_terms
    requester_methods = requester_profile.method_terms
    requester_coauthors = collect_coauthor_ids(requester_papers, requester_id)
    requester_citation_metric = citation_metric(requester_author, requester_papers)
    grouped = group_candidates_from_papers(candidate_papers, requester_id)
    # OpenAlex is a useful region fallback, but live demo responsiveness matters.
    # Cap lookups so sparse Semantic Scholar affiliations do not turn one search
    # into dozens of serial external requests.
    openalex_lookup_budget = 12 if request.region else 5

    candidates: list[dict[str, Any]] = []
    hidden = {
        "below_min_relevance": 0,
        "region_filter": 0,
        "neighbor_filter": 0,
        "known_non_us": 0,
        "result_limit": 0,
    }

    for author_id, record in grouped.items():
        details = author_details.get(author_id, {})
        name = normalize_space(details.get("name") or record.get("name"))
        papers = [paper for paper in (details.get("papers") or []) if isinstance(paper, dict)]
        evidence_papers = record["papers"][:3]
        combined_papers = evidence_papers + papers[:20]
        affiliations = candidate_affiliations(details)

        if known_non_us_affiliation(affiliations):
            hidden["known_non_us"] += 1
            continue

        openalex_geo = None
        if not affiliations and openalex and openalex_lookup_budget > 0:
            openalex_lookup_budget -= 1
            try:
                openalex_geo = openalex.find_us_author_geo(name)
                if openalex_geo and openalex_geo.get("institution"):
                    affiliations = [str(openalex_geo["institution"])]
            except ApiError:
                openalex_geo = None

        region_tag = infer_region_tag(affiliations, openalex_geo)
        region_fit, region_matches = region_score(request.region, region_tag, affiliations)
        if request.region and not region_matches:
            hidden["region_filter"] += 1
            continue

        candidate_keywords = keyword_set(combined_papers)
        candidate_methods = method_keyword_set(combined_papers)
        topic_fit = max(
            jaccard(requester_keywords, candidate_keywords),
            0.65 * bounded_overlap(requester_keywords, candidate_keywords),
        )
        # Recommendation edges are already a relevance signal; avoid zeroing out
        # candidates only because abstracts/fields are sparse.
        if evidence_papers:
            topic_fit = max(topic_fit, 0.48)

        method_similarity = max(
            jaccard(requester_methods, candidate_methods),
            0.75 * bounded_overlap(requester_methods, candidate_methods),
        )
        if requester_methods and not candidate_methods:
            method_similarity = 0.25
        elif not requester_methods and not candidate_methods:
            method_similarity = 0.4

        candidate_citation_metric = citation_metric(details, combined_papers)
        citation_stage = citation_stage_similarity(requester_citation_metric, candidate_citation_metric)
        neighbor_distance, neighbor_reason = estimate_neighbor_distance(
            author_id, combined_papers, requester_id, requester_coauthors
        )
        if neighbor_distance > request.max_neighbor:
            hidden["neighbor_filter"] += 1
            continue
        neighbor_score = score_from_distance(neighbor_distance)

        breakdown = {
            "topic_fit": round(topic_fit, 3),
            "method_similarity": round(method_similarity, 3),
            "citation_stage": round(citation_stage, 3),
            "region_fit": round(region_fit, 3),
            "coauthor_neighbor": round(neighbor_score, 3),
        }
        total_score = sum(breakdown[key] * DEFAULT_SCORE_WEIGHTS[key] for key in DEFAULT_SCORE_WEIGHTS)
        total_score = round(clamp(total_score, 0.0, 1.0), 3)
        if total_score < request.min_relevance:
            hidden["below_min_relevance"] += 1
            continue

        shared_methods = requester_methods & candidate_methods
        evidence = [
            {
                "title": normalize_space(paper.get("title")) or "Untitled paper",
                "year": paper.get("year"),
                "snippet": short_snippet(paper.get("abstract") or paper.get("title") or ""),
                "url": f"https://www.semanticscholar.org/paper/{paper.get('paperId')}"
                if paper.get("paperId")
                else None,
            }
            for paper in evidence_papers[:2]
        ]
        best_title = evidence[0]["title"] if evidence else "your recent publication"
        affiliation = affiliations[0] if affiliations else ""
        candidates.append(
            {
                "author_id": author_id,
                "name": name,
                "affiliation": affiliation or "Unknown (verify)",
                "region_tag": region_tag,
                "profile_url": details.get("url") or record.get("url") or f"https://www.semanticscholar.org/author/{author_id}",
                "score": total_score,
                "score_breakdown": breakdown,
                "coauthor_neighbor_distance": neighbor_distance,
                "coauthor_neighbor_note": neighbor_reason,
                "rationale": (
                    f"Technical/topic overlap score {breakdown['topic_fit']}; method similarity "
                    f"{breakdown['method_similarity']} based on shared terms "
                    f"{', '.join(sorted(shared_methods)[:5]) or 'limited extracted method terms'}; "
                    f"region tag {region_tag}; coauthor bridge heuristic: {neighbor_reason}."
                ),
                "evidence": evidence,
                "outreach_email": build_email(
                    request.requester_name, name, affiliation, best_title, shared_methods
                ),
            }
        )

    candidates.sort(key=lambda item: item["score"], reverse=True)
    if len(candidates) > request.max_results:
        hidden["result_limit"] = len(candidates) - request.max_results
        candidates = candidates[: request.max_results]
    return candidates, hidden


def match_collaborators(payload: dict[str, Any]) -> dict[str, Any]:
    request = parse_match_request(payload)
    if request.use_demo_data:
        requester_author, candidate_papers, author_details = demo_dataset(request.requester_name)
        data_notes = ["Using built-in demo data; no external API calls were made."]
    else:
        s2 = SemanticScholarClient()
        requester_author = resolve_requester_author(request, s2)
    requester_papers = seed_papers_from_author(requester_author, max_seed=30)
    requester_profile = requester_keyword_profile(requester_papers, request.ai_keywords)
    if not request.use_demo_data:
        candidate_papers, data_notes = collect_candidate_papers(requester_author, s2, requester_profile)
        candidate_ids = list(group_candidates_from_papers(candidate_papers, str(requester_author.get("authorId") or "")).keys())
        author_details = s2.batch_authors(candidate_ids)

    openalex = None if request.use_demo_data else OpenAlexClient()
    candidates, hidden = build_candidate_list(
        request,
        requester_author,
        candidate_papers,
        author_details,
        openalex=openalex,
        requester_profile=requester_profile,
    )
    return {
        "requester": {
            "name": request.requester_name,
            "semantic_scholar_author_id": requester_author.get("authorId"),
            "semantic_scholar_url": requester_author.get("url"),
            "google_scholar_url": request.google_scholar_url,
            "orcid": request.orcid,
        },
        "requester_debug": requester_debug_payload(requester_author, requester_profile),
        "filters": {
            "region": request.region,
            "min_relevance": request.min_relevance,
            "max_neighbor": request.max_neighbor,
            "max_results": request.max_results,
        },
        "score_weights": DEFAULT_SCORE_WEIGHTS,
        "heuristic_notes": [
            "Method similarity is inferred from titles, abstracts, fields, and method-like keywords.",
            "Citation-stage similarity is not a quality score.",
            "Region and coauthor-neighbor distance are best-effort heuristics from sparse public metadata.",
            "Google Scholar links are accepted as optional hints but are not scraped.",
            *requester_profile.notes,
        ],
        "data_notes": data_notes,
        "hidden_counts": hidden,
        "visible_count": len(candidates),
        "candidates": candidates,
    }


def demo_dataset(requester_name: str) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, dict[str, Any]]]:
    requester = {
        "authorId": "REQ-001",
        "name": requester_name,
        "url": "https://www.semanticscholar.org/author/demo-requester",
        "hIndex": 22,
        "citationCount": 2600,
        "papers": [
            {
                "paperId": "REQ-P1",
                "title": "Deep learning methods for biomedical signal prediction",
                "abstract": "A transformer and neural network approach for clinical biomedical signal prediction.",
                "year": 2024,
                "citationCount": 320,
                "fieldsOfStudy": ["Computer Science", "Medicine"],
                "authors": [{"authorId": "REQ-001", "name": requester_name}, {"authorId": "BRIDGE-1", "name": "A Bridge"}],
            },
            {
                "paperId": "REQ-P2",
                "title": "Interpretable machine learning for translational diagnostics",
                "abstract": "Machine learning, regression, and statistical validation for diagnostics.",
                "year": 2023,
                "citationCount": 210,
                "fieldsOfStudy": ["Computer Science", "Medicine"],
                "authors": [{"authorId": "REQ-001", "name": requester_name}, {"authorId": "BRIDGE-2", "name": "B Bridge"}],
            },
        ],
    }
    papers = [
        {
            "paperId": "CAND-P1",
            "title": "Transformer models for clinical signal analysis",
            "abstract": "Deep learning and transformer methods for biomedical time-series analysis.",
            "year": 2024,
            "citationCount": 180,
            "fieldsOfStudy": ["Computer Science", "Medicine"],
            "authors": [{"authorId": "CAND-1", "name": "Maria Chen"}, {"authorId": "BRIDGE-1", "name": "A Bridge"}],
        },
        {
            "paperId": "CAND-P2",
            "title": "Statistical validation of neural diagnostic systems",
            "abstract": "Regression and statistical evaluation for neural network clinical tools.",
            "year": 2022,
            "citationCount": 140,
            "fieldsOfStudy": ["Computer Science", "Medicine"],
            "authors": [{"authorId": "CAND-2", "name": "David Kim"}],
        },
        {
            "paperId": "CAND-P3",
            "title": "Biomedical machine learning in hospital workflows",
            "abstract": "Machine learning optimization for translational hospital workflows.",
            "year": 2023,
            "citationCount": 95,
            "fieldsOfStudy": ["Medicine"],
            "authors": [{"authorId": "CAND-3", "name": "Priya Patel"}],
        },
        {
            "paperId": "CAND-P4",
            "title": "Unrelated marine ecology field survey",
            "abstract": "A qualitative survey of marine ecology education programs.",
            "year": 2021,
            "citationCount": 30,
            "fieldsOfStudy": ["Biology"],
            "authors": [{"authorId": "CAND-LOW", "name": "Low Relevance"}],
        },
    ]
    details = {
        "CAND-1": {
            "authorId": "CAND-1",
            "name": "Maria Chen",
            "url": "https://www.semanticscholar.org/author/demo-maria-chen",
            "affiliations": ["Massachusetts Institute of Technology, Cambridge, MA, USA"],
            "hIndex": 24,
            "citationCount": 3100,
            "papers": [papers[0]],
        },
        "CAND-2": {
            "authorId": "CAND-2",
            "name": "David Kim",
            "url": "https://www.semanticscholar.org/author/demo-david-kim",
            "affiliations": ["Stanford University, Palo Alto, CA, USA"],
            "hIndex": 19,
            "citationCount": 2100,
            "papers": [papers[1]],
        },
        "CAND-3": {
            "authorId": "CAND-3",
            "name": "Priya Patel",
            "url": "https://www.semanticscholar.org/author/demo-priya-patel",
            "affiliations": ["Boston University, Boston, MA, USA"],
            "hIndex": 16,
            "citationCount": 1200,
            "papers": [papers[2]],
        },
        "CAND-LOW": {
            "authorId": "CAND-LOW",
            "name": "Low Relevance",
            "url": "https://www.semanticscholar.org/author/demo-low",
            "affiliations": ["University of Somewhere, USA"],
            "hIndex": 3,
            "citationCount": 80,
            "papers": [papers[3]],
        },
    }
    return requester, papers, details
