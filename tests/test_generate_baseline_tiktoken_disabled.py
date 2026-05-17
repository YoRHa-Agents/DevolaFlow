"""v12.4.0 PV-02 — verify ``generate_baseline.py`` honours the tiktoken pin.

Closes the v12.3.0 retrospective §4.2 learning. The
``benchmarks/devolaflow_context/generate_baseline.py`` module pins
``sys.modules["tiktoken"] = None`` at module import (Option B from
``tests/conftest.py::_force_fallback_token_estimator`` docstring) so
standalone regen scripts produce the same composite scores as pytest. This
test pins the contract.

Three assertions, in priority order:

1. ``test_tiktoken_disabled_at_import`` — after ``import benchmarks.\
   devolaflow_context.generate_baseline``, ``sys.modules.get("tiktoken")``
   is ``None``. This is the PRIMARY contract — without this, the rest of
   the file's determinism story falls apart.

2. ``test_baseline_regen_deterministic`` — invoking ``generate_full_baseline``
   twice produces byte-identical JSON output. Catches any non-determinism
   in the scoring pipeline (e.g. dict ordering, random floats).

3. ``test_no_regression_vs_pytest`` — re-scoring a single scenario via
   ``runner.run_scenario`` (the same code path pytest exercises) produces
   the SAME composite as running the same scenario through
   ``generate_full_baseline`` (within ±0.5 to absorb any floating-point
   rounding). This confirms the tiktoken pin works — without it, the two
   paths diverge by ~7pp per ``tests/conftest.py`` docstring.

Source: ``.local/research/v12.3.0_retrospective.md`` §4.2 +
``.local/research/v12.4.0_gap_analysis.md`` §2 D-1 (item 1).
"""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_tiktoken_disabled_at_import() -> None:
    """After (re-)importing ``generate_baseline``, ``sys.modules['tiktoken']`` is ``None``.

    The pin is at module top of ``benchmarks/devolaflow_context/generate_baseline.py``;
    importing the module must apply the pin even if pytest's autouse fixture
    has not yet fired (the pin lives BEFORE any benchmark/devolaflow import,
    matching Option B from the ``tests/conftest.py`` docstring).

    We force a reload so the module-top code re-runs deterministically —
    otherwise prior imports + autouse-fixture monkeypatch teardown could
    leave ``sys.modules['tiktoken']`` in any state (cached real module,
    missing, or already None), making this test order-dependent.
    """
    module_name = "benchmarks.devolaflow_context.generate_baseline"
    module = importlib.import_module(module_name)
    importlib.reload(module)

    assert "tiktoken" in sys.modules, (
        "Expected ``sys.modules['tiktoken']`` to be set (to ``None``) after "
        "reloading generate_baseline. The module-top pin "
        '`sys.modules["tiktoken"] = None` must execute before any other import. '
        "See v12.4.0 PV-02 docstring credit + tests/conftest.py Option B."
    )
    assert sys.modules.get("tiktoken") is None, (
        f"Expected ``sys.modules['tiktoken'] is None`` after reload; got "
        f"{sys.modules.get('tiktoken')!r}. The pin in "
        "benchmarks/devolaflow_context/generate_baseline.py must NOT be removed — "
        "without it, standalone baseline regen diverges from pytest scoring by "
        "~7pp on composite. See v12.3.0 retro §4.2."
    )

    # Cross-check: the literal string is present in the source as the
    # W-18 stanza expects. This is a belt-and-braces check — the runtime
    # assertion above is the primary contract.
    source_path = Path(module.__file__) if module.__file__ else None
    assert source_path is not None and source_path.is_file()
    src_text = source_path.read_text(encoding="utf-8")
    assert 'sys.modules["tiktoken"] = None' in src_text, (
        f"Source file {source_path} missing literal pin. The pin MUST be "
        'the byte-identical string ``sys.modules["tiktoken"] = None`` '
        "(double-quoted) so the W-18 stanza in tests/test_no_ghost_features.py "
        "stays GREEN."
    )


def test_baseline_regen_deterministic(tmp_path: Path) -> None:
    """Invoking ``generate_full_baseline`` twice yields byte-identical JSON output.

    Determinism check: if the scoring pipeline introduces any randomness
    (random.seed not pinned, dict ordering, etc.), the two outputs would
    differ. We compare raw bytes — sort_keys=True in generate_baseline
    means the JSON serialisation is canonical, so any byte difference is
    a real semantic change.
    """
    from benchmarks.devolaflow_context.generate_baseline import generate_full_baseline

    out_a = tmp_path / "baseline_a.json"
    out_b = tmp_path / "baseline_b.json"

    generate_full_baseline(output_path=out_a)
    generate_full_baseline(output_path=out_b)

    bytes_a = out_a.read_bytes()
    bytes_b = out_b.read_bytes()
    assert bytes_a == bytes_b, (
        "Two consecutive ``generate_full_baseline()`` calls produced different "
        f"output ({len(bytes_a)} vs {len(bytes_b)} bytes). The scoring pipeline "
        "must be deterministic for baseline regen to be reproducible across CI / "
        "dev / fresh-clone environments. Check for unpinned randomness or dict-"
        "ordering instability."
    )


def test_no_regression_vs_pytest(tmp_path: Path) -> None:
    """``generate_full_baseline`` composite matches direct ``run_scenario`` (±0.5).

    Both code paths invoke the same selector + evaluator; the only difference
    is the entry point. With the v12.4.0 PV-02 tiktoken pin in place, the
    two paths see the SAME ``estimate_tokens`` fallback and MUST produce
    matching scores (within 0.5 to absorb any floating-point rounding).

    The ±0.5 tolerance is generous: the conftest docstring quantifies
    "without the pin" divergence at ~7pp on composite, so even ±2 would
    catch a regression. ±0.5 is the conservative envelope.
    """
    from benchmarks.devolaflow_context.generate_baseline import (
        BASELINE_FIELDS,
        generate_full_baseline,
    )
    from benchmarks.devolaflow_context.runner import (
        SCENARIOS_DIR,
        load_scenario,
        run_scenario,
    )

    scenario_path = SCENARIOS_DIR / "hotfix_jwt.yaml"
    assert scenario_path.is_file(), (
        f"Expected canonical test scenario at {scenario_path}; the test relies "
        "on this fixture being present. If hotfix_jwt.yaml was renamed, update "
        "this test."
    )

    direct_score = run_scenario(load_scenario(scenario_path))
    direct_composite = direct_score.composite

    baseline_path = tmp_path / "baseline.json"
    generate_full_baseline(output_path=baseline_path)
    with baseline_path.open("r", encoding="utf-8") as f:
        baselines = json.load(f)
    assert "hotfix_jwt" in baselines, (
        f"Expected 'hotfix_jwt' scenario in generated baseline; got keys: "
        f"{sorted(baselines)}. The scenario discovery layer may have skipped it."
    )

    regen_composite = baselines["hotfix_jwt"]["composite"]

    # ±0.5 is conservative; the actual delta should be 0 (same code path).
    assert abs(regen_composite - direct_composite) < 0.5, (
        f"generate_full_baseline composite {regen_composite} differs from "
        f"direct run_scenario composite {direct_composite} by "
        f"{abs(regen_composite - direct_composite)} > 0.5. This indicates "
        "tiktoken availability diverges between the two code paths — verify "
        "``sys.modules['tiktoken']`` is None in BOTH paths."
    )

    # Sanity: BASELINE_FIELDS is the lockstep contract with BenchmarkScore.to_dict
    for field in BASELINE_FIELDS:
        assert field in baselines["hotfix_jwt"], (
            f"Expected BASELINE_FIELDS member '{field}' in baseline entry. "
            "BASELINE_FIELDS must stay in lockstep with BenchmarkScore.to_dict — "
            "see generate_baseline.py docstring."
        )


@pytest.fixture(autouse=True)
def _ensure_sys_path() -> None:
    """Make ``benchmarks/`` importable from the repo root (test-isolation safety).

    pytest's ``pythonpath = ["src"]`` (per pyproject.toml) handles
    ``devolaflow`` but NOT ``benchmarks``. The repo root is normally on
    sys.path by virtue of pytest's rootdir discovery, but we add it
    defensively so the test never depends on outer-test ordering.
    """
    repo_root_str = str(REPO_ROOT)
    if repo_root_str not in sys.path:
        sys.path.insert(0, repo_root_str)
