"""Authentication, 6-digit PIN management, and QR Code generation."""
import secrets
import time
import io
import qrcode
import qrcode.image.svg
import json
import re
from typing import Dict, Optional, Tuple
from .config import get_local_ip, SERVER_PORT
from .database import register_device

class PairingManager:
    MAX_ATTEMPTS = 5
    LOCKOUT_BASE_SECONDS = 30
    LOCKOUT_MAX_SECONDS = 600

    def __init__(self, pin_expiry_seconds: int = 600):
        self.pin_expiry_seconds = pin_expiry_seconds
        self.current_pin: Optional[str] = None
        self.pin_created_at: float = 0.0
        # TD-001: brute-force defence — failed attempt counter + lockout backoff.
        self.failed_attempts: int = 0
        self.locked_until: float = 0.0

    def generate_pin(self) -> str:
        """Generate a random 6-digit PIN."""
        self.current_pin = f"{secrets.randbelow(900000) + 100000}"
        self.pin_created_at = time.time()
        return self.current_pin

    def get_or_create_pin(self) -> str:
        """Get the active PIN or generate a fresh one if expired."""
        if not self.current_pin or (time.time() - self.pin_created_at) > self.pin_expiry_seconds:
            return self.generate_pin()
        return self.current_pin

    def verify_pin_and_pair(self, pin: str, device_name: str, device_id: str) -> Optional[str]:
        """Validate PIN and generate a secure permanent device auth token."""
        if not self.current_pin:
            return None

        if (time.time() - self.pin_created_at) > self.pin_expiry_seconds:
            self.current_pin = None
            self.failed_attempts = 0
            self.locked_until = 0.0
            return None

        # TD-001: reject during lockout regardless of PIN correctness.
        if time.time() < self.locked_until:
            return None

        if secrets.compare_digest(self.current_pin.strip(), pin.strip()):
            self.failed_attempts = 0
            self.locked_until = 0.0
            auth_token = secrets.token_urlsafe(32)
            register_device(device_name=device_name, device_id=device_id, auth_token=auth_token)
            # Cycle PIN after successful pairing for security
            self.generate_pin()
            return auth_token

        # Wrong PIN: count the attempt and apply exponential backoff lockout.
        self.failed_attempts += 1
        if self.failed_attempts >= self.MAX_ATTEMPTS:
            backoff = min(
                self.LOCKOUT_MAX_SECONDS,
                self.LOCKOUT_BASE_SECONDS * (2 ** (self.failed_attempts - self.MAX_ATTEMPTS)),
            )
            self.locked_until = time.time() + backoff
        return None

    def get_pairing_info(self) -> Dict[str, any]:
        """Return pairing metadata including local IP, port, PIN, and QR Code payload."""
        pin = self.get_or_create_pin()
        local_ip = get_local_ip()
        payload = {
            "version": 1,
            "host": local_ip,
            "port": SERVER_PORT,
            "pin": pin,
            "service": "freelansync"
        }
        return {
            "pin": pin,
            "host": local_ip,
            "port": SERVER_PORT,
            "expires_in": max(0, int(self.pin_expiry_seconds - (time.time() - self.pin_created_at))),
            "qr_payload": json.dumps(payload)
        }

    def _matrix_to_svg(self, text_payload: str, size_px: int = 240) -> str:
        img = qrcode.make(text_payload, image_factory=qrcode.image.svg.SvgPathImage, border=2)
        svg_xml = img.to_string().decode("utf-8")
        # Replace default mm width/height with target pixel size and dashboard styling
        return re.sub(
            r'<svg\s+width="[^"]*"\s+height="[^"]*"',
            f'<svg width="{size_px}" height="{size_px}" class="rounded-xl shadow-md bg-white p-2"',
            svg_xml,
            count=1
        )

    def generate_qr_svg(self) -> str:
        """Generate QR Code as SVG string for the Web Dashboard pairing."""
        info = self.get_pairing_info()
        return self._matrix_to_svg(info["qr_payload"], size_px=240)

    def generate_apk_download_qr_svg(self) -> str:
        """Generate QR Code for downloading the Android APK directly."""
        local_ip = get_local_ip()
        apk_url = f"http://{local_ip}:{SERVER_PORT}/static/FreeLanSync.apk"
        return self._matrix_to_svg(apk_url, size_px=220)

pairing_manager = PairingManager()
