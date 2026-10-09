"""Pairing payload (QR / deep-link) + UDP discovery responder tests.

Covers:
- GET /api/v1/pairing/info serves a parseable freelansync:// deep link on loopback
- PIN-bearing fields remain TD-012 gated for remote LAN peers
- UdpDiscoveryResponder answers FREELANSYNC_DISCOVER_V1 probes with a JSON envelope
- Non-probe datagrams are ignored; responder start/stop is idempotent
"""
import json
import socket
import time
from urllib.parse import urlparse, parse_qs

import pytest
from fastapi.testclient import TestClient

from server.main import app
from server.auth import build_pairing_uri, pairing_manager
from server.config import PAIRING_SCHEME, SERVER_PORT
from server.udp_discovery import UdpDiscoveryResponder, DISCOVERY_MAGIC, udp_discovery

client = TestClient(app)
# Simulates a real LAN client: non-loopback ASGI peer identity.
remote_client = TestClient(app, client=("192.168.1.50", 41234))


def _six_digit_pin() -> str:
    pin = pairing_manager.get_or_create_pin()
    assert len(pin) == 6
    return pin


def test_build_pairing_uri_format():
    uri = build_pairing_uri("192.168.1.42", 8080, "654321")
    parsed = urlparse(uri)
    assert parsed.scheme == PAIRING_SCHEME
    assert parsed.hostname == "192.168.1.42"
    assert parsed.port == 8080
    assert parse_qs(parsed.query)["pin"] == ["654321"]


def test_pairing_info_serves_pairing_uri_on_loopback():
    res = client.get("/api/v1/pairing/info")
    assert res.status_code == 200
    data = res.json()

    # Deep link present and well-formed for the local operator.
    assert "pairing_uri" in data, "loopback client must receive the freelansync:// payload"
    uri = data["pairing_uri"]
    parsed = urlparse(uri)
    assert parsed.scheme == PAIRING_SCHEME
    assert parsed.port == data["port"]
    assert parse_qs(parsed.query)["pin"] == [data["pin"]]
    assert parse_qs(parsed.query)["service"] == ["freelansync"]
    assert data["pairing_uri_scheme"] == PAIRING_SCHEME

    # The JSON QR payload and the deep link describe the same host/port/pin.
    qr = json.loads(data["qr_payload"])
    assert qr["host"] == data["host"]
    assert qr["port"] == data["port"] == qr["port"] == SERVER_PORT
    assert qr["pin"] == data["pin"]
    assert qr["service"] == "freelansync"

    # Round-trip: a client parsing the URI recovers the QR payload values.
    q = parse_qs(parsed.query)
    assert qr["host"] == parsed.hostname
    assert str(qr["port"]) == str(parsed.port)
    assert qr["pin"] == q["pin"][0]


def test_pairing_uri_hidden_from_remote_lan_peer_td012():
    res = remote_client.get("/api/v1/pairing/info")
    assert res.status_code == 200
    data = res.json()
    # Connection metadata still available off-host...
    assert "host" in data and "port" in data
    # ...but every PIN-bearing artifact stays loopback-only.
    for secret in ("pin", "qr_payload", "qr_svg", "pairing_uri", "pairing_uri_scheme"):
        assert secret not in data, f"TD-012: {secret} leaked to remote LAN peer"


def test_udp_probe_matching():
    assert UdpDiscoveryResponder.is_probe(DISCOVERY_MAGIC)
    assert UdpDiscoveryResponder.is_probe(DISCOVERY_MAGIC + b"  \n")
    assert not UdpDiscoveryResponder.is_probe(b"FREELANSYNC")
    assert not UdpDiscoveryResponder.is_probe(b"")
    assert not UdpDiscoveryResponder.is_probe(None)
    assert not UdpDiscoveryResponder.is_probe(b'{"service":"x"}')


def test_udp_discovery_responder_roundtrip():
    responder = UdpDiscoveryResponder(port=0, host="127.0.0.1")
    assert responder.start() is True
    assert responder.start() is True  # idempotent
    assert responder.port > 0
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as client_sock:
            client_sock.settimeout(2.0)
            client_sock.sendto(DISCOVERY_MAGIC, ("127.0.0.1", responder.port))
            data, addr = client_sock.recvfrom(2048)
        envelope = json.loads(data.decode("utf-8"))
        assert envelope["service"] == "freelansync"
        assert envelope["port"] == SERVER_PORT
        assert envelope["discovery"] == "udp"
        assert "pin" not in envelope and "auth_token" not in envelope, "discovery must not leak credentials"
        assert addr[0] == "127.0.0.1"
    finally:
        responder.stop()


def test_udp_responder_ignores_non_probe_datagrams():
    responder = UdpDiscoveryResponder(port=0, host="127.0.0.1")
    assert responder.start() is True
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as client_sock:
            client_sock.settimeout(0.6)
            client_sock.sendto(b"garbage-not-a-probe", ("127.0.0.1", responder.port))
            with pytest.raises(socket.timeout):
                client_sock.recvfrom(2048)
        # Probe after garbage still works (thread survived the bad datagram).
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as client_sock:
            client_sock.settimeout(2.0)
            client_sock.sendto(DISCOVERY_MAGIC, ("127.0.0.1", responder.port))
            data, _ = client_sock.recvfrom(2048)
        assert json.loads(data.decode("utf-8"))["service"] == "freelansync"
    finally:
        responder.stop()


def test_udp_responder_stop_is_safe_without_start():
    orphan = UdpDiscoveryResponder(port=0, host="127.0.0.1")
    orphan.stop()  # must not raise
    # Singleton is also stoppable in its default (never started) state.
    udp_discovery.stop()


def test_udp_responder_reports_busy_port_without_crashing():
    # Occupy a port, then confirm start() fails gracefully (returns False, no raise).
    blocker = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        blocker.bind(("127.0.0.1", 0))
        busy_port = blocker.getsockname()[1]
        responder = UdpDiscoveryResponder(port=busy_port, host="127.0.0.1")
        assert responder.start() is False
        assert responder._sock is None
        responder.stop()
    finally:
        blocker.close()
