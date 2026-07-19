# CLAUDE.md

Guidance for Claude Code (and other agents) working in this repository.
`AGENTS.md` is a symlink to this file.

## Project

**deluge-piaport** is a Deluge 2.x plugin that keeps Deluge's incoming (listen) port in
sync with the port [gluetun](https://github.com/qdm12/gluetun) forwards from PIA, with
configuration and live status in the Deluge **web interface**. It is a working
replacement for [`jawilson/deluge-piaportplugin`](https://github.com/jawilson/deluge-piaportplugin).

**Status: planning.** No plugin code exists yet. The complete, reviewed design lives in
[`IMPLEMENTATION_PLAN.md`](./IMPLEMENTATION_PLAN.md) — treat it as the source of truth for
architecture, the Deluge 2.x API surface, the egg build/deploy recipe, and the test plan.
Keep it in sync when the design changes.

## Key facts (don't rediscover these)

- **Why the old plugin fails:** it reads a file `/pia/forwarded_port`. In the target
  setup Deluge runs with `network_mode: "service:gluetun"`, which shares gluetun's
  *network* namespace but **not** its filesystem, so that file never exists.
- **The working approach:** query gluetun's HTTP control server (reachable at
  `http://localhost:8000` over the shared netns) — `GET /v1/portforward` with an
  `X-API-Key` header returns `{"port": N}` — then set Deluge `listen_ports` to `[N, N]`
  and reannounce.
- **Reference architecture:** Deluge's built-in **Label** plugin (three entry points:
  `core` / `web` / `gtk3ui`). The web UI is a Preferences page; note Label's page is
  static and does *not* model settings-saving — an `onApply()` must call `set_config`.
- **Target runtime:** `lscr.io/linuxserver/deluge:2.2.0-r1-ls364`; plugins load as eggs
  in `/config/plugins/`, built against the container's *exact* Python `py3.N`.
- **Deluge core runs in the Twisted reactor** — no blocking calls; use `deferToThread`
  for HTTP and guard the `LoopingCall` so a failed poll can't kill it.

## Git workflow

- **Branch-based development.** Do work on a branch named for its purpose, e.g.
  `feat/web-preferences-page` or `bugfix/looping-call-errback`. Don't commit feature work
  directly to `main`.
- **Commit as you go**, in the smallest chunks that each form a single logical, focused,
  working change toward the plan — not one giant end-of-task commit.
- **Concise, tagged commit messages.** Start the subject with a tag: `feat: …`,
  `bugfix: …` (also fine: `docs: …`, `refactor: …`, `test: …`, `chore: …`). A short body
  is welcome when it adds context — keep it to a single paragraph where possible.
