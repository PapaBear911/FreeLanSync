"""Review-grep guards for Android findings (TD-033 backup result, TD-028 WS token).

Limitation: the Android module has no unit-test harness (no testImplementation
dependencies installed), so these are source-level guards. Behavior on a device
(retry vs failure toasts, 401 surfacing) still needs a manual device check —
recorded in the tech-debt register rows for TD-033/TD-028.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ANDROID_SRC = ROOT / "android" / "app" / "src" / "main" / "java" / "com" / "photosync" / "app"
WORKER = ANDROID_SRC / "sync" / "FreeLanSyncWorker.kt"
API_CLIENT = ANDROID_SRC / "network" / "FreeLanSyncApiClient.kt"
WS = ANDROID_SRC / "network" / "DeviceBridgeWebSocket.kt"
MAIN_ACTIVITY = ANDROID_SRC / "MainActivity.kt"
DASHBOARD_SCREEN = ANDROID_SRC / "ui" / "DashboardScreen.kt"


def test_worker_success_is_guarded_by_zero_failures():
    """TD-033: Result.success() only when no transient/permanent failures."""
    src = WORKER.read_text(encoding="utf-8")
    # Success branch must sit behind the zero-failure condition.
    assert re.search(
        r"transientFailures == 0 && permanentFailures == 0\s*->\s*\{\s*"
        r"prefs\.setLastSyncTime\(System\.currentTimeMillis\(\)\)",
        src,
    ), "TD-033: worker no longer gates Result.success() on zero upload failures"
    # Failure reason is surfaced to the UI.
    assert "KEY_FAILURE_REASON" in src
    assert "Result.failure(workDataOf(KEY_FAILURE_REASON" in src
    # Transient vs permanent split exists; 4xx is permanent.
    assert "400..499" in src, "TD-033: 4xx responses must be non-retryable"
    assert "Result.retry()" in src


def test_api_client_surfaces_http_status_for_classification():
    src = API_CLIENT.read_text(encoding="utf-8")
    assert "class HttpStatusException" in src
    assert src.count("HttpStatusException(response.code") >= 2, (
        "TD-033: uploadPhoto and checkBatchHashes must surface the HTTP status"
    )


def test_main_activity_toasts_worker_failure_reason():
    """UI must not claim success when the worker reports a failure reason."""
    src = MAIN_ACTIVITY.read_text(encoding="utf-8")
    assert "KEY_FAILURE_REASON" in src
    assert "Backup finished successfully!" in src  # success toast still exists...
    # ...but only in the SUCCEEDED branch, with FAILED showing the reason:
    failed_idx = src.index("WorkInfo.State.FAILED")
    success_idx = src.index("WorkInfo.State.SUCCEEDED")
    assert failed_idx > success_idx
    assert "reason ?:" in src[failed_idx:failed_idx + 400]


def test_ws_url_carries_no_token():
    """TD-028: the device WS URL must not embed the credential."""
    src = WS.read_text(encoding="utf-8")
    assert "client_type=device&token=" not in src
    assert "&token=" not in src.split("fun connect", 1)[-1], (
        "TD-028: token leaked back into the WS query string"
    )
    assert '.header("Authorization", "Bearer $token")' in src, (
        "TD-028: token must travel in the Authorization header"
    )


def test_android_logs_never_interpolate_token():
    """TD-028: no Log/println statement may contain a token interpolation."""
    offenders = []
    for kt in ANDROID_SRC.rglob("*.kt"):
        for i, line in enumerate(kt.read_text(encoding="utf-8").splitlines(), 1):
            stripped = line.strip()
            if re.match(r"(Log\.\w+|println)\(", stripped) and "$token" in line:
                offenders.append(f"{kt.relative_to(ROOT)}:{i}: {stripped}")
    assert not offenders, "TD-028: token interpolated into log statement(s):\n" + "\n".join(offenders)


def test_upload_photo_uses_zero_copy_streaming_without_temp_file():
    """Streaming upload must not create temporary disk files in cacheDir."""
    src = API_CLIENT.read_text(encoding="utf-8")
    assert "createTempFile" not in src, "PhotoSyncApiClient must not create temp files for upload"
    assert "class ContentUriRequestBody" in src
    assert "override fun writeTo(sink: BufferedSink)" in src
    assert "contentResolver.openInputStream(uri)" in src
    assert "ByteArray(8192)" in src


def test_worker_status_code_matrix_routing():
    """Worker handles 400 (rehash retry), 413 (skip), 401/403 (abort & alert), 5xx (retry)."""
    src = WORKER.read_text(encoding="utf-8")
    assert "statusCode == 400" in src
    assert "scanner.calculateSha256(item.uri)" in src
    assert "413 ->" in src
    assert "401, 403 ->" in src
    assert "postAuthErrorNotification" in src
    assert "DeviceBridgeWebSocket.getInstance().sendNotification" in src
    assert "in 400..499 ->" in src


def test_drop_filename_traversal_guarded():
    """TD-030: drop filename must be sanitized with basename and traversal checks."""
    src = DASHBOARD_SCREEN.read_text(encoding="utf-8")
    assert "File(filename).name" in src
    assert "canonicalPath.startsWith" in src
    assert '.."' in src or "'..' in" in src or '".." in' in src or '!it.contains("..")' in src


def test_drop_endpoints_send_authorization_header():
    """TD-031: drop GET endpoints accept token and send Authorization Bearer."""
    src = API_CLIENT.read_text(encoding="utf-8")
    get_drops = src[src.index("fun getPendingDrops"):src.index("fun downloadDropFile")]
    dl_drop = src[src.index("fun downloadDropFile"):]
    assert "token: String?" in get_drops
    assert 'header("Authorization", "Bearer $token")' in get_drops
    assert "token: String?" in dl_drop
    assert 'header("Authorization", "Bearer $token")' in dl_drop


def test_drop_download_is_atomic_and_checks_body():
    """TD-034: downloadDropFile stages via tmp file, checks body, and deletes on failure."""
    src = API_CLIENT.read_text(encoding="utf-8")
    dl_drop = src[src.index("fun downloadDropFile"):]
    assert ".tmp_" in dl_drop
    assert "tempFile.delete()" in dl_drop
    assert "tempFile.renameTo" in dl_drop
    assert "Empty response body" in dl_drop or "throw IOException" in dl_drop


def test_worker_uses_parallel_coroutine_semaphore_pool():
    """Worker uploads via bounded coroutine pool (Semaphore) for gigabit concurrency."""
    src = WORKER.read_text(encoding="utf-8")
    assert "Semaphore(permits = 4)" in src or "Semaphore(4)" in src
    assert "supervisorScope" in src
    assert "awaitAll()" in src
    assert "withPermit" in src
    assert "AtomicInteger" in src


def test_user_guide_dialog_integrated():
    """Android app provides accessible in-app guide on Pairing and Dashboard screens."""
    guide_file = ANDROID_SRC / "ui" / "UserGuideDialog.kt"
    assert guide_file.exists()
    pairing_src = (ANDROID_SRC / "ui" / "PairingScreen.kt").read_text(encoding="utf-8")
    assert "UserGuideDialog" in pairing_src
    assert "showGuide" in pairing_src
    dash_src = DASHBOARD_SCREEN.read_text(encoding="utf-8")
    assert "UserGuideDialog" in dash_src
    assert "showGuide" in dash_src




