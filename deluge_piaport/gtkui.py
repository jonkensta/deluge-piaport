#
# Copyright (C) 2026 Jonathan Starr
#
# Plugin structure based on Deluge's built-in Label plugin.
#
# This file is licensed under GNU General Public License 3.0, or later, with the
# additional special exception to link portions of this program with the OpenSSL
# library. See LICENSE for more details.
#

"""Minimal GTK UI stub.

The target host is headless and web-first, so the GTK client gets no dedicated
UI. This stub exists only so the gtk3ui entry point loads cleanly when the plugin
is used from the GTK client.
"""

import logging

from deluge.plugins.pluginbase import Gtk3PluginBase

log = logging.getLogger(__name__)


class GtkUI(Gtk3PluginBase):
    def enable(self):
        log.debug('PiaPort GTK UI enabled (no-op stub)')

    def disable(self):
        log.debug('PiaPort GTK UI disabled (no-op stub)')
