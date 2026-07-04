"""openai_agent.py -- OpenAI-compatible streaming chat engine.

Works against any /v1/chat/completions endpoint that supports `stream: true`
Server-Sent Events, e.g. Ollama, LM Studio, llama.cpp's server, vLLM, Groq,
or the real OpenAI API. stdlib urllib only -- no `openai` package dependency.

The API key (if the endpoint needs one) is read from the environment variable
named in config `engines[].api_key_env`, never hardcoded and never logged.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Iterator


class OpenAIEngine:
    def __init__(self, base_url: str, model: str, api_key_env: str = "", timeout: float = 120.0):
        self.base_url = (base_url or "").rstrip("/")
        self.model = model
        self.api_key = os.environ.get(api_key_env, "") if api_key_env else ""
        self.timeout = timeout

    def stream(self, system: str, messages: list[dict]) -> Iterator[str]:
        url = self.base_url + "/chat/completions"
        payload = {
            "model": self.model,
            "stream": True,
            "messages": [{"role": "system", "content": system}] + list(messages),
        }
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = "Bearer " + self.api_key
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers=headers, method="POST")
        try:
            resp = urllib.request.urlopen(req, timeout=self.timeout)
        except urllib.error.HTTPError as e:
            code = e.code
            detail = ""
            try:
                detail = e.read().decode("utf-8", "replace")[:200]
            except Exception:
                pass
            yield "[engine error: %s returned HTTP %d%s]" % (
                self.model or "model", code, (" -- " + detail) if detail else "")
            return
        except Exception as e:
            yield "[engine error: could not reach %s (%s)]" % (self.base_url or "engine", type(e).__name__)
            return

        try:
            with resp:
                for raw_line in resp:
                    line = raw_line.decode("utf-8", "replace").strip()
                    if not line or not line.startswith("data:"):
                        continue
                    chunk = line[len("data:"):].strip()
                    if chunk == "[DONE]":
                        break
                    try:
                        obj = json.loads(chunk)
                    except json.JSONDecodeError:
                        continue
                    choices = obj.get("choices") or []
                    if not choices:
                        continue
                    delta = (choices[0].get("delta") or {}).get("content")
                    if delta:
                        yield delta
        except Exception as e:
            yield "[engine error: stream interrupted (%s)]" % type(e).__name__
