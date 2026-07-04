# CLAUDE.md

Guidance for Claude Code (or any AI coding agent) working in this repo.

## Repo map

```
server.py                stdlib HTTP server: UI, SSE chat, sessions, upload, feedback (written by sibling agents)
config.py                 config loader: defaults <- config.yaml <- OPENKB_DASH_* env vars
redaction.py              credential-only egress scrubber (passwords, API keys, tokens, PEM keys)
adapters/
  telemetry_base.py        TelemetryProvider protocol + load_provider() + strip_positions()
  telemetry_demo.py         built-in synthetic provider (default telemetry.provider)
  kb_client.py              thin stdlib client for the open-kb REST API (health/stats/search/ask)
engines/                   LLM engine adapters (openai-compatible, kb-direct) — picker backends
static/                    browser UI: HTML/CSS/JS, 3-theme design system, no external CDNs
config.example.yaml        copy to config.yaml and edit — every key documented in docs/configuration.md
docs/                      configuration.md, deployment.md, telemetry-adapter-guide.md
```

## Key commands

```bash
.venv/bin/pytest                 # run the test suite
python3 server.py                # start the dashboard (default :8090)
```

## The contract this repo implements

- `GET /` (UI), `/config/ui`, `/engines`, `/splash`, `/health`, `/source`,
  `/sessions[...]`
- `POST /chat` (SSE streaming), `/feedback`, `/upload`
- Optional HTTP Basic auth via `server.auth` in config
- Engine providers: `openai` (any OpenAI-compatible endpoint) and `kb`
  (answers via open-kb's own `/ask`, no extra LLM dependency)

## Conventions

- **Stdlib only.** No third-party runtime dependencies beyond PyYAML for
  config parsing. Don't add a framework where `http.server` + a bit of
  hand-rolled routing already does the job.
- **Config-driven, not hardcoded.** Every new knob needs a
  `config.example.yaml` entry, a `DEFAULTS` entry in `config.py`, and a row
  in `docs/configuration.md`. Don't hardcode a URL, theme value, or feature
  flag that belongs in config.
- **No external CDNs.** `static/` must work fully offline — no
  `<script src="https://...">`, no remote fonts, no remote icon packs. Vendor
  or inline anything the UI needs.
- **Fail-open toward the KB.** `adapters/kb_client.py` never raises on a
  network failure; every method returns a best-effort `{"error": ...}` or
  empty result so the dashboard stays usable when open-kb is unreachable.
- **Telemetry is provider-pluggable.** Never hardcode a telemetry protocol
  into `server.py` or `static/` — everything live-data-shaped goes through
  `adapters/telemetry_base.TelemetryProvider`. Respect
  `telemetry.sanitise_position` by construction, not by convention.

## Deployment tasks

For anything involving standing up open-kb itself, read the open-kb
project's [`docs/ai-operator-guide.md`](../open-kb/docs/ai-operator-guide.md)
first. For dashboard-specific placement, service templates, and the
upload-to-inbox wiring, see [`docs/deployment.md`](docs/deployment.md).
