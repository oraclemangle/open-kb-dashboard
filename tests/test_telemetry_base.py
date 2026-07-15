"""Tests for adapters/telemetry_base.py — strip_positions() and
load_provider()."""
from __future__ import annotations

import json

import pytest

from adapters.telemetry_base import load_provider, strip_positions, strip_positions_obj
from adapters.telemetry_demo import Provider as DemoProvider


def test_strip_positions_decimal_pair():
    text = "current fix: 10.5000, -140.2500 heading 090"
    out = strip_positions(text)
    assert "10.5000" not in out
    assert "[position redacted]" in out


def test_strip_positions_dms_token():
    text = "position 10°30.0'N holding station"
    out = strip_positions(text)
    assert "10°30.0" not in out
    assert "[position redacted]" in out


def test_strip_positions_json_keys():
    text = '{"lat": 10.50, "lon": -140.25, "speed": 12.3}'
    out = strip_positions(text)
    assert "10.50" not in out
    assert '"position": "[redacted]"' in out
    # Non-position labels survive untouched.
    assert '"speed": 12.3' in out


def test_strip_positions_leaves_plain_numbers_alone():
    text = "speed 12.3 units, load 45 pct, tank level 88.4"
    out = strip_positions(text)
    assert out == text


def test_strip_positions_obj_handles_nested_structured_payloads():
    payload = {"state": "underway", "extra": {"gps": {"lat": 10.5, "lon": -140.25}, "rpm": 1200}}
    out = strip_positions_obj(payload)
    assert "10.5" not in json.dumps(out)
    assert out["extra"]["rpm"] == 1200


def test_load_provider_none():
    assert load_provider({"telemetry": {"provider": "none"}}) is None
    assert load_provider({"telemetry": {"provider": ""}}) is None
    assert load_provider({}) is None


def test_load_provider_demo():
    provider = load_provider({"telemetry": {"provider": "demo"}})
    assert isinstance(provider, DemoProvider)


def test_load_provider_unknown_module_raises():
    with pytest.raises(ImportError):
        load_provider({"telemetry": {"provider": "this.module.does.not.exist"}})
