"""Tests for devolaflow.local.compiler module."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from devolaflow.local.compiler import (
    CompileResult,
    RuleCompiler,
    RuleLayer,
    TargetConfig,
    TokenBudgetExceededError,
    _estimate_tokens,
    _parse_mdc,
)


@pytest.fixture()
def rules_dir(tmp_path: Path) -> Path:
    """Create a minimal .rules/ directory with layer files and config."""
    rd = tmp_path / ".rules"
    rd.mkdir()

    (rd / "soul.mdc").write_text(
        '---\ndescription: "Soul rules"\npriority: P0\nalwaysApply: true\n---\n\n'
        "# Soul\n\n## S-1 — No absolute paths\n\nAll paths must be relative.\n",
        encoding="utf-8",
    )
    (rd / "architecture.mdc").write_text(
        '---\ndescription: "Architecture rules"\npriority: P1\nalwaysApply: true\n---\n\n'
        "# Architecture\n\n## A-1 — 4-Layer Hierarchy\n\nDispatcher agents must not implement.\n",
        encoding="utf-8",
    )
    (rd / "conventions.mdc").write_text(
        '---\ndescription: "Conventions"\npriority: P2\nalwaysApply: true\n---\n\n'
        "# Conventions\n\n## C-1 — Pre-commit checklist\n\nRun tests, lint, format.\n",
        encoding="utf-8",
    )
    (rd / "workflow.mdc").write_text(
        '---\ndescription: "Workflow"\npriority: P3\nalwaysApply: false\n---\n\n'
        "# Workflow\n\n## W-1 — Iteration gate\n\nPlan before implementing.\n",
        encoding="utf-8",
    )
    (rd / "style.mdc").write_text(
        '---\ndescription: "Style"\npriority: P4\nalwaysApply: false\n---\n\n'
        "# Style\n\n## ST-1 — Visual identity\n\nUse Devola palette.\n",
        encoding="utf-8",
    )

    config = {
        "version": "1.0",
        "source_dir": ".rules",
        "layers": [
            {"name": "soul", "file": "soul.mdc", "priority": 0, "always_include": True},
            {
                "name": "architecture",
                "file": "architecture.mdc",
                "priority": 1,
                "always_include": True,
            },
            {
                "name": "conventions",
                "file": "conventions.mdc",
                "priority": 2,
                "always_include": False,
            },
            {"name": "workflow", "file": "workflow.mdc", "priority": 3, "always_include": False},
            {"name": "style", "file": "style.mdc", "priority": 4, "always_include": False},
        ],
        "targets": {
            "cursor": {
                "output": ".cursor/rules/repo-governance.mdc",
                "format": "mdc",
                "token_budget": 8000,
                "include_layers": ["soul", "architecture", "conventions", "workflow", "style"],
                "frontmatter": {
                    "description": "Compiled governance rules",
                    "alwaysApply": True,
                },
            },
            "agents_md": {
                "output": "AGENTS.md",
                "format": "markdown",
                # v8.5.0 PV-05 — bumped 6000 → 8000 (parity with cursor target)
                # so W-16..W-20 rule additions fit; matches the canonical
                # .rules/compile-config.yaml budget. ADR-005 D5 records the
                # rationale.
                "token_budget": 8000,
                "include_layers": ["soul", "architecture", "conventions", "workflow"],
            },
        },
        "drift_detection": {
            "enabled": True,
            "hash_file": ".rules/.compile-hashes.json",
        },
    }
    (rd / "compile-config.yaml").write_text(
        yaml.dump(config, default_flow_style=False), encoding="utf-8"
    )

    return rd


class TestParseMdc:
    def test_with_frontmatter(self) -> None:
        text = '---\ndescription: "test"\nalwaysApply: true\n---\n\n# Body\n'
        fm, body = _parse_mdc(text)
        assert fm["description"] == "test"
        assert "# Body" in body

    def test_without_frontmatter(self) -> None:
        text = "# Just body\n\nSome content.\n"
        fm, body = _parse_mdc(text)
        assert fm == {}
        assert body == text


class TestEstimateTokens:
    def test_basic_estimate(self) -> None:
        assert _estimate_tokens("abcd") == 1
        assert _estimate_tokens("a" * 400) == 100

    def test_empty_string(self) -> None:
        assert _estimate_tokens("") == 0


class TestRuleCompiler:
    def test_load_config(self, rules_dir: Path) -> None:
        rc = RuleCompiler(rules_dir / "compile-config.yaml")
        assert len(rc.layers) == 5
        assert rc.layers[0].name == "soul"
        assert rc.layers[0].always_include is True
        assert "cursor" in rc.targets
        assert "agents_md" in rc.targets

    def test_load_layers(self, rules_dir: Path) -> None:
        rc = RuleCompiler(rules_dir / "compile-config.yaml")
        layers = rc.load_layers(rules_dir)
        assert len(layers) == 5
        assert "No absolute paths" in layers[0].content
        assert "4-Layer Hierarchy" in layers[1].content

    def test_compile_mdc_format(self, rules_dir: Path) -> None:
        rc = RuleCompiler(rules_dir / "compile-config.yaml")
        rc.load_layers(rules_dir)
        results = rc.compile("cursor")
        assert len(results) == 1
        r = results[0]
        assert r.target == "cursor"
        assert "---" in r.content
        assert "Soul" in r.content
        assert r.content_hash
        assert len(r.layers_included) == 5

    def test_compile_markdown_format(self, rules_dir: Path) -> None:
        rc = RuleCompiler(rules_dir / "compile-config.yaml")
        rc.load_layers(rules_dir)
        results = rc.compile("agents_md")
        assert len(results) == 1
        r = results[0]
        assert r.target == "agents_md"
        assert "<!-- Auto-generated" in r.content
        assert "Soul" in r.content
        assert "Style" not in r.content

    def test_compile_all_targets(self, rules_dir: Path) -> None:
        rc = RuleCompiler(rules_dir / "compile-config.yaml")
        rc.load_layers(rules_dir)
        results = rc.compile()
        assert len(results) == 2
        targets = {r.target for r in results}
        assert targets == {"cursor", "agents_md"}

    def test_unknown_target_raises(self, rules_dir: Path) -> None:
        rc = RuleCompiler(rules_dir / "compile-config.yaml")
        with pytest.raises(ValueError, match="Unknown target"):
            rc.compile("nonexistent")

    def test_compile_hash_generation(self, rules_dir: Path) -> None:
        rc = RuleCompiler(rules_dir / "compile-config.yaml")
        rc.load_layers(rules_dir)
        results = rc.compile()
        for r in results:
            assert len(r.content_hash) == 16
            assert all(c in "0123456789abcdef" for c in r.content_hash)

    def test_token_budget_overflow_raises_loudly(self, tmp_path: Path) -> None:
        """v14.2.1 G-011: budget overflow hard-fails instead of truncating.

        Pre-v14.2.1 the compiler silently dropped the lowest-priority
        non-``always_include`` layer(s) to fit the budget (S-5 violation;
        happened twice historically — v9.0.0 PV-07 Workflow drop,
        v11.4.0 Style drop). The error message must name the target and
        the overflow amount so the operator can act without re-deriving
        the arithmetic.
        """
        rd = tmp_path / ".rules_budget"
        rd.mkdir()

        big_content = "x" * 2000
        (rd / "soul.mdc").write_text(f"---\npriority: P0\n---\n\n{big_content}\n", encoding="utf-8")
        (rd / "style.mdc").write_text(
            f"---\npriority: P4\n---\n\n{big_content}\n", encoding="utf-8"
        )

        config = {
            "version": "1.0",
            "source_dir": str(rd),
            "layers": [
                {"name": "soul", "file": "soul.mdc", "priority": 0, "always_include": True},
                {"name": "style", "file": "style.mdc", "priority": 4, "always_include": False},
            ],
            "targets": {
                "tight": {
                    "output": "out.mdc",
                    "format": "mdc",
                    "token_budget": 600,
                    "include_layers": ["soul", "style"],
                }
            },
        }
        config_path = rd / "compile-config.yaml"
        config_path.write_text(yaml.dump(config), encoding="utf-8")

        rc = RuleCompiler(config_path)
        rc.load_layers(rd)
        with pytest.raises(TokenBudgetExceededError) as excinfo:
            rc.compile("tight")

        msg = str(excinfo.value)
        assert "'tight'" in msg, "error must name the overflowing target"
        assert "token_budget=600" in msg, "error must name the configured budget"
        # ~1000 rendered tokens vs 600 budget → overflow amount is stated.
        assert "exceeding" in msg and "by " in msg, "error must state the overflow amount"

    def test_overflow_with_only_always_include_layers_still_raises(self, tmp_path: Path) -> None:
        """v14.2.1 G-011: no escape hatch when nothing is droppable.

        Pre-v14.2.1 an all-``always_include`` overflow silently emitted
        OVER-budget output (the drop loop broke out with nothing
        droppable). Now it raises like every other overflow, with the
        message flagging that no layer is droppable.
        """
        rd = tmp_path / ".rules_soul"
        rd.mkdir()

        (rd / "soul.mdc").write_text(
            "---\npriority: P0\n---\n\n# Soul " + "x" * 4000 + "\n", encoding="utf-8"
        )

        config = {
            "version": "1.0",
            "layers": [
                {"name": "soul", "file": "soul.mdc", "priority": 0, "always_include": True},
            ],
            "targets": {
                "test": {
                    "output": "out.mdc",
                    "format": "mdc",
                    "token_budget": 100,
                    "include_layers": ["soul"],
                }
            },
        }
        config_path = rd / "compile-config.yaml"
        config_path.write_text(yaml.dump(config), encoding="utf-8")

        rc = RuleCompiler(config_path)
        rc.load_layers(rd)
        with pytest.raises(TokenBudgetExceededError, match="no non-always_include layer"):
            rc.compile("test")

    def test_compile_layers_included_reflects_post_truncation_state(self, tmp_path: Path) -> None:
        """v12.0.0 PV-05 accounting contract, re-pinned under v14.2.1 G-011.

        Originally this test pinned the v12.0.0 PV-05 fix where
        ``layers_included`` reflected the POST-truncation retained set.
        v14.2.1 (G-011) supersedes silent truncation entirely: overflow
        hard-fails. The post-truncation accounting now surfaces in the
        :class:`TokenBudgetExceededError` message instead — the error
        MUST name the exact layer(s) the legacy drop loop would have
        silently removed (``style`` here, the lowest-priority
        non-``always_include`` layer), preserving the v12.0.0 PV-05
        truth-in-accounting contract in its new loud-failure form.
        Source: ``.local/research/v14.2.0_gap_analysis.md`` §2.2 G-011 +
        ``docs/cycle-archive/v11.4.0/v11.4.0_retrospective.md`` §3 + §4.
        """
        rd = tmp_path / ".rules_post_trunc"
        rd.mkdir()

        big = "x" * 2800
        (rd / "soul.mdc").write_text(f"---\npriority: P0\n---\n\n{big}\n", encoding="utf-8")
        (rd / "conventions.mdc").write_text(f"---\npriority: P2\n---\n\n{big}\n", encoding="utf-8")
        (rd / "style.mdc").write_text(f"---\npriority: P4\n---\n\n{big}\n", encoding="utf-8")

        config = {
            "version": "1.0",
            "layers": [
                {"name": "soul", "file": "soul.mdc", "priority": 0, "always_include": True},
                {
                    "name": "conventions",
                    "file": "conventions.mdc",
                    "priority": 2,
                    "always_include": False,
                },
                {"name": "style", "file": "style.mdc", "priority": 4, "always_include": False},
            ],
            "targets": {
                "tight": {
                    "output": "out.mdc",
                    "format": "mdc",
                    "token_budget": 1500,
                    "include_layers": ["soul", "conventions", "style"],
                }
            },
        }
        config_path = rd / "compile-config.yaml"
        config_path.write_text(yaml.dump(config), encoding="utf-8")

        rc = RuleCompiler(config_path)
        rc.load_layers(rd)
        with pytest.raises(TokenBudgetExceededError) as excinfo:
            rc.compile("tight")

        msg = str(excinfo.value)
        assert "style" in msg, (
            "G-011 contract: the overflow error must name the layer(s) the "
            "legacy silent-truncation path would have dropped (style is the "
            "lowest-priority non-always_include layer in this fixture)."
        )
        assert "soul" not in msg.split("would have dropped")[-1].split(".")[0], (
            "soul (always_include=True) must NOT be listed among the would-have-dropped layers."
        )

    def test_compile_all_overflow_writes_no_outputs(self, tmp_path: Path) -> None:
        """v14.2.1 G-011: an overflowing ``compile_all`` leaves no partial files.

        ``compile_all`` compiles every target in-memory before writing;
        the overflow raise aborts the run before any output or hash-store
        write, so a failed compile cannot leave a half-regenerated
        ``.cursor/rules/`` + ``AGENTS.md`` surface behind.
        """
        rd = tmp_path / ".rules"
        rd.mkdir()
        (rd / "soul.mdc").write_text(
            "---\npriority: P0\n---\n\n# Soul " + "x" * 4000 + "\n", encoding="utf-8"
        )

        config = {
            "version": "1.0",
            "layers": [
                {"name": "soul", "file": "soul.mdc", "priority": 0, "always_include": True},
            ],
            "targets": {
                "tight": {
                    "output": "out.mdc",
                    "format": "mdc",
                    "token_budget": 100,
                    "include_layers": ["soul"],
                }
            },
            "drift_detection": {
                "enabled": True,
                "hash_file": ".rules/.compile-hashes.json",
            },
        }
        config_path = rd / "compile-config.yaml"
        config_path.write_text(yaml.dump(config), encoding="utf-8")

        rc = RuleCompiler(config_path)
        rc.load_layers(rd)
        with pytest.raises(TokenBudgetExceededError):
            rc.compile_all()

        assert not (tmp_path / "out.mdc").exists(), (
            "compile_all must not write target outputs when any target overflows"
        )
        assert not (rd / ".compile-hashes.json").exists(), (
            "compile_all must not update the drift hash store when compilation fails"
        )

    def test_compile_layers_included_happy_path_unchanged(self, rules_dir: Path) -> None:
        """v12.0.0 PV-05: happy-path ``layers_included`` reporting preserved.

        When no truncation runs (tokens <= token_budget), the
        ``layers_included`` field continues to reflect the ``selected``
        list (every layer matched by ``include_layers`` whose content is
        non-empty). This pins the byte-stable happy-path branch so the
        v12.0.0 PV-05 fix cannot accidentally regress the no-truncation
        path. See ``.local/research/v12.0.0_gap_analysis.md`` §6.
        """
        rc = RuleCompiler(rules_dir / "compile-config.yaml")
        rc.load_layers(rules_dir)
        cursor_results = rc.compile("cursor")
        r = cursor_results[0]
        assert r.tokens_used <= r.tokens_budget
        assert set(r.layers_included) == {
            "soul",
            "architecture",
            "conventions",
            "workflow",
            "style",
        }

    def test_compile_all_writes_files(self, rules_dir: Path) -> None:
        rc = RuleCompiler(rules_dir / "compile-config.yaml")
        rc.load_layers(rules_dir)
        results = rc.compile_all()
        assert len(results) == 2

        repo_root = rules_dir.parent
        cursor_output = repo_root / ".cursor" / "rules" / "repo-governance.mdc"
        assert cursor_output.exists()

        agents_output = repo_root / "AGENTS.md"
        assert agents_output.exists()

    def test_auto_loads_layers_on_compile(self, rules_dir: Path) -> None:
        rc = RuleCompiler(rules_dir / "compile-config.yaml")
        results = rc.compile()
        assert all(r.tokens_used > 0 for r in results)


class TestDataclasses:
    def test_rule_layer_defaults(self) -> None:
        layer = RuleLayer(name="test", priority=0, content="body")
        assert layer.always_include is False

    def test_target_config_fields(self) -> None:
        tc = TargetConfig(
            name="t",
            output="out.md",
            format="markdown",
            token_budget=1000,
            include_layers=["soul"],
        )
        assert tc.frontmatter is None
        assert tc.append_marker is None

    def test_compile_result_fields(self) -> None:
        cr = CompileResult(
            target="t",
            content="body",
            tokens_used=10,
            tokens_budget=100,
            layers_included=["soul"],
            content_hash="abc123",
        )
        assert cr.target == "t"
        assert cr.tokens_used == 10


REPO_ROOT = Path(__file__).resolve().parents[1]
REPO_COMPILE_CONFIG = REPO_ROOT / ".rules" / "compile-config.yaml"


@pytest.fixture(scope="module")
def repo_compile_results() -> dict[str, CompileResult]:
    """Compile the actual repo .rules/ in-memory (does not write to disk).

    Returns a mapping {target_name: CompileResult}. Used by the v8.3.0 v8.2.2
    rule-presence and budget assertions to avoid mutating the on-disk
    artifacts during the test run (the writers ran already at patch time).
    """
    rc = RuleCompiler(REPO_COMPILE_CONFIG)
    rc.load_layers(REPO_ROOT / ".rules")
    results = rc.compile()
    return {r.target: r for r in results}


class TestV822RulesFoundationCompile:
    """v8.2.2 — Rules Layer Foundation acceptance tests.

    Closes gaps H-002 (S-8 + S-9), H-003 (C-9), and M-004-part (A-4) per
    `.local/research/v8.3.0_design.md` §3 and `.local/research/v8.3.0_patch_plan.md`
    §v8.2.2 AC-2..AC-4 + AC-7.
    """

    def test_s8_in_cursor_compiled_output(
        self, repo_compile_results: dict[str, CompileResult]
    ) -> None:
        cursor = repo_compile_results["cursor"]
        assert "## S-8 — No Writes Outside Active Change Owned Files" in cursor.content
        assert "owned_files.txt" in cursor.content
        assert "v15-ADR-008 §S-8" in cursor.content

    def test_s9_in_cursor_compiled_output(
        self, repo_compile_results: dict[str, CompileResult]
    ) -> None:
        cursor = repo_compile_results["cursor"]
        assert "## S-9 — Handoff Envelopes Are Append-Only" in cursor.content
        assert "append-only" in cursor.content.lower()
        assert "v15-ADR-008 §S-9" in cursor.content

    def test_a4_in_cursor_compiled_output(
        self, repo_compile_results: dict[str, CompileResult]
    ) -> None:
        cursor = repo_compile_results["cursor"]
        assert "## A-4 — Source-of-Truth Spec Location (M-004 ADR)" in cursor.content
        assert ".local/memory/specs/" in cursor.content
        assert "v15-ADR-008 §A-4" in cursor.content

    def test_c9_in_cursor_compiled_output(
        self, repo_compile_results: dict[str, CompileResult]
    ) -> None:
        cursor = repo_compile_results["cursor"]
        assert "## C-9 — Lightweight Agent Workspace Artifacts" in cursor.content
        assert "Soft budget" in cursor.content
        assert "Hard ceiling" in cursor.content
        assert "v15-ADR-008 §C-9" in cursor.content

    def test_a4_c9_s8_s9_in_agents_md_compiled_output(
        self, repo_compile_results: dict[str, CompileResult]
    ) -> None:
        """All four new rules belong to always_include layers (soul/architecture/conventions),
        so they MUST appear in AGENTS.md per the compile-config target spec."""
        agents = repo_compile_results["agents_md"]
        assert "## S-8 — No Writes Outside Active Change Owned Files" in agents.content
        assert "## S-9 — Handoff Envelopes Are Append-Only" in agents.content
        assert "## A-4 — Source-of-Truth Spec Location (M-004 ADR)" in agents.content
        assert "## C-9 — Lightweight Agent Workspace Artifacts" in agents.content

    def test_compile_budget_agents_md_under_14000_tokens(
        self, repo_compile_results: dict[str, CompileResult]
    ) -> None:
        """AC-7: AGENTS.md token estimate must remain ≤ 14000 (compile-config budget).

        v8.5.0 PV-05 bumped the AGENTS.md target from 6000 → 8000 to match
        the cursor target (parity), allowing W-16..W-20 rule additions to
        fit without truncation. See ADR-005 D5 for the v8.5.0 rationale.

        v9.0.0 PV-07 bumped 8000 → 12000 to absorb the W-21 Soul-set freeze
        governance rule (~+30 LOC source). Pre-PV-07 utilization was
        ~8180/8000 (over budget — silently dropped the workflow layer);
        the bump preserved the full 4-layer corpus and gave ~46% headroom
        for v9.x sustaining additions per ADR-007 D5.

        v11.4.0 cycle-close bumped 12000 → 14000 (parity bump on cursor
        + agents_md targets) to absorb the new W-24 Subagent Pattern
        Selection rule. Pre-bump cursor utilization at v11.4.0 was
        11979/12000 (saturated; the W-24 push silently dropped the Style
        Rules layer in the cursor target); post-bump cursor 12740/14000
        (~9% headroom; all 5 layers preserved). agents_md was 11708/12000
        pre-bump (97.6%); post-bump 11708/14000 (~16% headroom; 4 layers).
        See `.local/research/v11.4.0_subagent_pattern_analysis.md` and
        the v11.4.0 retrospective §2 Q7 mid-cycle discovery for details.
        """
        agents = repo_compile_results["agents_md"]
        assert agents.tokens_budget == 14000
        assert agents.tokens_used <= 14000, (
            f"AGENTS.md exceeded 14000-token budget: {agents.tokens_used}"
        )

    def test_compile_budget_cursor_under_14000_tokens(
        self, repo_compile_results: dict[str, CompileResult]
    ) -> None:
        """AC-7: cursor MDC token estimate must remain ≤ 14000 (compile-config budget).

        v9.0.0 PV-07 bumped 8000 → 12000 (parity with agents_md target) to
        absorb the W-21 Soul-set freeze governance rule. Pre-PV-07 utilization
        was ~9210/8000 (over budget — dropped the workflow layer); the bump
        preserved the canonical 5-layer corpus per ADR-007 D5.

        v11.4.0 cycle-close bumped 12000 → 14000 (parity bump on both
        cursor + agents_md targets) to absorb the new W-24 Subagent Pattern
        Selection rule. Pre-bump utilization was 11979/12000 (saturated;
        W-24 push silently dropped the Style Rules layer); post-bump
        12740/14000 (~9% headroom; all 5 layers preserved per ADR-007 D5).
        See `.local/research/v11.4.0_subagent_pattern_analysis.md` and
        the v11.4.0 retrospective §2 Q7 mid-cycle discovery for details.
        """
        cursor = repo_compile_results["cursor"]
        assert cursor.tokens_budget == 14000
        assert cursor.tokens_used <= 14000, (
            f".cursor/rules/repo-governance.mdc exceeded 14000-token budget: {cursor.tokens_used}"
        )

    def test_existing_soul_rules_preserved_byte_identical(
        self, repo_compile_results: dict[str, CompileResult]
    ) -> None:
        """I-PV02-D R5 invariant: existing S-1..S-7 must remain present and
        unmodified after the S-8 + S-9 append. Verified by checking each
        rule heading is still emitted in the compiled cursor output."""
        cursor = repo_compile_results["cursor"]
        for rule in (
            "## S-1 — Dispatcher-Not-Implementer Invariant",
            "## S-2 — No Absolute Paths in Agent Files",
            "## S-3 — Test Coverage Floor",
            "## S-4 — No Ghost Features",
            "## S-5 — No Silent Failures",
            "## S-6 — Protected Branch Workflow",
            "## S-7 — External Resource URLs",
        ):
            assert rule in cursor.content, f"existing soul rule missing after append: {rule!r}"
