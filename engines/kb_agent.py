"""kb_agent.py -- zero-dependency chat engine: no LLM of its own.

This engine exists for a "does it work with nothing installed" mode: point
config `engines:` at `{"id": "kb", "provider": "kb"}` and the dashboard is
immediately usable with zero extra services -- no Ollama, no API key, no
GPU. It calls open-kb's own /ask endpoint (which does its own retrieval +
answer synthesis server-side) and yields the resulting answer as a single
delta. It ignores the `system`/`messages` prompt this module's caller
built (the persona, numbered context blocks, telemetry block, history
window) because open-kb's /ask already does its own retrieval and framing;
duplicating that context here would just be redundant tokens sent nowhere.

Useful as a fallback engine, a demo mode, or for deployments that would
rather keep 100% of generation inside open-kb itself.
"""
from __future__ import annotations

from typing import Iterator


class KBAgentEngine:
    def __init__(self, kb_client):
        self.kb = kb_client
        self.last_result = None

    def stream(self, system: str, messages: list[dict]) -> Iterator[str]:
        question = ""
        for m in reversed(messages or []):
            if m.get("role") == "user":
                question = m.get("content") or ""
                break
        if not question:
            yield "[engine error: no question to ask the knowledge base]"
            return
        result = self.kb.ask(question)
        self.last_result = result
        if not isinstance(result, dict) or result.get("error"):
            err = result.get("error") if isinstance(result, dict) else "unexpected response"
            yield "[engine error: knowledge base could not answer (%s)]" % err
            return
        answer = (result.get("answer") or "").strip()
        yield answer or "The knowledge base returned no answer for this question."
