# Telemetry adapter guide

How to give the dashboard live data — the splash-screen pulse and
live-data-aware chat answers — without the dashboard ever needing to know
what kind of asset or sensor bus you have.

## The contract

The dashboard only ever talks to a `TelemetryProvider`, defined in
`adapters/telemetry_base.py`:

```python
class TelemetryProvider(Protocol):
    def snapshot(self) -> dict | None: ...
    def fetch(self, question: str) -> tuple[str, dict] | None: ...
```

- **`snapshot()`** feeds the splash-screen "live pulse" widget. Return a
  small dict:

  ```python
  {"fresh": bool, "state": str | None, "speed": float | None,
   "depth": float | None, "wind_speed": float | None,
   "extra": {"label": value, ...}}
  ```

  Return `None`, or set `fresh: False`, when your data is stale or the
  upstream source is unreachable. The UI hides the pulse rather than show a
  stale number as if it were current — don't fight this by inventing a
  value just to keep the widget populated.

- **`fetch(question)`** is called for chat questions that look like they
  need live data. Return a `(text_block, meta)` tuple — a short plain-text
  block (a few hundred tokens at most) to inject into the LLM prompt, plus a
  small metadata dict for logging/debugging — or `None` to skip.

Point config at your provider with a plain dotted module path:

```yaml
telemetry:
  provider: adapters.my_provider   # any importable module exposing `Provider`
  sanitise_position: true
```

`load_provider()` in `telemetry_base.py` resolves `"none"` to no provider,
`"demo"` to the bundled synthetic one, and anything else to
`importlib.import_module(name).Provider()`.

## Where the dashboard calls this

```
splash screen  ──poll──>  snapshot()  ──>  live pulse widget

chat message  ──>  INTENT.search(question)?
                       │
                       ├─ no  ──>  answered normally, no telemetry involved
                       │
                       └─ yes ──>  fetch(question)
                                      │
                                      ├─ None        -> no live block injected
                                      └─ (text, meta) -> sanitise_position (if
                                                          enabled) -> text
                                                          injected into the
                                                          prompt before the
                                                          LLM call
```

`INTENT` (in `telemetry_base.py`) is a regex covering words like *live,
current, speed, depth, wind, tank, load, alarm, status*, etc. Providers may
expose their own `INTENT` attribute if the built-in regex over- or
under-triggers for their domain — the server checks the provider's `INTENT`
first if present, otherwise falls back to the module-level default.

## `sanitise_position` — keep it on

```yaml
telemetry:
  sanitise_position: true
```

When enabled (the default), every `fetch()` result is passed through
`strip_positions()` before it reaches an LLM or the browser. This strips:

- decimal-degree coordinate pairs (`"10.50, -140.25"`),
- DMS-style tokens (`10°30.0'N`),
- any JSON key named `lat`, `latitude`, `lon`, `lng`, `longitude`,
  `position`, `gps`, `fix`, or `coord`/`coords`.

Absolute position is the one field that turns "engineering telemetry" into
"where is this specific asset right now" — a materially different
sensitivity level, especially once that text is on its way to a
third-party LLM. Keep this on unless you have a specific, deliberate reason
to send raw position data off-box, and prefer implementing your own
provider-level redaction over disabling the safety net entirely if you can
avoid it.

## Worked options

### (a) Demo — zero infrastructure

```yaml
telemetry:
  provider: demo
```

`adapters/telemetry_demo.py` generates a believable random walk (state,
speed, depth, wind, load %) so the UI is fully functional the moment you
clone the repo. Nothing here is real — replace it once you have live data.

### (b) None — telemetry disabled

```yaml
telemetry:
  provider: none
```

`load_provider()` returns `None`. The splash pulse is hidden and `fetch()`
is never called; the dashboard behaves as a pure knowledge-base assistant.

### (c) HTTP JSON service

If you already have (or can stand up) a small internal service that exposes
your telemetry as JSON over HTTP, use
`adapters/telemetry_http_example.py` as a template:

```yaml
telemetry:
  provider: adapters.telemetry_http_example
```

```bash
export OPENKB_DASH_TELEMETRY_HTTP_BASE_URL="http://127.0.0.1:9000"
```

It uses `urllib` (stdlib, no extra dependency), a short timeout so a slow
upstream never stalls a chat turn, a 15-second snapshot cache so the splash
pulse doesn't hammer your service, and returns `None` on any failure
(connection refused, timeout, bad JSON) rather than raising.

### (d) NMEA 0183 / NMEA 2000 / SignalK

The dashboard should never speak NMEA directly — decoding a serial/CAN bus
is a different job with different failure modes (partial sentences, bus
noise, reconnect logic) than serving a web UI. The clean split:

```
NMEA / SignalK bus ──> small decoder process ──> JSON over HTTP (localhost)
                                                        │
                                                        v
                                          adapters.telemetry_http_example
                                          (or your own thin subclass)
```

- Run a small always-on process (a SignalK server, or your own script using
  a library such as `pynmea2`/`pynmea0183`) that decodes the bus and keeps
  the latest values in memory.
- Expose those values on a local HTTP endpoint returning JSON — SignalK
  already does this out of the box (its REST API serves the full data
  model as JSON).
- Point a `Provider` at that local endpoint using the HTTP-JSON pattern
  above, mapping SignalK/NMEA field paths (e.g. `navigation.speedOverGround`)
  onto the generic `speed` / `depth` / `wind_speed` keys.

This keeps protocol-specific code (and its dependencies) out of the
dashboard entirely — the dashboard's dependency surface stays "stdlib +
requests-free urllib" no matter what bus you're decoding.

### (e) Modbus / BMS / SCADA read-only gateways

Same shape as (d): most Modbus/BMS/SCADA stacks have (or can be fitted
with) a read-only gateway that polls registers/points and republishes them
as JSON over HTTP — many BMS vendors provide one, or a small script using a
Modbus library can do the polling and hold the latest values in memory
behind a tiny HTTP server. Keep the dashboard-facing side identical to (c):
a JSON GET endpoint, mapped onto the generic provider shape.

Treat these gateways as **read-only** — the dashboard has no business (and
this contract provides no mechanism) writing back to a BMS/SCADA system.

## Minimal complete custom provider

A self-contained example that polls a local JSON file (e.g. written by some
other process on the same machine) — the smallest possible real provider:

```python
# adapters/telemetry_file_example.py
"""Provider that reads the latest reading from a local JSON file, written
by some other process (a decoder, a cron job, whatever you have)."""
from __future__ import annotations

import json
import os
import time

READ_PATH_ENV = "OPENKB_DASH_TELEMETRY_FILE_PATH"
MAX_AGE_SECONDS = 60  # older than this -> treat as stale


class Provider:
    def __init__(self, path: str | None = None) -> None:
        self.path = path or os.environ.get(READ_PATH_ENV, "./data/telemetry.json")

    def _read(self) -> dict | None:
        try:
            age = time.time() - os.path.getmtime(self.path)
            if age > MAX_AGE_SECONDS:
                return None
            with open(self.path, "r", encoding="utf-8") as fh:
                return json.load(fh)
        except OSError:
            return None

    def snapshot(self) -> dict | None:
        data = self._read()
        if data is None:
            return None
        data = dict(data)
        data["fresh"] = True
        return data

    def fetch(self, question: str) -> tuple[str, dict] | None:
        data = self._read()
        if data is None:
            return None
        lines = ["LIVE ASSET DATA (file provider):"]
        lines += ["%s: %s" % (k, v) for k, v in data.items()]
        return "\n".join(lines), {"provider": "file", "path": self.path}
```

Point config at it:

```yaml
telemetry:
  provider: adapters.telemetry_file_example
```

That's the whole contract: two small methods, best-effort failure handling,
and `sanitise_position` doing the safety work so you don't have to
re-implement redaction in every provider.
