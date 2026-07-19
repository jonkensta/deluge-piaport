#
# Copyright (C) 2026 Jonathan Starr
#
# This file is licensed under GNU General Public License 3.0, or later, with the
# additional special exception to link portions of this program with the OpenSSL
# library. See LICENSE for more details.
#

"""Unit tests for deluge_piaport.gluetun (stdlib-only, no daemon required)."""

import socket

import pytest

from deluge_piaport.gluetun import GluetunError, fetch_forwarded_port


class _FakeResponse:
    def __init__(self, body):
        self._body = body

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _opener(body=None, exc=None, captured=None):
    def opener(request, timeout=None):
        if captured is not None:
            captured.append((request, timeout))
        if exc is not None:
            raise exc
        return _FakeResponse(body)

    return opener


def test_parses_port():
    port = fetch_forwarded_port('http://localhost:8000', opener=_opener(b'{"port": 54321}'))
    assert port == 54321


def test_port_zero_is_returned_not_an_error():
    # 0 == "not ready"; the caller decides what to do, so it must not raise.
    assert fetch_forwarded_port('http://localhost:8000', opener=_opener(b'{"port": 0}')) == 0


def test_trailing_slash_and_endpoint_join():
    captured = []
    fetch_forwarded_port(
        'http://localhost:8000/',
        endpoint='/v1/portforward',
        opener=_opener(b'{"port": 1}', captured=captured),
    )
    assert captured[0][0].full_url == 'http://localhost:8000/v1/portforward'


def test_api_key_header_sent_when_set():
    captured = []
    fetch_forwarded_port('http://localhost:8000', api_key='secret', opener=_opener(b'{"port": 1}', captured=captured))
    assert captured[0][0].get_header('X-api-key') == 'secret'


def test_api_key_header_absent_when_empty():
    captured = []
    fetch_forwarded_port('http://localhost:8000', api_key='', opener=_opener(b'{"port": 1}', captured=captured))
    assert captured[0][0].get_header('X-api-key') is None


def test_timeout_is_passed_through():
    captured = []
    fetch_forwarded_port('http://localhost:8000', timeout=3, opener=_opener(b'{"port": 1}', captured=captured))
    assert captured[0][1] == 3


def test_transport_error_becomes_gluetun_error():
    with pytest.raises(GluetunError):
        fetch_forwarded_port('http://localhost:8000', opener=_opener(exc=socket.timeout('timed out')))


def test_bad_json_becomes_gluetun_error():
    with pytest.raises(GluetunError):
        fetch_forwarded_port('http://localhost:8000', opener=_opener(b'not json'))


def test_missing_port_key_becomes_gluetun_error():
    with pytest.raises(GluetunError):
        fetch_forwarded_port('http://localhost:8000', opener=_opener(b'{"nope": 1}'))


def test_out_of_range_port_becomes_gluetun_error():
    with pytest.raises(GluetunError):
        fetch_forwarded_port('http://localhost:8000', opener=_opener(b'{"port": 70000}'))


def test_boolean_port_rejected():
    # bool is an int subclass; {"port": true} must not become port 1.
    with pytest.raises(GluetunError):
        fetch_forwarded_port('http://localhost:8000', opener=_opener(b'{"port": true}'))


def test_fractional_port_rejected():
    # Must not silently truncate 54321.9 -> 54321.
    with pytest.raises(GluetunError):
        fetch_forwarded_port('http://localhost:8000', opener=_opener(b'{"port": 54321.9}'))


def test_string_port_rejected():
    with pytest.raises(GluetunError):
        fetch_forwarded_port('http://localhost:8000', opener=_opener(b'{"port": "54321"}'))


def test_non_object_json_rejected():
    with pytest.raises(GluetunError):
        fetch_forwarded_port('http://localhost:8000', opener=_opener(b'[1, 2, 3]'))


def test_invalid_utf8_becomes_gluetun_error():
    with pytest.raises(GluetunError):
        fetch_forwarded_port('http://localhost:8000', opener=_opener(b'\xff\xfe\xff'))
