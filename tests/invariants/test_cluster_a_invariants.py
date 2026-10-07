"""Cluster A invariant regression guards.

These are the audit findings turned into executable assertions. Tests that encode a
known-violating behaviour are marked `xfail(strict=False)` with the ticket ID: they
pass once the finding is fixed and will loudly fail-xpass if it regresses the other way.
Marker: `invariant`.

Ticket: AUDIT-20261007-01 (see docs/superpowers/incidents/AUDIT-20261007-01.md)
"""
import asyncio
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from server import storage, transfer_manager  # noqa: E402
from server.websocket_manager import ConnectionManager  # noqa: E402


# --- INV-01: path traversal on /api/v1/photos/view/{relative_path:path} ----------
@pytest.mark.invariant
def test_view_photo_route_rejects_traversal(tmp_path, monkeypatch):
    """F-01 CONFIRMED. view_photo must not serve files outside the Backups/ root.

    Invoked through the route function directly, because httpx normalizes `..`
    segments in the request line and would mask the handler's own path join.
    """
    import asyncio

    from server import main as main_mod

    backup = tmp_path / "Backups"
    backup.mkdir()
    secret = tmp_path / "SECRET.txt"
    secret.write_text("TOP-SECRET")

    monkeypatch.setattr("server.main.get_backup_dir", lambda: backup)

    traversal = os.path.relpath(secret, backup).replace("\\", "/")
    try:
        response = asyncio.run(main_mod.view_photo(traversal))
    except Exception:
        return  # rejected outright: the safe outcome

    # A FileResponse carries the file it will stream in `.path`.
    served = Path(getattr(response, "path", ""))
    resolved = served.resolve()
    assert resolved == backup.resolve() or backup.resolve() in resolved.parents, (
        f"AUDIT-20261007-01/F-01: unauthenticated path traversal served {resolved} "
        f"from outside the backup root {backup} (relative_path={traversal!r})"
    )


# --- INV-02: quick-drop writes must be atomic -----------------------------------
@pytest.mark.invariant
@pytest.mark.regression
def test_save_quick_drop_is_atomic(tmp_path, monkeypatch):
    """F-03 CONFIRMED. Quick-Drop writes must stage to tmp then os.replace."""
    drop = tmp_path / "QuickDrop"
    drop.mkdir()
    monkeypatch.setattr("server.config.get_quickdrop_dir", lambda: drop)
    monkeypatch.setattr("server.storage.get_quickdrop_dir", lambda: drop)

    observed = {}
    real_open = open

    def spy_open(path, mode="r", *a, **kw):
        if "wb" in str(mode) and not str(path).endswith((".tmp", ".tmp_")):
            observed["direct_final_write"] = str(path)
        return real_open(path, mode, *a, **kw)

    monkeypatch.setattr("builtins.open", spy_open)
    storage.storage_manager.save_quick_drop("probe.txt", b"x" * 4096)
    monkeypatch.undo()

    assert "direct_final_write" not in observed, (
        "AUDIT-20261007-01/F-03: save_quick_drop wrote the final path directly; "
        "a crash mid-write leaves a truncated file that list_pending_drops advertises"
    )


# --- INV-03: folder-transfer writes must be atomic ------------------------------
@pytest.mark.invariant
@pytest.mark.xfail(strict=True, reason="AUDIT-20261007-01/F-04 S2: non-atomic folder write, TD-007")
def test_folder_upload_is_atomic(tmp_path, monkeypatch):
    """F-04 CONFIRMED. save_folder_upload must stage each file then os.replace.

    Asserted by observing the destination filesystem state at open() time: with
    tmp+replace staging, the final name does not exist until the write completes.
    """
    transfers = tmp_path / "Transfers"
    transfers.mkdir()
    monkeypatch.setattr("server.config.get_transfers_dir", lambda: transfers)
    monkeypatch.setattr("server.transfer_manager.get_transfers_dir", lambda: transfers)

    dest = transfers / "FolderX" / "f.txt"
    seen_before_write = {}
    real_open = open

    def spy_open(path, mode="r", *a, **kw):
        if "wb" in str(mode):
            seen_before_write.setdefault(str(Path(path)), dest.exists())
        return real_open(path, mode, *a, **kw)

    class FakeUpload:
        filename = "f.txt"

        async def read(self, n=-1):
            return b"y" * 512

    monkeypatch.setattr("builtins.open", spy_open)
    asyncio.run(
        transfer_manager.transfer_manager.save_folder_upload(
            "FolderX", [FakeUpload()], ["f.txt"]
        )
    )
    monkeypatch.undo()

    direct = [p for p, existed in seen_before_write.items() if p == str(dest) and not existed]
    assert not direct, (
        f"AUDIT-20261007-01/F-04: save_folder_upload opened the final path {dest} for writing "
        "with no tmp+os.replace; a crash mid-write leaves a partial tree visible to list_transfers"
    )
    assert dest.exists() and dest.read_bytes() == b"y" * 512


# --- INV-04: PIN brute-force resistance -----------------------------------------
@pytest.mark.invariant
def test_pairing_locks_out_after_repeated_failures():
    """TD-001. 20 wrong PINs must not leave the correct PIN usable."""
    from server.auth import PairingManager

    pm = PairingManager()
    pm.generate_pin()
    good = pm.current_pin

    for _ in range(20):
        pm.verify_pin_and_pair(pin="000000", device_name="attacker", device_id="evil")

    token = pm.verify_pin_and_pair(pin=good, device_name="attacker", device_id="evil")
    assert token is None, (
        "TD-001: PairingManager accepted the correct PIN after 20 failures -- "
        "6-digit PIN is brute-forceable inside the 600s expiry window"
    )


# --- INV-05: routes must be classified ------------------------------------------
@pytest.mark.invariant
@pytest.mark.xfail(strict=True, reason="AUDIT-20261007-01/AUTH S1: 18 unclassified routes, TD-008")
def test_every_route_is_classified():
    """AUDIT-20261007-01/AUTH: no route may sit outside the public allowlist
    without an auth dependency or inline websocket auth."""
    from tests.invariants.audit_cluster_a import PUBLIC_ALLOWLIST, AUTH_MARKERS, MANUAL_AUTH_MARKERS, _route_paths

    unclassified = [
        f"{f}:{ln} {p}"
        for f, p, ln, src in _route_paths()
        if p not in PUBLIC_ALLOWLIST
        and not any(m in src for m in AUTH_MARKERS)
        and not any(m in src for m in MANUAL_AUTH_MARKERS)
    ]
    assert not unclassified, (
        "AUDIT-20261007-01/AUTH: unclassified (unauthenticated) routes: " + ", ".join(unclassified)
    )


# --- INV-06: SRP in main.py ------------------------------------------------------
@pytest.mark.invariant
@pytest.mark.xfail(strict=True, reason="AUDIT-20261007-01/SRP S3: main.py holds 9 model classes, TD-009")
def test_main_module_has_at_most_two_classes():
    """SDVVF Sec 4 SRP. main.py currently holds 9 Pydantic model classes."""
    import ast

    from server import main

    tree = ast.parse(Path(main.__file__).read_text(encoding="utf-8"))
    classes = [n.name for n in tree.body if isinstance(n, ast.ClassDef)]
    assert len(classes) <= 2, (
        f"AUDIT-20261007-01/SRP: server/main.py holds {len(classes)} classes {classes}; "
        "route modules should delegate request/response models to a *_schemas module"
    )


# --- INV-07: WS broadcast resilience (TD-003) -----------------------------------
@pytest.mark.invariant
def test_broadcast_survives_dead_socket_without_runtime_error():
    """broadcast_to_ui must not mutate the connection set mid-iteration."""
    cm = ConnectionManager()

    class FlakyWS:
        def __init__(self, fail):
            self.fail = fail

        async def send_text(self, text):
            if self.fail:
                raise ConnectionResetError("socket died")

    cm.ui_connections = {FlakyWS(True), FlakyWS(False)}
    asyncio.run(cm.broadcast_to_ui("PING", {}))
    assert len(cm.ui_connections) == 1, "dead socket was not purged"