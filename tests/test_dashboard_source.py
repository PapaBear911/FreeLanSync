"""Source-level guards for the dashboard (server/static/index.html, TD-040).

Static HTML with inline script — grep-style guards match the house pattern.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INDEX = ROOT / "server" / "static" / "index.html"


def _refresh_data_body(src: str) -> str:
    m = re.search(r"function refreshData\([^)]*\)\s*\{(.*?)\n    \}", src, re.S)
    assert m, "refreshData function not found in index.html"
    return m.group(1)


def test_refresh_data_has_no_unconditional_show_toast():
    """The 12s interval must not pop a toast; only the manual button may."""
    src = INDEX.read_text(encoding="utf-8")
    body = _refresh_data_body(src)
    unguarded = [
        line for line in body.splitlines()
        if re.match(r"\s*showToast\(", line)
    ]
    assert not unguarded, f"refreshData toasts unconditionally: {unguarded}"
    assert "if (manual) showToast('Dashboard refreshed')" in body
    assert 'onclick="refreshData(true)"' in src, (
        "manual Refresh button must pass the manual flag"
    )


def test_ws_reconnect_backoff_has_cap():
    src = INDEX.read_text(encoding="utf-8")
    assert "const WS_BACKOFF_MAX_MS" in src, "missing WS backoff cap constant"
    assert "Math.min(wsReconnectDelayMs * 2, WS_BACKOFF_MAX_MS)" in src, (
        "WS reconnect delay must be exponentially capped by WS_BACKOFF_MAX_MS"
    )
    assert "setTimeout(connectWebSocket, wsReconnectDelayMs)" in src


def test_polling_skips_hidden_tab_and_refreshes_on_visible():
    src = INDEX.read_text(encoding="utf-8")
    assert "setInterval(() => { if (!document.hidden) refreshData(); }, 12000);" in src
    assert "document.addEventListener('visibilitychange'" in src


def test_unreachable_banner_and_fetch_failure_tracking_exist():
    src = INDEX.read_text(encoding="utf-8")
    assert 'id="serverStatusBanner"' in src
    assert 'id="serverStatusText"' in src
    assert "noteFetchFailure()" in src
    assert "noteFetchSuccess()" in src
    assert "FETCH_FAILURE_THRESHOLD" in src
    # Every finding-listed fetcher reports failures (no silent console.error only).
    for fn in ("fetchDevices", "fetchRecentMedia", "loadPendingDrops",
               "fetchPairingInfo", "fetchStorageSettings"):
        m = re.search(rf"function {fn}\(\)[^{{]*\{{(.*?)\n    \}}", src, re.S)
        assert m, f"{fn} not found"
        assert "noteFetchFailure()" in m.group(1), f"{fn} swallows failures"


def test_gallery_signature_and_pagination_untouched():
    """The refresh changes must not break the TD-038 signature guard or paging."""
    src = INDEX.read_text(encoding="utf-8")
    assert "lastGallerySignature" in src
    assert "GALLERY_PAGE_SIZE" in src
    assert "function loadMoreGallery" in src
    assert "initGalleryInfiniteScroll" in src
