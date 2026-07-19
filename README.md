# deluge-piaport

A [Deluge](https://deluge-torrent.org/) 2.x plugin that keeps Deluge's incoming
(listen) port in sync with the port that [gluetun](https://github.com/qdm12/gluetun)
forwards from [PIA](https://www.privateinternetaccess.com/) (Private Internet Access),
with configuration and live status exposed through the Deluge **web interface**.

> **Status: in development.** The core port-sync logic (gluetun polling, listen-port
> updates, reannounce), its unit tests, and the web Preferences UI (settings form +
> live status panel) are implemented. What remains is the egg build/deploy pass against
> the LinuxServer.io Deluge container. See
> [`IMPLEMENTATION_PLAN.md`](./IMPLEMENTATION_PLAN.md) for the full design and milestones.

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

## Planned features

- Polls gluetun's control server on a configurable interval (non-blocking, in the Twisted
  reactor).
- Updates Deluge's listen port only when the forwarded port actually changes; forces a
  tracker reannounce.
- Handles PIA reconnects gracefully (transient `port == 0` = "not ready", errors don't
  kill the poll loop).
- **Web UI**: a Preferences page (modeled on Deluge's built-in Label plugin) to configure
  the gluetun URL / API key / poll interval and view live status (forwarded port, current
  listen port, last checked, errors), plus a "Check now" button.

## Design & build details

Everything — architecture, the reviewed Deluge 2.x API surface, the egg build/deploy
recipe for the LinuxServer.io Deluge container, security handling of the API key, and the
test plan — lives in [`IMPLEMENTATION_PLAN.md`](./IMPLEMENTATION_PLAN.md).

## Credits

- Inspired by [`jawilson/deluge-piaportplugin`](https://github.com/jawilson/deluge-piaportplugin).
- Plugin architecture modeled on Deluge's built-in **Label** plugin.

## License

Intended to be GPL-3.0-or-later, matching Deluge and its plugins (to be finalized when the
code lands).
