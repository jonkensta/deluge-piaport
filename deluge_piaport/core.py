#
# Copyright (C) 2026 Jonathan Starr
#
# Plugin structure based on Deluge's built-in Label plugin.
#
# This file is licensed under GNU General Public License 3.0, or later, with the
# additional special exception to link portions of this program with the OpenSSL
# library. See LICENSE for more details.
#

"""PiaPort core plugin.

Keeps Deluge's listen port in sync with the port gluetun forwards from PIA by
polling gluetun's HTTP control server on a timer. See IMPLEMENTATION_PLAN.md
sections 2-4 for the design; the pure fetch/config logic lives in gluetun.py and
config.py so it can be tested without a running daemon.
"""

import logging
import time

import deluge.component as component
from deluge.configmanager import ConfigManager
from deluge.core.rpcserver import export
from deluge.plugins.pluginbase import CorePluginBase
from twisted.internet import defer
from twisted.internet.task import LoopingCall
from twisted.internet.threads import deferToThread

from .config import (
    CONFIG_KEYS,
    DEFAULT_PREFS,
    clamp_poll_interval,
    should_update_port,
    validate_and_clean,
)
from .gluetun import fetch_forwarded_port

log = logging.getLogger(__name__)


def _now():
    return time.strftime('%Y-%m-%d %H:%M:%S')


class Core(CorePluginBase):
    def enable(self):
        log.info('*** Start PiaPort plugin ***')
        self.config = ConfigManager('piaport.conf', DEFAULT_PREFS)
        self.core = component.get('Core')
        self._loop = None
        self._inflight = None
        # Bumped whenever the loop is stopped/restarted so a fetch already running
        # in a worker thread can't apply results after disable() or a config change.
        self._generation = 0
        self._status = {
            'forwarded_port': None,
            'listen_port': None,
            'port_forwarding': 'unknown',  # ok | not ready | error | unknown
            'last_checked': None,
            'last_success': None,
            'last_error': None,
            'running': False,
        }
        self._restart_loop()

    def disable(self):
        self._stop_loop()

    def update(self):
        pass

    # Loop management ---------------------------------------------------------

    def _stop_loop(self):
        if self._loop is not None and self._loop.running:
            self._loop.stop()
        self._loop = None
        self._status['running'] = False
        # Invalidate any fetch already dispatched to a worker thread: its result
        # belongs to a now-defunct config and must not be applied.
        self._generation += 1

    def _restart_loop(self):
        """Apply current config: stop any loop, restart only if enabled."""
        self._stop_loop()
        if not self.config['enabled']:
            log.info('PiaPort polling is disabled')
            return
        interval = clamp_poll_interval(self.config['poll_interval'])
        self._loop = LoopingCall(self._poll)
        self._status['running'] = True
        deferred = self._loop.start(interval, now=True)
        # Only fires if the loop stops unexpectedly; _poll never lets a failure
        # escape, so in practice this is a belt-and-suspenders guard.
        deferred.addErrback(self._on_loop_stopped)

    def _on_loop_stopped(self, failure):
        log.error('PiaPort poll loop stopped: %s', failure.getErrorMessage())
        self._status['running'] = False
        self._status['last_error'] = 'poll loop stopped: %s' % failure.getErrorMessage()

    # Polling -----------------------------------------------------------------

    def _poll(self):
        """Run one poll, coalescing with any already in flight.

        Always returns a Deferred that succeeds (errors are recorded, not raised),
        so neither the LoopingCall nor check_now can be wedged by a failed fetch.
        """
        if self._inflight is not None:
            return self._inflight
        generation = self._generation
        deferred = deferToThread(
            fetch_forwarded_port,
            self.config['gluetun_url'],
            self.config['port_endpoint'],
            self.config['api_key'],
        )
        self._inflight = deferred
        deferred.addCallbacks(
            self._on_fetch_ok,
            self._on_fetch_error,
            callbackArgs=(generation,),
            errbackArgs=(generation,),
        )
        deferred.addBoth(self._clear_inflight)
        return deferred

    def _clear_inflight(self, result):
        self._inflight = None
        return result

    def _is_stale(self, generation):
        return generation != self._generation

    def _on_fetch_error(self, failure, generation):
        if self._is_stale(generation):
            return None  # config changed/disabled since dispatch; ignore.
        self._status['last_checked'] = _now()
        self._status['port_forwarding'] = 'error'
        self._status['last_error'] = failure.getErrorMessage()
        log.warning('PiaPort: gluetun poll failed: %s', failure.getErrorMessage())
        return None  # swallow: keep the loop alive

    def _on_fetch_ok(self, port, generation):
        if self._is_stale(generation):
            log.debug('PiaPort: dropping stale poll result (config changed)')
            return None
        self._status['last_checked'] = _now()
        self._status['last_error'] = None
        if port == 0:
            # Reachable but port forwarding not ready (e.g. mid-reconnect). Keep
            # the last known good port and make no change.
            self._status['port_forwarding'] = 'not ready'
            log.debug('PiaPort: gluetun reports port not ready (0)')
            return None
        self._status['forwarded_port'] = port
        self._status['port_forwarding'] = 'ok'
        self._status['last_success'] = _now()
        try:
            self._apply_port(port)
        except Exception as exc:
            log.error('PiaPort: failed to apply port %d: %s', port, exc)
            self._status['last_error'] = 'apply failed: %s' % exc
        return None

    def _apply_port(self, port):
        current = self.core.get_listen_port()
        self._status['listen_port'] = current
        if not should_update_port(current, port):
            log.debug('PiaPort: listen port already %s, nothing to do', current)
            return

        new_config = {'listen_ports': [port, port]}
        if self.config['set_random_port_false']:
            new_config['random_port'] = False
        self.core.set_config(new_config)
        self._status['listen_port'] = port
        log.info('PiaPort: updated listen port %s -> %d', current, port)

        if self.config['force_reannounce']:
            try:
                ids = list(self.core.torrentmanager.get_torrent_list())
                if ids:
                    self.core.force_reannounce(ids)
            except Exception as exc:
                # Port is already applied; a reannounce failure must not undo that.
                log.warning('PiaPort: reannounce failed (port still applied): %s', exc)

    # RPC surface -------------------------------------------------------------

    @export
    def get_config(self):
        """Return non-secret config plus api_key_set (never the raw api_key)."""
        cfg = {key: self.config[key] for key in CONFIG_KEYS}
        cfg['api_key_set'] = bool(self.config['api_key'])
        return cfg

    @export
    def set_config(self, options):
        """Validate + persist config and restart the loop.

        api-key protocol (IMPLEMENTATION_PLAN.md section 7): 'api_key' absent = keep,
        non-empty = replace, 'clear_api_key': True = clear.
        """
        settings, key_action = validate_and_clean(options)
        for key, value in settings.items():
            self.config[key] = value
        if key_action[0] == 'clear':
            self.config['api_key'] = ''
        elif key_action[0] == 'set':
            self.config['api_key'] = key_action[1]
        self.config.save()
        self._restart_loop()

    @export
    def get_status(self):
        """Return live status for the web UI status panel."""
        return dict(self._status)

    @export
    def check_now(self):
        """Trigger (or join) an immediate poll and resolve to the new status."""
        result = defer.Deferred()
        self._poll().addBoth(lambda _: result.callback(self.get_status()))
        return result
