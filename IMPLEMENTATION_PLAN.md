# Implementation Plan: `PiaPort` — Deluge plugin for gluetun/PIA port forwarding

## Goal

Build a Deluge 2.x plugin that keeps Deluge's incoming (listen) port in sync with the
port that gluetun forwards from PIA, and expose configuration + live status through a
web interface modeled on the built-in **Label** plugin. It must actually work in the
deployment described by `~/Source/mediacenter/docker-compose.mediaserver.yml`, where
`jawilson/deluge-piaportplugin` does not.

---

## 1. Why the existing `jawilson/deluge-piaportplugin` fails here

Root cause is a wrong assumption about *how the forwarded port is exposed*:

1. **It reads a file `/pia/forwarded_port`.** In this deployment Deluge runs with
   `network_mode: "service:gluetun"`. That shares gluetun's **network namespace only**,
   not its filesystem. gluetun writes the forwarded port inside its *own* container
   (`/gluetun/forwarded_port`) and exposes it over its **HTTP control server**. No
   `/pia` volume is mounted into the Deluge container, so the file never exists and the
   plugin silently gives up (`Failed to open and read port file`).

2. **It only acts when `core.test_listen_port()` reports the port blocked.** That test
   is slow and unreliable, and PIA's forwarded port changes on every VPN
   reconnect/rotation even while the old port still tests "open" momentarily — so
   updates are missed.

3. **Lifecycle bug:** `self.check_timer = self.check_timer.start(...)` overwrites the
   `LoopingCall` object with the `Deferred` that `start()` returns, so `disable()` then
   calls `.stop()` on a `Deferred` and raises.

4. **Python-2-era code** (`from __future__ import unicode_literals`, `%`-logging of
   deferred values) — brittle under the LSIO container's Python 3.

### The approach that already works

`~/Source/mediacenter/bin/update-deluge-port` proves the reliable path: because Deluge
shares gluetun's network namespace, it can reach gluetun's control server at
`http://localhost:8000`:

```bash
docker exec gluetun wget -qO- --header='X-API-Key: <key>' \
  http://localhost:8000/v1/portforward   # -> {"port": 54321, ...}
docker exec deluge deluge-console ... "config -s listen_ports [$PORT,$PORT]"
```

The plugin will do exactly this, but from *inside* the Deluge daemon, on a timer, with
a web UI — no `docker exec`, no cron, no external script.

---

## 2. High-level design

A standard three-entry-point Deluge plugin (`core` / `web` / optional `gtk3ui`),
mirroring `deluge/plugins/Label`:

- **Core plugin** runs a `LoopingCall` that polls gluetun's control server, and when the
  forwarded port differs from Deluge's current listen port, sets `listen_ports` and
  forces a reannounce. It exposes `@export`ed RPC methods for config + status.
- **Web plugin** ships one ExtJS script that registers a **Preferences page** (same
  mechanism Label uses via `deluge.preferences.addPage`) with editable settings and a
  live status panel.
- **GTK UI** is an optional thin stub (the target box is headless; web is primary).

### Data flow

```
LoopingCall (every poll_interval s)
  -> HTTP GET {gluetun_url}/v1/portforward  (X-API-Key header)   [non-blocking]
  -> parse JSON -> forwarded_port
  -> if forwarded_port > 0 and != current deluge listen port:
        core.set_config({'listen_ports': [p, p], 'random_port': False})
        core.force_reannounce(all_torrent_ids)
  -> record status (last_checked, last_success, last_error, forwarded_port, listen_port)
```

### Non-blocking HTTP (critical)

The Deluge daemon runs in the Twisted reactor; a blocking `urllib` call in the reactor
thread would freeze the daemon. Options, in order of preference:

1. **`twisted.internet.threads.deferToThread`** wrapping a plain `urllib.request` GET
   with a short timeout. Zero extra dependencies, guaranteed available, trivially
   testable. **← chosen default.**
2. `treq` / `twisted.web.client.Agent` (fully async) — cleaner but `treq` may not be
   present in the LSIO image; Agent is more boilerplate. Documented as an alternative.

We use option 1: a small `_fetch_forwarded_port()` sync helper run via `deferToThread`,
with `socket`/urllib timeout ≈ 10s so a hung control server can't pile up threads.

### Loop robustness (must-haves, not optional)

- **`_poll()` must never let a failure escape.** `LoopingCall` stops permanently if the
  Deferred it drives fails, and gluetun being briefly unreachable during a VPN
  reconnect is *expected*. `_poll()` returns the `deferToThread` Deferred with an
  **errback** attached that records `last_error` and swallows the failure (returns a
  normal value) so the loop keeps ticking. The Deferred returned by `LoopingCall.start()`
  is also kept and given an errback so nothing is unhandled.
- **No overlap between `check_now()` and the scheduled poll.** `LoopingCall` only serializes
  its *own* iterations; a separately invoked `check_now()` RPC could start a second thread
  that races on status/config/reannounce. Keep a single in-flight Deferred (`self._inflight`):
  `check_now()` returns the existing in-flight Deferred if one is running, otherwise starts one.
- **`port == 0` is a distinct "reachable but not ready" state, not an error and not a
  success to apply.** During reconnection gluetun legitimately returns `0`. On `0`: record
  `last_checked` + a `port_forwarding: 'not ready'` status, **preserve** the last known good
  `forwarded_port`, make **no** change to Deluge, and keep polling. Only `port > 0` and
  `port != current listen port` triggers an update.

---

## 3. Configuration

Stored in `piaport.conf` via `deluge.configmanager.ConfigManager`:

| Key | Default | Notes |
|-----|---------|-------|
| `enabled` | `True` | Master on/off for the polling loop |
| `gluetun_url` | `http://localhost:8000` | Control-server base URL (localhost works via shared netns) |
| `api_key` | `''` | Sent as `X-API-Key`. Sensitive. |
| `poll_interval` | `300` | Seconds between polls; clamp to a sane minimum (e.g. ≥ 30) |
| `port_endpoint` | `/v1/portforward` | Overridable; fallback `/v1/openvpn/portforwarded` |
| `force_reannounce` | `True` | Reannounce after a port change |
| `set_random_port_false` | `True` | Also disable Deluge's "use random port" so it can't override us |

Config changes are applied by a dedicated `_restart_loop()` helper (**not** the buggy
`disable()/enable()` dance the old plugin used), with precise semantics:

1. If a loop is running (`self._loop and self._loop.running`) → `self._loop.stop()`.
2. Persist the new config.
3. Start a fresh `LoopingCall` **only if `enabled` is True**; if `enabled` is False, leave
   it stopped (do not restart a disabled loop). An interval change therefore takes effect
   immediately, and toggling `enabled` starts/stops without error even when already stopped.

---

## 4. File layout (mirrors `deluge/plugins/Label`)

```
deluge/plugins/PiaPort/
  setup.py                     # entry points: deluge.plugin.core/web/gtk3ui
  README.md                    # what it does, build & install, config
  deluge_piaport/
    __init__.py                # CorePlugin / WebUIPlugin / GtkUIPlugin init classes
    common.py                  # get_resource()
    core.py                    # Core(CorePluginBase): polling + @export RPC
    webui.py                   # WebUI(WebPluginBase): scripts = [get_resource('piaport.js')]
    gtkui.py                   # optional minimal GtkUI (stub)
    data/
      piaport.js               # ExtJS preferences page + status panel
```

### Core `@export` API (`core.py`)

- `get_config()` -> dict. The `api_key` is **never returned**; instead return a boolean
  `api_key_set` so the UI can show whether a key is stored (see §7).
- `set_config(options)` -> validates keys (reject unknown), clamps `poll_interval`
  (min 30), applies explicit api-key keep/replace/clear semantics, persists, calls
  `_restart_loop()`.
- `get_status()` -> `{forwarded_port, listen_port, port_forwarding, last_checked,
  last_success, last_error, running}` where `port_forwarding` ∈ `{ok, not ready, error}`.
- `check_now()` -> triggers/returns the in-flight poll (coalesced, see §2) and resolves
  to the resulting status, for the UI "Check now" button.

Internal: `enable()` loads config and starts the `LoopingCall` (if `enabled`);
`disable()` stops the loop if running; `_poll()` does the guarded deferToThread fetch +
apply; `_apply_port(port)` does the compare/set/reannounce. **No per-torrent status field
is registered** — `CorePluginManager.register_status_field()` is a per-torrent callback
mechanism (invoked with a `torrent_id`) and is irrelevant to this plugin's global status;
including it would be dead code that must also be deregistered in `disable()`. Reannounce
uses an explicit torrent-id list from `core.torrentmanager.get_torrent_list()` (there is
no zero-arg "all torrents" form of `force_reannounce`), and a reannounce failure must not
invalidate an otherwise-successful port update.

---

## 5. Web interface (`data/piaport.js`)

Same *registration* pattern as `label.js`
(`Deluge.registerPlugin('PiaPort', ...)`, `deluge.preferences.addPage(...)` in
`onEnable`, `removePage` in `onDisable`).

> **Important — Label is not a model for saving settings.** The Label preferences page
> is static text; it has no editable fields, so it never saves anything. Adding a page
> does **not** make Deluge persist its fields. The Preferences window calls each page's
> **`onApply()`** on OK/Apply — the plugin's page must implement `onApply()` to gather its
> form values and call `deluge.client.piaport.set_config(values, {success, failure})`,
> handling errors and the api-key protocol below. (This is the pattern the built-in
> Scheduler/AutoAdd web pages use.) An `onOk()` that also applies is included for parity.

**Preferences page contents:**

- *Settings* fieldset (form):
  - `enabled` checkbox
  - `gluetun_url` textfield
  - `api_key` **password** textfield, always rendered empty; when `get_config().api_key_set`
    is true the field's emptyText/placeholder reads "(key stored — leave blank to keep)".
  - **`clear_api_key` checkbox** labeled "Clear stored key", placed directly under the
    api-key field and shown/enabled only when `api_key_set` is true. Submit semantics per §7.
  - `poll_interval` spinnerfield (min 30)
  - `force_reannounce` checkbox
  - `set_random_port_false` checkbox
- *Status* fieldset (read-only, refreshed on show + after actions):
  - Forwarded port (from gluetun) · Deluge listen port · Last checked · Last
    success · Last error · Loop running
- Buttons: **Check now** (`deluge.client.piaport.check_now`) and rely on the standard
  Preferences **Apply/OK** to call `set_config`.

The page pulls initial values with `deluge.client.piaport.get_config` /
`get_status` in `onRender`/`show`, mirroring how `LabelOptionsWindow.getLabelOptions`
loads data. It never populates the api-key field from the server.

---

## 6. Deployment into the LSIO container

Third-party Deluge plugins load as **eggs** dropped in `/config/plugins/` (i.e.
`/opt/mediaserver/deluge/plugins/` on the host). **Deluge only loads an egg whose Python
version tag matches the running interpreter**, so the egg must be built against the same
Python the LSIO `deluge:2.2.0-r1-ls364` image ships.

**Build recipe (documented in the plugin README).** LSIO images use `/init` (s6) as
their entrypoint, so a build command appended to `docker run` is intercepted by `/init`,
not executed. Override the entrypoint explicitly, and build against the container's
**exact** Python major.minor (Deluge discovers eggs by their `py3.N` tag, so a merely
"Python 3" venv can produce an egg Deluge silently ignores):

```bash
# 1. Confirm the container's EXACT python version — the egg's py3.N tag must match
docker exec deluge python3 --version        # e.g. Python 3.12.x  -> tag py3.12

# 2. Build the egg in the SAME image, overriding the s6 entrypoint
docker run --rm --entrypoint python3 \
  -v "$PWD/deluge/plugins/PiaPort:/src" -w /src \
  lscr.io/linuxserver/deluge:2.2.0-r1-ls364 \
  setup.py bdist_egg -d /src/dist

# 3. Verify the produced egg's py tag matches step 1 before deploying
ls deluge/plugins/PiaPort/dist/PiaPort-*.egg   # ...-py3.12.egg

# 4. Deploy and enable
cp deluge/plugins/PiaPort/dist/PiaPort-*.egg /opt/mediaserver/deluge/plugins/
docker restart deluge
# Web UI -> Preferences -> Plugins -> enable "PiaPort"
```

(Equivalent alternative: `docker exec` the build inside the already-running container with
the source bind-mounted. A local venv works only if it is the *exact* same Python
major.minor as the image; the version tag is the only hard constraint since the code is
pure Python.)

`docker-compose.mediaserver.yml` already sets everything the plugin needs
(`VPN_PORT_FORWARDING=on`, control-server API key). The plugin's `api_key` must match the
`apikey` in `HTTP_CONTROL_SERVER_AUTH_DEFAULT_ROLE`.

---

## 7. Security considerations

- The gluetun API key is a secret, so `get_config()` **never returns it** — it returns a
  boolean `api_key_set` instead, so the raw key is never shipped to a browser. The web
  form's api-key field is always empty on load, with an explicit submit protocol so both
  "keep" and "clear" are expressible (blank-means-unchanged alone cannot clear a key):
  - field left **blank** → `set_config` omits `api_key` → keep existing.
  - field with a **new value** → replace.
  - **"Clear stored key" checkbox** (the concrete UI control, §5) → `onApply` sends
    `clear_api_key: true` (and omits `api_key`) → clear.

  Concretely, `set_config` treats these as: `api_key` absent = keep, `api_key` non-empty =
  replace, `clear_api_key: true` = clear. `onApply` never sends an empty-string `api_key`,
  so a stray empty field can never wipe the stored key by accident. When the checkbox is
  ticked, any typed key is ignored in favor of the clear.
- `piaport.conf` inherits Deluge's config-dir permissions (same as `auth`), acceptable
  for a single-user host.
- Requests target `localhost` inside the shared VPN namespace; no secret leaves the host.

---

## 8. Testing

- **Unit (pytest, mirrors `deluge/plugins/Label/.../test.py` style):**
  - `_fetch_forwarded_port` parses `{"port": N}`; handles non-200, timeout, bad JSON,
    `port == 0` (PF not ready) → no change.
  - `_apply_port` only sets config when the port actually changed; respects
    `force_reannounce` / `set_random_port_false`; passes an explicit id list to
    `force_reannounce`; a reannounce exception still leaves the port applied + status ok.
  - `_poll` errback path: a fetch exception records `last_error` and the (mocked)
    `LoopingCall` keeps running (no unhandled failure, loop not stopped).
  - `check_now` coalesces with an in-flight poll (no second thread / double apply).
  - `set_config` validation: unknown keys rejected, `poll_interval` clamped to ≥30;
    `_restart_loop` respects `enabled` (stays stopped when False, no `stop()` on a
    non-running loop).
  - `get_config` never returns `api_key`; returns `api_key_set`. api-key protocol:
    absent=keep, non-empty=replace, `clear_api_key`=clear.
- **Integration (manual, documented):**
  - `docker exec deluge python3 -c "import urllib.request…"` against the live control
    server returns a port.
  - Enable plugin, force a VPN reconnect, confirm `listen_ports` follows within one
    poll interval (check `core.get_listen_port()` / UI status panel).

---

## 9. Build order (milestones)

1. Scaffold `deluge/plugins/PiaPort` from the Label plugin (setup.py, `__init__.py`,
   `common.py`, `webui.py`, empty `core.py`).
2. Implement `core.py`: config, `LoopingCall`, `deferToThread` fetch, `_apply_port`,
   `@export` methods, status tracking. **No web UI yet — verify via `deluge-console`.**
3. Add unit tests; get the fetch/apply/config logic green.
4. Implement `data/piaport.js` preferences page + status panel; wire buttons.
5. Optional GTK stub.
6. Write README with build/deploy recipe; build egg in-image and smoke-test on the host.

---

## 10. Open questions / assumptions

- Assumes gluetun endpoint `/v1/portforward` returning `{"port": N}` (as used by the
  working script). Fallback `/v1/openvpn/portforwarded` is configurable if the gluetun
  version differs.
- Plugin lives in-tree under `deluge/plugins/PiaPort` for development; it is distributed
  as a standalone egg (it does **not** need to be merged into Deluge to be used).
- GTK UI is intentionally minimal; the target host is headless and web-first.
