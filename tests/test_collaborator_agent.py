import http.client
import json
import subprocess
import threading
import unittest
from unittest.mock import patch

from collaborator_agent import (
    RequesterKeywordProfile,
    citation_stage_similarity,
    codex_command,
    CODEX_KEYWORD_SEMAPHORE,
    extract_semantic_scholar_author_id,
    fallback_search_query,
    match_collaborators,
    parse_ai_keyword_response,
    parse_match_request,
    run_codex_keyword_extraction,
)
from server import create_server


class CollaboratorAgentTests(unittest.TestCase):
    def test_extract_semantic_scholar_author_id(self):
        self.assertEqual(extract_semantic_scholar_author_id("12345"), "12345")
        self.assertEqual(
            extract_semantic_scholar_author_id("https://www.semanticscholar.org/author/Jane-Doe-98765"),
            "98765",
        )
        self.assertEqual(
            extract_semantic_scholar_author_id("https://www.semanticscholar.org/author/Jane-Doe/98765"),
            "98765",
        )
        self.assertEqual(extract_semantic_scholar_author_id("https://x.test/?authorId=A-1"), "A-1")
        self.assertIsNone(extract_semantic_scholar_author_id(""))

    def test_parse_request_clamps_user_filters(self):
        request = parse_match_request(
            {
                "requester_name": "  Demo Researcher  ",
                "min_relevance": "2",
                "max_neighbor": "0",
                "max_results": "500",
                "use_demo_data": "on",
            }
        )
        self.assertEqual(request.requester_name, "Demo Researcher")
        self.assertEqual(request.min_relevance, 1.0)
        self.assertEqual(request.max_neighbor, 1)
        self.assertEqual(request.max_results, 100)
        self.assertTrue(request.use_demo_data)
        self.assertFalse(request.ai_keywords)

    def test_parse_request_accepts_ai_keyword_flag(self):
        request = parse_match_request({"requester_name": "Demo Researcher", "ai_keywords": "true"})
        self.assertTrue(request.ai_keywords)

    def test_citation_similarity_is_bounded(self):
        for left, right in [(0, 0), (10, 100), (1000, 1000), (-5, 10)]:
            score = citation_stage_similarity(left, right)
            self.assertGreaterEqual(score, 0)
            self.assertLessEqual(score, 1)

    def test_demo_match_returns_sorted_filterable_collaborators(self):
        result = match_collaborators(
            {
                "requester_name": "Demo Researcher",
                "use_demo_data": True,
                "min_relevance": 0.50,
                "max_neighbor": 5,
                "max_results": 10,
            }
        )
        candidates = result["candidates"]
        self.assertGreaterEqual(len(candidates), 2)
        self.assertEqual([c["score"] for c in candidates], sorted([c["score"] for c in candidates], reverse=True))
        self.assertGreater(result["hidden_counts"]["below_min_relevance"], 0)
        self.assertIn("outreach_email", candidates[0])
        self.assertIn("score_breakdown", candidates[0])
        debug = result["requester_debug"]
        self.assertGreaterEqual(len(debug["publications"]), 2)
        self.assertIn(
            "biomedical",
            {item["term"] for item in debug["topic_keywords"]},
        )
        self.assertIn(
            "deep learning",
            {item["term"] for item in debug["method_keywords"]},
        )
        self.assertEqual(debug["keyword_source"], "heuristic")

    def test_parse_ai_keyword_response_accepts_json_object(self):
        topics, methods = parse_ai_keyword_response(
            '{"topic_keywords":["Biomedical Signal Processing"],"method_keywords":["Deep Learning"]}'
        )
        self.assertEqual(topics, [{"term": "biomedical signal processing", "count": 1}])
        self.assertEqual(methods, [{"term": "deep learning", "count": 1}])

    def test_parse_ai_keyword_response_rejects_empty_keywords(self):
        with self.assertRaises(ValueError):
            parse_ai_keyword_response('{"topic_keywords":[],"method_keywords":[]}')

    def test_codex_command_places_approval_before_exec(self):
        command = codex_command()
        self.assertLess(command.index("--ask-for-approval"), command.index("exec"))

    def test_run_codex_keyword_extraction_reads_final_message_file(self):
        def fake_run(command, **kwargs):
            output_path = command[command.index("--output-last-message") + 1]
            with open(output_path, "w", encoding="utf-8") as output:
                output.write('{"topic_keywords":["clinical diagnostics"],"method_keywords":["regression"]}')
            return subprocess.CompletedProcess(command, 0, stdout="ignored", stderr="")

        with patch("collaborator_agent.subprocess.run", side_effect=fake_run) as run:
            topics, methods = run_codex_keyword_extraction(["A title"], timeout=1)
        run.assert_called_once()
        self.assertEqual(topics[0]["term"], "clinical diagnostics")
        self.assertEqual(methods[0]["term"], "regression")

    def test_run_codex_keyword_extraction_raises_generic_nonzero_error(self):
        completed = subprocess.CompletedProcess(["codex"], 2, stdout="secret path", stderr="auth detail")
        with patch("collaborator_agent.subprocess.run", return_value=completed):
            with self.assertRaisesRegex(RuntimeError, "^Codex keyword extraction failed$"):
                run_codex_keyword_extraction(["A title"], timeout=1)

    def test_run_codex_keyword_extraction_rejects_concurrent_invocation(self):
        self.assertTrue(CODEX_KEYWORD_SEMAPHORE.acquire(blocking=False))
        try:
            with self.assertRaisesRegex(RuntimeError, "already running"):
                run_codex_keyword_extraction(["A title"], timeout=1)
        finally:
            CODEX_KEYWORD_SEMAPHORE.release()

    def test_ai_keyword_match_uses_codex_terms_for_requester_reranking(self):
        with patch(
            "collaborator_agent.run_codex_keyword_extraction",
            return_value=(
                [{"term": "marine ecology", "count": 1}],
                [{"term": "survey", "count": 1}],
            ),
        ) as extractor:
            result = match_collaborators(
                {
                    "requester_name": "Demo Researcher",
                    "use_demo_data": True,
                    "ai_keywords": True,
                    "min_relevance": 0.0,
                    "max_neighbor": 5,
                    "max_results": 10,
                }
            )
        extractor.assert_called_once()
        debug = result["requester_debug"]
        self.assertEqual(debug["keyword_source"], "ai")
        self.assertIn("marine ecology", {item["term"] for item in debug["topic_keywords"]})
        self.assertIn("survey", {item["term"] for item in debug["method_keywords"]})
        self.assertEqual(result["candidates"][0]["name"], "Low Relevance")

    def test_ai_keyword_failure_falls_back_to_heuristics(self):
        with patch("collaborator_agent.run_codex_keyword_extraction", side_effect=RuntimeError("missing codex")):
            result = match_collaborators(
                {
                    "requester_name": "Demo Researcher",
                    "use_demo_data": True,
                    "ai_keywords": True,
                    "min_relevance": 0.50,
                    "max_neighbor": 5,
                }
            )
        debug = result["requester_debug"]
        self.assertEqual(debug["keyword_source"], "heuristic")
        self.assertTrue(debug["keyword_notes"])
        self.assertIn("fell back", " ".join(result["heuristic_notes"]))

    def test_fallback_search_query_prefers_ai_profile_terms(self):
        profile = RequesterKeywordProfile(
            source="ai",
            topic_terms={"health economics"},
            method_terms={"bayesian model"},
            topic_keywords=[{"term": "health economics", "count": 1}],
            method_keywords=[{"term": "bayesian model", "count": 1}],
            notes=[],
        )
        query = fallback_search_query([], profile)
        self.assertEqual(query, "bayesian model health economics")

    def test_region_filter_and_result_limit(self):
        result = match_collaborators(
            {
                "requester_name": "Demo Researcher",
                "use_demo_data": True,
                "region": "Boston",
                "min_relevance": 0.40,
                "max_neighbor": 5,
                "max_results": 1,
            }
        )
        self.assertEqual(result["visible_count"], 1)
        self.assertIn("Boston", result["candidates"][0]["region_tag"])

    def test_missing_requester_is_error(self):
        with self.assertRaises(ValueError):
            parse_match_request({"use_demo_data": True})


class ServerSmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = create_server("127.0.0.1", 0)
        cls.host, cls.port = cls.server.server_address
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)

    def request(self, method, path, body=None, extra_headers=None):
        conn = http.client.HTTPConnection(self.host, self.port, timeout=5)
        encoded = None
        headers = dict(extra_headers or {})
        if body is not None:
            encoded = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        conn.request(method, path, body=encoded, headers=headers)
        response = conn.getresponse()
        payload = response.read()
        conn.close()
        return response.status, payload

    def test_homepage_has_run_button_and_inputs(self):
        status, body = self.request("GET", "/")
        text = body.decode("utf-8")
        self.assertEqual(status, 200)
        self.assertIn("Run", text)
        self.assertIn("requester_name", text)
        self.assertIn("max_neighbor", text)
        self.assertIn("google_scholar_url", text)
        self.assertIn("Requester debug", text)
        self.assertIn("AI-assisted keyword extraction", text)

    def ai_token(self):
        status, body = self.request("GET", "/")
        self.assertEqual(status, 200)
        marker = "const aiKeywordToken = '"
        text = body.decode("utf-8")
        start = text.index(marker) + len(marker)
        end = text.index("';", start)
        return text[start:end]

    def test_api_match_demo_data(self):
        status, body = self.request(
            "POST",
            "/api/match",
            {
                "requester_name": "Demo Researcher",
                "use_demo_data": True,
                "min_relevance": 0.5,
                "max_neighbor": 5,
            },
        )
        data = json.loads(body.decode("utf-8"))
        self.assertEqual(status, 200)
        self.assertGreater(data["visible_count"], 0)
        self.assertIn("requester_debug", data)
        self.assertGreaterEqual(len(data["requester_debug"]["publications"]), 2)
        self.assertTrue(data["requester_debug"]["topic_keywords"])
        self.assertEqual(data["requester_debug"]["keyword_source"], "heuristic")
        self.assertIn("Google Scholar links are accepted", " ".join(data["heuristic_notes"]))

    def test_api_match_demo_data_with_ai_keywords(self):
        with patch(
            "collaborator_agent.run_codex_keyword_extraction",
            return_value=(
                [{"term": "marine ecology", "count": 1}],
                [{"term": "survey", "count": 1}],
            ),
        ):
            status, body = self.request(
                "POST",
                "/api/match",
                {
                    "requester_name": "Demo Researcher",
                    "use_demo_data": True,
                    "ai_keywords": True,
                    "min_relevance": 0.0,
                    "max_neighbor": 5,
                },
                {"X-TIPA-AI-Token": self.ai_token()},
            )
        data = json.loads(body.decode("utf-8"))
        self.assertEqual(status, 200)
        self.assertEqual(data["requester_debug"]["keyword_source"], "ai")
        self.assertIn("marine ecology", {item["term"] for item in data["requester_debug"]["topic_keywords"]})

    def test_api_rejects_ai_keywords_without_local_token(self):
        status, body = self.request(
            "POST",
            "/api/match",
            {
                "requester_name": "Demo Researcher",
                "use_demo_data": True,
                "ai_keywords": True,
            },
        )
        data = json.loads(body.decode("utf-8"))
        self.assertEqual(status, 403)
        self.assertIn("local page token", data["error"])

    def test_api_rejects_ai_keywords_on_get(self):
        status, body = self.request("GET", "/api/match?requester_name=Demo+Researcher&ai_keywords=true")
        data = json.loads(body.decode("utf-8"))
        self.assertEqual(status, 403)
        self.assertIn("POST", data["error"])

    def test_api_does_not_emit_wildcard_cors(self):
        conn = http.client.HTTPConnection(self.host, self.port, timeout=5)
        conn.request("OPTIONS", "/api/match")
        response = conn.getresponse()
        response.read()
        headers = dict(response.getheaders())
        conn.close()
        self.assertEqual(response.status, 204)
        self.assertNotIn("Access-Control-Allow-Origin", headers)

    def test_api_rejects_malformed_json(self):
        conn = http.client.HTTPConnection(self.host, self.port, timeout=5)
        conn.request("POST", "/api/match", body=b"{bad", headers={"Content-Type": "application/json"})
        response = conn.getresponse()
        payload = json.loads(response.read().decode("utf-8"))
        conn.close()
        self.assertEqual(response.status, 400)
        self.assertIn("invalid JSON", payload["error"])

    def test_api_rejects_oversized_body_without_aborting_response(self):
        conn = http.client.HTTPConnection(self.host, self.port, timeout=5)
        oversized = b'{"requester_name":"' + (b"a" * 210_000) + b'"}'
        conn.request("POST", "/api/match", body=oversized, headers={"Content-Type": "application/json"})
        response = conn.getresponse()
        payload = json.loads(response.read().decode("utf-8"))
        conn.close()
        self.assertEqual(response.status, 400)
        self.assertIn("too large", payload["error"])


if __name__ == "__main__":
    unittest.main()
