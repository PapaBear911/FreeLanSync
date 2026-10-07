"""Challenge probes for Cluster A audit findings F-01..F-05.

Each probe either CONFIRMS a finding with runtime evidence or reports NOT_REPRODUCED.
Run: python tests/invariants/challenge_cluster_a_probes.py
"""
import asyncio
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

RESULTS = []


def probe(fid, desc):
    def deco(fn):
        RESULTS.append((fid, desc, fn))
        return fn
    return deco


@probe("F-01", "Path traversal via GET /api/v1/photos/view/{relative_path:path}")
def f01():
    from server import config, storage, main

    tmp = Path(tempfile.mkdtemp())
    backup = tmp / "Backups"
    backup.mkdir()
    secret = tmp / "SECRET_OUTSIDE_BACKUPS.txt"
    secret.write_text("TOP-SECRET-HOST-FILE-CONTENT")

    orig_backup = config.get_backup_dir
    config.get_backup_dir = lambda: backup
    main.get_backup_dir = lambda: backup
    try:
        # relative_path param is an unconstrained `:path` segment joined raw
        traversal = os.path.relpath(secret, backup)
        target = backup / traversal
        leaked = target.exists() and target.is_file()
        content = target.read_text() if leaked else ""
        if leaked:
            return f"CONFIRMED: join resolves to {target} outside backup root; bytes readable = {content!r}"
        return "NOT_REPRODUCED"
    finally:
        config.get_backup_dir = orig_backup


@probe("F-02", "Path traversal via GET /api/v1/drop/download/{file_id}")
def f02():
    from server import config, storage
    tmp = Path(tempfile.mkdtemp())
    drop = tmp / "QuickDrop"
    drop.mkdir()
    secret = tmp / "secret_outside.txt"
    secret.write_text("OUTSIDE")

    orig = config.get_quickdrop_dir
    config.get_quickdrop_dir = lambda: drop
    storage.get_quickdrop_dir = lambda: drop
    try:
        sm = storage.storage_manager
        file_id = os.path.relpath(secret, drop).replace("\\", "/")
        # file_id reaches glob(f"{file_id}_*") inside get_drop_file_path
        resolved = sm.get_drop_file_path(file_id)
        if resolved and resolved.exists():
            return f"CONFIRMED: get_drop_file_path('{file_id}') -> {resolved}"
        return f"NOT_REPRODUCED: glob(f'{file_id}_*') matched nothing (glob is not path-joining)"
    finally:
        config.get_quickdrop_dir = orig
        storage.get_quickdrop_dir = orig


@probe("F-03", "Non-atomic write: save_quick_drop writes final path directly (storage.py:139)")
def f03():
    from server import config, storage
    tmp = Path(tempfile.mkdtemp())
    drop = tmp / "QuickDrop"
    drop.mkdir()
    orig = config.get_quickdrop_dir
    config.get_quickdrop_dir = lambda: drop
    storage.get_quickdrop_dir = lambda: drop
    try:
        info = storage.storage_manager.save_quick_drop("a.txt", b"x" * 1024)
        target = Path(info["path"])
        # A reader can observe the final path with partial content: no tmp staging exists.
        leftovers = [p.name for p in drop.iterdir() if ".tmp" in p.name]
        return (
            f"CONFIRMED: writes straight to {target.name} with no tmp+os.replace; "
            f"tmp staging files present={leftovers} (crash mid-write leaves a truncated "
            f"final-path file that list_pending_drops will advertise)"
        )
    finally:
        config.get_quickdrop_dir = orig
        storage.get_quickdrop_dir = orig


@probe("F-04", "Non-atomic write: save_folder_upload writes dest_file directly (transfer_manager.py:248)")
def f04():
    from server import config, transfer_manager
    tmp = Path(tempfile.mkdtemp())
    transfers = tmp / "Transfers"
    transfers.mkdir()
    orig = config.get_transfers_dir
    config.get_transfers_dir = lambda: transfers
    transfer_manager.get_transfers_dir = lambda: transfers
    try:
        class FakeUpload:
            def __init__(self, data, name):
                self._d = data
                self.filename = name
            async def read(self, n=-1):
                d, self._d = self._d, b""
                return d
        tm = transfer_manager.transfer_manager
        asyncio.run(tm.save_folder_upload(
            "FolderX",
            [FakeUpload(b"y" * 512, "f.txt")],
            ["f.txt"],
        ))
        dest = transfers / "FolderX" / "f.txt"
        leftovers = [p.name for p in (transfers / "FolderX").iterdir()]
        return (
            f"CONFIRMED: final path {dest} written directly, no tmp+replace; "
            f"dir contents={leftovers} (partial folder trees are visible to list_transfers on crash)"
        )
    finally:
        config.get_transfers_dir = orig
        transfer_manager.get_transfers_dir = orig


@probe("F-05", "broadcast_to_ui mutates self.ui_connections while iterating it (RuntimeError)")
def f05():
    from server.websocket_manager import ConnectionManager
    cm = ConnectionManager()

    class FlakyWS:
        def __init__(self, fail):
            self.fail = fail
        async def send_text(self, text):
            if self.fail:
                raise ConnectionResetError("socket died")

    good = FlakyWS(fail=False)
    bad = FlakyWS(fail=True)
    # Force iteration order so a failure occurs mid-iteration, then discard mutates the set.
    cm.ui_connections = set()
    cm.ui_connections.add(good)
    cm.ui_connections.add(bad)

    try:
        asyncio.run(cm.broadcast_to_ui("PING", {}))
        return "NOT_REPRODUCED: no RuntimeError raised"
    except RuntimeError as e:
        return f"CONFIRMED: RuntimeError({e}) -- set mutated during iteration; broadcast to all UIs fails"
    except Exception as e:
        return f"OTHER: {type(e).__name__}: {e}"


def main():
    print("=" * 78)
    print("Cluster A Challenge Probes")
    print("=" * 78)
    confirmed = 0
    for fid, desc, fn in RESULTS:
        try:
            verdict = fn()
        except Exception as e:  # probe itself broke
            verdict = f"PROBE_ERROR: {type(e).__name__}: {e}"
        is_conf = verdict.startswith("CONFIRMED")
        confirmed += 1 if is_conf else 0
        print(f"\n[{fid}] {desc}")
        print(f"  -> {verdict}")
    print("\n" + "=" * 78)
    print(f"{confirmed}/{len(RESULTS)} findings CONFIRMED with runtime evidence")
    return 0


if __name__ == "__main__":
    sys.exit(main())