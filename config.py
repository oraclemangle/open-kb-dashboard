"""Configuration loader for open-kb-dashboard.

Precedence (later wins): DEFAULTS -> config.yaml -> OPENKB_DASH_* env vars.
Search order for the YAML: $OPENKB_DASH_CONFIG, ./config.yaml. Same shape and
override grammar as the open-kb project: OPENKB_DASH_<SECTION>_<KEY>, double
underscore for nesting (e.g. OPENKB_DASH_SERVER_AUTH__USER).
"""
from __future__ import annotations

import copy
import os
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None

DEFAULTS: dict[str, Any] = {
    "server": {
        "host": "127.0.0.1",
        "port": 8090,
        "auth": {"user": "", "password": ""},
    },
    "kb": {"api_url": "http://127.0.0.1:8080", "token": "", "inbox_dir": ""},
    "engines": [
        {"id": "local", "label": "Local model", "provider": "openai",
         "base_url": "http://127.0.0.1:11434/v1", "model": "your-instruct-model",
         "api_key_env": ""},
        {"id": "kb", "label": "KB direct", "provider": "kb"},
    ],
    "telemetry": {"provider": "demo", "sanitise_position": True},
    "ui": {
        "brand": "open-kb",
        "subtitle": "knowledge base assistant",
        # DG1/MSB-1 in the default tips/chips refer to open-kb's synthetic demo
        # corpus, so a fresh install demos end-to-end; override with your own.
        "tips": [
            'Ask about any equipment by tag, e.g. "DG1 service intervals".',
            "Cite-check answers with the source chips under each reply.",
            "Drag documents onto the chat to teach the knowledge base.",
        ],
        "qa_chips": [
            "What equipment is covered by this knowledge base?",
            "Show the maintenance schedule for DG1.",
            "Which cables feed MSB-1?",
        ],
        "domain_meta": {},
    },
    "paths": {"data_dir": "./data"},
    "redaction": {"enabled": True},
}


def _deep_merge(base: dict, extra: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in (extra or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = copy.deepcopy(v)
    return out


def _coerce(current: Any, raw: str) -> Any:
    if isinstance(current, bool):
        return raw.strip().lower() not in ("0", "false", "no", "off", "")
    if isinstance(current, int) and not isinstance(current, bool):
        try:
            return int(raw)
        except ValueError:
            return current
    if isinstance(current, float):
        try:
            return float(raw)
        except ValueError:
            return current
    return raw


def _apply_env(cfg: dict) -> dict:
    prefix = "OPENKB_DASH_"
    for name, raw in os.environ.items():
        if not name.startswith(prefix) or name == "OPENKB_DASH_CONFIG":
            continue
        path = name[len(prefix):].lower()
        section, _, rest = path.partition("_")
        if section not in cfg or not rest or not isinstance(cfg[section], dict):
            continue
        node = cfg[section]
        keys = rest.split("__")
        for key in keys[:-1]:
            node = node.setdefault(key, {})
            if not isinstance(node, dict):
                break
        else:
            leaf = keys[-1]
            node[leaf] = _coerce(node.get(leaf), raw)
    return cfg


def load_config(path: str | None = None) -> dict:
    cfg = copy.deepcopy(DEFAULTS)
    candidates = (path,) if path else (os.environ.get("OPENKB_DASH_CONFIG", ""), "./config.yaml")
    for cand in candidates:
        if cand and os.path.isfile(cand):
            if yaml is None:
                raise RuntimeError("PyYAML is required to read %s" % cand)
            with open(cand, "r", encoding="utf-8") as fh:
                cfg = _deep_merge(cfg, yaml.safe_load(fh) or {})
            break
    cfg = _apply_env(cfg)
    cfg["paths"]["data_dir"] = os.path.expanduser(str(cfg["paths"]["data_dir"]))
    return cfg
