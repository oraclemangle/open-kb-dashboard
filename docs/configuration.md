# Configuration reference

open-kb-dashboard is configured entirely through `config.yaml` (copy it from
`config.example.yaml`), with every key overridable by an environment
variable. Precedence, later wins: **built-in defaults → `config.yaml` →
`OPENKB_DASH_*` environment variables.** This is the same shape and override
grammar as the open-kb project itself.

## Finding the config file

`load_config()` (in `config.py`) looks in this order and stops at the first
hit:

1. `$OPENKB_DASH_CONFIG` (an explicit path), or
2. `./config.yaml` (current working directory)

If neither exists, every value falls back to its built-in default — enough
to start the dashboard with no config file at all, assuming open-kb is
reachable at `127.0.0.1:8080` and a local model server at
`127.0.0.1:11434`.

## Environment-variable override syntax

`OPENKB_DASH_<SECTION>_<KEY>`, upper-case, matching the YAML section and key
names. Nested keys use a double underscore:

```bash
export OPENKB_DASH_SERVER_PORT=8091
export OPENKB_DASH_KB_API_URL=http://127.0.0.1:8080
export OPENKB_DASH_SERVER_AUTH__USER=operator
export OPENKB_DASH_SERVER_AUTH__PASSWORD='change-me'
export OPENKB_DASH_TELEMETRY_SANITISE_POSITION=0
```

Booleans accept `0`/`false`/`no`/`off` (case-insensitive) as false, anything
else (including empty) as true, when the underlying default is boolean.
Numeric env values are coerced to match the type of the default they
replace; a value that fails to coerce is silently ignored (the previous
value is kept) rather than crashing config load. The `engines` list and
`ui.domain_meta`/`ui.tips`/`ui.qa_chips` collections are only configurable
via YAML — env overrides only reach scalar leaves under a section.

---

## `server`

| Key | Default | Env var | Notes |
|---|---|---|---|
| `host` | `127.0.0.1` | `OPENKB_DASH_SERVER_HOST` | Bind address. Leave on loopback unless a reverse proxy is fronting the dashboard |
| `port` | `8090` | `OPENKB_DASH_SERVER_PORT` | HTTP port |
| `auth.user` | `""` | `OPENKB_DASH_SERVER_AUTH__USER` | HTTP Basic auth username; empty disables auth entirely |
| `auth.password` | `""` | `OPENKB_DASH_SERVER_AUTH__PASSWORD` | HTTP Basic auth password. Never commit a real value — set via env var or a gitignored `config.yaml` |

## `kb`

| Key | Default | Env var | Notes |
|---|---|---|---|
| `api_url` | `http://127.0.0.1:8080` | `OPENKB_DASH_KB_API_URL` | Base URL of the open-kb REST API this dashboard fronts |
| `token` | `""` | `OPENKB_DASH_KB_TOKEN` | Must match open-kb's own `api.token` if it has one set. Sent as `Authorization: Bearer <token>` on `POST` routes only |
| `inbox_dir` | *(unset)* | `OPENKB_DASH_KB_INBOX_DIR` | Optional. Set to open-kb's `paths.inbox` **on the same host** to make drag-drop upload land directly in the ingest inbox. See `docs/deployment.md` |
| `upload_max_bytes` | `104857600` | `OPENKB_DASH_KB_UPLOAD_MAX_BYTES` | Hard per-file limit (100 MiB by default); checked before the request body is read |
| `upload_min_free_bytes` | `536870912` | `OPENKB_DASH_KB_UPLOAD_MIN_FREE_BYTES` | Refuse completion when it would leave less free space than this reserve (512 MiB by default) |

## `engines`

A YAML list (not overridable piecemeal by env var — edit the list directly).
Each entry populates one option in the UI's engine picker:

| Key | Meaning |
|---|---|
| `id` | Stable identifier, used internally and in session records |
| `label` | Display name in the picker |
| `provider` | `openai` (any OpenAI-compatible `/v1/chat/completions` endpoint) or `kb` (answer entirely via open-kb's own `/ask`, no separate LLM call) |
| `base_url` | *(provider `openai` only)* endpoint base URL, e.g. `http://127.0.0.1:11434/v1` for Ollama |
| `model` | *(provider `openai` only)* model name as the endpoint expects it |
| `api_key_env` | *(provider `openai` only)* name of an environment variable holding an API key, if the endpoint needs one; leave empty for a local server with no auth |

The built-in default ships two engines: `local` (an `openai`-provider entry
pointed at a local Ollama instance) and `kb` (direct open-kb answering).

## `telemetry`

Controls the optional splash-screen "live pulse" and chat prompt injection
for live-data questions. See the README's **Live telemetry** section and
`docs/telemetry-adapter-guide.md` for the full picture.

| Key | Default | Env var | Notes |
|---|---|---|---|
| `provider` | `demo` | `OPENKB_DASH_TELEMETRY_PROVIDER` | `none` (feature hidden), `demo` (synthetic data, works out of the box), or an importable module path exposing a `Provider` class |
| `sanitise_position` | `true` | `OPENKB_DASH_TELEMETRY_SANITISE_POSITION` | Strips absolute position fields (lat/long pairs, GPS/fix keys) from telemetry text before it reaches an LLM prompt or the browser. Sensible default for any moving or location-sensitive asset; set `false` only if positions should be visible |

## `ui`

| Key | Default | Env var | Notes |
|---|---|---|---|
| `brand` | `open-kb` | `OPENKB_DASH_UI_BRAND` | Header text and browser tab title |
| `subtitle` | `knowledge base assistant` | `OPENKB_DASH_UI_SUBTITLE` | Shown under the brand on the splash screen |
| `tips` | *(3 built-in tips)* | *(YAML only)* | Rotating splash-screen operating hints |
| `qa_chips` | *(3 built-in questions)* | *(YAML only)* | Canned starter questions shown as clickable chips on the splash screen |
| `domain_meta` | `{}` | *(YAML only)* | Optional per-domain display metadata, e.g. `{00_ELECTRICAL: {label: Electrical, icon: bolt}}`. Domains not listed here fall back to sensible defaults derived from the domain name |

## `paths`

| Key | Default | Env var | Notes |
|---|---|---|---|
| `data_dir` | `./data` | `OPENKB_DASH_PATHS_DATA_DIR` | Root for sessions, uploads, and the feedback log. `~` is expanded at load time |

## `redaction`

| Key | Default | Env var | Notes |
|---|---|---|---|
| `enabled` | `true` | `OPENKB_DASH_REDACTION_ENABLED` | Scrub credential-shaped strings (passwords, API keys, client secrets, bearer tokens, PEM keys, AWS-style access keys) from text before it leaves the server. See `redaction.py` for the exact patterns — this is a creds-only scrubber, not a general PII/topology redactor |
