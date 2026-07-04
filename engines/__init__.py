"""engines package -- resolves a configured engine id to a runnable engine instance.

Two providers ship built in (see config.example.yaml `engines:`):
  openai -- any OpenAI-compatible /v1/chat/completions endpoint (Ollama, LM Studio,
            llama.cpp, Groq, ...). See engines/openai_agent.py.
  kb     -- no LLM of its own; answers entirely via open-kb's own /ask endpoint.
            See engines/kb_agent.py.
"""
from __future__ import annotations

from typing import Any


def get_engine(cfg: dict, engine_id: str):
    """Resolve `engine_id` (or the first configured engine if empty/unknown) to an
    engine instance plus its config dict. Returns (engine_instance, engine_cfg) or
    (None, None) if no engines are configured at all."""
    engines: list[dict[str, Any]] = cfg.get("engines") or []
    if not engines:
        return None, None
    econf = next((e for e in engines if e.get("id") == engine_id), None) or engines[0]
    provider = econf.get("provider", "openai")
    if provider == "kb":
        from .kb_agent import KBAgentEngine
        from adapters.kb_client import KBClient

        kb_cfg = cfg.get("kb", {})
        kb = KBClient(kb_cfg.get("api_url", ""), token=kb_cfg.get("token", ""))
        return KBAgentEngine(kb), econf
    # default / "openai"
    from .openai_agent import OpenAIEngine

    return OpenAIEngine(
        base_url=econf.get("base_url", ""),
        model=econf.get("model", ""),
        api_key_env=econf.get("api_key_env", ""),
    ), econf
