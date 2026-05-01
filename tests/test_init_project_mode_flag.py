"""v9.2.3 PV-02 — `--mode={core,standard,full}` shorthand CLI flag tests.

These tests pin the v9.2.3 PV-02 ``_parse_mode`` surface plus the
mode-aware default wiring inside ``init_project.main``: each mode
selects an exact (compile_rules, with_examples) tuple at dispatch
time, individual flags ALWAYS override the mode-derived default
(explicit-beats-implicit), and an invalid mode value exits 1 with an
informative message that names the valid set.

Source artefacts:

* ``.local/feedbacks/feedback_for_v9.2.1.md`` §Notes (mode dispatch
  shorthand suggestion).
* ``.local/research/v9.2.2_gap_analysis.md`` §2 PV-02 scope.
* ``src/devolaflow/init_project.py`` lines around ``_parse_mode`` +
  ``main()`` (the mode-aware default block).
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest

from devolaflow import init_project
from devolaflow.init_project import (
    VALID_MODES,
    _parse_mode,
)

# ── Direct ``_parse_mode`` smoke (cheap helper coverage) ───────────


def test_parse_mode_returns_none_when_absent() -> None:
    """Without ``--mode=`` the helper returns ``None`` (mode-not-selected sentinel)."""
    assert _parse_mode([]) is None
    assert _parse_mode(["local", "--no-compile"]) is None


def test_parse_mode_picks_first_valid_value() -> None:
    """A single ``--mode=core`` argument resolves to ``"core"``."""
    assert _parse_mode(["local", "--mode=core"]) == "core"
    assert _parse_mode(["local", "--mode=standard"]) == "standard"
    assert _parse_mode(["local", "--mode=full"]) == "full"


def test_valid_modes_pinned() -> None:
    """Surface pin: ``VALID_MODES`` is the exact 3-element frozenset.

    Future PVs that wish to widen / narrow the set MUST also update
    ``tests/test_no_ghost_features.py::test_v9_2_3_mode_flag_surface_complete``
    + the ``--mode`` documentation in ``init_project.py`` docstring +
    ``README.md`` Troubleshooting subsection. This lint is the leaf
    surface check; the W-18 ghost-audit lint is the discovery path.
    """
    assert frozenset({"core", "standard", "full"}) == VALID_MODES, (
        f"v9.2.3 PV-02 surface drift: VALID_MODES = {VALID_MODES!r}; expected "
        f"frozenset({{'core', 'standard', 'full'}})"
    )
    assert isinstance(VALID_MODES, frozenset), (
        f"VALID_MODES must be a frozenset (immutable surface); got {type(VALID_MODES).__name__!r}"
    )


# ── End-to-end mode wiring through ``init_project.main`` ───────────
#
# The 5 acceptance-criteria-pinned scenarios from the PV-02 dispatch
# (AC #3..#6) flow through ``main()`` so we monkeypatch ``install_local``
# to capture the keyword arguments it receives. The fake captures the
# call without performing scaffolding so the tests are fast + isolated.


@pytest.fixture
def captured_install_local_kwargs(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> dict[str, Any]:
    """Monkeypatch ``install_local`` to capture its kwargs and short-circuit.

    The fixture also stubs ``_find_agent_dir`` to return a fake path
    that has SKILL.md present (so the agent-dir-required deferred
    check never fires for non-``local`` targets). Returns a mutable
    dict; the test mutates ``captured["call_count"]`` from inside the
    fake ``install_local`` to assert single-dispatch.
    """
    captured: dict[str, Any] = {"call_count": 0, "kwargs": None, "args": None}

    fake_agent_dir = tmp_path / "_fake_agent_dir"
    fake_agent_dir.mkdir(parents=True, exist_ok=True)
    (fake_agent_dir / "SKILL.md").write_text("stub", encoding="utf-8")

    def _fake_install_local(
        agent_dir: Path, cwd: Path, scope: str = "project", **kwargs: Any
    ) -> None:
        captured["call_count"] += 1
        captured["args"] = (agent_dir, cwd, scope)
        captured["kwargs"] = kwargs

    monkeypatch.setitem(init_project.TOOLS, "local", _fake_install_local)
    monkeypatch.setattr(init_project, "_find_agent_dir", lambda: fake_agent_dir)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path / "_home"))
    monkeypatch.delenv("CODEX_HOME", raising=False)
    return captured


def _resolved_kwargs(captured: dict[str, Any]) -> tuple[bool, bool]:
    """Return ``(compile_rules, with_examples)`` from the captured kwargs.

    Mirrors the dispatch contract in ``main()``: ``compile_rules`` is
    only forwarded when ``no_compile`` is True (i.e. compile defaults
    to True at the ``install_local`` signature level), so absence of
    the kwarg means ``compile_rules=True``.
    """
    kwargs = captured["kwargs"] or {}
    compile_rules = kwargs.get("compile_rules", True)
    with_examples = kwargs.get("with_examples", False)
    return compile_rules, with_examples


def test_mode_core_implies_no_compile_and_no_examples(
    monkeypatch: pytest.MonkeyPatch, captured_install_local_kwargs: dict[str, Any]
) -> None:
    """AC #3: ``--mode=core`` → ``compile_rules=False, with_examples=False``."""
    monkeypatch.setattr(sys, "argv", ["devola-init", "local", "--mode=core"])

    init_project.main()

    assert captured_install_local_kwargs["call_count"] == 1, (
        "AC #3 dispatch contract: install_local must be invoked exactly once"
    )
    compile_rules, with_examples = _resolved_kwargs(captured_install_local_kwargs)
    assert compile_rules is False, (
        f"AC #3: --mode=core MUST imply compile_rules=False (got {compile_rules!r})"
    )
    assert with_examples is False, (
        f"AC #3: --mode=core MUST imply with_examples=False (got {with_examples!r})"
    )


def test_mode_full_enables_examples_and_compile(
    monkeypatch: pytest.MonkeyPatch, captured_install_local_kwargs: dict[str, Any]
) -> None:
    """AC #4: ``--mode=full`` → ``compile_rules=True, with_examples=True``."""
    monkeypatch.setattr(sys, "argv", ["devola-init", "local", "--mode=full"])

    init_project.main()

    assert captured_install_local_kwargs["call_count"] == 1
    compile_rules, with_examples = _resolved_kwargs(captured_install_local_kwargs)
    assert compile_rules is True, (
        f"AC #4: --mode=full MUST keep compile_rules=True (got {compile_rules!r})"
    )
    assert with_examples is True, (
        f"AC #4: --mode=full MUST imply with_examples=True (got {with_examples!r})"
    )


def test_mode_standard_matches_current_defaults(
    monkeypatch: pytest.MonkeyPatch, captured_install_local_kwargs: dict[str, Any]
) -> None:
    """``--mode=standard`` → byte-identical to the pre-v9.2.3 default ``local`` flow.

    The pre-v9.2.3 default was: ``compile_rules=True``, ``with_examples=False``
    (the v9.2.0 PV-06 cycle plan §"PV-06 — repo-init seed examples"
    pinned ``mode=core`` defaults at OFF). ``--mode=standard`` re-states
    that contract verbatim — operators get a documented name for what
    used to be the implicit default.
    """
    monkeypatch.setattr(sys, "argv", ["devola-init", "local", "--mode=standard"])

    init_project.main()

    assert captured_install_local_kwargs["call_count"] == 1
    compile_rules, with_examples = _resolved_kwargs(captured_install_local_kwargs)
    assert compile_rules is True, (
        "--mode=standard: compile_rules default must remain True (matches pre-v9.2.3)"
    )
    assert with_examples is False, (
        "--mode=standard: with_examples default must remain False (matches pre-v9.2.3)"
    )


def test_explicit_flag_overrides_mode(
    monkeypatch: pytest.MonkeyPatch, captured_install_local_kwargs: dict[str, Any]
) -> None:
    """AC #5: explicit ``--no-with-examples`` beats ``--mode=full``.

    Pinned in the dispatch's "Mode + individual flags" docstring:
    explicit-beats-implicit. The user wrote ``--mode=full`` AND
    ``--no-with-examples`` — interpret the explicit override as an
    operator who wants compile-on (from ``--mode=full``) but does NOT
    want example seeds. CI scripts that compose both surfaces depend
    on this precedence.
    """
    monkeypatch.setattr(
        sys,
        "argv",
        ["devola-init", "local", "--mode=full", "--no-with-examples"],
    )

    init_project.main()

    assert captured_install_local_kwargs["call_count"] == 1
    compile_rules, with_examples = _resolved_kwargs(captured_install_local_kwargs)
    assert compile_rules is True, "AC #5: --mode=full's compile_rules=True default still applies"
    assert with_examples is False, (
        "AC #5 explicit-beats-implicit: --no-with-examples wins over --mode=full"
    )


def test_invalid_mode_exits_nonzero_with_clear_message(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    """AC #6: ``--mode=bogus`` exits 1; error names the valid values.

    S-5 explicit error state — the helper prints to stdout (matches
    the rest of the CLI's reporter style; pre-v9.2.3 errors followed
    the same pattern) AND raises ``SystemExit(1)``. The test captures
    both surfaces.
    """
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path / "_home"))
    monkeypatch.delenv("CODEX_HOME", raising=False)
    monkeypatch.setattr(sys, "argv", ["devola-init", "local", "--mode=bogus"])

    with pytest.raises(SystemExit) as excinfo:
        init_project.main()

    assert excinfo.value.code == 1, (
        f"AC #6: invalid --mode must exit 1 (got code={excinfo.value.code!r})"
    )

    out = capsys.readouterr().out
    assert "--mode" in out, f"AC #6: error must mention `--mode` (got {out!r})"
    for valid in ("core", "standard", "full"):
        assert valid in out, f"AC #6: error must list valid value {valid!r} (got {out!r})"
    assert "bogus" in out, f"AC #6: error must echo the invalid value 'bogus' (got {out!r})"


# ── Backward-compatibility regression: --mode is purely additive ───


def test_no_mode_preserves_legacy_local_default(
    monkeypatch: pytest.MonkeyPatch, captured_install_local_kwargs: dict[str, Any]
) -> None:
    """Without ``--mode=``, ``devola-init local`` behaves byte-identically to v9.2.2.

    Pre-v9.2.3 ``devola-init local`` produced ``compile_rules=True``
    and ``with_examples=False`` (the default-OFF-for-mode-core matrix).
    The PV-02 ``--mode`` plumbing must NEVER regress this default —
    operators who never type ``--mode`` get the exact same install they
    got before the shorthand existed.
    """
    monkeypatch.setattr(sys, "argv", ["devola-init", "local"])

    init_project.main()

    assert captured_install_local_kwargs["call_count"] == 1
    compile_rules, with_examples = _resolved_kwargs(captured_install_local_kwargs)
    assert compile_rules is True, (
        "regression: bare `devola-init local` must keep compile_rules=True"
    )
    assert with_examples is False, (
        "regression: bare `devola-init local` must keep with_examples=False"
    )
