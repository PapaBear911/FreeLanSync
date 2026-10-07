# Defect Loop Log — FLS-20261007-TD006-closeout
# Defect restated: `pytest tests/ -q` fails strict-XPASS on
# tests/invariants/test_cluster_a_invariants.py::test_save_quick_drop_is_atomic —
# save_quick_drop already stages via tmp+os.replace but its guard still expects failure.
# Mode: act. Budget: N=8 steps, one written-reason extension max.
# step/action/result — append-only; this file is the loop state.
1/recall/matched TD-006 + F-03 playbook (AUDIT-20261007-01 Sec 3, tech-debt TD-006, SDVVF N4 atomic-invariant) — fix pattern already in tree, stale xfail marker is the open defect/verified storage.py:141-145 stages to .tmp then os.replace
2/reproduce/`python -m pytest tests/invariants/test_cluster_a_invariants.py::test_save_quick_drop_is_atomic -q -rxX` → 1 failed [XPASS(strict)] AUDIT-20261007-01/F-03/artifact pytest output captured 2026-10-08
3/reproduce/`python -m pytest tests/invariants/ -q -rxX` → 4 passed, 3 xfailed (TD-007/TD-008/TD-009 still xfail as designed)/confirms only INV-02 flips to XPASS
4/trace/component server/storage.py save_quick_drop → state QuickDrop dir → data list_pending_drops glob `*_*` also matches `.tmp_*` staging names on CPython pathlib (dotfiles need explicit glob to match, but `*` as first char here is literal `*` matching `.tmp_` prefix)/cause = stale xfail marker + missing staging-file filter in list_pending_drops
5/fix/`server/storage.py list_pending_drops` skips `p.name.startswith(".tmp_")`; `tests/invariants/test_cluster_a_invariants.py` promotes INV-02 from xfail(strict) to regression guard/YAGNI: no new dep, no new abstraction; narrow startswith so legit `notes.tmp` final files still list
6/challenge/adversarial `notes.tmp` final name still listed (suffix check rejected — would hide user data); crash-leftover `.tmp_<id>_*.tmp` never listed; `file_id="*"` glob-escape noted as TD-016, out of scope, one-line debt pointer only/no new defect opened
7/review/targeted `test_save_quick_drop_is_atomic + test_websocket_and_drop.py` → 7 passed; `tests/invariants/ -q -rxX` → 4 passed, 3 xfailed (TD-007/TD-008/TD-009 untouched)/no validation/security/data-loss/a11y cut; no ponytail comment needed
8/close/TD-006 fix verified present + staging filter landed; lesson deposited in docs/superpowers/lessons.md; incident doc docs/superpowers/incidents/FLS-20261007-TD006-closeout.md; loop CLOSED with proof + explainer
