"""Tests for adapters/telemetry_demo.py — snapshot shape + fetch intent text."""
from __future__ import annotations

from adapters.telemetry_demo import Provider


def test_snapshot_shape():
    p = Provider()
    snap = p.snapshot()
    assert snap is not None
    assert snap["fresh"] is True
    assert snap["state"] in ("Operating", "Standby")
    assert isinstance(snap["speed"], float)
    assert isinstance(snap["depth"], float)
    assert isinstance(snap["wind_speed"], float)
    assert "load_pct" in snap["extra"]
    assert isinstance(snap["extra"]["load_pct"], float)


def test_snapshot_values_stay_in_sane_ranges():
    p = Provider()
    for _ in range(20):
        snap = p.snapshot()
        assert 0.0 <= snap["speed"] <= 20.0
        assert 5.0 <= snap["depth"] <= 200.0
        assert 0.0 <= snap["wind_speed"] <= 35.0
        assert 0.0 <= snap["extra"]["load_pct"] <= 100.0


def test_fetch_returns_text_and_meta():
    p = Provider()
    result = p.fetch("what is the current speed?")
    assert result is not None
    text, meta = result
    assert "LIVE ASSET DATA (demo provider" in text
    assert "synthetic" in text.lower()
    assert meta == {"provider": "demo"}


def test_fetch_text_contains_expected_fields():
    p = Provider()
    text, _ = p.fetch("status check")
    for field in ("state:", "speed:", "depth:", "wind_speed:", "load_pct:"):
        assert field in text
