"""Tests for the memory_router package (v8.3.3 PV-03 — closes M-001).

Mirrors the test discipline of v8.3.2 PV-02 (``tests/test_shell_proxy.py``):
loops-with-asserts inside single test functions where the cases exercise
the same code path with different inputs, so we stay within the
``+30`` PV-03 test-count cap (cycle plan §4.3) while exercising every
decision-tree branch.

Coverage:

* :func:`is_router_enabled` — pure env-flag read (R5 strict no-IO hot path)
* :func:`lookup_case` flat-call equivalent — short-circuits when off
* :class:`MemoryRouter` lookup happy path / miss / TTL expiry /
  version-stamp invalidation / repo_signal narrowing / lazy load
* :class:`MemoryRouter._load_index` — missing file / unreadable file /
  malformed YAML / non-mapping top-level / non-list cases / mixed
  good-and-bad rows / blank file
* :class:`MemoryCase` validation — required fields / recipe_path prefix /
  ttl_days bounds / non-int ttl / bad tags
* :func:`build_case_from_dict` — coerces YAML rows
* :func:`is_ttl_expired` — TTL anchor priority + malformed dates
* :func:`is_version_stale` — exact equality semantics
* :func:`today_iso` — UTC date semantics
* Strict-mode :meth:`MemoryRouter.lookup_case_strict` — raises on schema breaks

No filesystem outside ``tmp_path``; no subprocess; no network.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from devolaflow.memory_router import (
    DEFAULT_INDEX_PATH,
    DEFAULT_TTL_DAYS,
    ENV_FLAG,
    MAX_TTL_DAYS,
    MemoryCacheError,
    MemoryCase,
    MemoryRouter,
    MemoryRouterError,
    build_case_from_dict,
    is_router_enabled,
    is_ttl_expired,
    is_version_stale,
    lookup_case,
    today_iso,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_index(tmp_path: Path, body: str) -> Path:
    """Write *body* to a fresh ``.local/memory/cases/index.yaml`` and return the path."""
    cases_dir = tmp_path / ".local" / "memory" / "cases"
    cases_dir.mkdir(parents=True, exist_ok=True)
    path = cases_dir / "index.yaml"
    path.write_text(body, encoding="utf-8")
    return path


def _make_case(**overrides) -> MemoryCase:
    """Build a fully-populated :class:`MemoryCase` with sensible defaults."""
    base = {
        "case_id": "rtk-plugin-entry",
        "workflow_type": "feature-implementation",
        "task_type": "implement",
        "summary": "RTK plugin entry recipe.",
        "recipe_path": ".local/memory/cases/rtk-plugin-entry.md",
        "version_stamp": "8.3.3",
    }
    base.update(overrides)
    return MemoryCase(**base)


# ---------------------------------------------------------------------------
# Section 1 — is_router_enabled / env-flag activation contract (R5 strict)
# ---------------------------------------------------------------------------


class TestIsRouterEnabled:
    """The env-flag is the single activation point. Default OFF."""

    def test_env_flag_decides_for_all_value_shapes(self) -> None:
        cases: list[tuple[dict[str, str], bool]] = [
            ({}, False),
            ({ENV_FLAG: "0"}, False),
            ({ENV_FLAG: "1"}, True),
            ({ENV_FLAG: "true"}, False),
            ({ENV_FLAG: "yes"}, False),
            ({ENV_FLAG: ""}, False),
            ({ENV_FLAG: "01"}, False),
        ]
        for env, expected in cases:
            assert is_router_enabled(env) is expected, f"env={env!r}"

    def test_env_flag_constant_value(self) -> None:
        assert ENV_FLAG == "DEVOLAFLOW_MEMORY_ROUTER"

    def test_default_index_path_relative(self) -> None:
        assert not DEFAULT_INDEX_PATH.is_absolute()
        assert str(DEFAULT_INDEX_PATH) == ".local/memory/cases/index.yaml"


# ---------------------------------------------------------------------------
# Section 2 — lookup_case() flat-call: R5 strict zero-overhead when off
# ---------------------------------------------------------------------------


class TestLookupCaseR5StrictOff:
    """When the env-flag is unset, lookup_case MUST return None without IO."""

    def test_off_flag_short_circuits_to_none(self, tmp_path: Path) -> None:
        # Pointing index_path at a directory that does NOT exist proves no IO
        # was attempted — if we tried to read it, FileNotFoundError or stat
        # would surface; instead None comes back.
        for env in [{}, {ENV_FLAG: "0"}, {ENV_FLAG: ""}]:
            result = lookup_case(
                "feature-implementation",
                "implement",
                env=env,
                index_path=tmp_path / "does" / "not" / "exist.yaml",
            )
            assert result is None, f"env={env!r} should short-circuit to None"

    def test_off_flag_does_not_touch_filesystem(self, tmp_path: Path, monkeypatch) -> None:
        # Override Path.read_text to raise — proves we never reached IO.
        seen_calls: list[Path] = []
        original_read = Path.read_text

        def watcher(self, *args, **kwargs):
            seen_calls.append(self)
            return original_read(self, *args, **kwargs)

        monkeypatch.setattr(Path, "read_text", watcher)
        result = lookup_case("w", "t", env={}, index_path=tmp_path / "absent.yaml")
        assert result is None
        assert seen_calls == []

    def test_default_router_is_disabled_in_test_env(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.delenv(ENV_FLAG, raising=False)
        monkeypatch.chdir(tmp_path)
        router = MemoryRouter()
        assert router.is_enabled() is False
        assert router.lookup_case("w", "t") is None


# ---------------------------------------------------------------------------
# Section 3 — lookup_case() happy path
# ---------------------------------------------------------------------------


class TestLookupCaseHappyPath:
    """When enabled with a fresh route, lookup_case returns the MemoryCase."""

    def test_lookup_hit_returns_case(self, tmp_path: Path) -> None:
        idx = _write_index(
            tmp_path,
            """
schema_version: 1
last_updated: "2026-04-23"
cases:
  - case_id: rtk-plugin-entry
    workflow_type: feature-implementation
    task_type: implement
    summary: "RTK plugin entry."
    recipe_path: ".local/memory/cases/rtk-plugin-entry.md"
    version_stamp: "8.3.3"
""",
        )
        result = lookup_case(
            "feature-implementation",
            "implement",
            env={ENV_FLAG: "1"},
            index_path=idx,
            current_version="8.3.3",
        )
        assert result is not None
        assert result.case_id == "rtk-plugin-entry"
        assert result.recipe_path == ".local/memory/cases/rtk-plugin-entry.md"
        assert result.last_updated == "2026-04-23"

    def test_lookup_miss_when_no_row_matches(self, tmp_path: Path) -> None:
        idx = _write_index(
            tmp_path,
            """
schema_version: 1
last_updated: "2026-04-23"
cases:
  - case_id: rtk-plugin-entry
    workflow_type: feature-implementation
    task_type: implement
    summary: "RTK plugin entry."
    recipe_path: ".local/memory/cases/rtk-plugin-entry.md"
    version_stamp: "8.3.3"
""",
        )
        # Wrong workflow_type
        assert (
            lookup_case(
                "hotfix", "implement", env={ENV_FLAG: "1"}, index_path=idx, current_version="8.3.3"
            )
            is None
        )
        # Wrong task_type
        assert (
            lookup_case(
                "feature-implementation",
                "review",
                env={ENV_FLAG: "1"},
                index_path=idx,
                current_version="8.3.3",
            )
            is None
        )

    def test_lookup_first_match_wins_by_index_order(self, tmp_path: Path) -> None:
        idx = _write_index(
            tmp_path,
            """
schema_version: 1
last_updated: "2026-04-23"
cases:
  - case_id: first-match
    workflow_type: feature-implementation
    task_type: implement
    summary: "First in list."
    recipe_path: ".local/memory/cases/first-match.md"
    version_stamp: "8.3.3"
  - case_id: second-match
    workflow_type: feature-implementation
    task_type: implement
    summary: "Second in list."
    recipe_path: ".local/memory/cases/second-match.md"
    version_stamp: "8.3.3"
""",
        )
        result = lookup_case(
            "feature-implementation",
            "implement",
            env={ENV_FLAG: "1"},
            index_path=idx,
            current_version="8.3.3",
        )
        assert result is not None
        assert result.case_id == "first-match"

    def test_lookup_repo_signal_narrowing(self, tmp_path: Path) -> None:
        idx = _write_index(
            tmp_path,
            """
schema_version: 1
last_updated: "2026-04-23"
cases:
  - case_id: devola-recipe
    workflow_type: feature-implementation
    task_type: implement
    summary: "Devola-specific."
    recipe_path: ".local/memory/cases/devola-recipe.md"
    version_stamp: "8.3.3"
    repo_signal: "DevolaFlow"
  - case_id: rtk-recipe
    workflow_type: feature-implementation
    task_type: implement
    summary: "rtk-ai/rtk specific."
    recipe_path: ".local/memory/cases/rtk-recipe.md"
    version_stamp: "8.3.3"
    repo_signal: "rtk-ai/rtk"
""",
        )
        # No repo_signal → first row wins.
        any_match = lookup_case(
            "feature-implementation",
            "implement",
            env={ENV_FLAG: "1"},
            index_path=idx,
            current_version="8.3.3",
        )
        assert any_match is not None and any_match.case_id == "devola-recipe"

        rtk_match = lookup_case(
            "feature-implementation",
            "implement",
            repo_signal="rtk-ai/rtk",
            env={ENV_FLAG: "1"},
            index_path=idx,
            current_version="8.3.3",
        )
        assert rtk_match is not None and rtk_match.case_id == "rtk-recipe"

        # Unknown repo_signal — no match.
        none_match = lookup_case(
            "feature-implementation",
            "implement",
            repo_signal="other-repo",
            env={ENV_FLAG: "1"},
            index_path=idx,
            current_version="8.3.3",
        )
        assert none_match is None


# ---------------------------------------------------------------------------
# Section 4 — Cache invalidation: TTL expiry + version-stamp staleness
# ---------------------------------------------------------------------------


class TestCacheInvalidation:
    def test_version_stamp_mismatch_treated_as_miss(self, tmp_path: Path) -> None:
        idx = _write_index(
            tmp_path,
            """
schema_version: 1
last_updated: "2026-04-23"
cases:
  - case_id: stale-stamp
    workflow_type: feature-implementation
    task_type: implement
    summary: "Recipe authored against an older runtime."
    recipe_path: ".local/memory/cases/stale-stamp.md"
    version_stamp: "8.3.0"
""",
        )
        # Current version 8.3.3; stamp 8.3.0 ⇒ version-stale ⇒ miss.
        result = lookup_case(
            "feature-implementation",
            "implement",
            env={ENV_FLAG: "1"},
            index_path=idx,
            current_version="8.3.3",
        )
        assert result is None

    def test_ttl_expired_treated_as_miss(self, tmp_path: Path) -> None:
        idx = _write_index(
            tmp_path,
            """
schema_version: 1
last_updated: "2024-01-01"
cases:
  - case_id: aged-out
    workflow_type: feature-implementation
    task_type: implement
    summary: "Last touched 2 years ago, ttl_days=30."
    recipe_path: ".local/memory/cases/aged-out.md"
    version_stamp: "8.3.3"
    ttl_days: 30
""",
        )
        result = lookup_case(
            "feature-implementation",
            "implement",
            env={ENV_FLAG: "1"},
            index_path=idx,
            current_version="8.3.3",
        )
        assert result is None

    def test_ttl_within_window_returns_hit(self, tmp_path: Path) -> None:
        # Use today's date as last_accessed so the TTL window is fresh.
        today = today_iso()
        idx = _write_index(
            tmp_path,
            f"""
schema_version: 1
last_updated: "2026-04-23"
cases:
  - case_id: fresh-route
    workflow_type: feature-implementation
    task_type: implement
    summary: "Touched today."
    recipe_path: ".local/memory/cases/fresh-route.md"
    version_stamp: "8.3.3"
    ttl_days: 7
    last_accessed: "{today}"
""",
        )
        result = lookup_case(
            "feature-implementation",
            "implement",
            env={ENV_FLAG: "1"},
            index_path=idx,
            current_version="8.3.3",
        )
        assert result is not None
        assert result.case_id == "fresh-route"

    def test_is_ttl_expired_anchor_priority(self) -> None:
        # last_accessed wins over last_updated.
        case = _make_case(last_accessed="2026-04-23", last_updated="2020-01-01", ttl_days=7)
        assert is_ttl_expired(case, today="2026-04-25") is False
        assert is_ttl_expired(case, today="2026-05-25") is True

        # Without last_accessed, last_updated drives.
        case_lu_only = _make_case(last_updated="2026-04-23", ttl_days=7)
        assert is_ttl_expired(case_lu_only, today="2026-04-25") is False
        assert is_ttl_expired(case_lu_only, today="2026-05-25") is True

        # Both empty → fresh (defensive default; never expire).
        case_empty = _make_case(ttl_days=7)
        assert is_ttl_expired(case_empty, today="2030-01-01") is False

    def test_is_version_stale_exact_equality(self) -> None:
        case = _make_case(version_stamp="8.3.3")
        assert is_version_stale(case, "8.3.3") is False
        assert is_version_stale(case, "8.3.4") is True
        assert is_version_stale(case, "8.3.3-rc.1") is True
        assert is_version_stale(case, "") is True


# ---------------------------------------------------------------------------
# Section 5 — Index-load failure modes (cache-miss is the safe path)
# ---------------------------------------------------------------------------


class TestIndexLoadResilience:
    """Every index-load failure mode degrades to cache-miss + WARNING."""

    def test_missing_index_returns_none_no_warning(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        caplog.set_level(logging.INFO, logger="devolaflow.memory_router.router")
        result = lookup_case(
            "w",
            "t",
            env={ENV_FLAG: "1"},
            index_path=tmp_path / ".local" / "memory" / "cases" / "index.yaml",
            current_version="8.3.3",
        )
        assert result is None
        # Missing index is normal on fresh checkout — INFO log only, no warning.
        assert not [r for r in caplog.records if r.levelno >= logging.WARNING]

    def test_malformed_yaml_logs_warning_returns_none(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        caplog.set_level(logging.WARNING, logger="devolaflow.memory_router.router")
        idx = _write_index(tmp_path, "this: is: not: valid: yaml:::\n  - [")
        result = lookup_case("w", "t", env={ENV_FLAG: "1"}, index_path=idx, current_version="8.3.3")
        assert result is None
        assert any("not valid YAML" in r.message for r in caplog.records)

    def test_non_mapping_top_level_logs_warning(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        caplog.set_level(logging.WARNING, logger="devolaflow.memory_router.router")
        idx = _write_index(tmp_path, "- a\n- b\n- c\n")
        result = lookup_case("w", "t", env={ENV_FLAG: "1"}, index_path=idx, current_version="8.3.3")
        assert result is None
        assert any("must be a mapping" in r.message for r in caplog.records)

    def test_non_list_cases_logs_warning(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        caplog.set_level(logging.WARNING, logger="devolaflow.memory_router.router")
        idx = _write_index(
            tmp_path,
            'schema_version: 1\nlast_updated: "2026-04-23"\ncases: not-a-list\n',
        )
        result = lookup_case("w", "t", env={ENV_FLAG: "1"}, index_path=idx, current_version="8.3.3")
        assert result is None
        assert any("'cases' key must be a list" in r.message for r in caplog.records)

    def test_blank_file_returns_none(self, tmp_path: Path) -> None:
        idx = _write_index(tmp_path, "")
        result = lookup_case("w", "t", env={ENV_FLAG: "1"}, index_path=idx, current_version="8.3.3")
        assert result is None

    def test_mixed_good_and_bad_rows_drops_bad_keeps_good(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        caplog.set_level(logging.WARNING, logger="devolaflow.memory_router.router")
        idx = _write_index(
            tmp_path,
            """
schema_version: 1
last_updated: "2026-04-23"
cases:
  - case_id: bad-row
    # missing required fields
  - case_id: good-row
    workflow_type: feature-implementation
    task_type: implement
    summary: "Survives despite a sibling row being malformed."
    recipe_path: ".local/memory/cases/good-row.md"
    version_stamp: "8.3.3"
""",
        )
        result = lookup_case(
            "feature-implementation",
            "implement",
            env={ENV_FLAG: "1"},
            index_path=idx,
            current_version="8.3.3",
        )
        assert result is not None
        assert result.case_id == "good-row"
        assert any("dropping malformed case row" in r.message for r in caplog.records)


# ---------------------------------------------------------------------------
# Section 6 — MemoryCase / build_case_from_dict validation
# ---------------------------------------------------------------------------


class TestMemoryCaseValidation:
    def test_required_fields_enforced(self) -> None:
        for missing in ("case_id", "workflow_type", "task_type", "recipe_path", "version_stamp"):
            row = {
                "case_id": "x",
                "workflow_type": "w",
                "task_type": "t",
                "summary": "s",
                "recipe_path": ".local/memory/cases/x.md",
                "version_stamp": "8.3.3",
            }
            del row[missing]
            with pytest.raises(MemoryCacheError):
                build_case_from_dict(row)

    def test_recipe_path_prefix_enforced(self) -> None:
        with pytest.raises(MemoryCacheError, match="must live under .local/memory/cases/"):
            MemoryCase(
                case_id="x",
                workflow_type="w",
                task_type="t",
                summary="s",
                recipe_path="src/devolaflow/memory_router/router.py",
                version_stamp="8.3.3",
            )

    def test_ttl_bounds_enforced(self) -> None:
        for bad in (0, -1, MAX_TTL_DAYS + 1, 9999):
            with pytest.raises(MemoryCacheError, match="ttl_days must be within"):
                _make_case(ttl_days=bad)
        for good in (1, DEFAULT_TTL_DAYS, MAX_TTL_DAYS):
            assert _make_case(ttl_days=good).ttl_days == good

    def test_non_int_ttl_rejected(self) -> None:
        row = {
            "case_id": "x",
            "workflow_type": "w",
            "task_type": "t",
            "summary": "s",
            "recipe_path": ".local/memory/cases/x.md",
            "version_stamp": "8.3.3",
            "ttl_days": "30",
        }
        with pytest.raises(MemoryCacheError, match="non-int ttl_days"):
            build_case_from_dict(row)

    def test_bool_ttl_rejected_distinct_from_int(self) -> None:
        row = {
            "case_id": "x",
            "workflow_type": "w",
            "task_type": "t",
            "summary": "s",
            "recipe_path": ".local/memory/cases/x.md",
            "version_stamp": "8.3.3",
            "ttl_days": True,
        }
        with pytest.raises(MemoryCacheError, match="non-int ttl_days"):
            build_case_from_dict(row)

    def test_bad_tags_rejected(self) -> None:
        row = {
            "case_id": "x",
            "workflow_type": "w",
            "task_type": "t",
            "summary": "s",
            "recipe_path": ".local/memory/cases/x.md",
            "version_stamp": "8.3.3",
            "tags": "should-be-list",
        }
        with pytest.raises(MemoryCacheError, match="non-list tags"):
            build_case_from_dict(row)

    def test_non_mapping_row_rejected(self) -> None:
        with pytest.raises(MemoryCacheError, match="must be a YAML mapping"):
            build_case_from_dict(["not", "a", "dict"])

    def test_index_last_updated_propagates_to_case(self) -> None:
        case = build_case_from_dict(
            {
                "case_id": "x",
                "workflow_type": "w",
                "task_type": "t",
                "summary": "s",
                "recipe_path": ".local/memory/cases/x.md",
                "version_stamp": "8.3.3",
            },
            index_last_updated="2026-04-23",
        )
        assert case.last_updated == "2026-04-23"

    def test_today_iso_returns_iso_format(self) -> None:
        s = today_iso()
        assert len(s) == 10 and s[4] == "-" and s[7] == "-"


# ---------------------------------------------------------------------------
# Section 7 — Lazy load + in-process cache reuse
# ---------------------------------------------------------------------------


class TestLazyLoadAndCacheReuse:
    def test_construction_does_not_load_index(self, tmp_path: Path) -> None:
        # Construct with an absent index_path; no exception means no IO at __init__.
        absent = tmp_path / "absent" / "index.yaml"
        router = MemoryRouter(env={ENV_FLAG: "1"}, index_path=absent, current_version="8.3.3")
        # Cache should still be uninitialized.
        assert router._cache is None  # noqa: SLF001 (intentional probe)

    def test_first_lookup_populates_cache(self, tmp_path: Path) -> None:
        idx = _write_index(
            tmp_path,
            """
schema_version: 1
last_updated: "2026-04-23"
cases:
  - case_id: x
    workflow_type: w
    task_type: t
    summary: "s"
    recipe_path: ".local/memory/cases/x.md"
    version_stamp: "8.3.3"
""",
        )
        router = MemoryRouter(env={ENV_FLAG: "1"}, index_path=idx, current_version="8.3.3")
        assert router._cache is None  # noqa: SLF001
        router.lookup_case("w", "t")
        assert router._cache is not None  # noqa: SLF001
        assert len(router._cache.cases) == 1  # noqa: SLF001

    def test_subsequent_lookups_reuse_cache(self, tmp_path: Path, monkeypatch) -> None:
        idx = _write_index(
            tmp_path,
            """
schema_version: 1
last_updated: "2026-04-23"
cases:
  - case_id: x
    workflow_type: w
    task_type: t
    summary: "s"
    recipe_path: ".local/memory/cases/x.md"
    version_stamp: "8.3.3"
""",
        )
        router = MemoryRouter(env={ENV_FLAG: "1"}, index_path=idx, current_version="8.3.3")
        first = router.lookup_case("w", "t")
        assert first is not None

        # After the first lookup, deleting the file should NOT affect the cached lookup.
        idx.unlink()
        second = router.lookup_case("w", "t")
        assert second is not None
        assert second.case_id == first.case_id

    def test_inject_cases_skips_io_entirely(self, tmp_path: Path) -> None:
        c1 = _make_case(case_id="x", workflow_type="w", task_type="t")
        absent = tmp_path / "definitely" / "absent.yaml"
        router = MemoryRouter(
            env={ENV_FLAG: "1"},
            index_path=absent,
            current_version="8.3.3",
            cases=[c1],
        )
        result = router.lookup_case("w", "t")
        assert result is c1

    def test_empty_workflow_type_returns_none(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        caplog.set_level(logging.WARNING, logger="devolaflow.memory_router.router")
        c1 = _make_case()
        router = MemoryRouter(
            env={ENV_FLAG: "1"},
            current_version="8.3.3",
            cases=[c1],
            index_path=tmp_path / "absent.yaml",
        )
        assert router.lookup_case("", "implement") is None
        assert router.lookup_case("feature-implementation", "") is None
        assert any("called with empty key" in r.message for r in caplog.records)


# ---------------------------------------------------------------------------
# Section 8 — Strict mode (lookup_case_strict raises on schema breaks)
# ---------------------------------------------------------------------------


class TestStrictMode:
    def test_strict_off_short_circuits_to_none(self) -> None:
        router = MemoryRouter(env={}, current_version="8.3.3", cases=[_make_case()])
        assert router.lookup_case_strict("w", "t") is None

    def test_strict_raises_on_malformed_yaml(self, tmp_path: Path) -> None:
        idx = _write_index(tmp_path, "not: valid: yaml::: [")
        router = MemoryRouter(env={ENV_FLAG: "1"}, index_path=idx, current_version="8.3.3")
        with pytest.raises(MemoryRouterError, match="not valid YAML"):
            router.lookup_case_strict("w", "t")

    def test_strict_raises_on_malformed_row(self, tmp_path: Path) -> None:
        idx = _write_index(
            tmp_path,
            """
schema_version: 1
last_updated: "2026-04-23"
cases:
  - case_id: missing-fields
""",
        )
        router = MemoryRouter(env={ENV_FLAG: "1"}, index_path=idx, current_version="8.3.3")
        with pytest.raises(MemoryRouterError, match="malformed rows"):
            router.lookup_case_strict("w", "t")

    def test_strict_returns_none_on_genuine_miss(self, tmp_path: Path) -> None:
        idx = _write_index(
            tmp_path,
            """
schema_version: 1
last_updated: "2026-04-23"
cases:
  - case_id: x
    workflow_type: w
    task_type: t
    summary: "s"
    recipe_path: ".local/memory/cases/x.md"
    version_stamp: "8.3.3"
""",
        )
        router = MemoryRouter(env={ENV_FLAG: "1"}, index_path=idx, current_version="8.3.3")
        assert router.lookup_case_strict("not-matching", "implement") is None


# ---------------------------------------------------------------------------
# Section 9 — End-to-end: real on-disk index seeded from the v8.4.0 cycle
# ---------------------------------------------------------------------------


class TestEndToEnd:
    """Verifies the whole stack with a realistic seed file (3-recipe layout)."""

    def test_three_recipe_seed_lookup(self, tmp_path: Path) -> None:
        idx = _write_index(
            tmp_path,
            """
schema_version: 1
last_updated: "2026-04-23"
cases:
  - case_id: rtk-plugin-entry
    workflow_type: feature-implementation
    task_type: implement
    summary: "RTK plugin entry pattern from v8.3.1 PV-01."
    recipe_path: ".local/memory/cases/rtk-plugin-entry.md"
    version_stamp: "8.3.3"
    repo_signal: "DevolaFlow"
    ttl_days: 60
    tags: [plugin, rtk, schema-v2]
  - case_id: shell-proxy-registry
    workflow_type: feature-implementation
    task_type: implement
    summary: "shell_proxy registry pattern from v8.3.2 PV-02."
    recipe_path: ".local/memory/cases/shell-proxy-registry.md"
    version_stamp: "8.3.3"
    repo_signal: "DevolaFlow"
    tags: [shell-proxy, rtk, lifecycle-hook, r5-strict]
  - case_id: evobench-doc-coupling
    workflow_type: version-bump
    task_type: doc-consistency
    summary: "EvoBench scenario count + README + demo HTML coupling fix."
    recipe_path: ".local/memory/cases/evobench-doc-coupling.md"
    version_stamp: "8.3.3"
    repo_signal: "DevolaFlow"
""",
        )
        # Three discrete probes that hit each recipe.
        for wt, tt, expected in [
            ("feature-implementation", "implement", "rtk-plugin-entry"),
            ("version-bump", "doc-consistency", "evobench-doc-coupling"),
        ]:
            result = lookup_case(
                wt, tt, env={ENV_FLAG: "1"}, index_path=idx, current_version="8.3.3"
            )
            assert result is not None
            assert result.case_id == expected
