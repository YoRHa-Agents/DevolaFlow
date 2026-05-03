"""Tests for the v9.5.0 PV-02 ``si_chip_bridge`` package.

Pins the contract for the typed Python wrappers around Si-Chip's
``profile_static.py`` / ``count_tokens.py`` / ``aggregate_eval.py`` CLI
scripts.

Test surfaces (kept tight per W-17 +30/PV cap):

1. **Public API surface** — every documented symbol imports cleanly
   from `devolaflow.si_chip_bridge`.
2. **Install resolver** — search-order priority + missing-install ``None``
   return + ``$SI_CHIP_HOME`` opt-in + nested-path fallback (the v0.4.0
   packaging-defect workaround captured in
   `.local/research/v9.5.0_gap_analysis.md` §3.2 D-S-7).
3. **Pure-Python apply/defer threshold gate** — `aggregate_delta` +
   `apply_or_defer` decide APPLY vs DEFER per Si-Chip spec §23 (+0.10
   default).
4. **Subprocess wrapper error modes** — `SiChipUnavailable` for missing
   install, `SiChipError` for non-zero subprocess exit, `SiChipError`
   for malformed YAML output.
5. **Top-level orchestration** — `run_dogfood_cycle` returns DEFER when
   no eval data is supplied (the PV-04 lifecycle hook common case).

Source: `.local/research/v9.5.0_gap_analysis.md` §3.1 D-S-2 + §6 AC-3 + AC-4.
"""

from __future__ import annotations

import importlib
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml

from devolaflow.si_chip_bridge import (
    ApplyVerdict,
    BasicAbilityProfile,
    MetricsReport,
    SiChipError,
    SiChipInstall,
    SiChipResult,
    SiChipUnavailable,
    aggregate_delta,
    apply_or_defer,
    find_si_chip_install,
)
from devolaflow.si_chip_bridge import install_resolver as _resolver
from devolaflow.si_chip_bridge import runner as _runner
from devolaflow.si_chip_bridge.install_resolver import read_installed_si_chip_version

# ---------------------------------------------------------------------------
# §1 — public API surface
# ---------------------------------------------------------------------------


class TestPublicApiSurface:
    """Pin the documented public symbols."""

    @pytest.mark.parametrize(
        "symbol",
        [
            "ApplyVerdict",
            "BasicAbilityProfile",
            "IterationDeltaReport",
            "MetricsReport",
            "SiChipError",
            "SiChipInstall",
            "SiChipResult",
            "SiChipUnavailable",
            "aggregate_delta",
            "apply_or_defer",
            "count_tokens",
            "evaluate",
            "find_si_chip_install",
            "profile",
            "run_dogfood_cycle",
        ],
    )
    def test_public_api_imports(self, symbol: str) -> None:
        """Every documented symbol must resolve from the package root.

        Catches accidental name collisions, circular imports, and the
        v6.0.3-style "feature mentioned in CHANGELOG but never wired"
        anti-pattern. Mirrors the W-18 lint discharged for v9.5.0 in
        `tests/test_no_ghost_features.py`.
        """
        mod = importlib.import_module("devolaflow.si_chip_bridge")
        assert hasattr(mod, symbol), (
            f"v9.5.0 PV-02 contract: si_chip_bridge.{symbol} must be a "
            f"public symbol; missing from the package surface"
        )


# ---------------------------------------------------------------------------
# §2 — install resolver
# ---------------------------------------------------------------------------


class TestInstallResolver:
    """Pin the multi-candidate search order from `install_resolver.py`."""

    def test_resolver_returns_none_when_nothing_present(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Returns None when no candidate dir contains SKILL.md."""
        monkeypatch.delenv(_resolver.ENV_HOME, raising=False)
        monkeypatch.delenv(_resolver.ENV_FALLBACK, raising=False)
        monkeypatch.setattr(Path, "home", lambda: tmp_path / "fakehome")
        assert find_si_chip_install() is None

    def test_resolver_finds_env_home_first(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """``$SI_CHIP_HOME`` overrides the standard search order."""
        env_dir = tmp_path / "custom-si-chip"
        env_dir.mkdir()
        (env_dir / "SKILL.md").write_text("---\nid: x\n---\nbody\n")
        (env_dir / "scripts").mkdir()
        (env_dir / "references").mkdir()
        monkeypatch.setenv(_resolver.ENV_HOME, str(env_dir))
        monkeypatch.delenv(_resolver.ENV_FALLBACK, raising=False)
        # Even if cursor_global also has SKILL.md, env_home wins.
        cursor_dir = tmp_path / ".cursor" / "skills" / "si-chip"
        cursor_dir.mkdir(parents=True)
        (cursor_dir / "SKILL.md").write_text("decoy")
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        install = find_si_chip_install()
        assert install is not None
        assert install.source == "env_home"
        assert install.root == env_dir
        assert install.scripts_dir == env_dir / "scripts"
        assert install.references_dir == env_dir / "references"

    def test_resolver_finds_nested_install_when_only_nested_path_present(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """v0.4.0 packaging defect: SKILL.md at ``si-chip/si-chip/SKILL.md``.

        Closes D-S-7 from `.local/research/v9.5.0_gap_analysis.md`
        §3.2 — the resolver MUST find the install even when the
        upstream installer leaves it at the double-nested path.
        """
        monkeypatch.delenv(_resolver.ENV_HOME, raising=False)
        monkeypatch.delenv(_resolver.ENV_FALLBACK, raising=False)
        nested_dir = tmp_path / ".cursor" / "skills" / "si-chip" / "si-chip"
        nested_dir.mkdir(parents=True)
        (nested_dir / "SKILL.md").write_text("---\nid: si-chip\n---\nbody\n")
        # Critically: do NOT create the single-level SKILL.md.
        single = tmp_path / ".cursor" / "skills" / "si-chip" / "SKILL.md"
        assert not single.exists()
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        install = find_si_chip_install()
        assert install is not None
        assert install.source == "cursor_global_nested"
        assert install.root == nested_dir

    def test_resolver_prefers_single_level_over_nested(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Documented priority: single-level path beats nested path."""
        monkeypatch.delenv(_resolver.ENV_HOME, raising=False)
        monkeypatch.delenv(_resolver.ENV_FALLBACK, raising=False)
        cursor_root = tmp_path / ".cursor" / "skills" / "si-chip"
        cursor_root.mkdir(parents=True)
        (cursor_root / "SKILL.md").write_text("single")
        nested_root = cursor_root / "si-chip"
        nested_root.mkdir()
        (nested_root / "SKILL.md").write_text("nested")
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        install = find_si_chip_install()
        assert install is not None
        assert install.source == "cursor_global"
        assert install.root == cursor_root

    def test_si_chip_install_script_path_returns_none_for_partial_install(
        self,
        tmp_path: Path,
    ) -> None:
        """SKILL.md present + scripts/ missing → script_path returns None."""
        root = tmp_path / "partial"
        root.mkdir()
        (root / "SKILL.md").write_text("body")
        install = SiChipInstall(
            root=root,
            skill_md=root / "SKILL.md",
            scripts_dir=None,  # partial install: scripts/ missing
            references_dir=None,
            source="cursor_global",
        )
        assert install.script_path("profile_static.py") is None


# ---------------------------------------------------------------------------
# §3 — pure-Python apply/defer threshold gate
# ---------------------------------------------------------------------------


class TestApplyOrDeferThreshold:
    """Pin Si-Chip spec §23 +0.10 threshold gate."""

    def test_aggregate_delta_computes_composite_difference(self) -> None:
        before = MetricsReport(
            composite=0.85,
            metadata_tokens=94,
            body_tokens=4646,
            task_delta=0.0,
            value_vector=0.0,
        )
        after = MetricsReport(
            composite=0.95,
            metadata_tokens=94,
            body_tokens=4500,
            task_delta=0.10,
            value_vector=0.10,
        )
        delta = aggregate_delta(before, after)
        assert delta.iteration_delta == pytest.approx(0.10)
        assert delta.threshold == pytest.approx(0.10)  # default
        assert delta.before is before
        assert delta.after is after

    @pytest.mark.parametrize(
        "before_composite,after_composite,threshold,expected",
        [
            # Exactly at threshold → APPLY (use exact-representable floats)
            (0.5, 0.6, 0.10, ApplyVerdict.APPLY),
            # Above threshold → APPLY
            (0.5, 0.65, 0.10, ApplyVerdict.APPLY),
            # Below threshold → DEFER
            (0.5, 0.5001, 0.10, ApplyVerdict.DEFER),
            # Regression → DEFER
            (0.5, 0.45, 0.10, ApplyVerdict.DEFER),
            # No-op → DEFER
            (0.5, 0.5, 0.10, ApplyVerdict.DEFER),
            # Custom threshold honoured: at threshold → APPLY
            (0.5, 0.55, 0.05, ApplyVerdict.APPLY),
            # Custom threshold honoured: below → DEFER
            (0.5, 0.54, 0.05, ApplyVerdict.DEFER),
        ],
    )
    def test_apply_or_defer_threshold_matrix(
        self,
        before_composite: float,
        after_composite: float,
        threshold: float,
        expected: ApplyVerdict,
    ) -> None:
        """Verdict matrix per Si-Chip spec §23.

        ``iteration_delta >= threshold`` → APPLY; else DEFER. The threshold
        kwarg overrides the value baked into the IterationDeltaReport.
        Uses exact-representable float pairs to avoid IEEE 754 precision
        traps near the threshold boundary.
        """
        before = MetricsReport(
            composite=before_composite,
            metadata_tokens=94,
            body_tokens=4646,
            task_delta=0.0,
            value_vector=0.0,
        )
        after = MetricsReport(
            composite=after_composite,
            metadata_tokens=94,
            body_tokens=4646,
            task_delta=after_composite - before_composite,
            value_vector=after_composite - before_composite,
        )
        delta = aggregate_delta(before, after, threshold=threshold)
        verdict = apply_or_defer(delta)
        assert verdict == expected, (
            f"iteration_delta={delta.iteration_delta} threshold={threshold} "
            f"expected={expected.value} got={verdict.value}"
        )


# ---------------------------------------------------------------------------
# §4 — subprocess wrapper error modes
# ---------------------------------------------------------------------------


class TestSubprocessErrorModes:
    """Pin S-5 loud-failure contract for the subprocess wrappers."""

    def test_profile_raises_si_chip_unavailable_when_no_install(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Missing install → :class:`SiChipUnavailable` (distinct exception)."""
        monkeypatch.setattr(
            "devolaflow.si_chip_bridge.runner.find_si_chip_install",
            lambda: None,
        )
        with pytest.raises(SiChipUnavailable) as exc_info:
            _runner.profile("devola-flow", tmp_path / "profile.yaml")
        assert "Si-Chip not installed" in str(exc_info.value)
        # Distinct from SiChipError (callers can downgrade to "skip").
        assert isinstance(exc_info.value, SiChipError)  # subclass relation
        assert exc_info.value.details.get("canonical_url") == (
            "https://github.com/YoRHa-Agents/Si-Chip"
        )

    def test_profile_raises_si_chip_error_on_subprocess_nonzero_exit(self, tmp_path: Path) -> None:
        """Non-zero subprocess exit → loud :class:`SiChipError`.

        The bridge MUST NOT silently swallow profile_static.py failures
        — operators need the stderr in the exception details to debug
        upstream Si-Chip issues.
        """
        fake_install = _make_fake_install(tmp_path)
        bad_completed = MagicMock(returncode=42, stderr="boom\n", stdout="")
        with (
            patch.object(_runner, "_run", return_value=bad_completed),
            pytest.raises(SiChipError) as exc_info,
        ):
            _runner.profile(
                "devola-flow",
                tmp_path / "profile.yaml",
                install=fake_install,
            )
        assert "exited 42" in str(exc_info.value)
        assert exc_info.value.details["returncode"] == 42
        assert "boom" in exc_info.value.details["stderr"]

    def test_evaluate_raises_si_chip_error_when_yaml_missing(self, tmp_path: Path) -> None:
        """Subprocess succeeded but output YAML missing → loud error.

        Catches partial-failure modes where Si-Chip exits 0 but leaves
        no metrics_report.yaml on disk (e.g. a flag-misuse upstream
        bug). The bridge surfaces this loudly per S-5 rather than
        defaulting to a zero-metrics report.
        """
        fake_install = _make_fake_install(tmp_path)
        ok_completed = MagicMock(returncode=0, stderr="", stdout="ok")
        with (
            patch.object(_runner, "_run", return_value=ok_completed),
            pytest.raises(SiChipError) as exc_info,
        ):
            _runner.evaluate(
                skill_md=tmp_path / "skill.md",
                runs_dir=tmp_path / "runs",
                baseline_dir=tmp_path / "baseline",
                out_path=tmp_path / "metrics.yaml",
                install=fake_install,
            )
        assert "did not produce expected output file" in str(exc_info.value)


# ---------------------------------------------------------------------------
# §5 — top-level orchestration (`run_dogfood_cycle`)
# ---------------------------------------------------------------------------


class TestRunDogfoodCycle:
    """Pin the PV-04 lifecycle hook common case + PV-05 dogfood path."""

    def test_dogfood_cycle_returns_defer_when_no_eval_data(self, tmp_path: Path) -> None:
        """Common case for the PV-04 hook: no eval data → DEFER + notes.

        Most SKILL-touching commits don't have eval runs prepared; the
        cycle MUST return a DEFER verdict (with explanatory note) rather
        than crash. The PV-05 dogfood pass IS the rare commit that
        supplies runs_dir + baseline_dir.
        """
        fake_install = _make_fake_install(tmp_path)
        profile_yaml = {
            "ability_id": "devola-flow",
            "metadata_tokens": 94,
            "body_tokens": 4646,
            "references_count": 10,
            "examples_count": 3,
        }
        # Stub the profile() subprocess call — return a happy YAML dict.
        ok_completed = MagicMock(returncode=0, stderr="", stdout="")
        out_path_holder: dict[str, Path] = {}

        def fake_run(cmd, *, timeout=90, cwd=None):
            # Locate the --out path in cmd and write the YAML to it.
            i = cmd.index("--out")
            out = Path(cmd[i + 1])
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(yaml.safe_dump(profile_yaml), encoding="utf-8")
            out_path_holder["profile"] = out
            return ok_completed

        with patch.object(_runner, "_run", side_effect=fake_run):
            result = _runner.run_dogfood_cycle(
                ability_name="devola-flow",
                skill_md=tmp_path / "fake_skill.md",
                work_dir=tmp_path / "work",
                install=fake_install,
            )
        assert isinstance(result, SiChipResult)
        assert result.verdict == ApplyVerdict.DEFER, (
            "no runs_dir/baseline_dir → DEFER (no iteration_delta computed)"
        )
        assert result.delta is None
        assert result.install_source == "cursor_global"
        assert any("evaluate: skipped" in n for n in result.notes), (
            f"expected an explanatory note about skipped evaluate; got {result.notes!r}"
        )
        # The profile YAML was actually written to the work_dir.
        assert out_path_holder["profile"].is_file()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_fake_install(tmp_path: Path) -> SiChipInstall:
    """Construct a SiChipInstall with all 3 expected scripts on disk."""
    root = tmp_path / "fake-si-chip"
    scripts_dir = root / "scripts"
    references_dir = root / "references"
    scripts_dir.mkdir(parents=True)
    references_dir.mkdir()
    (root / "SKILL.md").write_text("---\nid: si-chip\n---\nbody\n")
    for script in ("profile_static.py", "count_tokens.py", "aggregate_eval.py"):
        (scripts_dir / script).write_text("#!/usr/bin/env python3\n")
    return SiChipInstall(
        root=root,
        skill_md=root / "SKILL.md",
        scripts_dir=scripts_dir,
        references_dir=references_dir,
        source="cursor_global",
    )


# ---------------------------------------------------------------------------
# §6 — model parsing helpers (BasicAbilityProfile.from_yaml_dict + co.)
# ---------------------------------------------------------------------------


class TestModelParsing:
    """Pin the YAML-dict → dataclass converters tolerate Si-Chip drift."""

    def test_basic_ability_profile_from_yaml_dict_handles_missing_fields(self) -> None:
        """Si-Chip v0.4.0 sometimes omits examples_count for slim abilities."""
        partial = {"ability_id": "x", "metadata_tokens": 50, "body_tokens": 1000}
        profile_data = BasicAbilityProfile.from_yaml_dict(partial)
        assert profile_data.ability_id == "x"
        assert profile_data.metadata_tokens == 50
        assert profile_data.body_tokens == 1000
        assert profile_data.references_count == 0  # default
        assert profile_data.examples_count == 0  # default
        assert profile_data.raw == partial  # forward-compat preserved

    def test_metrics_report_from_yaml_dict_accepts_legacy_field_aliases(self) -> None:
        """C1_metadata_tokens (legacy) and metadata_tokens (newer) both work.

        Si-Chip v0.3.x emitted ``C1_metadata_tokens``; v0.4.0 added
        ``metadata_tokens``. The bridge accepts both for forward-compat.
        """
        legacy = {"composite": 0.8, "C1_metadata_tokens": 94, "C2_body_tokens": 4646}
        modern = {"composite": 0.8, "metadata_tokens": 94, "body_tokens": 4646}
        l_report = MetricsReport.from_yaml_dict(legacy)
        m_report = MetricsReport.from_yaml_dict(modern)
        assert l_report.metadata_tokens == 94
        assert l_report.body_tokens == 4646
        assert m_report.metadata_tokens == 94
        assert m_report.body_tokens == 4646


# ---------------------------------------------------------------------------
# §7 — read_installed_si_chip_version (v10.2.0 PV-01 / D-P-3)
# ---------------------------------------------------------------------------


class TestReadInstalledSiChipVersion:
    """Pin `read_installed_si_chip_version` frontmatter-parse contract.

    Closes D-P-3 from `.local/research/v10.2.0_gap_analysis.md` §3.1.
    The pre-v10.2.0 heuristic in `runtime-plugins.yaml` emitted a
    hardcoded `si-chip/0.4.0` string; this helper reads the real
    version from the installed `SKILL.md` frontmatter so
    `devolaflow.plugins.installer._meets_min` can order
    0.4.0 < 0.4.1 < 0.5.0 correctly once v0.4.1+ ships upstream.
    """

    @staticmethod
    def _make_install(skill_md_path: Path) -> SiChipInstall:
        """Build a minimal SiChipInstall pointing at the given SKILL.md."""
        root = skill_md_path.parent
        return SiChipInstall(
            root=root,
            skill_md=skill_md_path,
            scripts_dir=None,
            references_dir=None,
            source="env_home",
        )

    def test_returns_none_when_file_missing(self, tmp_path: Path) -> None:
        missing = tmp_path / "ghost" / "SKILL.md"
        assert not missing.exists()
        install = self._make_install(missing)
        assert read_installed_si_chip_version(install) is None

    def test_returns_version_string_for_quoted_frontmatter(self, tmp_path: Path) -> None:
        skill_md = tmp_path / "SKILL.md"
        skill_md.write_text(
            '---\nname: si-chip\nversion: "1.2.3"\nother: "y"\n---\nbody\n',
            encoding="utf-8",
        )
        install = self._make_install(skill_md)
        assert read_installed_si_chip_version(install) == "1.2.3"

    def test_returns_version_string_for_bare_frontmatter(self, tmp_path: Path) -> None:
        """Real Si-Chip v0.4.0 uses bare `version: 0.4.0` (no quotes)."""
        skill_md = tmp_path / "SKILL.md"
        skill_md.write_text(
            "---\nname: si-chip\nversion: 0.4.0\nlicense: Apache-2.0\n---\nbody\n",
            encoding="utf-8",
        )
        install = self._make_install(skill_md)
        assert read_installed_si_chip_version(install) == "0.4.0"

    def test_returns_none_when_no_frontmatter(self, tmp_path: Path) -> None:
        skill_md = tmp_path / "SKILL.md"
        skill_md.write_text(
            "# Si-Chip (no frontmatter)\n\nbody goes here\n",
            encoding="utf-8",
        )
        install = self._make_install(skill_md)
        assert read_installed_si_chip_version(install) is None

    def test_returns_none_when_frontmatter_has_no_version_field(self, tmp_path: Path) -> None:
        skill_md = tmp_path / "SKILL.md"
        skill_md.write_text(
            "---\nname: si-chip\nlicense: Apache-2.0\n---\nbody\n",
            encoding="utf-8",
        )
        install = self._make_install(skill_md)
        assert read_installed_si_chip_version(install) is None

    def test_returns_none_when_version_field_is_empty(self, tmp_path: Path) -> None:
        """Empty-value `version:` means "version unknown" → None."""
        skill_md = tmp_path / "SKILL.md"
        skill_md.write_text(
            '---\nname: si-chip\nversion: ""\n---\nbody\n',
            encoding="utf-8",
        )
        install = self._make_install(skill_md)
        assert read_installed_si_chip_version(install) is None
