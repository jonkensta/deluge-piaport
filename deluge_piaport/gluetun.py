#
# Copyright (C) 2026 Jonathan Starr
#
# This file is licensed under GNU General Public License 3.0, or later, with the
# additional special exception to link portions of this program with the OpenSSL
# library. See LICENSE for more details.
#

"""gluetun HTTP control-server client.

A single blocking helper that fetches the currently forwarded port from gluetun's
control server. It is stdlib-only (no Deluge/Twisted) so it is unit-testable and
so core.py can run it off the reactor via deferToThread (IMPLEMENTATION_PLAN.md
section 2).

Deluge reaches gluetun over the shared network namespace, e.g.:
    GET http://localhost:8000/v1/portforward
    X-API-Key: <key>
    -> {"port": 54321, ...}
"""

import json
import urllib.request

DEFAULT_ENDPOINT = '/v1/portforward'
DEFAULT_TIMEOUT = 10


class GluetunError(Exception):
    """Raised when the forwarded port cannot be fetched or parsed."""


def fetch_forwarded_port(
    base_url,
    endpoint=DEFAULT_ENDPOINT,
    api_key='',
    timeout=DEFAULT_TIMEOUT,
    opener=urllib.request.urlopen,
):
    """Return gluetun's currently forwarded port as an int (0 == not ready).

    Raises GluetunError on any transport, HTTP, decoding, or validation failure so
    the caller's errback can record it and keep polling. ``opener`` is injectable
    for testing.
    """
    url = base_url.rstrip('/') + endpoint
    request = urllib.request.Request(url)
    if api_key:
        request.add_header('X-API-Key', api_key)

    try:
        with opener(request, timeout=timeout) as response:
            raw = response.read()
    except Exception as exc:  # URLError, HTTPError, socket.timeout, ...
        raise GluetunError('request to %s failed: %s' % (url, exc)) from exc

    try:
        port = int(json.loads(raw)['port'])
    except (ValueError, TypeError, KeyError) as exc:
        raise GluetunError('unexpected response from %s: %s' % (url, exc)) from exc

    if not 0 <= port <= 65535:
        raise GluetunError('port out of range: %d' % port)

    return port
