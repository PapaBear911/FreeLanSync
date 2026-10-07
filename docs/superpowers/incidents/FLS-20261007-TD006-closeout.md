# FLS-20261007-TD006-closeout — Strict-XPASS on Quick-Drop atomic-write guard
**Status:** CLOSED | **Severity:** S2 | **Loops:** `loops_vd:0 loops_cf:0 loops_total:1`
**Date:** 2026-10-08 | **Scope:** `server/storage.py`, `tests/invariants/test_cluster_a_invariants.py`

## What broke
`python -m pytest tests/ -q` failed with `[XPASS(strict)] test_save_quick_drop_is_atomic`.
The guard expected Quick-Drop writes to be non-atomic, but the code already writes safely.

## Why
Someone fixed the write (stage to a temp file, then atomic rename) but left the old
"expected to fail" marker on the test. Strict mode turns that surprise-pass into a failure.
Tracing also found a second half: the pending-drops lister matched staging temp files,
so a crash leftover could look like a finished file.

## What changed
- `server/storage.py` — pending-drops list now skips staging names (`.tmp_*` prefix).
  Narrow prefix check only, so a real file named `notes.tmp` still shows up.
- `tests/invariants/test_cluster_a_invariants.py` — guard promoted from
  `xfail(strict=True)` to `regression`. It now fails only if atomicity regresses.
- TD-006 stays OPEN in the debt register until the audit doc + register are updated
  in a follow-up; the code defect itself is closed with proof below.

```mermaid
flowchart LR
    Upload[drop upload] --> Stage[write .tmp file]
    Stage --> Replace[os.replace to final]
    Replace --> List[list_pending_drops]
    List -. crash leftover .tmp shown as done .-> Leak((phone gets truncated file))
    Fix{{skip .tmp_ in lister + promote guard}} -.fixes.-> List
```

## Proof
- Cause ← repro: `pytest tests/invariants/test_cluster_a_invariants.py::test_save_quick_drop_is_atomic -q -rxX` → `[XPASS(strict)]` before, `passed` after.
- Fixed ← failing-then-passing test: `test_save_quick_drop_is_atomic` + `tests/test_websocket_and_drop.py` → `7 passed`.
- No regression: `pytest tests/invariants/ -q -rxX` → `4 passed, 3 xfailed` (TD-007/TD-008/TD-009 untouched).
- Challenge: staging leftover hidden; legit `.tmp`-suffixed final file still listed; `file_id="*"` glob-escape is TD-016, out of scope.
- Log: `docs/superpowers/loops/FLS-20261007-TD006-closeout.log.md`. Lesson: `docs/superpowers/lessons.md`.
