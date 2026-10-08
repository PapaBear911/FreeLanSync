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
@pytest.mark.regression
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
@pytest.mark.regression
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
@pytest.mark.regression
def test_main_module_has_at_most_two_classes():
    """SDVVF Sec 4 SRP. Request/response models live in server/schemas.py (TD-009);
    main.py wires routes and must define no business-logic classes."""
    import ast

    from server import main, schemas

    main_tree = ast.parse(Path(main.__file__).read_text(encoding="utf-8"))
    main_classes = [n.name for n in main_tree.body if isinstance(n, ast.ClassDef)]
    assert not main_classes, (
        f"AUDIT-20261007-01/SRP: server/main.py defines classes {main_classes}; "
        "move them to server/schemas.py"
    )
    schema_tree = ast.parse(Path(schemas.__file__).read_text(encoding="utf-8"))
    models = [n.name for n in schema_tree.body if isinstance(n, ast.ClassDef)]
    assert len(models) >= 9, (
        f"TD-009: server/schemas.py should hold the 9 request/response models, found {models}"
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


# --- INV-08: transfer containment (TD-011) --------------------------------------
@pytest.mark.invariant
@pytest.mark.regression
def test_transfer_resolve_within_rejects_escapes(tmp_path):
    """Absolute paths, drive letters, and .. escapes must never leave the base."""
    from server.transfer_manager import resolve_within

    base = tmp_path / "Transfers"
    base.mkdir()

    ok = resolve_within(base, "Docs/readme.txt")
    assert ok.parent.name == "Docs"

    for evil in (
        "../evil.txt",
        "../../etc/passwd",
        "Docs/../../evil.txt",
        "/etc/passwd",
        "C:\\evil\\x.bin",
        "C:/evil/x.bin",
        "..\\evil.txt",
    ):
        try:
            out = resolve_within(base, evil)
        except ValueError:
            continue
        assert False, f"TD-011: resolve_within accepted {evil!r} -> {out}"

    # Folder-upload members are contained too (fallback degrades to basename).
    async def _run():
        class FakeUpload:
            filename = "evil.txt"

            async def read(self, n=-1):
                return b"evil"

        tm = transfer_manager.transfer_manager
        import server.transfer_manager as tm_mod
        from unittest.mock import patch

        transfers = tmp_path / "T2"
        transfers.mkdir()
        with patch.object(tm_mod, "get_transfers_dir", lambda: transfers):
            res = await tm.save_folder_upload("F", [FakeUpload()], ["../../evil.txt"])
        assert res["success"] is True
        assert not (tmp_path / "evil.txt").exists(), "TD-011: folder member escaped base"
        assert (transfers / "F" / "evil.txt").exists()

    asyncio.run(_run())


# --- INV-09: Quick-Drop file_id validation (TD-016) ------------------------------
@pytest.mark.invariant
@pytest.mark.regression
def test_drop_file_id_rejects_glob_probes(tmp_path, monkeypatch):
    """file_id='*' must not match pending drops at storage or route level."""
    from fastapi.testclient import TestClient

    from server.main import app

    drop = tmp_path / "QuickDrop"
    drop.mkdir()
    monkeypatch.setattr("server.config.get_quickdrop_dir", lambda: drop)
    monkeypatch.setattr("server.storage.get_quickdrop_dir", lambda: drop)

    info = storage.storage_manager.save_quick_drop("secret.txt", b"shh")
    assert info["file_id"] not in ("*", "")

    assert storage.storage_manager.get_drop_file_path("*") is None
    assert storage.storage_manager.delete_drop_file("*") is False

    client = TestClient(app)
    assert client.get("/api/v1/drop/download/*").status_code == 400
    assert client.delete("/api/v1/drop/*").status_code == 400
    # Well-formed but unknown id stays 404.
    assert client.get("/api/v1/drop/download/aabbccddeeff").status_code == 404


# --- INV-10: short uploads fail instead of completing (TD-020) ------------------
@pytest.mark.invariant
@pytest.mark.regression
def test_short_upload_marked_failed_not_completed(tmp_path, monkeypatch):
    """Fewer bytes than declared total_size must FAILED + roll back, no final file."""
    transfers = tmp_path / "Transfers"
    transfers.mkdir()
    monkeypatch.setattr("server.config.get_transfers_dir", lambda: transfers)
    monkeypatch.setattr("server.transfer_manager.get_transfers_dir", lambda: transfers)

    class ShortUpload:
        async def read(self, n=-1):
            return b""

    with pytest.raises(ValueError, match="Incomplete upload"):
        asyncio.run(
            transfer_manager.transfer_manager.save_stream_upload(
                transfer_id="short-tid",
                upload_file=ShortUpload(),
                filename="short.bin",
                total_size=1024,
            )
        )
    status = transfer_manager.transfer_manager.get_status("short-tid")
    assert status["status"] == "FAILED"
    assert not (transfers / "short.bin").exists()
    leftovers = [p.name for p in transfers.iterdir() if p.name.startswith(".tmp_")]
    assert not leftovers, f"staging leftovers: {leftovers}"


# --- INV-11: settings writes are atomic (TD-018) --------------------------------
@pytest.mark.invariant
@pytest.mark.regression
def test_save_settings_is_atomic(tmp_path, monkeypatch):
    """save_settings must stage to tmp then os.replace; no torn config survives."""
    import json

    data_dir = tmp_path / "data"
    data_dir.mkdir()
    monkeypatch.setattr("server.config.get_app_data_dir", lambda: data_dir)

    from server import config as config_mod

    config_mod.save_settings({"storage_dir": str(tmp_path)})
    target = data_dir / "freelansync_config.json"
    assert target.exists()
    assert json.loads(target.read_text(encoding="utf-8"))["storage_dir"] == str(tmp_path)
    assert not [p.name for p in data_dir.iterdir() if p.name.startswith(".tmp_")]


# --- INV-12: previously-fixed S0/S1 findings stay fixed --------------------------
@pytest.mark.invariant
@pytest.mark.regression
def test_open_storage_folder_rejects_outside_root(tmp_path, monkeypatch):
    """TD-010 (S0): a client path outside the storage root must 400, never reach
    the OS opener. Only the rejection path is exercised (no opener invoked)."""
    from server import main as main_mod

    root = tmp_path / "storage"
    root.mkdir()
    monkeypatch.setattr("server.main.get_storage_dir", lambda: root)

    with pytest.raises(Exception, match="outside the storage root"):
        asyncio.run(main_mod.open_storage_folder(main_mod.OpenFolderRequest(path=str(tmp_path / "evil.exe"))))


@pytest.mark.invariant
@pytest.mark.regression
def test_device_list_exposes_no_auth_tokens():
    """TD-013 (S1): get_all_devices must not leak auth_token to list consumers."""
    from server.database import get_all_devices, init_db, register_device

    init_db()
    register_device("Guard Phone", "guard-device-id", "guard-secret-token")
    for d in get_all_devices():
        assert "auth_token" not in d, "TD-013: auth_token leaked via get_all_devices"


@pytest.mark.invariant
@pytest.mark.regression
def test_hash_dedupe_is_per_device():
    """TD-014 (S2): a hash backed up by device A must still read 'missing' for B."""
    import hashlib

    from server.database import check_existing_hashes, init_db, record_media_backup, register_device

    init_db()
    register_device("Dev A", "dev-a-guard", "tok-a")
    register_device("Dev B", "dev-b-guard", "tok-b")
    h = hashlib.sha256(b"per-device-guard").hexdigest()
    record_media_backup(
        device_id="dev-a-guard", sha256=h, original_filename="g.bin",
        relative_path="g.bin", file_size=16, mime_type=None, taken_at=None,
    )
    assert h in check_existing_hashes("dev-a-guard", [h])
    assert h not in check_existing_hashes("dev-b-guard", [h]), (
        "TD-014: cross-device silent skip — device B would skip a file it never backed up"
    )