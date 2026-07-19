#
# Copyright (C) 2026 Jonathan Starr
#
# This file is licensed under GNU General Public License 3.0, or later, with the
# additional special exception to link portions of this program with the OpenSSL
# library. See LICENSE for more details.
#

"""Pytest bootstrap.

The unit tests only exercise the pure modules (config.py, gluetun.py), but
importing them pulls in the package __init__, which imports Deluge. Deluge (and
Twisted) are not installed in a bare test/CI environment, so we stub the single
symbol __init__ needs. Tests never touch Deluge itself; the daemon-coupled code
in core.py is covered by manual integration testing.
"""

import os
import sys
import types

sys.path.insert(0, os.path.dirname(__file__))

if 'deluge' not in sys.modules:
    deluge = types.ModuleType('deluge')
    plugins = types.ModuleType('deluge.plugins')
    init = types.ModuleType('deluge.plugins.init')

    class PluginInitBase:  # minimal stand-in for the real base class
        def __init__(self, *args, **kwargs):
            pass

    init.PluginInitBase = PluginInitBase
    plugins.init = init
    deluge.plugins = plugins
    sys.modules['deluge'] = deluge
    sys.modules['deluge.plugins'] = plugins
    sys.modules['deluge.plugins.init'] = init
