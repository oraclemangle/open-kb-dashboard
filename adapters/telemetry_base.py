"""TelemetryProvider — the contract for live asset data on the dashboard.

The dashboard itself knows nothing about NMEA, SignalK, Modbus, BMS or SCADA.
It only ever talks to a TelemetryProvider. Implement this interface against
your own data source and point config `telemetry.provider` at your module
(any importable path exposing `Provider`). See docs/telemetry-adapter-guide.md.

Two methods:

  snapshot() -> dict | None
      Small dict for the splash-screen "live pulse". Return None (or set
      fresh=False) when data is stale/unavailable — the UI then hides the
      pulse rather than showing stale numbers. Expected keys (all optional
      except fresh):
        {"fresh": bool, "state": str|None, "speed": float|None,
         "depth": float|None, "wind_speed": float|None,
         "extra": {label: value, ...}}

  fetch(question: str) -> tuple[str, dict] | None
      Called when a chat question looks like it needs live data (the server
      applies `INTENT` first). Return a plain-text block to inject into the
      LLM prompt plus a meta dict, or None to skip. Keep it small — a few
      hundred tokens at most.

Safety default: if config `telemetry.sanitise_position` is true the server
passes every fetch() result through `strip_positions()` below so absolute
coordinates never reach an LLM or the browser. Override consciously, not by
accident.
"""
from __future__ import annotations

import re
from typing import Protocol

# Questions matching this regex trigger fetch(). Providers may override
# with their own INTENT attribute.
INTENT = re.compile(
    r"\b(live|current|right now|now|today)\b|"
    r"\b(speed|depth|wind|weather|temperature|pressure|tank|fuel|load|"
    r"power|generator|engine|alarm|status)\b",
    re.I,
)

_COORD = re.compile(
    r"[-+]?\d{1,3}\.\d{3,}\s*,\s*[-+]?\d{1,3}\.\d{3,}"       # decimal pairs
    r"|\b\d{1,3}[°]\s*\d{1,2}(\.\d+)?['′]?\s*[NSEW]\b",       # DMS tokens
)
_POS_KEYS = re.compile(r'"(lat|latitude|lon|lng|longitude|position|gps|fix|coords?)"\s*:\s*[^,}]+', re.I)


def strip_positions(text: str) -> str:
    """Remove absolute-position values from a telemetry text block."""
    text = _POS_KEYS.sub('"position": "[redacted]"', text)
    return _COORD.sub("[position redacted]", text)


class TelemetryProvider(Protocol):
    def snapshot(self) -> dict | None: ...
    def fetch(self, question: str) -> tuple[str, dict] | None: ...


def load_provider(cfg: dict):
    """Resolve config telemetry.provider to an instance (or None)."""
    name = str(cfg.get("telemetry", {}).get("provider", "none")).strip()
    if not name or name == "none":
        return None
    if name == "demo":
        from adapters.telemetry_demo import Provider
        return Provider()
    import importlib
    mod = importlib.import_module(name)
    return mod.Provider()
