"""Tests for redaction.py (credential-only egress scrubber).

Guarded: a sibling agent owns this module. If it isn't present yet in a
given checkout, these tests skip rather than fail the whole suite.
"""
from __future__ import annotations

import pytest

redaction = pytest.importorskip("redaction")


def test_scrub_redacts_password():
    text = 'password: "hunter2"'
    out, count = redaction.scrub(text)
    assert "hunter2" not in out
    assert count == 1


def test_scrub_redacts_bearer_token():
    text = "Authorization: Bearer abcdefghijklmnopqrstuvwxyz123456"
    out, count = redaction.scrub(text)
    assert "abcdefghijklmnopqrstuvwxyz123456" not in out
    assert count == 1


def test_scrub_leaves_ordinary_text_alone():
    text = "the engine speed is 12.3 units at 10.50"
    out, count = redaction.scrub(text)
    assert out == text
    assert count == 0


def test_scrub_obj_recurses_into_dict():
    # scrub_obj scrubs each string VALUE independently (it has no notion of
    # the dict key as a label) — a bare "hunter2" string has no
    # password=/token= marker in it, so it is left alone. Embedding the
    # label inside the string value itself is what triggers redaction.
    obj = {"note": 'password: "hunter2"', "speed": 12.3}
    out, count = redaction.scrub_obj(obj)
    assert "hunter2" not in out["note"]
    assert out["speed"] == 12.3
    assert count == 1
