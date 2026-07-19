#!/usr/bin/env python3
#
# Copyright (C) 2026 Jonathan Starr
#
# This file is licensed under GNU General Public License 3.0, or later, with the
# additional special exception to link portions of this program with the OpenSSL
# library. See LICENSE for more details.
#
"""Print PiaPort's live config + status via the Deluge daemon RPC.

Run inside the Deluge container (reads localclient creds from /config/auth):
    docker exec deluge /lsiopy/bin/python3 /tmp/piaport-status.py

`make status` copies this in and runs it for you.
"""

from deluge.ui.client import client
from twisted.internet import defer, reactor


def _localclient_password(path='/config/auth'):
    with open(path) as handle:
        for line in handle:
            if line.startswith('localclient:'):
                return line.split(':')[1]
    raise SystemExit('localclient entry not found in %s' % path)


@defer.inlineCallbacks
def main():
    try:
        yield client.connect(
            host='127.0.0.1',
            port=58846,
            username='localclient',
            password=_localclient_password(),
        )
        config = yield client.piaport.get_config()
        status = yield client.piaport.get_status()
        print('config:', config)
        print('status:', status)
    except Exception as exc:
        print('ERROR:', repr(exc))
    finally:
        try:
            client.disconnect()
        except Exception:
            pass
        if reactor.running:
            reactor.stop()


reactor.callLater(0, main)
reactor.callLater(30, reactor.stop)
reactor.run()
