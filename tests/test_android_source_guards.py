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
WORKER = ANDROID_SRC / "sync" / "PhotoSyncWorker.kt"
API_CLIENT = ANDROID_SRC / "network" / "PhotoSyncApiClient.kt"
WS = ANDROID_SRC / "network" / "DeviceBridgeWebSocket.kt"
MAIN_ACTIVITY = ANDROID_SRC / "MainActivity.kt"


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
