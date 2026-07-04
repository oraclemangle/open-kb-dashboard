"""Tests for adapters/kb_client.py parsing (stubbed urllib, no real network).

Guarded: a sibling agent owns this module. If it isn't present, these tests
skip rather than fail the whole suite.
"""
from __future__ import annotations

import json
import io

import pytest

kb_client_mod = pytest.importorskip("adapters.kb_client")
KBClient = kb_client_mod.KBClient


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def read(self):
        return json.dumps(self._payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_health_parses_ok_response(monkeypatch):
    def fake_urlopen(req, timeout=None):
        return _FakeResponse({"ok": True, "documents": 5, "chunks": 42})

    monkeypatch.setattr(kb_client_mod.urllib.request, "urlopen", fake_urlopen)
    client = KBClient("http://127.0.0.1:8080")
    result = client.health()
    assert result == {"ok": True, "documents": 5, "chunks": 42}


def test_health_returns_none_on_failure(monkeypatch):
    def fake_urlopen(req, timeout=None):
        raise OSError("connection refused")

    monkeypatch.setattr(kb_client_mod.urllib.request, "urlopen", fake_urlopen)
    client = KBClient("http://127.0.0.1:8080")
    assert client.health() is None


def test_search_returns_hits(monkeypatch):
    def fake_urlopen(req, timeout=None):
        return _FakeResponse({"hits": [{"id": 1}, {"id": 2}]})

    monkeypatch.setattr(kb_client_mod.urllib.request, "urlopen", fake_urlopen)
    client = KBClient("http://127.0.0.1:8080")
    hits = client.search("some query")
    assert hits == [{"id": 1}, {"id": 2}]


def test_search_returns_empty_list_on_failure(monkeypatch):
    def fake_urlopen(req, timeout=None):
        raise OSError("boom")

    monkeypatch.setattr(kb_client_mod.urllib.request, "urlopen", fake_urlopen)
    client = KBClient("http://127.0.0.1:8080")
    assert client.search("q") == []


def test_ask_returns_answer_dict(monkeypatch):
    def fake_urlopen(req, timeout=None):
        return _FakeResponse({"answer": "42", "sources": []})

    monkeypatch.setattr(kb_client_mod.urllib.request, "urlopen", fake_urlopen)
    client = KBClient("http://127.0.0.1:8080")
    result = client.ask("what is the answer?")
    assert result == {"answer": "42", "sources": []}
