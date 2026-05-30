# Ultragoal Brief: Requester AI-Assisted Keyword Extraction

Source spec: `.omx/specs/deep-interview-requester-ai-keywords.md`

Objective: Deliver requester-only AI-assisted keyword extraction through local Codex CLI, exposed by an explicit Requester debug button / `ai_keywords` flag. Successful AI extraction reranks results with AI requester keywords. Normal matching remains heuristic by default, candidate extraction remains heuristic, and Codex failures fall back to heuristics.

Verification target: `python -m unittest` when a Python interpreter is available; static/code review and adversarial QA otherwise document the interpreter blocker.
