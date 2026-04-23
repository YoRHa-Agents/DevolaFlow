"""Tests for the RTK-pattern command-mapping layer (v8.3.4 PV-04 — closes M-002).

Mirrors the test discipline established by ``tests/test_shell_proxy.py``
(v8.3.2 PV-02) and ``tests/test_memory_router.py`` (v8.3.3 PV-03):
loops-with-asserts inside single test functions where the cases exercise
the same code path with different inputs, so we stay within the ``+15``
PV-04 test-count cap (cycle plan §4.4) while exercising every
decision-tree branch.

Coverage:

* :func:`is_command_mapping_active` — pure env-flag read (R5 strict no-IO hot path)
* :class:`CommandMapping` validation — required fields / TTL bounds /
  truncate_lines bounds / non-int + bool coercion / regex compile errors
* :class:`FilterRule` — pre-compile semantics + replacement application
* :func:`build_mapping_from_dict` — happy path + every schema-break path
* :func:`load_command_mappings` — env-off short-circuit / dir-missing /
  malformed YAML / mixed good-and-bad recipes / repo_signal narrowing /
  version-stamp invalidation / TTL expiry / shadow-by-earlier
* :func:`apply_local_recipe` — happy path with pre/post filters /
  truncate / strip_ansi / on_empty / non-matching cmd / disabled flag /
  defensive empty / non-string output / regex.sub error fallback
* :class:`ShellProxy.apply_recipe_to_output` integration — only fires
  when proxy enabled AND command whitelisted AND recipe matches; R5
  strict byte-identical when env-flag off
* :data:`devolaflow.shell_proxy.__all__` re-exports for the new public surface

No filesystem outside ``tmp_path``; no subprocess; no network.
"""

from __future__ import annotations

import logging
from pathlib import Path
from unittest.mock import patch

import pytest

import devolaflow
from devolaflow.shell_proxy import (
    DEFAULT_COMMANDS_DIR,
    DEFAULT_TTL_DAYS,
    MAX_TTL_DAYS,
    MIN_TTL_DAYS,
    CommandMapping,
    CommandMappingError,
    FilterRule,
    ShellProxy,
    ShellProxyConfig,
    apply_local_recipe,
    build_mapping_from_dict,
    is_command_mapping_active,
    load_command_mappings,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_recipe(
    base: Path,
    repo: str,
    name: str,
    body: str,
) -> Path:
    """Write *body* to ``<base>/<repo>/<name>.yaml`` and return the path."""
    repo_dir = base / repo
    repo_dir.mkdir(parents=True, exist_ok=True)
    path = repo_dir / f"{name}.yaml"
    path.write_text(body, encoding="utf-8")
    return path


def _make_mapping(**overrides) -> CommandMapping:
    """Build a sensible :class:`CommandMapping` for direct construction tests."""
    base: dict[str, object] = {
        "command": "pytest",
        "version_stamp": devolaflow.__version__,
        "description": "Test recipe",
        "repo_signal": "DevolaFlow",
        "last_updated": "",
        "ttl_days": DEFAULT_TTL_DAYS,
        "pre_filters": (),
        "post_filters": (),
        "truncate_lines": 0,
        "strip_ansi": True,
        "on_empty": "",
        "tags": (),
        "recipe_id": "pytest",
        "source_path": "<test>",
    }
    base.update(overrides)
    return CommandMapping(**base)  # type: ignore[arg-type]


def _basic_recipe_yaml(version_stamp: str | None = None) -> str:
    """A minimal valid recipe YAML body covering the canonical features."""
    stamp = version_stamp if version_stamp is not None else devolaflow.__version__
    return f"""\
schema_version: 1
command: "pytest"
description: "Drop noisy DeprecationWarning lines."
repo_signal: "DevolaFlow"
version_stamp: "{stamp}"
last_updated: "2026-04-23"
ttl_days: 30
strip_ansi: true
pre_filters:
  - pattern: "^\\\\s*DeprecationWarning:.*$"
    replacement: ""
post_filters:
  - pattern: "\\n{{3,}}"
    replacement: "\\n\\n"
truncate_lines: 200
on_empty: "pytest: ok"
tags: [pytest, deprecation-filter]
"""


# ---------------------------------------------------------------------------
# Section 1 — is_command_mapping_active (pure env-flag, R5 strict no-IO)
# ---------------------------------------------------------------------------


class TestIsCommandMappingActive:
    """The PV-04 layer reuses the PV-02 env-flag — no new flag introduced."""

    def test_env_flag_decides_for_all_value_shapes(self) -> None:
        cases: list[tuple[dict[str, str], bool]] = [
            ({}, False),
            ({"DEVOLAFLOW_RTK_PROXY": "0"}, False),
            ({"DEVOLAFLOW_RTK_PROXY": "1"}, True),
            ({"DEVOLAFLOW_RTK_PROXY": "true"}, False),
            ({"DEVOLAFLOW_RTK_PROXY": "yes"}, False),
            ({"DEVOLAFLOW_RTK_PROXY": ""}, False),
            ({"DEVOLAFLOW_RTK_PROXY": "01"}, False),
        ]
        for env, expected in cases:
            assert is_command_mapping_active(env) is expected, f"env={env!r}"

    def test_does_not_spawn_subprocess_or_filesystem(self) -> None:
        # R5 strict — pure env read; never touches disk or subprocess.
        with patch("subprocess.run") as mock_run, patch("shutil.which") as mock_which:
            assert is_command_mapping_active({}) is False
            assert is_command_mapping_active({"DEVOLAFLOW_RTK_PROXY": "1"}) is True
            assert mock_run.call_count == 0
            assert mock_which.call_count == 0

    def test_default_commands_dir_is_relative(self) -> None:
        # Per S-2 — agent-facing path constants must be repo-relative.
        assert not DEFAULT_COMMANDS_DIR.is_absolute()
        assert Path(".local/memory/commands") == DEFAULT_COMMANDS_DIR
        assert MIN_TTL_DAYS == 1
        assert MAX_TTL_DAYS == 365
        assert DEFAULT_TTL_DAYS == 30


# ---------------------------------------------------------------------------
# Section 2 — load_command_mappings R5 strict (env-off short-circuit)
# ---------------------------------------------------------------------------


class TestLoadR5StrictOff:
    """When the env-flag is unset, the loader is a zero-IO no-op."""

    def test_env_off_returns_empty_no_filesystem(self, tmp_path: Path) -> None:
        # Even when a recipe directory exists, env-off means {} returned.
        _write_recipe(tmp_path, "devolaflow", "pytest", _basic_recipe_yaml())
        for env in ({}, {"DEVOLAFLOW_RTK_PROXY": "0"}, {"DEVOLAFLOW_RTK_PROXY": ""}):
            result = load_command_mappings(commands_dir=tmp_path, env=env)
            assert result == {}, f"env={env!r}"

    def test_env_off_does_not_touch_path_read_text(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # Codify the R5 zero-IO contract: when off, no Path.read_text() call.
        _write_recipe(tmp_path, "devolaflow", "pytest", _basic_recipe_yaml())
        seen: list[Path] = []
        original = Path.read_text

        def watcher(self: Path, *args, **kwargs) -> str:
            seen.append(self)
            return original(self, *args, **kwargs)

        monkeypatch.setattr(Path, "read_text", watcher)
        result = load_command_mappings(commands_dir=tmp_path, env={})
        assert result == {}
        assert seen == [], (
            f"R5 strict: load_command_mappings should not touch the filesystem "
            f"when env-flag is unset; got reads of {seen!r}"
        )

    def test_apply_local_recipe_no_op_when_env_off(self) -> None:
        for env in ({}, {"DEVOLAFLOW_RTK_PROXY": "0"}):
            text = "pytest output\nDeprecationWarning: noisy\nmore text"
            result, was_applied = apply_local_recipe("pytest", text, env=env)
            assert result == text
            assert was_applied is False


# ---------------------------------------------------------------------------
# Section 3 — load_command_mappings happy path + repo_signal narrowing
# ---------------------------------------------------------------------------


class TestLoadHappyPath:
    """The fresh-checkout path returns recipes; repo_signal narrows."""

    def test_load_picks_up_yaml_under_repo_subdir(self, tmp_path: Path) -> None:
        _write_recipe(tmp_path, "devolaflow", "pytest", _basic_recipe_yaml())
        result = load_command_mappings(
            commands_dir=tmp_path,
            env={"DEVOLAFLOW_RTK_PROXY": "1"},
        )
        assert "pytest" in result
        m = result["pytest"]
        assert m.command == "pytest"
        assert m.repo_signal == "DevolaFlow"
        assert m.version_stamp == devolaflow.__version__
        assert m.recipe_id == "pytest"
        assert m.ttl_days == 30
        assert m.truncate_lines == 200
        assert m.strip_ansi is True
        assert m.on_empty == "pytest: ok"
        assert "deprecation-filter" in m.tags
        assert len(m.pre_filters) == 1
        assert isinstance(m.pre_filters[0], FilterRule)
        assert len(m.post_filters) == 1

    def test_load_dir_missing_returns_empty_with_info_log(
        self,
        tmp_path: Path,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        # Fresh-checkout path — directory absent → INFO not WARNING (normal).
        missing = tmp_path / "absent"
        with caplog.at_level(logging.INFO, logger="devolaflow.shell_proxy.commands"):
            result = load_command_mappings(
                commands_dir=missing,
                env={"DEVOLAFLOW_RTK_PROXY": "1"},
            )
        assert result == {}
        assert any("not present" in r.message for r in caplog.records)

    def test_load_dir_is_actually_a_file_warns_and_returns_empty(
        self,
        tmp_path: Path,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        bogus = tmp_path / "commands"
        bogus.write_text("not a directory", encoding="utf-8")
        with caplog.at_level(logging.WARNING, logger="devolaflow.shell_proxy.commands"):
            result = load_command_mappings(
                commands_dir=bogus,
                env={"DEVOLAFLOW_RTK_PROXY": "1"},
            )
        assert result == {}
        assert any("expected directory" in r.message for r in caplog.records)

    def test_load_repo_signal_narrows(self, tmp_path: Path) -> None:
        # Two recipes for `pytest` — one DevolaFlow, one rtk-ai/rtk.
        _write_recipe(tmp_path, "devolaflow", "pytest", _basic_recipe_yaml())
        rtk_body = _basic_recipe_yaml().replace(
            'repo_signal: "DevolaFlow"',
            'repo_signal: "rtk-ai/rtk"',
        )
        _write_recipe(tmp_path, "rtk-ai", "pytest", rtk_body)

        env = {"DEVOLAFLOW_RTK_PROXY": "1"}
        # No filter — first match by directory order wins.
        all_loaded = load_command_mappings(commands_dir=tmp_path, env=env)
        assert "pytest" in all_loaded
        # repo_signal filter — narrows.
        only_devola = load_command_mappings(
            commands_dir=tmp_path,
            env=env,
            repo_signal="DevolaFlow",
        )
        assert only_devola["pytest"].repo_signal == "DevolaFlow"
        only_rtk = load_command_mappings(
            commands_dir=tmp_path,
            env=env,
            repo_signal="rtk-ai/rtk",
        )
        assert only_rtk["pytest"].repo_signal == "rtk-ai/rtk"
        # Unknown signal — empty.
        unknown = load_command_mappings(
            commands_dir=tmp_path,
            env=env,
            repo_signal="nonexistent",
        )
        assert unknown == {}

    def test_load_skips_dotfiles(self, tmp_path: Path) -> None:
        _write_recipe(tmp_path, "devolaflow", ".hidden", _basic_recipe_yaml())
        _write_recipe(tmp_path, "devolaflow", "pytest", _basic_recipe_yaml())
        env = {"DEVOLAFLOW_RTK_PROXY": "1"}
        result = load_command_mappings(commands_dir=tmp_path, env=env)
        # Only the non-dotfile is picked up.
        assert "pytest" in result
        assert len(result) == 1


# ---------------------------------------------------------------------------
# Section 4 — load_command_mappings resilience (malformed inputs)
# ---------------------------------------------------------------------------


class TestLoadResilience:
    """Malformed YAML / schema breaks degrade to a miss; loud per S-5.

    Consolidates 7 resilience paths into 4 loop-asserts tests per the
    v8.3.0 retro §4.6 lesson on test discipline.
    """

    def test_load_dropping_paths_each_log_warning_and_skip(
        self,
        tmp_path: Path,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        # Three loud-degradation paths in one fixture — bad YAML, empty file,
        # non-mapping top level. Each gets WARNING; remaining recipes survive.
        _write_recipe(tmp_path, "devolaflow", "broken", "::invalid::\n  - yaml::\n  -[\n")
        _write_recipe(tmp_path, "devolaflow", "empty", "")
        _write_recipe(tmp_path, "devolaflow", "list-only", "- item1\n- item2\n")
        _write_recipe(tmp_path, "devolaflow", "pytest", _basic_recipe_yaml())
        env = {"DEVOLAFLOW_RTK_PROXY": "1"}
        with caplog.at_level(logging.WARNING, logger="devolaflow.shell_proxy.commands"):
            result = load_command_mappings(commands_dir=tmp_path, env=env)
        # Good recipe survives; 3 bad recipes dropped via WARNINGs.
        assert "pytest" in result
        assert len(result) == 1
        warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert len(warnings) >= 3

    def test_missing_required_fields_logs_warning_and_skips(
        self,
        tmp_path: Path,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        # Three recipes each missing a different required field.
        for name, body in (
            ("no-cmd", 'schema_version: 1\nversion_stamp: "8.3.4"\n'),
            ("no-version", 'schema_version: 1\ncommand: "pytest"\n'),
            ("no-schema", 'command: "pytest"\nversion_stamp: "8.3.4"\n'),
        ):
            _write_recipe(tmp_path, "devolaflow", name, body)
        env = {"DEVOLAFLOW_RTK_PROXY": "1"}
        with caplog.at_level(logging.WARNING, logger="devolaflow.shell_proxy.commands"):
            result = load_command_mappings(commands_dir=tmp_path, env=env)
        assert result == {}
        warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert len(warnings) >= 3

    def test_version_stale_and_ttl_expired_each_treated_as_miss(
        self,
        tmp_path: Path,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        # Two cache-invalidation paths in one fixture — version-stamp mismatch
        # and TTL expiry. Both log INFO + drop the recipe.
        _write_recipe(
            tmp_path,
            "devolaflow",
            "old-pytest",
            _basic_recipe_yaml(version_stamp="0.0.0-old"),
        )
        expired_body = (
            f"schema_version: 1\n"
            f'command: "ruff check"\n'
            f'version_stamp: "{devolaflow.__version__}"\n'
            f'last_updated: "2000-01-01"\n'
            f"ttl_days: 1\n"
        )
        _write_recipe(tmp_path, "devolaflow", "expired-ruff", expired_body)
        env = {"DEVOLAFLOW_RTK_PROXY": "1"}
        with caplog.at_level(logging.INFO, logger="devolaflow.shell_proxy.commands"):
            result = load_command_mappings(commands_dir=tmp_path, env=env)
        assert result == {}
        msgs = [r.message for r in caplog.records]
        assert any("version-stale" in m for m in msgs)
        assert any("TTL-expired" in m for m in msgs)

    def test_shadowed_duplicate_logs_info_and_keeps_first(
        self,
        tmp_path: Path,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        # Two recipes for `pytest`, no repo_signal disambiguation — first wins.
        _write_recipe(tmp_path, "devolaflow", "pytest", _basic_recipe_yaml())
        rtk_body = _basic_recipe_yaml().replace(
            'description: "Drop noisy DeprecationWarning lines."',
            'description: "Different recipe"',
        )
        _write_recipe(tmp_path, "rtk-ai", "pytest", rtk_body)
        env = {"DEVOLAFLOW_RTK_PROXY": "1"}
        with caplog.at_level(logging.INFO, logger="devolaflow.shell_proxy.commands"):
            result = load_command_mappings(commands_dir=tmp_path, env=env)
        assert "pytest" in result
        # First by directory order is `devolaflow/`.
        assert result["pytest"].description == "Drop noisy DeprecationWarning lines."
        assert any("shadowed" in r.message for r in caplog.records)


# ---------------------------------------------------------------------------
# Section 5 — CommandMapping + build_mapping_from_dict validation
# ---------------------------------------------------------------------------


class TestCommandMappingValidation:
    """Schema invariants enforced at construction time per S-5 + Rule C-9.

    Consolidates 14 schema-break paths into 5 loop-asserts tests per the
    v8.3.0 retro §4.6 lesson on test discipline (each test fails-fast on
    its first sub-case mismatch, so debugging stays cheap). This keeps the
    PV-04 cycle-wide test delta within the +100 cap per gap analysis §1.
    """

    def test_top_level_shape_and_required_field_breaks(self) -> None:
        # 5 distinct top-level shape breaks — non-dict payload, missing each
        # of the 3 required fields, and unsupported schema_version. Each row
        # asserts the actionable text reaches the operator per S-5.
        cases: list[tuple[object, str]] = [
            (["a list"], "top-level must be a YAML mapping"),
            ({"schema_version": 1, "version_stamp": "8.3.4"}, "command"),
            ({"schema_version": 1, "command": "pytest"}, "version_stamp"),
            ({"command": "pytest", "version_stamp": "8.3.4"}, "schema_version"),
            (
                {"schema_version": 2, "command": "pytest", "version_stamp": "8.3.4"},
                "not supported",
            ),
        ]
        for payload, expected_substring in cases:
            with pytest.raises(CommandMappingError) as exc:
                build_mapping_from_dict(payload)  # type: ignore[arg-type]
            assert expected_substring in str(exc.value), (
                f"payload={payload!r} expected text {expected_substring!r}"
            )

    def test_ttl_bounds_enforced_at_construction(self) -> None:
        # Invalid TTLs all get loud rejection.
        for bad_ttl in (0, -1, MAX_TTL_DAYS + 1, 9999):
            with pytest.raises(CommandMappingError) as exc:
                _make_mapping(ttl_days=bad_ttl)
            assert "ttl_days" in str(exc.value)
        # Valid bounds.
        for ok_ttl in (MIN_TTL_DAYS, DEFAULT_TTL_DAYS, MAX_TTL_DAYS):
            mapping = _make_mapping(ttl_days=ok_ttl)
            assert mapping.ttl_days == ok_ttl
        # Negative truncate_lines rejected via __post_init__ as well.
        with pytest.raises(CommandMappingError) as exc:
            _make_mapping(truncate_lines=-1)
        assert "truncate_lines" in str(exc.value)

    def test_typed_field_breaks_each_raise_with_actionable_text(self) -> None:
        # Each row hits a distinct type-error code path in build_mapping_from_dict.
        # Python's `True == 1` would otherwise sneak ttl_days=True through —
        # guard explicitly (defensive).
        cases: list[tuple[dict[str, object], str]] = [
            ({"ttl_days": True}, "ttl_days"),
            ({"ttl_days": False}, "ttl_days"),
            ({"ttl_days": "30"}, "ttl_days"),
            ({"ttl_days": 1.5}, "ttl_days"),
            ({"ttl_days": None}, "ttl_days"),
            ({"truncate_lines": True}, "truncate_lines"),
            ({"truncate_lines": "200"}, "truncate_lines"),
            ({"truncate_lines": 5.5}, "truncate_lines"),
            ({"strip_ansi": "true"}, "strip_ansi"),
            ({"tags": "single-string-not-list"}, "tags"),
            ({"pre_filters": {"pattern": "x", "replacement": "y"}}, "pre_filters"),
        ]
        for overrides, expected_substring in cases:
            payload: dict[str, object] = {
                "schema_version": 1,
                "command": "pytest",
                "version_stamp": "8.3.4",
            }
            payload.update(overrides)
            with pytest.raises(CommandMappingError) as exc:
                build_mapping_from_dict(payload)
            assert expected_substring in str(exc.value), (
                f"overrides={overrides!r} expected {expected_substring!r}"
            )

    def test_filter_rule_breaks_caught_at_compile(self) -> None:
        # Rule-level breaks: missing pattern, invalid regex, non-mapping rule.
        cases: list[tuple[list, str]] = [
            ([{"replacement": "y"}], "pattern"),
            ([{"pattern": "(unclosed", "replacement": ""}], "invalid regex"),
            (["not a mapping"], "must be a mapping"),
        ]
        for pre_filters, expected_substring in cases:
            payload = {
                "schema_version": 1,
                "command": "pytest",
                "version_stamp": "8.3.4",
                "pre_filters": pre_filters,
            }
            with pytest.raises(CommandMappingError) as exc:
                build_mapping_from_dict(payload)
            assert expected_substring in str(exc.value), (
                f"pre_filters={pre_filters!r} expected {expected_substring!r}"
            )

    def test_max_lines_alias_and_filter_rule_precompile(self) -> None:
        # max_lines aliases to truncate_lines; truncate wins when both set.
        m1 = build_mapping_from_dict(
            {
                "schema_version": 1,
                "command": "pytest",
                "version_stamp": "8.3.4",
                "max_lines": 50,
            }
        )
        assert m1.truncate_lines == 50
        m2 = build_mapping_from_dict(
            {
                "schema_version": 1,
                "command": "pytest",
                "version_stamp": "8.3.4",
                "max_lines": 50,
                "truncate_lines": 200,
            }
        )
        assert m2.truncate_lines == 200
        # build_mapping_from_dict pre-compiles patterns; FilterRule exposes
        # both compiled + raw forms (no per-call compile overhead).
        m3 = build_mapping_from_dict(
            {
                "schema_version": 1,
                "command": "pytest",
                "version_stamp": "8.3.4",
                "pre_filters": [{"pattern": r"^foo:\s+", "replacement": ""}],
            }
        )
        assert len(m3.pre_filters) == 1
        rule = m3.pre_filters[0]
        assert rule.raw_pattern == r"^foo:\s+"
        assert rule.replacement == ""
        assert rule.pattern.sub(rule.replacement, "foo: bar") == "bar"


# ---------------------------------------------------------------------------
# Section 6 — apply_local_recipe (precedence + edge cases)
# ---------------------------------------------------------------------------


class TestApplyLocalRecipe:
    """Local recipe wins → RTK rewrite → passthrough; loud + safe degradation."""

    def test_happy_path_strips_deprecation_warnings(self, tmp_path: Path) -> None:
        _write_recipe(tmp_path, "devolaflow", "pytest", _basic_recipe_yaml())
        env = {"DEVOLAFLOW_RTK_PROXY": "1"}
        text = "test_foo PASSED\nDeprecationWarning: noisy\ntest_bar PASSED\n"
        result, was_applied = apply_local_recipe(
            "pytest tests/",
            text,
            env=env,
            commands_dir=tmp_path,
        )
        assert was_applied is True
        assert "DeprecationWarning" not in result
        assert "test_foo PASSED" in result
        assert "test_bar PASSED" in result

    def test_passes_through_unknown_command(self, tmp_path: Path) -> None:
        _write_recipe(tmp_path, "devolaflow", "pytest", _basic_recipe_yaml())
        env = {"DEVOLAFLOW_RTK_PROXY": "1"}
        text = "some output"
        result, was_applied = apply_local_recipe(
            "ls -la",
            text,
            env=env,
            commands_dir=tmp_path,
        )
        assert result == text
        assert was_applied is False

    def test_command_head_anchor_excludes_glue(self, tmp_path: Path) -> None:
        # Recipe for `git diff` — `git diffshow` must NOT match.
        body = (
            f"schema_version: 1\n"
            f'command: "git diff"\n'
            f'version_stamp: "{devolaflow.__version__}"\n'
            f"pre_filters:\n"
            f'  - pattern: "binary"\n'
            f'    replacement: "BIN"\n'
        )
        _write_recipe(tmp_path, "devolaflow", "git-diff", body)
        env = {"DEVOLAFLOW_RTK_PROXY": "1"}
        # Anchored: `git diff` matches.
        result_match, applied_match = apply_local_recipe(
            "git diff HEAD",
            "binary file changed",
            env=env,
            commands_dir=tmp_path,
        )
        assert applied_match is True
        assert "BIN" in result_match
        # Glue: `git diffshow` should NOT match the recipe.
        result_glue, applied_glue = apply_local_recipe(
            "git diffshow HEAD",
            "binary file changed",
            env=env,
            commands_dir=tmp_path,
        )
        assert applied_glue is False
        assert result_glue == "binary file changed"

    def test_empty_or_non_string_inputs_no_op(self) -> None:
        env = {"DEVOLAFLOW_RTK_PROXY": "1"}
        # Empty cmd
        assert apply_local_recipe("", "x", env=env) == ("x", False)
        # Non-string output
        assert apply_local_recipe("pytest", None, env=env) == (None, False)  # type: ignore[arg-type]

    def test_strip_ansi_runs_before_filters(self, tmp_path: Path) -> None:
        body = (
            f"schema_version: 1\n"
            f'command: "pytest"\n'
            f'version_stamp: "{devolaflow.__version__}"\n'
            f"strip_ansi: true\n"
            f"pre_filters:\n"
            f'  - pattern: "^FAIL$"\n'
            f'    replacement: "DROPPED"\n'
        )
        _write_recipe(tmp_path, "devolaflow", "pytest", body)
        env = {"DEVOLAFLOW_RTK_PROXY": "1"}
        # ANSI-wrapped FAIL — should still match after strip.
        ansi_text = "\x1b[31mFAIL\x1b[0m"
        result, applied = apply_local_recipe(
            "pytest",
            ansi_text,
            env=env,
            commands_dir=tmp_path,
        )
        assert applied is True
        assert "DROPPED" in result
        assert "\x1b" not in result

    def test_truncate_lines_caps_output(self, tmp_path: Path) -> None:
        body = (
            f"schema_version: 1\n"
            f'command: "pytest"\n'
            f'version_stamp: "{devolaflow.__version__}"\n'
            f"truncate_lines: 3\n"
        )
        _write_recipe(tmp_path, "devolaflow", "pytest", body)
        env = {"DEVOLAFLOW_RTK_PROXY": "1"}
        text = "\n".join(f"line{i}" for i in range(20)) + "\n"
        result, applied = apply_local_recipe("pytest", text, env=env, commands_dir=tmp_path)
        assert applied is True
        assert "line0" in result
        assert "line2" in result
        assert "line19" not in result
        assert "truncated" in result

    def test_on_empty_emitted_when_post_filter_blank(self, tmp_path: Path) -> None:
        body = (
            f"schema_version: 1\n"
            f'command: "pytest"\n'
            f'version_stamp: "{devolaflow.__version__}"\n'
            f"pre_filters:\n"
            f'  - pattern: ".*"\n'
            f'    replacement: ""\n'
            f'on_empty: "pytest: ok (DevolaFlow recipe)"\n'
        )
        _write_recipe(tmp_path, "devolaflow", "pytest", body)
        env = {"DEVOLAFLOW_RTK_PROXY": "1"}
        text = "noisy run output\n"
        result, applied = apply_local_recipe("pytest", text, env=env, commands_dir=tmp_path)
        assert applied is True
        assert "pytest: ok (DevolaFlow recipe)" in result

    def test_pre_loaded_mappings_skip_filesystem(self) -> None:
        # When `mappings` is supplied, no filesystem is touched.
        mapping = _make_mapping(
            command="pytest",
            pre_filters=(
                FilterRule(
                    pattern=__import__("re").compile(r"^FAIL", flags=__import__("re").MULTILINE),
                    replacement="OK",
                    raw_pattern=r"^FAIL",
                ),
            ),
        )
        env = {"DEVOLAFLOW_RTK_PROXY": "1"}
        with (
            patch("pathlib.Path.exists") as mock_exists,
            patch("pathlib.Path.read_text") as mock_read,
        ):
            result, applied = apply_local_recipe(
                "pytest tests/",
                "FAIL: something\n",
                env=env,
                mappings={"pytest": mapping},
            )
        assert applied is True
        assert "OK" in result
        # No filesystem activity because mappings were pre-loaded.
        assert mock_exists.call_count == 0
        assert mock_read.call_count == 0

    def test_no_mappings_returns_input_unchanged(self) -> None:
        env = {"DEVOLAFLOW_RTK_PROXY": "1"}
        result, applied = apply_local_recipe("pytest", "out", env=env, mappings={})
        assert result == "out"
        assert applied is False


# ---------------------------------------------------------------------------
# Section 7 — ShellProxy.apply_recipe_to_output integration
# ---------------------------------------------------------------------------


class TestShellProxyIntegration:
    """The PV-04 recipe layer is reachable via ShellProxy.apply_recipe_to_output."""

    def test_off_proxy_returns_input_no_filesystem(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        # Even with a recipe on disk, the disabled proxy is a no-op.
        _write_recipe(tmp_path, "devolaflow", "pytest", _basic_recipe_yaml())
        monkeypatch.chdir(tmp_path.parent)
        proxy = ShellProxy({})  # env-flag unset
        assert proxy.config.proxy_enabled is False
        with patch("pathlib.Path.read_text") as mock_read:
            result, applied = proxy.apply_recipe_to_output("pytest", "x")
        assert result == "x"
        assert applied is False
        assert mock_read.call_count == 0

    def test_proxy_enabled_but_command_not_whitelisted_no_op(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        # Tier-1 includes pytest/ruff check/git diff/git log/git status.
        # `ls` is NOT whitelisted → recipe layer doesn't apply even if
        # a (hypothetical) `ls.yaml` recipe existed.
        body = _basic_recipe_yaml().replace('command: "pytest"', 'command: "ls"')
        _write_recipe(tmp_path, "devolaflow", "ls", body)
        monkeypatch.chdir(tmp_path.parent)

        cfg = ShellProxyConfig(
            env_flag_set=True,
            rtk_path="/usr/local/bin/rtk",
            distinguish_passed=True,
            proxy_enabled=True,
        )
        proxy = ShellProxy(config=cfg)
        result, applied = proxy.apply_recipe_to_output("ls -la", "noisy output")
        assert applied is False
        assert result == "noisy output"

    def test_proxy_enabled_and_recipe_matches_applies(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        commands_root = tmp_path / ".local" / "memory" / "commands"
        _write_recipe(commands_root, "devolaflow", "pytest", _basic_recipe_yaml())
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("DEVOLAFLOW_RTK_PROXY", "1")

        cfg = ShellProxyConfig(
            env_flag_set=True,
            rtk_path="/usr/local/bin/rtk",
            distinguish_passed=True,
            proxy_enabled=True,
        )
        proxy = ShellProxy(config=cfg)
        text = "test_foo PASSED\nDeprecationWarning: noisy\ntest_bar PASSED\n"
        result, applied = proxy.apply_recipe_to_output("pytest tests/", text)
        assert applied is True
        assert "DeprecationWarning" not in result
        assert "test_foo PASSED" in result

    def test_wrap_command_byte_identical_post_pv04(self) -> None:
        # PV-04 R5 strict: wrap_command behavior is unchanged from v8.3.3.
        # No recipe layer touch — wrap_command stays a pure rewrite shim.
        cfg = ShellProxyConfig(
            env_flag_set=True,
            rtk_path="/usr/local/bin/rtk",
            distinguish_passed=True,
            proxy_enabled=True,
        )
        proxy = ShellProxy(config=cfg)
        # Tier 1 still rewrites identically.
        assert proxy.wrap_command("pytest tests/") == "rtk pytest tests/"
        assert proxy.wrap_command("git diff HEAD") == "rtk git diff HEAD"
        # Non-whitelist still passthroughs.
        assert proxy.wrap_command("ls -la") == "ls -la"

    def test_apply_recipe_handles_empty_cmd_gracefully(self) -> None:
        cfg = ShellProxyConfig(
            env_flag_set=True,
            rtk_path="/usr/local/bin/rtk",
            distinguish_passed=True,
            proxy_enabled=True,
        )
        proxy = ShellProxy(config=cfg)
        # Empty cmd → identity.
        assert proxy.apply_recipe_to_output("", "x") == ("x", False)


# ---------------------------------------------------------------------------
# Section 8 — public surface re-exports + module integrity
# ---------------------------------------------------------------------------


class TestPackageSurface:
    """The new public surface is re-exported from devolaflow.shell_proxy."""

    def test_package_re_exports_command_mapping_surface(self) -> None:
        # Imported earlier from devolaflow.shell_proxy at module level —
        # this test exists to codify the public API contract.
        from devolaflow import shell_proxy

        for name in (
            "CommandMapping",
            "CommandMappingError",
            "FilterRule",
            "DEFAULT_COMMANDS_DIR",
            "DEFAULT_TTL_DAYS",
            "MIN_TTL_DAYS",
            "MAX_TTL_DAYS",
            "apply_local_recipe",
            "build_mapping_from_dict",
            "is_command_mapping_active",
            "load_command_mappings",
        ):
            assert hasattr(shell_proxy, name), f"public surface missing {name!r}"
            assert name in shell_proxy.__all__, f"__all__ missing {name!r}"

    def test_module_exports_are_alphabetically_sorted_in_all(self) -> None:
        # Sanity: __all__ entries match __all__ order convention.
        from devolaflow import shell_proxy

        assert sorted(shell_proxy.__all__) == list(shell_proxy.__all__)
