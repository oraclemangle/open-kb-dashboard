"""telemetry_http_example.py — TEACHING ARTEFACT, not wired in by default.

Shows how to wrap ANY JSON-over-HTTP telemetry service as a TelemetryProvider
using only the standard library (urllib). This is not referenced by
config.example.yaml or DEFAULTS — to use it, set

    telemetry:
      provider: adapters.telemetry_http_example

in your own config.yaml, and set whatever env var you chose (see
`base_url_env` below) to point at your service.

Read this alongside adapters/telemetry_base.py (the protocol) and
docs/telemetry-adapter-guide.md (the full integration guide) — this file is
deliberately kept small and heavily commented rather than "production
hardened", so the pattern stays visible.
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request

# --- configuration ----------------------------------------------------------
# Pick your OWN env var name for the base URL of your telemetry service —
# there is nothing special about this string, it's just an example. Doing it
# this way (rather than hardcoding a URL) keeps real endpoints out of source
# control entirely.
DEFAULT_BASE_URL_ENV = "OPENKB_DASH_TELEMETRY_HTTP_BASE_URL"

# Keep network calls short — this is called from request handlers and must
# never make the dashboard feel slow. A provider should fail fast and let
# the caller treat a None/timeout as "no live data available".
TIMEOUT_SECONDS = 3.0

# How long a snapshot() result may be reused before we re-fetch. Splash-pulse
# polling can be frequent; there is no need to hit the upstream service on
# every single request.
SNAPSHOT_CACHE_SECONDS = 15.0


class Provider:
    """Example JSON-over-HTTP TelemetryProvider.

    Expects the upstream service to expose:
      GET {base_url}/live   -> JSON object with (some subset of) the fields
                                below.

    Generic field mapping (adjust to whatever your own service returns):
        state       <- upstream "state" | "mode" | "status"
        speed       <- upstream "speed" | "sog"
        depth       <- upstream "depth"
        wind_speed  <- upstream "wind_speed" | "wind"
        extra       <- anything else you want surfaced, as a flat dict of
                        {label: value}

    This class intentionally does NOT know about NMEA, Modbus, SignalK, or
    any specific vendor protocol — it only ever speaks JSON-over-HTTP to
    whatever local service you point it at. If your real data source is one
    of those lower-level protocols, put a small bridge process in front of
    it that decodes the bus and serves JSON; see
    docs/telemetry-adapter-guide.md for that pattern.
    """

    def __init__(self, base_url: str | None = None, base_url_env: str = DEFAULT_BASE_URL_ENV) -> None:
        # Read the base URL from an env var whose NAME you choose (passed in
        # as base_url_env, or hardcode your own default here) rather than
        # committing a real address to source control.
        self.base_url = (base_url or os.environ.get(base_url_env, "") or "").rstrip("/")
        self._cache: dict | None = None
        self._cache_ts: float = 0.0

    # -- internal helpers -----------------------------------------------
    def _get_json(self, path: str) -> dict | None:
        if not self.base_url:
            return None
        url = self.base_url + path
        try:
            req = urllib.request.Request(url, headers={"Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as resp:
                return json.loads(resp.read())
        except (urllib.error.URLError, TimeoutError, ValueError, OSError):
            # Any failure (network, timeout, bad JSON) degrades to "no data"
            # rather than raising — the dashboard should never break a chat
            # turn or the splash screen because a telemetry service hiccuped.
            return None

    def _map_fields(self, raw: dict) -> dict:
        """Translate an arbitrary upstream JSON shape into the small,
        generic shape the dashboard expects. Adjust the key names on the
        right-hand side of each .get() call to match YOUR service."""
        state = raw.get("state") or raw.get("mode") or raw.get("status")
        speed = raw.get("speed", raw.get("sog"))
        depth = raw.get("depth")
        wind_speed = raw.get("wind_speed", raw.get("wind"))
        known = {"state", "mode", "status", "speed", "sog", "depth", "wind_speed", "wind"}
        extra = {k: v for k, v in raw.items() if k not in known}
        return {
            "state": state,
            "speed": speed,
            "depth": depth,
            "wind_speed": wind_speed,
            "extra": extra,
        }

    # -- TelemetryProvider protocol ---------------------------------------
    def snapshot(self) -> dict | None:
        now = time.time()
        if self._cache is not None and (now - self._cache_ts) < SNAPSHOT_CACHE_SECONDS:
            return self._cache

        raw = self._get_json("/live")
        if raw is None:
            return None  # unavailable/stale -> UI hides the pulse

        mapped = self._map_fields(raw)
        mapped["fresh"] = True
        self._cache = mapped
        self._cache_ts = now
        return mapped

    def fetch(self, question: str) -> tuple[str, dict] | None:
        raw = self._get_json("/live")
        if raw is None:
            return None

        mapped = self._map_fields(raw)
        lines = ["LIVE ASSET DATA (http example provider):"]
        for key in ("state", "speed", "depth", "wind_speed"):
            if mapped.get(key) is not None:
                lines.append("%s: %s" % (key, mapped[key]))
        for label, value in (mapped.get("extra") or {}).items():
            lines.append("%s: %s" % (label, value))
        return "\n".join(lines), {"provider": "http_example", "base_url": self.base_url}
