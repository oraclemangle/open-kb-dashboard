from __future__ import annotations

import json

from server import DashboardApp, SessionStore


def _cfg(tmp_path, provider="openai"):
    return {
        "paths": {"data_dir": str(tmp_path)},
        "kb": {"api_url": "http://kb.invalid", "token": "", "inbox_dir": ""},
        "server": {"auth": {}},
        "redaction": {"enabled": True},
        "telemetry": {"provider": "none", "sanitise_position": True},
        "engines": [{"id": "engine", "label": "Engine", "provider": provider}],
    }


def test_session_reload_preserves_legacy_content_and_current_text(tmp_path):
    sessions = tmp_path / "sessions"
    sessions.mkdir()
    (sessions / "abc.json").write_text(
        json.dumps({"history": [{"role": "user", "content": "legacy"}, {"role": "assistant", "text": "current"}]}),
        encoding="utf-8",
    )
    history = SessionStore(str(tmp_path)).get("abc")["history"]
    assert [turn["text"] for turn in history] == ["legacy", "current"]


def test_chat_redacts_before_any_egress_and_buffers_stream(tmp_path, monkeypatch):
    app = DashboardApp(_cfg(tmp_path))
    seen = {}

    class KB:
        def search_status(self, query, **kwargs):
            seen["search"] = query
            return {"hits": [{"document_id": 1, "source": "manual", "text": "safe"}], "state": "ok"}

    class Engine:
        def stream(self, system, messages):
            seen["prompt"] = messages[-1]["content"]
            yield "password=hunt"
            yield "er2 answer [1]"

    app.kb = KB()
    monkeypatch.setattr("server.get_engine", lambda cfg, engine_id: (Engine(), cfg["engines"][0]))
    events = []
    done = app.run_chat("abc", "password=hunter2 question", "engine", events.append)

    assert "hunter2" not in seen["search"]
    assert "hunter2" not in seen["prompt"]
    assert all("hunter2" not in json.dumps(event) for event in events)
    assert len([event for event in events if event.get("type") == "delta"]) == 1
    assert done["state"] == "grounded"


def test_kb_failure_states_are_distinct_and_never_grounded(tmp_path, monkeypatch):
    app = DashboardApp(_cfg(tmp_path))

    class KB:
        def search_status(self, query, **kwargs):
            return {"hits": [], "state": "auth_mismatch", "error": "kb authentication mismatch"}

    class Engine:
        def stream(self, system, messages):
            yield "An ungrounded model reply"

    app.kb = KB()
    monkeypatch.setattr("server.get_engine", lambda cfg, engine_id: (Engine(), cfg["engines"][0]))
    done = app.run_chat("abc", "question", "engine", lambda event: None)
    assert done["state"] == "auth_mismatch"
    assert done["sources"] == []


def test_kb_direct_receives_only_the_scrubbed_original_question(tmp_path, monkeypatch):
    app = DashboardApp(_cfg(tmp_path, provider="kb"))
    seen = {}

    class Engine:
        last_result = {"answer": "answer [1]", "sources": [{"document_id": 1}], "state": "grounded"}

        def stream(self, system, messages):
            seen["messages"] = messages
            yield "answer [1]"

    monkeypatch.setattr("server.get_engine", lambda cfg, engine_id: (Engine(), cfg["engines"][0]))
    app.run_chat("abc", "token=abcdefgh question", "engine", lambda event: None)
    assert seen["messages"] == [{"role": "user", "content": "token=[REDACTED:SECRET] question"}]


def test_feedback_records_stable_turn_and_provenance(tmp_path):
    app = DashboardApp(_cfg(tmp_path))
    assert app.append_feedback({
        "session_id": "s", "turn_id": "turn-123", "verdict": "down", "note": "bad",
        "engine": "local", "state": "partial", "source_ids": [4, 8],
    })
    record = json.loads((tmp_path / "feedback.jsonl").read_text(encoding="utf-8"))
    assert record["turn_id"] == "turn-123"
    assert record["engine"] == "local"
    assert record["state"] == "partial"
    assert record["source_ids"] == [4, 8]


def test_stats_data_has_health_and_query_counts(tmp_path):
    app = DashboardApp(_cfg(tmp_path))
    app.kb = type("KB", (), {
        "health": lambda self: {"ok": True, "documents": 3, "chunks": 9},
        "stats": lambda self: {"domains": []},
    })()
    stats = app.stats_data()
    assert stats["kb"]["documents"] == 3
    assert stats["queries_today"] == 0
