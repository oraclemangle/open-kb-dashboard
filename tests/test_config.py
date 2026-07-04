"""Tests for config.py — defaults, YAML merge, env override (incl. nested
auth__user)."""
from __future__ import annotations

import os

import config as config_mod


def test_load_config_defaults_when_no_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)  # no ./config.yaml here
    cfg = config_mod.load_config()
    assert cfg["server"]["port"] == 8090
    assert cfg["telemetry"]["provider"] == "demo"
    assert cfg["telemetry"]["sanitise_position"] is True
    assert cfg["redaction"]["enabled"] is True


def test_load_config_data_dir_is_expanded(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    cfg = config_mod.load_config()
    assert "~" not in cfg["paths"]["data_dir"]


def test_load_config_yaml_merge(tmp_path):
    yaml_path = tmp_path / "config.yaml"
    yaml_path.write_text(
        "server:\n  port: 9999\ntelemetry:\n  provider: none\n",
        encoding="utf-8",
    )
    cfg = config_mod.load_config(str(yaml_path))
    assert cfg["server"]["port"] == 9999
    assert cfg["telemetry"]["provider"] == "none"
    # Untouched defaults survive the merge.
    assert cfg["server"]["host"] == "127.0.0.1"
    assert cfg["kb"]["api_url"] == "http://127.0.0.1:8080"


def test_load_config_yaml_merge_preserves_nested_defaults(tmp_path):
    yaml_path = tmp_path / "config.yaml"
    yaml_path.write_text("server:\n  auth:\n    user: alice\n", encoding="utf-8")
    cfg = config_mod.load_config(str(yaml_path))
    assert cfg["server"]["auth"]["user"] == "alice"
    assert cfg["server"]["auth"]["password"] == ""  # default preserved


def test_env_override_simple_key(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("OPENKB_DASH_SERVER_PORT", "1234")
    cfg = config_mod.load_config()
    assert cfg["server"]["port"] == 1234
    assert isinstance(cfg["server"]["port"], int)


def test_env_override_nested_double_underscore(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("OPENKB_DASH_SERVER_AUTH__USER", "bob")
    monkeypatch.setenv("OPENKB_DASH_SERVER_AUTH__PASSWORD", "hunter2")
    cfg = config_mod.load_config()
    assert cfg["server"]["auth"]["user"] == "bob"
    assert cfg["server"]["auth"]["password"] == "hunter2"


def test_env_override_bool_coercion(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("OPENKB_DASH_TELEMETRY_SANITISE_POSITION", "false")
    cfg = config_mod.load_config()
    assert cfg["telemetry"]["sanitise_position"] is False


def test_env_override_unknown_section_ignored(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("OPENKB_DASH_NOPE_SOMETHING", "x")
    cfg = config_mod.load_config()
    assert "nope" not in cfg


def test_openkb_dash_config_env_points_to_file(tmp_path, monkeypatch):
    yaml_path = tmp_path / "custom.yaml"
    yaml_path.write_text("server:\n  port: 4242\n", encoding="utf-8")
    monkeypatch.setenv("OPENKB_DASH_CONFIG", str(yaml_path))
    monkeypatch.chdir(tmp_path)
    cfg = config_mod.load_config()
    assert cfg["server"]["port"] == 4242
