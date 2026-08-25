"""Shared test fixtures for DevolaFlow."""

from __future__ import annotations

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
