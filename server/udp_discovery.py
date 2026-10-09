"""UDP broadcast discovery responder for mobile clients.

Fallback discovery path when mDNS/NSD is unavailable (common on dual-band
routers, AP/client isolation, or Android builds with broken mDNS). Mobile
clients broadcast ``FREELANSYNC_DISCOVER_V1`` to port 8079/UDP; any host
running the FreeLanSync server answers with a small JSON envelope so the
client learns the HTTP port (and can then validate via ``GET /api/v1/ping``).
"""
import json
import socket
import threading
from typing import Optional

from .config import DISCOVERY_UDP_PORT, SERVICE_NAME, SERVER_PORT, get_local_ip

DISCOVERY_MAGIC = b"FREELANSYNC_DISCOVER_V1"


class UdpDiscoveryResponder:
    """Daemon-thread UDP responder answering LAN discovery probes."""

    def __init__(self, port: int = DISCOVERY_UDP_PORT, host: str = "0.0.0.0"):
        self.port = port
        self.host = host
        self._sock: Optional[socket.socket] = None
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()

    @staticmethod
    def build_response() -> dict:
        """Discovery envelope. Deliberately contains NO credentials/PIN (TD-012)."""
        return {
            "service": "freelansync",
            "name": SERVICE_NAME,
            "version": "1.1.0",
            "host": get_local_ip(),
            "port": SERVER_PORT,
            "discovery": "udp",
        }

    @staticmethod
    def is_probe(data: bytes) -> bool:
        return data is not None and data.strip().startswith(DISCOVERY_MAGIC)

    def start(self) -> bool:
        with self._lock:
            if self._thread is not None:
                return True
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                # No SO_REUSEADDR: a second server instance on the same port must
                # fail loudly (gracefully, via start() -> False) instead of silently
                # sharing the discovery port.
                sock.bind((self.host, self.port))
                sock.settimeout(1.0)
                # Resolve the actual port when an ephemeral port (0) was requested.
                self.port = sock.getsockname()[1]
                self._sock = sock
            except Exception as e:
                print(f"[UDP-Discovery] Warning: failed to bind UDP {self.host}:{self.port}: {e}")
                return False

            self._stop_event.clear()
            self._thread = threading.Thread(
                target=self._loop, name="freelansync-udp-discovery", daemon=True
            )
            self._thread.start()
            print(f"[UDP-Discovery] Listening on {self.host}:{self.port}")
            return True

    def _loop(self):
        while not self._stop_event.is_set():
            sock = self._sock
            if sock is None:
                break
            try:
                data, addr = sock.recvfrom(2048)
            except socket.timeout:
                continue
            except OSError:
                break
            try:
                if not self.is_probe(data):
                    continue
                payload = json.dumps(self.build_response()).encode("utf-8")
                sock.sendto(payload, addr)
            except Exception:
                # Never let a malformed datagram kill the responder thread.
                continue

    def stop(self):
        with self._lock:
            self._stop_event.set()
            sock = self._sock
            self._sock = None
            thread = self._thread
            self._thread = None
        if sock is not None:
            try:
                sock.close()
            except Exception:
                pass
        if thread is not None and thread.is_alive():
            thread.join(timeout=3.0)


udp_discovery = UdpDiscoveryResponder()
