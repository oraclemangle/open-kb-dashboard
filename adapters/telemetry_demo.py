"""telemetry_demo.py — the built-in "demo" TelemetryProvider.

This exists so the dashboard works with ZERO infrastructure: a fresh clone,
no sensors, no bus decoder, no BMS — just `telemetry.provider: demo` in
config.yaml (the default) and the splash pulse + live-data chat answers work
out of the box with plausible, clearly-labelled synthetic numbers.

Replace this with your own provider (see docs/telemetry-adapter-guide.md and
adapters/telemetry_base.py) once you have a real data source to wire up.
Nothing here reads real sensors or calls any network service — it is a
random walk seeded from wall-clock time so the values drift believably
between calls instead of jumping around or staying static.
"""
from __future__ import annotations

import random
import time

_STATES = ("Operating", "Standby")


class Provider:
    """Deterministic-ish random-walk fake telemetry.

    Each instance keeps a small amount of state so successive snapshot()/
    fetch() calls drift smoothly rather than jumping to unrelated random
    values. The walk is seeded from time.time() so different processes (or
    the same process at different times) don't all show identical numbers,
    while still being cheap and dependency-free (stdlib `random` only).
    """

    def __init__(self) -> None:
        seed_source = time.time()
        self._rng = random.Random(seed_source)
        self._state = self._rng.choice(_STATES)
        self._speed = round(self._rng.uniform(4.0, 14.0), 1)
        self._depth = round(self._rng.uniform(20.0, 120.0), 1)
        self._wind_speed = round(self._rng.uniform(2.0, 18.0), 1)
        self._load_pct = round(self._rng.uniform(30.0, 70.0), 1)
        self._last_step = 0.0

    def _walk(self, value: float, lo: float, hi: float, step: float) -> float:
        value += self._rng.uniform(-step, step)
        return round(min(hi, max(lo, value)), 1)

    def _advance(self) -> None:
        """Step every value a little. Cheap enough to call on every access;
        avoids needing a background thread just for a demo provider."""
        now = time.time()
        if now - self._last_step < 0.05:
            return
        self._last_step = now
        self._speed = self._walk(self._speed, 0.0, 20.0, 0.6)
        self._depth = self._walk(self._depth, 5.0, 200.0, 3.0)
        self._wind_speed = self._walk(self._wind_speed, 0.0, 35.0, 1.2)
        self._load_pct = self._walk(self._load_pct, 0.0, 100.0, 4.0)
        # Occasionally flip operating state, like a real asset cycling modes.
        if self._rng.random() < 0.05:
            self._state = self._rng.choice(_STATES)

    def snapshot(self) -> dict | None:
        """Small dict for the splash-screen live pulse. Always fresh=True —
        this is a synthetic feed, so it is never "stale" in the way a real
        sensor bus can be; a real provider should set fresh=False instead
        of fabricating numbers when its upstream has gone quiet."""
        self._advance()
        return {
            "fresh": True,
            "state": self._state,
            "speed": self._speed,
            "depth": self._depth,
            "wind_speed": self._wind_speed,
            "extra": {"load_pct": self._load_pct},
        }

    def fetch(self, question: str) -> tuple[str, dict] | None:
        """Return a small plausible text block for prompt injection plus a
        meta dict. Real providers should return None when they have nothing
        useful for this question; the demo provider always has something to
        say since it exists purely to demonstrate the shape of the contract.
        """
        self._advance()
        block = (
            "LIVE ASSET DATA (demo provider — synthetic):\n"
            "state: %s\n"
            "speed: %.1f\n"
            "depth: %.1f\n"
            "wind_speed: %.1f\n"
            "load_pct: %.1f\n"
            "NOTE: this is synthetic demo data, not a real reading. Configure "
            "telemetry.provider in config.yaml to point at a real adapter."
            % (self._state, self._speed, self._depth, self._wind_speed, self._load_pct)
        )
        return block, {"provider": "demo"}
