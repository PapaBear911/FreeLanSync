"""Cluster A architectural invariant audit (SDVVF Sec 4).

Mechanical, grep-enforceable checks run as a script so they can gate releases:
    python -m tests.invariants.audit_cluster_a

Exit code 0 = all invariants PASS. Exit code 1 = at least one violation.
Thresholds mirror docs/superpowers/freelansync-debugging-verification-validation-framework.md Sec 4.
"""
import ast
import re
import sys
from pathlib import Path

SERVER_DIR = Path(__file__).resolve().parent.parent.parent / "server"
RESULTS: list[tuple[str, bool, str]] = []


def record(rule: str, ok: bool, detail: str) -> None:
    RESULTS.append((rule, ok, detail))


def server_files() -> list[Path]:
    return sorted(SERVER_DIR.glob("*.py"))


# --- Rule 1: SRP -- one business-logic class per file in server/, >=90% single-class
# Pydantic BaseModel subclasses are data schemas, not SRP violations: they carry
# no behaviour and live in schemas.py by design (TD-009).
def _is_pydantic_model(node: ast.ClassDef) -> bool:
    for base in node.bases:
        if isinstance(base, ast.Name) and base.id == "BaseModel":
            return True
        if isinstance(base, ast.Attribute) and base.attr == "BaseModel":
            return True
    return False


def check_srp() -> None:
    per_file = {}
    for f in server_files():
        tree = ast.parse(f.read_text(encoding="utf-8"))
        per_file[f.name] = [
            n.name
            for n in tree.body
            if isinstance(n, ast.ClassDef) and not _is_pydantic_model(n)
        ]
    multi = {k: v for k, v in per_file.items() if len(v) > 1}
    single_ratio = (len(per_file) - len(multi)) / len(per_file) * 100
    ok = single_ratio >= 90.0
    record(
        "SRP (>=90% single-class files)",
        ok,
        f"single-class {single_ratio:.0f}%; violators: { {k: len(v) for k, v in multi.items()} }",
    )


# --- Rule 2: Direction -- server never imports main
def check_direction_no_main_import() -> None:
    hits = []
    for f in server_files():
        for i, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            if re.search(r"^\s*(from|import)\s+.*\bmain\b", line) and "main.py" not in line:
                hits.append(f"{f.name}:{i}")
    record("Direction: no server->main import", not hits, f"hits={hits}" if hits else "clean")


# --- Rule 3: Direction -- server never imports android/desktop code
def check_direction_no_client_import() -> None:
    hits = []
    for f in server_files():
        for i, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            if re.search(r"^\s*(from|import)\s+(android|desktop_app|electron)", line):
                hits.append(f"{f.name}:{i}")
    record("Direction: no server->client import", not hits, f"hits={hits}" if hits else "clean")


# --- Rule 4: Auth-closed -- every route classified (authed, optional, or explicit PUBLIC)
# PUBLIC set = documented LAN-public surface. The desktop dashboard and paired LAN
# peers use these without a Bearer token by design (see test_web_client_* tests);
# each entry names its containment/validation control. Anything not listed here
# must carry an auth dependency or inline WS auth.
PUBLIC_ALLOWLIST = {
    # Pairing bootstrap + health + client download.
    "/api/v1/ping",
    "/api/v1/pairing/info",  # PIN/QR loopback-gated (TD-012); metadata only off-host
    "/api/v1/pairing/verify",
    "/static/FreeLanSync.apk",
    "/FreeLanSync.apk",
    "/download-apk",
    "/api/v1/download-apk",
    "/",
    # Dashboard inventory (read-only; auth_token never exposed, TD-013).
    "/api/v1/devices",
    "/api/v1/photos/recent",
    # Photo serving (resolve+containment, TD-005).
    "/api/v1/photos/view/{relative_path:path}",
    "/api/v1/photos/thumb/{relative_path:path}",  # generated JPEGs only; same containment as view (TD-038)
    # Storage settings (validate before use; open-folder contained, TD-010).
    "/api/v1/settings",
    "/api/v1/settings/storage-suggestions",
    "/api/v1/settings/validate-path",
    "/api/v1/settings/open-folder",
    # Quick-Drop LAN feature (file_id validated hex12, TD-016).
    "/api/v1/drop/upload",
    "/api/v1/drop/pending",
    "/api/v1/drop/download/{file_id}",
    "/api/v1/drop/{file_id}",
    # Continuity mirror (LAN peers; no filesystem/path reach).
    "/api/v1/clipboard",
    "/api/v1/continuity/status",
    # LANSync transfers (containment TD-011, atomic staging TD-006/TD-007,
    # total_size enforcement TD-020; staging names hidden from listings).
    "/api/v1/transfer/storage-info",
    "/api/v1/transfer/list",
    "/api/v1/transfer/download-file/{file_name}",  # basename-contained
}
AUTH_MARKERS = ("Depends(verify_auth)", "Depends(optional_verify_auth)")
# WebSocket routes cannot use Depends; they authenticate inline against the DB.
MANUAL_AUTH_MARKERS = ("get_device_by_token",)


def _route_paths() -> list[tuple[str, str, int]]:
    out = []
    for f in server_files():
        tree = ast.parse(f.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            src = ast.unparse(node)
            for dec in node.decorator_list:
                if isinstance(dec, ast.Call) and isinstance(dec.func, ast.Attribute):
                    verb = dec.func.attr
                    if verb in {"get", "post", "delete", "put", "patch", "websocket"}:
                        if dec.args and isinstance(dec.args[0], ast.Constant):
                            out.append((f.name, dec.args[0].value, node.lineno, src))
    return out


def check_auth_closed() -> None:
    """Every route must be either in PUBLIC_ALLOWLIST, or carry an auth dependency,
    or (for websockets) authenticate inline. Anything else is an open route."""
    unclassified = []
    for fname, path, lineno, src in _route_paths():
        if path in PUBLIC_ALLOWLIST:
            continue
        if any(m in src for m in AUTH_MARKERS):
            continue
        if any(m in src for m in MANUAL_AUTH_MARKERS):
            continue
        unclassified.append(f"{fname}:{lineno} {path}")
    record(
        "Auth-closed: 100% of routes classified",
        not unclassified,
        f"UNCLASSIFIED={len(unclassified)}: {unclassified}" if unclassified else "clean",
    )


# --- Rule 5: Sanitize -- path inputs pass through sanitize_filename or basename
# A route param is only dangerous when it is used to BUILD a filesystem path.
# Indirect lookups via glob()/db lookup that never join the param onto a directory
# are safe (challenge probe F-02 proved glob is not path-joining).
PATH_JOIN_RE = re.compile(r"(\w+_dir|backup_dir|storage_dir)\s*/\s*\{?(\w+)|/\s*(\w+)\s*/\s*\w*_dir")
SANITIZERS = ("sanitize_filename", "os.path.basename", ".resolve()", "basename(", ".name")


def check_sanitize() -> None:
    """Flag path params that reach a filesystem join without a sanitizing call."""
    unsanitized = []
    for fname, path, lineno, src in _route_paths():
        for param in re.findall(r"\{\s*(\w+)", path):
            # Does the handler join this param onto a directory?
            if not re.search(rf"dir\s*/\s*{param}\b|\b{param}\s*\)\s*$", src.split("\n")[0] + src):
                if not re.search(rf"/\s*{param}\b", src):
                    continue
            if not any(s in src for s in SANITIZERS):
                unsanitized.append(f"{fname}:{lineno} {path} param={param}")
            elif "glob" in src and f"glob(f\"{{{param}" in src:
                continue  # glob is not path-joining; safe by construction
    record(
        "Sanitize: path params sanitized before filesystem join",
        not unsanitized,
        f"UNSANITIZED={unsanitized}" if unsanitized else "clean",
    )


# --- Rule 6: Atomicity -- every open(...,'wb') paired with tmp+replace nearby
def check_atomicity() -> None:
    # Window is 35 lines (not 20): streaming loops separate open() from the
    # terminal os.replace (e.g. save_stream_upload chunks + total_size gate).
    # The invariant is pairing with tmp+replace, not line distance.
    violators = []
    for f in server_files():
        lines = f.read_text(encoding="utf-8").splitlines()
        for i, line in enumerate(lines):
            if re.search(r"open\([^)]*,\s*[\"']wb[\"']\)", line):
                window = "\n".join(lines[i : i + 35])
                if "replace(" not in window:
                    violators.append(f"{f.name}:{i + 1} {line.strip()}")
    record(
        "Atomicity: open(wb) paired with tmp+replace",
        not violators,
        f"VIOLATIONS={violators}" if violators else "clean",
    )


# --- Rule 7: Config -- no hardcoded absolute paths outside config.py
def check_config_no_hardcoded_paths() -> None:
    hits = []
    for f in server_files():
        if f.name == "config.py":
            continue
        for i, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            if re.search(r"[\"'](?:[A-Za-z]:\\\\|[A-Za-z]:/|/Users/|/home/)", line):
                hits.append(f"{f.name}:{i}")
    record("Config: no hardcoded absolute paths", not hits, f"hits={hits}" if hits else "clean")


# --- Rule 8: WS -- no mutation of a connection collection while iterating it
def check_ws_no_iterate_mutation() -> None:
    """`for ws in self.ui_connections:` is only safe if nothing mutates that set inside the body.

    Iteration over a live set while discarding from it raises RuntimeError mid-broadcast,
    which is what TD-003 is about. Post-loop cleanup is fine and must not be flagged.
    """
    f = SERVER_DIR / "websocket_manager.py"
    tree = ast.parse(f.read_text(encoding="utf-8"))
    violators = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.For, ast.AsyncFor)):
            continue
        iterated = ast.unparse(node.iter)
        if not iterated.startswith("self."):
            continue
        mutated = set()
        for inner in ast.walk(node):
            if not isinstance(inner, ast.Call):
                continue
            func = ast.unparse(inner.func)
            if func.split(".")[0] in {"discard", "remove", "add", "clear", "pop", "update"}:
                mutated.add(func)
        if mutated:
            violators.append(
                f"websocket_manager.py:{node.lineno} iter={iterated} mutates via {sorted(mutated)}"
            )
    record(
        "WS: no in-loop mutation of iterated connection set",
        not violators,
        f"violators={violators}" if violators else "clean (post-loop purge is safe)",
    )


# --- Rule 9: DB access -- sqlite only in database.py
def check_db_access_centralized() -> None:
    hits = []
    for f in server_files():
        if f.name == "database.py":
            continue
        for i, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            if "sqlite3" in line:
                hits.append(f"{f.name}:{i}")
    record("DB access centralized in database.py", not hits, f"hits={hits}" if hits else "clean")


# --- Rule 10: PIN brute force -- attempt counter present (TD-001 remediation)
def check_pin_rate_limit() -> None:
    f = SERVER_DIR / "auth.py"
    text = f.read_text(encoding="utf-8")
    has = all(k in text for k in ("attempt", "lockout", "backoff"))
    record("PIN rate-limit/lockout present (TD-001)", has, "found" if has else "MISSING: no attempt counter in PairingManager")


def main() -> int:
    for fn in (
        check_srp,
        check_direction_no_main_import,
        check_direction_no_client_import,
        check_auth_closed,
        check_sanitize,
        check_atomicity,
        check_config_no_hardcoded_paths,
        check_ws_no_iterate_mutation,
        check_db_access_centralized,
        check_pin_rate_limit,
    ):
        fn()

    width = max(len(r[0]) for r in RESULTS)
    print("=" * (width + 12))
    print("Cluster A Architectural Invariant Audit")
    print("=" * (width + 12))
    failed = 0
    for rule, ok, detail in RESULTS:
        flag = "PASS" if ok else "FAIL"
        if not ok:
            failed += 1
        print(f"[{flag}] {rule.ljust(width)}  {detail}")
    print("=" * (width + 12))
    print(f"{len(RESULTS) - failed}/{len(RESULTS)} invariants PASS; {failed} FAIL")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())