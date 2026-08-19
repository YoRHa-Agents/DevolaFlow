"""Shared test fixtures for DevolaFlow."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """v8.5.0 PV-05 (M-05) — honour ``@pytest.mark.deferred`` markers.

    Walks the collected test items; for any item carrying
    ``@pytest.mark.deferred(strict=True, reason=...)`` (the marker
    declared in ``pyproject.toml [tool.pytest.ini_options] markers``),
    apply ``pytest.mark.skip`` so the test is skipped at runtime with a
    clear message that surfaces the deferral reason in the pytest -v
    summary.

    Why a second marker class (alongside ``persistence_probe``):
    ``persistence_probe`` is a SELECTOR (collector filters by the marker
    in CI configs); ``deferred`` is a SIGNAL (the marker carries WHY a
    test is intentionally inactive in the current cycle, with a
    cite-able ``reason`` string). The two classes have orthogonal
    purposes and MUST NOT be conflated — the M-05 ADR-005 D2 records
    the rationale.

    Strict mode (default ``strict=True``): the marker asserts that the
    test is currently skipped. If a future PV inadvertently flips a
    deferred test back ON without removing the marker, the test runs
    and either passes (the deferred condition resolved — remove the
    marker) or fails (the deferred work still pending — restore the
    skip). Either way the strict mode forces the author to revisit the
    deferral, preventing silent re-activation.
    """
    for item in items:
        marker = item.get_closest_marker("deferred")
        if marker is None:
            continue
        reason = marker.kwargs.get("reason", "deferred without reason — see ADR-005 D2")
        strict = marker.kwargs.get("strict", True)
        if strict:
            item.add_marker(pytest.mark.skip(reason=f"DEFERRED: {reason}"))
        else:
            item.add_marker(pytest.mark.xfail(reason=f"DEFERRED (xfail): {reason}", strict=False))


@pytest.fixture(autouse=True)
def _force_fallback_token_estimator(request, monkeypatch):
    """Force ``tiktoken=None`` for deterministic benchmark scoring (autouse).

    ``devolaflow.task_adaptive_selector.estimate_tokens`` uses ``tiktoken``
    when available, otherwise falls back to ``len(text) // 4``. The two
    estimators disagree by enough that benchmark scenarios pick different
    section sets — and the v6.0.5+
    ``test_v6_baseline_matches_current_results_within_tolerance`` staleness
    guard becomes flaky when local and CI environments differ on
    tiktoken availability.

    Solution: hide ``tiktoken`` from ``sys.modules`` for the duration of
    every benchmark test so both environments take the deterministic
    fallback path. Production runtime is unaffected — agents that have
    tiktoken installed still get the more accurate estimate.

    Scope: applies only to tests in ``test_benchmarks.py`` (matched by
    the test's file path containing ``"test_benchmarks"``) to avoid
    changing behavior of other test modules (e.g. compressor or
    selector unit tests that may explicitly want tiktoken).

    Why this fixture exists (recap for v11.1.3 D-3 readers):
        Without the autouse force-to-fallback, EvoBench scenarios produce
        different absolute composite scores depending on whether the test
        runner has ``tiktoken`` installed (CI runner vs. dev laptop vs.
        fresh clone). The fallback estimator (``len(text) // 4``) is
        deterministic per fixture input; the ``tiktoken`` BPE estimator
        is *also* deterministic but produces a different absolute count,
        leading to ~7-percentage-point divergence on benchmark composite
        scores between the two environments. Pinning to fallback keeps
        pytest results comparable across machines.

    W-16 baseline regen note (v11.1.3 D-3; closes the v11.1.0 PV-02
    closeout finding telegraphed at v11.1.0 cycle close):
        Operators regenerating EvoBench baselines OUTSIDE the pytest
        harness (e.g., a standalone script that imports
        ``devolaflow.benchmarks`` directly, or a one-shot
        ``python scripts/...`` invocation that does not load conftest)
        WILL NOT see this fixture apply, and the resulting baselines
        will diverge from pytest scoring by ~7pp on the composite axis.

        Three options to reproduce pytest scoring outside pytest:

          Option A (preferred — least surprise): invoke regen under the
            pytest harness, e.g. ``pytest tests/test_benchmarks.py
            --regenerate-baselines`` (or whichever flag the regen
            entry-point exposes for the cycle in question). The autouse
            fixture fires automatically because conftest is loaded.

          Option B: pre-set ``sys.modules["tiktoken"] = None`` BEFORE
            importing any ``devolaflow`` modules in the regen script.
            This replicates the fixture's effect at import-time:

                import sys
                sys.modules["tiktoken"] = None
                from devolaflow import ...  # noqa: E402 — order matters

            The order is load-bearing: imports BEFORE the assignment
            still resolve to the real ``tiktoken`` if it's installed.

          Option C: uninstall tiktoken from the venv (``pip uninstall
            tiktoken``). Heavy-handed — affects every workflow in the
            env, not just the regen — and undesirable on dev laptops
            that use tiktoken for unrelated work. Only consider this
            for a dedicated CI venv whose sole purpose is baseline
            regeneration.

        Cross-reference: ``workflow-system/agent/references/
        troubleshooting.md`` §2.16 "Token-estimation determinism (W-16
        baseline regen)" carries the same 3-option summary in the
        operator-facing reference layer.

        Source: ``docs/cycle-archive/v11.1.0/retrospective.md`` cycle-
        close summary (the v11.1.0 PV-02 W-16 wholesale baseline regen
        was the first cycle where this divergence surfaced empirically;
        v11.1.3 D-3 closes the documentation gap).
    """
    fspath = str(getattr(request.node, "fspath", ""))
    if "test_benchmarks" not in fspath:
        return
    # Block both raw import and any cached module reference.
    monkeypatch.setitem(sys.modules, "tiktoken", None)


@pytest.fixture
def project_root() -> Path:
    """Return the project root directory."""
    return Path(__file__).parent.parent


@pytest.fixture
def design_docs_dir(project_root: Path) -> Path:
    """Return the design docs directory."""
    return project_root / "docs" / "designs"


@pytest.fixture
def templates_dir(project_root: Path) -> Path:
    """Return the built-in templates directory."""
    return project_root / "workflow-system" / "agent" / "templates" / "builtin"


@pytest.fixture
def schemas_dir(project_root: Path) -> Path:
    """Return the schemas directory."""
    return project_root / "schemas"


@pytest.fixture
def _compression_e2e_workspace(tmp_path: Path) -> dict:
    """Build a synthetic two-stage workspace for the persistence probe.

    Creates ``stage_a/artifact.md`` with a seeded preserve-list panel,
    ``stage_b/dispatch.yaml`` rendered as a canonical-layout lean dispatch
    that embeds Stage A's ``summarise_predecessor`` output verbatim under
    ``pred[0].key_facts``, and ``stage_b/context_packed.yaml`` which records
    the token accounting. Returns a dict containing absolute paths to all
    three files plus the ground-truth entity list extracted from Stage A.

    Implementation notes:
      * The artifact content is deterministic (no clock-dependent data) so
        the probe is stable across CI runs.
      * Three scenarios are supported via the ``scenario`` key in the
        returned dict: ``easy`` (~500-token artifact, 5 entities),
        ``medium`` (~5 000-token artifact, 20 entities), and ``hard``
        (~15 000-token artifact, 50 entities). Caller selects by setting
        the ``DEVOLAFLOW_PROBE_SCENARIO`` env var or by calling
        ``_build_probe_workspace(...)`` directly (see
        ``tests/test_e2e_compression.py``).
      * The default is ``easy``; tests that need the other scenarios call
        the top-level builder from the test module.
    """
    from tests._probe_fixtures import build_probe_workspace

    return build_probe_workspace(tmp_path, scenario="easy")
