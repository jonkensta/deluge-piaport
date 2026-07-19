#
# Copyright (C) 2026 Jonathan Starr
#
# Plugin structure based on Deluge's built-in Label plugin.
#
# This file is licensed under GNU General Public License 3.0, or later, with the
# additional special exception to link portions of this program with the OpenSSL
# library. See LICENSE for more details.
#

import logging

from deluge.plugins.pluginbase import WebPluginBase

from .common import get_resource

log = logging.getLogger(__name__)


class WebUI(WebPluginBase):
    scripts = [get_resource('piaport.js')]
    debug_scripts = scripts
