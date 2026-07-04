# Deployment

The dashboard is a thin client of one open-kb instance and one or more LLM
endpoints. This doc covers running it alongside open-kb — on the same host
or split across two — plus service templates and a reverse-proxy sample.

## Placement: same host or split

**Same host (simplest).** Run `openkb serve` and `python3 server.py` on the
same machine. Point `kb.api_url` at `http://127.0.0.1:8080` (open-kb's
default). No network exposure needed beyond the dashboard's own port.

**Split hosts (the open-kb two-host pattern).** If you're already running
open-kb's ingest/serve split (see the open-kb project's
[`docs/deployment.md`](../../open-kb/docs/deployment.md)), the dashboard
belongs **on the serving host, next to the read-replica** — not on the
ingest host. The serving host is the cheap, always-on one; the dashboard is
cheap and always-on too, so they pair naturally:

```
┌───────────────────────┐        ┌──────────────────────────────────┐
│  HOST A — ingest box    │  SSH  │  HOST B — serving host             │
│  openkb ingest (cron)   │ push  │  openkb serve  (:8080)             │
│  owns writable kb.db     │──────▶│  open-kb-dashboard server.py (:8090)│
└───────────────────────┘  kb.db  │  reads read-only replica            │
                             replica└──────────────────────────────────┘
```

Set the dashboard's `kb.api_url` to `http://127.0.0.1:8080` on HOST B (same
host, loopback) rather than reaching across the network to HOST A — HOST B's
`openkb serve` already reads the local replica.

## Pairing configuration

At minimum, point the dashboard at a reachable open-kb instance:

```yaml
kb:
  api_url: http://127.0.0.1:8080
  token: ""          # must match open-kb's api.token if it has one set
```

If open-kb has `api.token` set (see its `docs/configuration.md`), set the
same value here — `adapters/kb_client.py` sends it as a Bearer token on
every `POST` route; open-kb's `GET` routes stay open regardless.

## Upload → inbox wiring

The dashboard's drag-drop upload can write incoming files straight into
open-kb's ingest inbox so they're picked up by the next scheduled
`openkb ingest` run, with no manual copy step:

```yaml
kb:
  inbox_dir: /srv/open-kb/data/inbox   # MUST be open-kb's paths.inbox, same host
```

Requirements:

- `kb.inbox_dir` must resolve to the **same path** open-kb's own
  `paths.inbox` points at (see open-kb's `docs/configuration.md`) — this
  only works when the two processes share a filesystem, i.e. the same host
  or a shared mount.
- If `kb.inbox_dir` is unset or unreachable, upload still works but files
  are only kept under the dashboard's own `paths.data_dir` — nothing is
  auto-ingested until you move them across yourself.
- Nothing here bypasses open-kb's own secret-detection gate — files still
  go through `openkb ingest`'s normal quarantine check once picked up.

## Running as a service

### systemd (Linux)

Create `/etc/systemd/system/openkb-dashboard.service`:

```ini
[Unit]
Description=open-kb-dashboard
After=network.target
Wants=openkb.service

[Service]
Type=simple
User=<SERVICE_USER>
WorkingDirectory=<PATH_TO_OPEN_KB_DASHBOARD>
Environment=OPENKB_DASH_CONFIG=<PATH_TO_OPEN_KB_DASHBOARD>/config.yaml
ExecStart=/usr/bin/python3 <PATH_TO_OPEN_KB_DASHBOARD>/server.py
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now openkb-dashboard.service
journalctl -u openkb-dashboard.service -f
```

If open-kb also runs as a systemd unit named `openkb.service`, the
`Wants=`/`After=` ordering above starts the dashboard after it without hard
sequencing failure into a boot loop if open-kb is briefly unavailable — the
KB client is best-effort and degrades gracefully (see `adapters/kb_client.py`).

### launchd (macOS)

Create `~/Library/LaunchAgents/com.openkb.dashboard.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.openkb.dashboard</string>
  <key>ProgramArguments</key>
  <array>
    <string>/usr/bin/python3</string>
    <string><PATH_TO_OPEN_KB_DASHBOARD>/server.py</string>
  </array>
  <key>WorkingDirectory</key>
  <string><PATH_TO_OPEN_KB_DASHBOARD></string>
  <key>EnvironmentVariables</key>
  <dict>
    <key>OPENKB_DASH_CONFIG</key>
    <string><PATH_TO_OPEN_KB_DASHBOARD>/config.yaml</string>
  </dict>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <true/>
  <key>StandardOutPath</key>
  <string><PATH_TO_LOGS>/openkb-dashboard.out.log</string>
  <key>StandardErrorPath</key>
  <string><PATH_TO_LOGS>/openkb-dashboard.err.log</string>
</dict>
</plist>
```

```bash
launchctl load ~/Library/LaunchAgents/com.openkb.dashboard.plist
launchctl start com.openkb.dashboard
```

## Reverse proxy (nginx / Caddy)

The dashboard binds to `127.0.0.1` by default and has no TLS of its own —
put a reverse proxy in front for any exposure beyond the local machine, and
keep Basic auth turned on behind it (defence in depth, not either/or).

### nginx

```nginx
server {
    listen 443 ssl;
    server_name <YOUR_HOSTNAME>;

    ssl_certificate     <PATH_TO_CERT>;
    ssl_certificate_key <PATH_TO_KEY>;

    location / {
        proxy_pass http://127.0.0.1:8090;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        # SSE chat streaming needs buffering off and a generous timeout
        proxy_buffering off;
        proxy_read_timeout 300s;
    }
}
```

### Caddy

```
<YOUR_HOSTNAME> {
    reverse_proxy 127.0.0.1:8090 {
        flush_interval -1
    }
}
```

Caddy handles TLS automatically; `flush_interval -1` disables buffering so
SSE chat responses stream rather than arriving in one burst at the end.

Either way, also set `server.auth.user` / `server.auth.password` in the
dashboard's own config — the reverse proxy is the network boundary, Basic
auth is the application-level check behind it.
