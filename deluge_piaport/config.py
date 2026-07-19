#
# Copyright (C) 2026 Jonathan Starr
#
# This file is licensed under GNU General Public License 3.0, or later, with the
# additional special exception to link portions of this program with the OpenSSL
# library. See LICENSE for more details.
#

"""Pure config helpers for the PiaPort plugin.

Deliberately free of any Deluge/Twisted imports so this logic is unit-testable on
its own (see tests/test_config.py). core.py wires these into the daemon.
"""

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

# Keys set_config may write directly. 'api_key' is excluded: it is handled via the
# keep/replace/clear protocol below (IMPLEMENTATION_PLAN.md section 7).
CONFIG_KEYS = frozenset(k for k in DEFAULT_PREFS if k != 'api_key')


class ConfigError(Exception):
    """Raised when set_config is given invalid options."""


def clamp_poll_interval(value):
    """Coerce value to an int and clamp it to >= MIN_POLL_INTERVAL."""
    try:
        seconds = int(value)
    except (TypeError, ValueError):
        raise ConfigError('poll_interval must be an integer, got %r' % (value,))
    return max(MIN_POLL_INTERVAL, seconds)


def validate_and_clean(options):
    """Split raw set_config options into (settings, api_key_action).

    - settings: validated dict of CONFIG_KEYS to persist (poll_interval clamped).
    - api_key_action: one of ('keep',), ('set', key), ('clear',).

    'clear_api_key': True takes precedence over any supplied 'api_key' value, so a
    ticked "Clear stored key" checkbox always wins (IMPLEMENTATION_PLAN.md section 7).
    Raises ConfigError on unknown keys.
    """
    options = dict(options)
    clear = bool(options.pop('clear_api_key', False))
    new_key = options.pop('api_key', None)

    unknown = set(options) - set(CONFIG_KEYS)
    if unknown:
        raise ConfigError('unknown config keys: %s' % sorted(unknown))

    settings = {}
    for key, value in options.items():
        if key == 'poll_interval':
            value = clamp_poll_interval(value)
        settings[key] = value

    if clear:
        action = ('clear',)
    elif new_key:
        action = ('set', new_key)
    else:
        action = ('keep',)

    return settings, action


def should_update_port(current_listen_port, forwarded_port):
    """True only when gluetun reports a real port that differs from Deluge's.

    A forwarded_port of 0 means "port forwarding not ready" and must never trigger
    a change.
    """
    return forwarded_port > 0 and forwarded_port != current_listen_port
