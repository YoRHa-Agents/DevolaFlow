"""Shared test fixtures for DevolaFlow."""

import sys
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def _force_fallback_token_estimator(request, monkeypatch):
    """Make ``estimate_tokens`` deterministic for benchmark tests.

    ``devolaflow.task_adaptive_selector.estimate_tokens`` uses ``tiktoken``
    when available, otherwise falls back to ``len(text) // 4``. The two
    estimators disagree by enough that benchmark scenarios pick different
    section sets — and the v6.0.5+ ``test_v6_baseline_matches_current_results_within_tolerance``
    staleness guard becomes flaky when local and CI environments differ
    on tiktoken availability.

    Solution: hide ``tiktoken`` from ``sys.modules`` for the duration of
    every benchmark test so both environments take the deterministic
    fallback path. Production runtime is unaffected — agents that have
    tiktoken installed still get the more accurate estimate.

    Scope: applies only to tests in test_benchmarks.py (matched by the
    test's file path containing "test_benchmarks") to avoid changing
    behavior of other test modules (e.g. compressor or selector unit
    tests that may explicitly want tiktoken).
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
    return project_root / "doc" / "designs"


@pytest.fixture
def templates_dir(project_root: Path) -> Path:
    """Return the built-in templates directory."""
    return project_root / "workflow-system" / "agent" / "templates" / "builtin"


@pytest.fixture
def schemas_dir(project_root: Path) -> Path:
    """Return the schemas directory."""
    return project_root / "schemas"
