#
# Copyright (C) 2026 Jonathan Starr
#
# This file is licensed under GNU General Public License 3.0, or later, with the
# additional special exception to link portions of this program with the OpenSSL
# library. See LICENSE for more details.
#

"""Unit tests for deluge_piaport.config (stdlib-only, no daemon required)."""

import pytest

from deluge_piaport.config import (
    MIN_POLL_INTERVAL,
    ConfigError,
    clamp_poll_interval,
    should_update_port,
    validate_and_clean,
)


# clamp_poll_interval -------------------------------------------------------

def test_clamp_raises_floor():
    assert clamp_poll_interval(5) == MIN_POLL_INTERVAL


def test_clamp_keeps_large_value():
    assert clamp_poll_interval(600) == 600


def test_clamp_coerces_numeric_string():
    assert clamp_poll_interval('120') == 120


def test_clamp_rejects_non_numeric():
    with pytest.raises(ConfigError):
        clamp_poll_interval('soon')


# validate_and_clean --------------------------------------------------------

def test_rejects_unknown_key():
    with pytest.raises(ConfigError):
        validate_and_clean({'bogus': 1})


def test_clamps_poll_interval_in_settings():
    settings, _ = validate_and_clean({'poll_interval': 1})
    assert settings['poll_interval'] == MIN_POLL_INTERVAL


def test_passes_through_known_settings():
    settings, action = validate_and_clean({'enabled': False, 'gluetun_url': 'http://x:8000'})
    assert settings == {'enabled': False, 'gluetun_url': 'http://x:8000'}
    assert action == ('keep',)


def test_api_key_absent_means_keep():
    _, action = validate_and_clean({'enabled': True})
    assert action == ('keep',)


def test_api_key_value_means_set():
    settings, action = validate_and_clean({'api_key': 'newkey'})
    assert action == ('set', 'newkey')
    assert 'api_key' not in settings  # never persisted via the settings dict


def test_clear_flag_means_clear():
    _, action = validate_and_clean({'clear_api_key': True})
    assert action == ('clear',)


def test_clear_beats_supplied_key():
    # Ticked "Clear stored key" wins even if a key was also typed.
    _, action = validate_and_clean({'api_key': 'typed', 'clear_api_key': True})
    assert action == ('clear',)


def test_control_keys_not_treated_as_unknown():
    # api_key / clear_api_key are consumed, not flagged as unknown config keys.
    validate_and_clean({'api_key': 'k', 'clear_api_key': False})


# should_update_port --------------------------------------------------------

def test_no_update_when_port_zero():
    assert should_update_port(50000, 0) is False


def test_no_update_when_unchanged():
    assert should_update_port(54321, 54321) is False


def test_update_when_changed():
    assert should_update_port(50000, 54321) is True


def test_update_from_none_current():
    # Current listen port unknown -> a real forwarded port should apply.
    assert should_update_port(None, 54321) is True
