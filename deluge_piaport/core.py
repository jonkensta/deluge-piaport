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

Keeps Deluge's listen port in sync with the port gluetun forwards from PIA, by
polling gluetun's HTTP control server.

This is a SCAFFOLD (milestone 1): lifecycle, config, and the exported RPC surface
are stubbed so the plugin loads and the web UI can bind to it. The polling loop,
port-apply logic, and api-key protocol are implemented in milestone 2 -- see
IMPLEMENTATION_PLAN.md sections 2-4.
"""

import logging

from deluge.configmanager import ConfigManager
from deluge.core.rpcserver import export
from deluge.plugins.pluginbase import CorePluginBase

log = logging.getLogger(__name__)

DEFAULT_PREFS = {
    'enabled': True,
    'gluetun_url': 'http://localhost:8000',
    'api_key': '',
    'poll_interval': 300,
    'port_endpoint': '/v1/portforward',
    'force_reannounce': True,
    'set_random_port_false': True,
}

MIN_POLL_INTERVAL = 30

# Keys that set_config may write; api_key is handled via the keep/replace/clear
# protocol (see IMPLEMENTATION_PLAN.md section 7), not written directly.
CONFIG_KEYS = set(DEFAULT_PREFS) - {'api_key'}


class Core(CorePluginBase):
    def enable(self):
        log.info('*** Start PiaPort plugin ***')
        self.config = ConfigManager('piaport.conf', DEFAULT_PREFS)
        self._loop = None
        self._inflight = None
        self._status = {
            'forwarded_port': None,
            'listen_port': None,
            'port_forwarding': 'unknown',  # ok | not ready | error | unknown
            'last_checked': None,
            'last_success': None,
            'last_error': None,
            'running': False,
        }
        # TODO(milestone 2): start the LoopingCall via _restart_loop() when enabled.

    def disable(self):
        # TODO(milestone 2): stop the LoopingCall if running.
        self._loop = None

    def update(self):
        pass

    # RPC surface -------------------------------------------------------------

    @export
    def get_config(self):
        """Return non-secret config plus api_key_set (never the raw api_key)."""
        cfg = {key: self.config[key] for key in CONFIG_KEYS}
        cfg['api_key_set'] = bool(self.config['api_key'])
        return cfg

    @export
    def set_config(self, options):
        """Persist config and restart the loop.

        api-key protocol (IMPLEMENTATION_PLAN.md section 7): 'api_key' absent = keep,
        non-empty = replace, 'clear_api_key': True = clear.
        """
        # TODO(milestone 2): validate keys, clamp poll_interval to MIN_POLL_INTERVAL,
        # apply the api-key keep/replace/clear protocol, then _restart_loop().
        raise NotImplementedError('set_config is implemented in milestone 2')

    @export
    def get_status(self):
        """Return live status for the web UI status panel."""
        return dict(self._status)

    @export
    def check_now(self):
        """Trigger (or join) an immediate poll and return the resulting status."""
        # TODO(milestone 2): coalesce with any in-flight poll and run one now.
        raise NotImplementedError('check_now is implemented in milestone 2')
