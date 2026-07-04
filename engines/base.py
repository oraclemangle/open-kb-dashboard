"""base.py -- the engine interface every open-kb-dashboard chat engine implements.

An engine turns (system prompt, message list) into a stream of text deltas. It knows
nothing about HTTP, sessions, or the knowledge base beyond what it's handed -- the
server assembles the prompt (persona + numbered context blocks + telemetry block +
history window) and simply asks the engine to stream a reply to it.

Interface
---------
  stream(system: str, messages: list[dict]) -> Iterator[str]
      `messages` is a list of {"role": "user"|"assistant", "content": str} dicts,
      oldest first, NOT including the system prompt (passed separately as `system`).
      Yields plain-text deltas as they become available. An engine that has no
      true token-level streaming (e.g. kb_agent) may yield its entire answer as a
      single delta -- that's a valid, if degenerate, implementation.

      Implementations should never raise for "the backend is down" -- they should
      yield a short human-readable error message as their one delta instead, so a
      dead LLM backend degrades to a visible chat message rather than a 500.
"""
from __future__ import annotations

from typing import Iterator, Protocol


class Engine(Protocol):
    def stream(self, system: str, messages: list[dict]) -> Iterator[str]: ...
