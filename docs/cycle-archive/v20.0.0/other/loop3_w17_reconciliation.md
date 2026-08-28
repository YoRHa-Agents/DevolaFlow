# Loop v3 W-17 Reconciliation — Test-Function Budget and Collected-Case Growth

Recorded at fill-close of the Loop v3 functional-test cycle, before the
release-integration PV. The midpoint numbers below are reconstructed from the
per-file inventory at the point PV-0 through PV-2 scope was complete; this
artifact is the cycle's explicit W-17 record required by the SI-1 acceptance
criteria (`.local/research/loop3_functional_test_system_gap_analysis.md` §8
item 13).

## 1. Counting basis

- Baseline: 0 functional test functions and 0 functional matrix cases at the
  loop start (`bc1cd8f`, v19.0.0). The pre-loop suite collected 5,535 cases.
- Counted unit: newly declared `def test_` functions. Parametrized expansions
  (matrix rows fanned out by `pytest.mark.parametrize`) are reported as
  collected-case growth, not as new functions.
- Verification commands:
  - `git diff bc1cd8f..HEAD -- tests/ | grep -cE '^\+\s*def test_'` plus
    per-file `rg -c '^def test_'` over the new untracked test files.
  - `python -m pytest tests/ --collect-only -q | tail -1` for collection.

## 2. New test functions by file and wave

| Wave (O-scope) | File | New functions |
|---|---|---:|
| PV-0 matrix infrastructure (O-01/O-02) | `tests/functional/test_matrix_contract.py` | 4 |
| PV-0 matrix infrastructure (O-01/O-02/O-15) | `tests/functional/test_domain_adapters.py` | 2 |
| PV-1 entrypoints (O-03/O-04) | `tests/functional/test_entrypoints.py` | 4 |
| PV-1 gate/dispatch safety (O-05) | `tests/test_loop3_dispatch_gate.py` | 5 |
| PV-1 state safety (O-06/O-07) | `tests/test_loop3_state_safety.py` | 5 |
| PV-2 delivery (O-11/O-12) | `tests/functional/test_delivery.py` | 3 |
| PV-3 plugin cleanup (O-13) | `tests/test_plugin_loop3_cleanup.py` | 7 |
| PV-4 archive safety (O-08) | `tests/test_loop3_archive_safety.py` | 6 |
| PV-4 hostbridge/shell/codegraph (O-14) | `tests/test_loop3_hostbridge_shell.py` | 7 |
| PV-5 repair (deterministic artifact / reporter `--now`) | `tests/test_reporter.py` | 1 |
| Cycle close (W-18 ghost audit) | `tests/ghost/test_features_v20_0.py` | 2 |
| **Cycle total** | | **46** |

Modified tracked test files (`tests/test_plugins.py`) added 0 new functions.

## 3. Cap compliance

- Per-wave maximum observed: 14 (PV-1: 4 + 5 + 5). Every wave is at or below
  the +30 W-17 per-PV ceiling.
- Cycle total: 46 ≤ 150. The SI-1 preferred budget forecast was 32–47; the
  actual total lands inside that forecast.
- Midpoint state (after PV-0 through PV-2 scope, before the plugin and slow
  waves): 23 new functions, forecast 44–47 for the cycle — under both caps,
  so no rows were deferred for budget reasons.

## 4. Collected-case growth

- Pre-loop collection: 5,535 cases.
- Current collection: 5,667 cases (+132), of which `tests/functional/`
  contributes 91 collected cases (matrix parametrization over 46 rows plus
  contract/policy checks).
- Growth is within the SI-1 expected range (160–330 upper band not reached;
  parametrization kept function count flat while rows expanded).

## 5. Disposition

No required matrix row was deleted, reclassified, or deferred to satisfy the
budget. The `remove+decouple` plugin path was not exercised; all five plugins
remain `suggest` with explicit optional installation per the adjudicated
disposition.
