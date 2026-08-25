"""Tests for the v10.2.1 PV-02 ``dispatch_dogfood_cycle`` wrapper.

Pins the contract in :func:`devolaflow.dispatch.dispatch_dogfood_cycle`
(owner module since the v14.5.0 ADR-006 split; the ``devolaflow.feedback``
re-export shim was retired in v17.0.0):

1. **Returns a SiChipResult** — the wrapper delegates to
   :func:`devolaflow.si_chip_bridge.runner.run_dogfood_cycle` and returns
   the verdict envelope unchanged.
2. **Default work_dir tracks ``__version__``** (D-S-6 closure) — when no
   ``work_dir`` is supplied, the wrapper defaults to
   ``Path.cwd() / ".local" / "dogfood" / __version__`` (NOT the historical
   v9.5.0 literal that the bridge default carried prior to this PV).
3. **Explicit work_dir is honoured** — caller-supplied ``work_dir`` is
   passed through untouched.
4. **P1 invariant** — the wrapper does NOT directly invoke any
   subprocess that mutates skill files. Subprocess work happens inside
   ``run_dogfood_cycle`` (which the wrapper delegates to via mock here),
   not in the wrapper body itself.

Source: `.local/research/v10.2.0_gap_analysis.md` §3.2 D-S-2 +
`.local/research/v10.2.0_cycle_plan.md` §3 PV-02.
External tool reference: https://github.com/YoRHa-Agents/Si-Chip
"""

from __future__ import annotations

import inspect
from pathlib import Path
from unittest.mock import MagicMock, patch

from devolaflow import __version__
from devolaflow.dispatch import dispatch_dogfood_cycle
from devolaflow.si_chip_bridge import ApplyVerdict, SiChipResult


def _fake_si_chip_result(
    skill_md: Path,
    verdict: ApplyVerdict = ApplyVerdict.DEFER,
) -> SiChipResult:
    """Construct a minimal SiChipResult fixture for stubbing."""
    return SiChipResult(
        verdict=verdict,
        delta=None,
        install_source="cursor_global",
        skill_md=skill_md,
        notes=["fake — wrapper test stub"],
    )


def test_dispatch_dogfood_cycle_returns_si_chip_result(tmp_path: Path) -> None:
    """Wrapper invocation returns a SiChipResult with a recognised verdict."""
    skill_files = [tmp_path / "skill.md"]
    skill_files[0].write_text("---\nversion: '0.0.0'\n---\n# Stub\n", encoding="utf-8")

    captured: dict = {}

    def fake_run(**kwargs):
        captured.update(kwargs)
        return _fake_si_chip_result(kwargs["skill_md"], ApplyVerdict.DEFER)

    with patch(
        "devolaflow.si_chip_bridge.runner.run_dogfood_cycle",
        side_effect=fake_run,
    ):
        result = dispatch_dogfood_cycle(
            workflow_name="skill-optimization",
            skill_files=skill_files,
            work_dir=tmp_path / "work",
        )

    assert isinstance(result, SiChipResult)
    assert result.verdict in {ApplyVerdict.APPLY, ApplyVerdict.DEFER}
    assert captured["ability_name"] == "skill-optimization"
    assert captured["skill_md"] == skill_files[0]


def test_dispatch_dogfood_cycle_default_work_dir_tracks_version(tmp_path: Path) -> None:
    """D-S-6 closure: when work_dir is omitted, the default tracks ``__version__``.

    The pre-v10.2.1 hardcoded ``"v9.5.0"`` literal in
    ``run_dogfood_cycle`` (and the wrapper) was version-pinned even after
    DevolaFlow bumped past v9.5.0 — cycle-level outputs co-mingled in a
    directory named for an obsolete version. v10.2.1 PV-02 D-S-6 swaps
    the literal for ``__version__`` so the path tracks the *current*
    DevolaFlow release.
    """
    captured: dict = {}

    def fake_run(**kwargs):
        captured.update(kwargs)
        return _fake_si_chip_result(kwargs["skill_md"], ApplyVerdict.DEFER)

    with patch(
        "devolaflow.si_chip_bridge.runner.run_dogfood_cycle",
        side_effect=fake_run,
    ):
        dispatch_dogfood_cycle(
            workflow_name="skill-optimization",
            skill_files=[tmp_path / "skill.md"],
        )

    expected = Path.cwd() / ".local" / "dogfood" / __version__
    assert captured["work_dir"] == expected, (
        f"Default work_dir must track __version__ ({__version__!r}); got {captured['work_dir']!r}"
    )
    # Sanity: the obsolete v9.5.0 literal MUST NOT appear in the resolved path.
    assert "v9.5.0" not in str(captured["work_dir"]), (
        "D-S-6 violation: the pre-v10.2.1 hardcoded 'v9.5.0' literal "
        "leaked into the default work_dir"
    )


def test_dispatch_dogfood_cycle_explicit_work_dir_honored(tmp_path: Path) -> None:
    """Explicit ``work_dir`` overrides the version-tracking default."""
    explicit_work_dir = tmp_path / "explicit-override"

    captured: dict = {}

    def fake_run(**kwargs):
        captured.update(kwargs)
        return _fake_si_chip_result(kwargs["skill_md"], ApplyVerdict.APPLY)

    with patch(
        "devolaflow.si_chip_bridge.runner.run_dogfood_cycle",
        side_effect=fake_run,
    ):
        dispatch_dogfood_cycle(
            workflow_name="self-update",
            skill_files=[tmp_path / "skill.md"],
            work_dir=explicit_work_dir,
        )

    assert captured["work_dir"] == explicit_work_dir, (
        "Caller-supplied work_dir MUST be passed through untouched"
    )


def test_dispatch_dogfood_cycle_explicit_str_work_dir_coerced(tmp_path: Path) -> None:
    """When ``work_dir`` is a string, it is coerced to a ``Path`` before forwarding.

    Documents the type-acceptance contract: the wrapper signature accepts
    ``Path | str | None`` for caller convenience but the underlying
    ``run_dogfood_cycle`` always receives a ``Path``.
    """
    captured: dict = {}

    def fake_run(**kwargs):
        captured.update(kwargs)
        return _fake_si_chip_result(kwargs["skill_md"], ApplyVerdict.DEFER)

    with patch(
        "devolaflow.si_chip_bridge.runner.run_dogfood_cycle",
        side_effect=fake_run,
    ):
        dispatch_dogfood_cycle(
            workflow_name="nines-assisted",
            skill_files=[tmp_path / "skill.md"],
            work_dir=str(tmp_path / "from-str"),
        )

    assert isinstance(captured["work_dir"], Path)
    assert captured["work_dir"] == tmp_path / "from-str"


def test_dispatch_dogfood_cycle_p1_invariant(tmp_path: Path) -> None:
    """P1 (Soul Rule S-1) — the wrapper itself does NOT spawn subprocesses.

    All Si-Chip subprocess work is delegated to ``run_dogfood_cycle``
    (which the bridge's runner.py implements). The wrapper is a pure
    Python delegation layer — its body must not call ``subprocess.run``
    or any equivalent. We mock ``subprocess.run`` and assert it is NOT
    invoked when ``run_dogfood_cycle`` itself is mocked away.
    """
    fake_skill = tmp_path / "skill.md"
    fake_skill.write_text("---\nversion: '0.0.0'\n---\n# stub\n", encoding="utf-8")

    sentinel = _fake_si_chip_result(fake_skill, ApplyVerdict.DEFER)
    fake_runner = MagicMock(return_value=sentinel)

    with (
        patch("devolaflow.si_chip_bridge.runner.run_dogfood_cycle", fake_runner),
        patch("subprocess.run") as fake_subprocess,
    ):
        result = dispatch_dogfood_cycle(
            workflow_name="skill-optimization",
            skill_files=[fake_skill],
            work_dir=tmp_path / "work",
        )

    assert result is sentinel, (
        "Wrapper must return the SiChipResult produced by run_dogfood_cycle "
        "without modification (delegation contract)"
    )
    assert fake_runner.call_count == 1, (
        "Wrapper must invoke run_dogfood_cycle exactly once per call"
    )
    assert fake_subprocess.call_count == 0, (
        "P1 violation: dispatch_dogfood_cycle invoked subprocess.run "
        "directly. The wrapper must delegate ALL subprocess work to "
        "run_dogfood_cycle; the wrapper body itself must NOT spawn "
        "processes that could mutate skill files."
    )


def test_dispatch_dogfood_cycle_default_skill_files(tmp_path: Path) -> None:
    """When ``skill_files`` is None, the default points at the canonical SKILL.md.

    Documents the convenience-default contract: callers that want to
    dogfood the canonical entry point can omit ``skill_files`` entirely.
    """
    captured: dict = {}

    def fake_run(**kwargs):
        captured.update(kwargs)
        return _fake_si_chip_result(kwargs["skill_md"], ApplyVerdict.DEFER)

    with patch(
        "devolaflow.si_chip_bridge.runner.run_dogfood_cycle",
        side_effect=fake_run,
    ):
        dispatch_dogfood_cycle(
            workflow_name="skill-optimization",
            work_dir=tmp_path / "work",
        )

    assert captured["skill_md"] == Path("workflow-system/agent/SKILL.md")


def test_dispatch_dogfood_cycle_signature_matches_runner_overlap() -> None:
    """The wrapper's keyword-only params overlap the runner's contract.

    Per the cycle plan PV-02 spec ("the exact signature MUST match the
    existing run_dogfood_cycle"), the parameters that the wrapper exposes
    upward (``runs_dir``, ``baseline_dir``, ``threshold``, ``work_dir``)
    MUST exist as keyword-only params on the underlying
    ``run_dogfood_cycle``. This test pins the overlap so future signature
    drift on either side fails CI loudly.
    """
    from devolaflow.si_chip_bridge.runner import run_dogfood_cycle

    wrapper_sig = inspect.signature(dispatch_dogfood_cycle)
    runner_sig = inspect.signature(run_dogfood_cycle)

    overlap_params = {"runs_dir", "baseline_dir", "threshold", "work_dir"}
    for name in overlap_params:
        assert name in wrapper_sig.parameters, (
            f"Wrapper missing expected param {name!r}; the wrapper-runner "
            "API contract requires this parameter on both sides."
        )
        assert name in runner_sig.parameters, (
            f"Runner missing expected param {name!r}; if removed, the "
            "wrapper at devolaflow.dispatch.dispatch_dogfood_cycle must "
            "be updated in the same PV (D-S-2 contract)."
        )

    # The wrapper introduces 2 NEW dispatch-level params not present on the
    # runner: ``workflow_name`` (positional) and ``skill_files`` (list-shaped).
    assert "workflow_name" in wrapper_sig.parameters
    assert "skill_files" in wrapper_sig.parameters
