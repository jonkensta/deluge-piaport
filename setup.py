#
# Copyright (C) 2026 Jonathan Starr
#
# Plugin structure based on Deluge's built-in Label plugin:
# Copyright (C) 2008 Martijn Voncken <mvoncken@gmail.com>
#
# This file is licensed under GNU General Public License 3.0, or later, with the
# additional special exception to link portions of this program with the OpenSSL
# library. See LICENSE for more details.
#

from setuptools import find_packages, setup

__plugin_name__ = 'PiaPort'
__author__ = 'Jonathan Starr'
__author_email__ = 'github@jstarr.me'
__version__ = '0.1.0'
__url__ = 'https://github.com/jonkensta/deluge-piaport'
__license__ = 'GPLv3'
__description__ = "Sync Deluge's listen port with gluetun's PIA port-forward"
__long_description__ = """
Keeps Deluge's incoming (listen) port in sync with the port that gluetun forwards
from PIA, by polling gluetun's HTTP control server. Configuration and live status
are exposed through the Deluge web interface.
"""
__pkg_data__ = {'deluge_' + __plugin_name__.lower(): ['data/*']}

setup(
    name=__plugin_name__,
    version=__version__,
    description=__description__,
    author=__author__,
    author_email=__author_email__,
    url=__url__,
    license=__license__,
    long_description=__long_description__,
    packages=find_packages(),
    package_data=__pkg_data__,
    entry_points="""
    [deluge.plugin.core]
    %s = deluge_%s:CorePlugin
    [deluge.plugin.gtk3ui]
    %s = deluge_%s:GtkUIPlugin
    [deluge.plugin.web]
    %s = deluge_%s:WebUIPlugin
    """
    % ((__plugin_name__, __plugin_name__.lower()) * 3),
)
