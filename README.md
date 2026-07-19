# deluge-piaport

A [Deluge](https://deluge-torrent.org/) 2.x plugin that keeps Deluge's incoming
(listen) port in sync with the port that [gluetun](https://github.com/qdm12/gluetun)
forwards from [PIA](https://www.privateinternetaccess.com/) (Private Internet Access),
with configuration and live status exposed through the Deluge **web interface**.

> **Status: working.** Core port-sync, the web Preferences UI, and unit tests are done,
> and the plugin has been built, installed, and validated end-to-end against a live
> LinuxServer.io Deluge + gluetun/PIA setup (it corrected Deluge's listen port to the
> forwarded port on demand). See [`IMPLEMENTATION_PLAN.md`](./IMPLEMENTATION_PLAN.md) for
> the full design.

## Why

This is a working replacement for
[`jawilson/deluge-piaportplugin`](https://github.com/jawilson/deluge-piaportplugin),
which does not work in a common gluetun-based setup. That plugin reads a file at
`/pia/forwarded_port`, but when Deluge runs with `network_mode: "service:gluetun"` it
shares gluetun's *network* namespace, **not** its filesystem — so the file never exists
in the Deluge container and the plugin silently gives up.

Instead, this plugin queries gluetun's **HTTP control server** (which *is* reachable at
`http://localhost:8000` over the shared network namespace):

```
GET http://localhost:8000/v1/portforward
Header: X-API-Key: <your gluetun api key>
-> {"port": 54321, ...}
```

…then sets Deluge's `listen_ports` to `[port, port]` and reannounces — all from inside
the daemon, on a timer, no `docker exec` or cron required.

## Features

- Polls gluetun's control server on a configurable interval (non-blocking, in the Twisted
  reactor).
- Updates Deluge's listen port only when the forwarded port actually changes; forces a
  tracker reannounce.
- Handles PIA reconnects gracefully (transient `port == 0` = "not ready", errors don't
  kill the poll loop; in-flight results are discarded across config changes).
- **Web UI**: a Preferences page (modeled on Deluge's built-in Label plugin) to configure
  the gluetun URL / API key / poll interval and view live status (forwarded port, current
  listen port, last checked, errors), plus a "Check now" button.

## Requirements

- Deluge 2.x. Tested against `lscr.io/linuxserver/deluge` (Python 3.12).
- gluetun with port forwarding on and its **HTTP control server** enabled with an API key
  (`VPN_PORT_FORWARDING=on`, `HTTP_CONTROL_SERVER_AUTH_DEFAULT_ROLE={"auth":"apikey","apikey":"…"}`).
- Deluge sharing gluetun's network namespace (`network_mode: "service:gluetun"`), so it can
  reach the control server at `http://localhost:8000`.

## Installation

Deluge loads third-party plugins as **eggs**, and only loads an egg whose Python version
tag matches the daemon's interpreter — so the egg is built inside the Deluge container's
own image. The `Makefile` auto-detects that image, so you don't have to hardcode a version:

```bash
make install    # builds the egg in the container's image, copies it in, restarts Deluge
make enable     # waits for the daemon, then enables the plugin
```

Then set the gluetun API key (see below). To check it's running:

```bash
make status     # prints the plugin's live config + status over RPC
```

If your container isn't named `deluge`, export the name once so it applies to every
command (a `make install DELUGE_CONTAINER=…` override would not carry over to `make enable`):

```bash
export DELUGE_CONTAINER=mydeluge
make install && make enable
```

## Configuration

In the Deluge **web UI**, open **Preferences → PiaPort** and set:

- **Gluetun control URL** — default `http://localhost:8000`.
- **Gluetun API key** — the `apikey` from gluetun's `HTTP_CONTROL_SERVER_AUTH_DEFAULT_ROLE`.
  Stored server-side and never sent back to the browser; leave blank to keep the existing
  key, or tick **Clear stored key** to remove it.
- **Poll interval** (seconds, min 30), and the reannounce / disable-random-port toggles.

Use **Check now** to poll immediately and see the result in the status panel.

## Development

```bash
make test    # runs the pure-logic unit tests (no Deluge/Twisted needed)
```

Architecture, the reviewed Deluge 2.x API surface, security handling of the API key, and
the full test plan live in [`IMPLEMENTATION_PLAN.md`](./IMPLEMENTATION_PLAN.md).

## Credits

- Inspired by [`jawilson/deluge-piaportplugin`](https://github.com/jawilson/deluge-piaportplugin).
- Plugin architecture modeled on Deluge's built-in **Label** plugin.

## License

GPL-3.0-or-later, matching Deluge and its plugins. See [`LICENSE`](./LICENSE).
