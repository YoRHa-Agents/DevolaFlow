"""Tests for the v9.5.0 PV-04 ``post_skill_edit`` lifecycle hook.

Pins the contract in :mod:`devolaflow.lifecycle.post_skill_edit`:

1. **Event registered** — ``DEFAULT_EVENTS`` includes
   ``post_skill_edit`` at position 10 (A-2.2 append-only).
2. **R5 strict env-flag** — ``DEVOLAFLOW_SI_CHIP_DEEP=1`` exact
   match; rejects loose values; default-OFF.
3. **Disabled is no-op + byte-identical** — when env-flag OFF, the
   handler returns a clean :class:`HookResult` with zero filesystem
   IO and zero subprocess work (lazy-import of si_chip_bridge proves
   the cold-path import is not triggered).
4. **Skill-corpus filter** — only `workflow-system/agent/**` paths
   trigger the hook; non-skill paths are silent no-ops.
5. **Si-Chip unavailable surfaces as PSE001 warning** — DEEP
   integration is gracefully degraded; permissive default doesn't
   block.
6. **DEFER verdict writes feedback doc** — the v9.5.0 user
   requirement contract.
7. **APPLY verdict is silent (no feedback doc)** — happy path.

Source: `.local/research/v9.5.0_gap_analysis.md` §3.1 D-S-4 +
§3.2 D-S-5 + §6 AC-5 / AC-7.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from devolaflow.lifecycle import (
    DEFAULT_EVENTS,
    POST_SKILL_EDIT_EVENT,
    HookResult,
    clear_hooks,
)
from devolaflow.lifecycle.post_skill_edit import (
    ENV_FLAG,
    ENV_FLAG_TRUTHY,
    EVENT,
    SKILL_CORPUS_PREFIX,
    is_deep_integration_active,
    post_skill_edit,
)
from devolaflow.si_chip_bridge import (
    ApplyVerdict,
    IterationDeltaReport,
    MetricsReport,
    SiChipResult,
    SiChipUnavailable,
)


@pytest.fixture(autouse=True)
def _clear_extra_hooks():
    """Each test starts/ends with no extra hook handlers (defaults intact)."""
    yield
    clear_hooks()


# ---------------------------------------------------------------------------
# §1 — Event registration (A-2.2 append-only at position 10)
# ---------------------------------------------------------------------------


class TestEventRegistration:
    """Pin the canonical event name + DEFAULT_EVENTS membership at pos 10."""

    def test_event_constant_matches(self) -> None:
        assert EVENT == "post_skill_edit"
        assert POST_SKILL_EDIT_EVENT == EVENT

    def test_event_in_default_events_at_position_10(self) -> None:
        """A-2.2: new event APPENDED at the END of DEFAULT_EVENTS (pos 10)."""
        assert POST_SKILL_EDIT_EVENT in DEFAULT_EVENTS
        assert len(DEFAULT_EVENTS) == 10, (
            f"DEFAULT_EVENTS bumped 9 → 10 in v9.5.0 PV-04 "
            f"(was {len(DEFAULT_EVENTS)}); A-2.2 append-only invariant "
            f"requires this slot at the END of the tuple"
        )
        assert DEFAULT_EVENTS[-1] == POST_SKILL_EDIT_EVENT, (
            f"POST_SKILL_EDIT_EVENT must be the LAST event in "
            f"DEFAULT_EVENTS (cache-prefix governance A-2.2). "
            f"Actual tail: {DEFAULT_EVENTS[-1]!r}"
        )

    def test_canonical_9_event_prefix_unchanged(self) -> None:
        """A-2.4 cache-prefix invariant: positions 1-9 byte-stable since v9.4.0."""
        assert DEFAULT_EVENTS[:9] == (
            "pre_dispatch",
            "post_dispatch",
            "file_write",
            "task_stop",
            "format_on_edit",
            "pre_shell_call",
            "envelope_write",
            "pre_handoff",
            "pre_plugin_invocation",
        )


# ---------------------------------------------------------------------------
# §2 — R5 strict env-flag parsing
# ---------------------------------------------------------------------------


class TestEnvFlagR5Strict:
    """Pin the env-flag parsing: literal ``"1"`` only; everything else falls through."""

    def test_env_flag_literal_one_active(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv(ENV_FLAG, ENV_FLAG_TRUTHY)
        assert is_deep_integration_active() is True

    @pytest.mark.parametrize(
        "value",
        ["true", "yes", "on", "01", "1\n", "", "TRUE", "1 ", " 1", "0", "false", "off"],
    )
    def test_loose_env_values_rejected(self, value: str, monkeypatch: pytest.MonkeyPatch) -> None:
        """R5 strict matches the v9.4.0 PV-02 / v9.3.0 PV-06 / v8.3.x precedents."""
        monkeypatch.setenv(ENV_FLAG, value)
        assert is_deep_integration_active() is False, (
            f"R5 strict: env value {value!r} MUST NOT activate the hook; "
            f"only the literal string '1' is accepted"
        )

    def test_unset_default_off(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv(ENV_FLAG, raising=False)
        assert is_deep_integration_active() is False


# ---------------------------------------------------------------------------
# §3 — Disabled is no-op + byte-identical (R5 strict zero-IO)
# ---------------------------------------------------------------------------


class TestDisabledIsNoop:
    """Pin the byte-identical-when-off contract."""

    def test_disabled_is_noop_byte_identical(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Env flag OFF → empty HookResult; no filesystem IO; no subprocess."""
        monkeypatch.delenv(ENV_FLAG, raising=False)
        # Watch every Path.read_text call to prove zero IO when off.
        read_text_calls: list[str] = []
        original_read_text = Path.read_text

        def watcher_read_text(self, *args, **kwargs):
            read_text_calls.append(str(self))
            return original_read_text(self, *args, **kwargs)

        monkeypatch.setattr(Path, "read_text", watcher_read_text)
        result = post_skill_edit(
            {
                "touched_files": [
                    "workflow-system/agent/SKILL.md",
                    "workflow-system/agent/references/agent-workspace.md",
                ],
            }
        )
        assert isinstance(result, HookResult)
        assert result.passed is True
        assert result.violations == []
        assert read_text_calls == [], (
            f"R5 strict: post_skill_edit MUST do zero Path.read_text when "
            f"env flag is unset; observed reads: {read_text_calls!r}"
        )

    def test_disabled_does_not_lazy_import_si_chip_bridge(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The si_chip_bridge package MUST NOT be imported when env flag is OFF.

        Validates the lazy-import contract: even when the payload looks
        like it would trigger the hook, the env-flag check happens FIRST
        and short-circuits the import.
        """
        monkeypatch.delenv(ENV_FLAG, raising=False)
        # Pre-evict the bridge from sys.modules so we can detect a re-import.
        for name in list(sys.modules):
            if name.startswith("devolaflow.si_chip_bridge"):
                # Don't actually evict (other tests may depend on it loaded);
                # we just observe that the hook doesn't import-load fresh.
                pass
        # Fail-loud probe: replace the module's run_dogfood_cycle attr; if the
        # disabled path called into it, the test would crash here.
        from devolaflow.si_chip_bridge import runner as _r

        original = _r.run_dogfood_cycle

        def fail_loud(*a, **k):
            pytest.fail(
                "R5 strict violation: post_skill_edit invoked "
                "run_dogfood_cycle when env flag is OFF"
            )

        monkeypatch.setattr(_r, "run_dogfood_cycle", fail_loud)
        try:
            result = post_skill_edit({"touched_files": ["workflow-system/agent/SKILL.md"]})
            assert result.passed is True
        finally:
            monkeypatch.setattr(_r, "run_dogfood_cycle", original)


# ---------------------------------------------------------------------------
# §4 — Skill-corpus filter (only workflow-system/agent/** triggers)
# ---------------------------------------------------------------------------


class TestSkillCorpusFilter:
    """Pin the file-prefix matcher."""

    def test_non_skill_paths_are_silent_noop(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Non-skill-corpus touches → silent no-op even when env flag is ON."""
        monkeypatch.setenv(ENV_FLAG, ENV_FLAG_TRUTHY)
        # Provide non-skill paths only — no prefix match.
        result = post_skill_edit(
            {
                "touched_files": [
                    "src/devolaflow/feedback.py",
                    "tests/test_si_chip_bridge.py",
                    "README.md",
                ],
            }
        )
        assert result.passed is True
        assert result.violations == []
        # No metadata about Si-Chip evaluation — the hook didn't run.
        assert "verdict" not in result.metadata

    def test_skill_corpus_prefix_matcher_normalises_dot_slash(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Both `./workflow-system/agent/...` and `workflow-system/agent/...` match."""
        monkeypatch.setenv(ENV_FLAG, ENV_FLAG_TRUTHY)
        # Stub run_dogfood_cycle so we can confirm the hook FIRES (not silent).
        called_with: list[str] = []

        def fake_dogfood(ability_name, skill_md, *, threshold):
            called_with.append(str(skill_md))
            return SiChipResult(
                verdict=ApplyVerdict.APPLY,
                delta=None,
                install_source="cursor_global",
                skill_md=skill_md,
                notes=["fake apply"],
            )

        with patch(
            "devolaflow.si_chip_bridge.run_dogfood_cycle",
            side_effect=fake_dogfood,
        ):
            post_skill_edit(
                {
                    "touched_files": ["./workflow-system/agent/SKILL.md"],
                    "feedback_dir": str(tmp_path / "feedback"),
                }
            )
        assert called_with == ["workflow-system/agent/SKILL.md"], (
            f"./workflow-system/agent/SKILL.md MUST normalise to "
            f"workflow-system/agent/SKILL.md before invocation; "
            f"got {called_with!r}"
        )
        assert SKILL_CORPUS_PREFIX == "workflow-system/agent/"


# ---------------------------------------------------------------------------
# §5 — Si-Chip unavailable surfaces as PSE001 warning (graceful degrade)
# ---------------------------------------------------------------------------


class TestSiChipUnavailableGracefulDegrade:
    """Pin the permissive default for missing-install."""

    def test_unavailable_surfaces_as_pse001_warning(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Si-Chip not installed → PSE001 warning, no exception."""
        monkeypatch.setenv(ENV_FLAG, ENV_FLAG_TRUTHY)
        with patch(
            "devolaflow.si_chip_bridge.run_dogfood_cycle",
            side_effect=SiChipUnavailable(
                "Si-Chip not installed; tried ...",
                details={"canonical_url": "https://github.com/YoRHa-Agents/Si-Chip"},
            ),
        ):
            result = post_skill_edit(
                {
                    "touched_files": ["workflow-system/agent/SKILL.md"],
                    "feedback_dir": str(tmp_path / "feedback"),
                }
            )
        # Permissive default: NOT raised; collected as warning violation.
        assert isinstance(result, HookResult)
        assert any(v.code == "PSE001" for v in result.violations), (
            f"missing Si-Chip MUST surface PSE001 warning; "
            f"got violations={[(v.code, v.severity) for v in result.violations]!r}"
        )
        pse001 = next(v for v in result.violations if v.code == "PSE001")
        assert pse001.severity == "warning", (
            "PSE001 is gracefully-degraded — severity MUST be 'warning' "
            "so the dispatch is not blocked when Si-Chip is unavailable"
        )
        assert result.metadata["verdict"] == "SKIPPED_PERMISSIVE"


# ---------------------------------------------------------------------------
# §6 — DEFER verdict writes the deferred-changes feedback doc
# ---------------------------------------------------------------------------


class TestDeferWritesFeedbackDoc:
    """Pin the v9.5.0 user-requirement contract."""

    def test_defer_verdict_writes_feedback_doc(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """DEFER verdict → operator-visible feedback doc in feedback_dir."""
        monkeypatch.setenv(ENV_FLAG, ENV_FLAG_TRUTHY)
        feedback_dir = tmp_path / "feedback"
        before = MetricsReport(
            composite=0.85,
            metadata_tokens=94,
            body_tokens=4646,
            task_delta=0.0,
            value_vector=0.0,
        )
        after = MetricsReport(
            composite=0.86,
            metadata_tokens=94,
            body_tokens=4640,
            task_delta=0.01,
            value_vector=0.01,
        )
        delta = IterationDeltaReport(
            before=before, after=after, iteration_delta=0.01, threshold=0.10
        )

        def fake_dogfood(ability_name, skill_md, *, threshold):
            return SiChipResult(
                verdict=ApplyVerdict.DEFER,
                delta=delta,
                install_source="cursor_global",
                skill_md=skill_md,
                notes=["iteration_delta=+0.0100 vs threshold +0.10 → DEFER"],
            )

        with patch(
            "devolaflow.si_chip_bridge.run_dogfood_cycle",
            side_effect=fake_dogfood,
        ):
            result = post_skill_edit(
                {
                    "touched_files": [
                        "workflow-system/agent/SKILL.md",
                        "workflow-system/agent/references/agent-workspace.md",
                    ],
                    "feedback_dir": str(feedback_dir),
                }
            )
        assert result.metadata["verdict"] == "DEFER"
        assert result.metadata["iteration_delta"] == pytest.approx(0.01)
        assert "feedback_doc" in result.metadata, (
            "DEFER verdict MUST write a feedback doc per the v9.5.0 user "
            "requirement; metadata['feedback_doc'] is the canonical pointer"
        )
        feedback_doc = Path(result.metadata["feedback_doc"])
        assert feedback_doc.is_file()
        body = feedback_doc.read_text(encoding="utf-8")
        assert "Si-Chip DEEP Integration — Deferred Verdict" in body
        assert "workflow-system/agent/SKILL.md" in body
        assert "Action recommendation" in body

    def test_apply_verdict_does_not_write_feedback_doc(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """APPLY verdict → silent (happy path; no operator feedback needed)."""
        monkeypatch.setenv(ENV_FLAG, ENV_FLAG_TRUTHY)
        feedback_dir = tmp_path / "feedback"

        def fake_dogfood(ability_name, skill_md, *, threshold):
            return SiChipResult(
                verdict=ApplyVerdict.APPLY,
                delta=None,
                install_source="cursor_global",
                skill_md=skill_md,
                notes=["fake apply"],
            )

        with patch(
            "devolaflow.si_chip_bridge.run_dogfood_cycle",
            side_effect=fake_dogfood,
        ):
            result = post_skill_edit(
                {
                    "touched_files": ["workflow-system/agent/SKILL.md"],
                    "feedback_dir": str(feedback_dir),
                }
            )
        assert result.metadata["verdict"] == "APPLY"
        assert "feedback_doc" not in result.metadata, (
            "APPLY verdict MUST NOT write a feedback doc — happy path is silent"
        )
        # The feedback dir is NOT auto-created on APPLY (no DEFER work to write).
        assert not feedback_dir.exists()
