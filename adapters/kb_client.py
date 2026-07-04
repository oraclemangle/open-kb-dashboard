"""kb_client.py -- thin client for the open-kb REST API.

open-kb (see the open-kb project's src/openkb/api.py) exposes:
  GET  /health          -> {"ok": bool, "documents": int, "chunks": int} (or {"ok": false, "error": ...})
  GET  /stats           -> {"domains": [{"domain","documents","chunks"}...], "equipment", "db_size_bytes"}
  GET  /domains         -> {"domains": [{"name","documents"}...]}
  GET  /source?document_id=N (or rel_path=...) -> {"document": {...}, "text": "..."}
  POST /search {"query","domains"?,"k"?,"mode"?} -> {"hits": [...]}
  POST /ask    {"query","domains"?,"k"?}         -> {"answer","sources"}

Bearer auth is only required on the POST routes when open-kb's own `api.token` is set;
GET routes stay open. This client always sends the token when configured -- open-kb
ignores it on unauthenticated GET routes.

stdlib urllib only. Every method is best-effort: on any failure it returns a small
{"error": "..."} dict (or an empty list for list-shaped calls) rather than raising, so
the dashboard can render fine even when the knowledge base is unreachable.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any


class KBClient:
    """Read-mostly client for one open-kb instance."""

    def __init__(self, api_url: str, token: str = "", timeout: float = 20.0):
        self.api_url = (api_url or "").rstrip("/")
        self.token = token or ""
        self.timeout = timeout

    # -- transport --------------------------------------------------------
    def _headers(self) -> dict:
        h = {"Content-Type": "application/json"}
        if self.token:
            h["Authorization"] = "Bearer " + self.token
        return h

    def _get(self, path: str) -> Any:
        req = urllib.request.Request(self.api_url + path, headers=self._headers(), method="GET")
        with urllib.request.urlopen(req, timeout=self.timeout) as r:
            return json.load(r)

    def _post(self, path: str, payload: dict) -> Any:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(self.api_url + path, data=data, headers=self._headers(), method="POST")
        with urllib.request.urlopen(req, timeout=self.timeout) as r:
            return json.load(r)

    @staticmethod
    def _err(e: Exception) -> dict:
        if isinstance(e, urllib.error.HTTPError):
            try:
                detail = json.loads(e.read())
                if isinstance(detail, dict) and detail.get("error"):
                    return {"error": str(detail["error"])}
            except Exception:
                pass
            return {"error": "kb returned HTTP %d" % e.code}
        return {"error": "kb unreachable (%s)" % type(e).__name__}

    # -- endpoints ----------------------------------------------------------
    def health(self) -> dict | None:
        """GET /health -> dict, or None if the kb could not be reached at all."""
        try:
            return self._get("/health")
        except Exception:
            return None

    def stats(self) -> dict:
        """GET /stats -> {"domains","equipment","db_size_bytes"}; {"error":...} on failure."""
        try:
            return self._get("/stats")
        except Exception as e:
            return self._err(e)

    def domains(self) -> list:
        """GET /domains -> [{"name","documents"}...]; falls back to deriving the
        list from /stats for older open-kb servers without the route."""
        try:
            data = self._get("/domains")
            doms = data.get("domains") if isinstance(data, dict) else None
            if isinstance(doms, list):
                return doms
        except Exception:
            pass
        data = self.stats()
        doms = data.get("domains") if isinstance(data, dict) else None
        return doms if isinstance(doms, list) else []

    def search(self, query: str, k: int = 8, domains: list[str] | None = None) -> list:
        """POST /search -> list of hit dicts. Returns [] on failure."""
        try:
            payload: dict = {"query": query, "k": k}
            if domains:
                payload["domains"] = domains
            data = self._post("/search", payload)
            hits = data.get("hits") if isinstance(data, dict) else data
            return hits if isinstance(hits, list) else []
        except Exception:
            return []

    def ask(self, query: str, k: int = 8, domains: list[str] | None = None) -> dict:
        """POST /ask -> {"answer","sources"}; {"error":...} on failure."""
        try:
            payload: dict = {"query": query, "k": k}
            if domains:
                payload["domains"] = domains
            return self._post("/ask", payload)
        except Exception as e:
            return self._err(e)

    def get_source(self, document_id) -> dict:
        """GET /source?document_id=N -> {"document": {...}, "text": "..."}.
        Requires open-kb's api.token (when set) since it returns raw indexed
        text. Returns {"error": ...} when unavailable."""
        try:
            data = self._get("/source?document_id=%s" % urllib.parse.quote(str(document_id)))
            return data if isinstance(data, dict) else {"error": "unexpected response"}
        except Exception as e:
            return self._err(e)
