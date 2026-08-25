"""Ghost audit — consolidated W-18 feature stanza for the v17.0 R2 slice.

Pins the G17-B1/G17-B2 closure surfaces (host-bridge package + dogfood
host configs + layer-token-budget dispatch assertion) BEFORE the cycle's
CHANGELOG entry lands, per W-18. R1 removal features are pinned in their
domain suites (``tests/test_complexity_cleanup.py``,
``tests/test_agent_workspace_change_layout.py``,
``tests/test_layer_normalization.py``, ``tests/test_cascade_enforcement.py``).
"""

from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path


def test_v17_0_0_r2_hostbridge_surface_registered(project_root: Path) -> None:
    """W-18 v17.0.0 R2: the five-host bridge core and its flag are wired."""
    from devolaflow.hostbridge import (
        ENV_FLAG,
        KNOWN_HOSTS,
        decide,
        install_cursor,
        kimi_snippet,
        normalize_event,
    )

    assert ENV_FLAG == "DEVOLAFLOW_HOST_ENFORCE"
    assert set(KNOWN_HOSTS) == {"cursor", "claude", "codex", "kimi", "dsh"}
    assert callable(decide) and callable(normalize_event)
    assert callable(install_cursor) and callable(kimi_snippet)
    # CLI entry point is importable without side effects (guarded main).
    assert importlib.util.find_spec("devolaflow.hostbridge.__main__") is not None
    # W-20 same-PR flag registration + the SF-4 reference are on disk.
    env_flags = (
        project_root / "workflow-system" / "agent" / "references" / "env-flags.md"
    ).read_text(encoding="utf-8")
    assert "DEVOLAFLOW_HOST_ENFORCE" in env_flags
    assert (project_root / "workflow-system" / "agent" / "references" / "host-bridges.md").is_file()


def test_v17_0_0_r2_dogfood_host_configs_present(project_root: Path) -> None:
    """W-18 v17.0.0 R2: committed host configs route through the bridge."""
    cursor_hooks = json.loads((project_root / ".cursor" / "hooks.json").read_text(encoding="utf-8"))
    assert cursor_hooks.get("version") == 1
    claude_settings = json.loads(
        (project_root / ".claude" / "settings.json").read_text(encoding="utf-8")
    )
    assert "PreToolUse" in claude_settings.get("hooks", {})
    codex_hooks = json.loads((project_root / ".codex" / "hooks.json").read_text(encoding="utf-8"))
    assert "PreToolUse" in codex_hooks.get("hooks", {})
    for wrapper in (
        project_root / ".cursor" / "hooks" / "devola-boundary.sh",
        project_root / ".claude" / "hooks" / "devola-boundary.sh",
        project_root / ".codex" / "hooks" / "devola-boundary.sh",
    ):
        assert wrapper.is_file() and os.access(wrapper, os.X_OK)
    dsh_plugin = (project_root / "packages" / "dsh-plugin" / "index.mjs").read_text(
        encoding="utf-8"
    )
    assert "tools/pre-execute" in dsh_plugin


def test_v17_0_0_r5_capacity_and_probe_table_wired(project_root: Path) -> None:
    """W-18 v17.0.0 R5: capacity SSOT reader + probe model table + W-24.2 record."""
    from devolaflow.harness.capacity import (
        CAPACITY_TARGET_RANGES,
        CapacityConfigError,
        CapacityProfile,
        capacity_profile,
    )
    from devolaflow.harness.probe import (
        ProbeModel,
        load_probe_model_table,
        sanitize_model_for_filename,
    )

    # Dark config: shipped context_profiles.yaml has no meta.capacity block,
    # so the profile is byte-identical to the pre-R5 hardcoded literals.
    profile = capacity_profile()
    assert isinstance(profile, CapacityProfile)
    assert (
        profile.round_capacity,
        profile.max_concurrency,
        profile.stagnation_rounds,
        profile.unsuccessful_item_rounds,
    ) == (5, 4, 2, 3)
    assert set(profile.sources.values()) == {"default"}
    assert set(CAPACITY_TARGET_RANGES) == {
        "meta.capacity.round_capacity",
        "meta.capacity.max_concurrency",
        "meta.capacity.stop_guard.stagnation_rounds",
        "meta.capacity.stop_guard.unsuccessful_item_rounds",
    }
    assert issubclass(CapacityConfigError, ValueError)

    # Probe model table ships dark too; helpers are importable and pure.
    assert ProbeModel is not None
    assert load_probe_model_table() == ()
    assert sanitize_model_for_filename("m/1") == "m_1"

    # W-24.2 verdict: stale forward-looking phrasing is gone from the
    # compiled corpus; the re-deferral gate is recorded.
    agents_md = (project_root / "AGENTS.md").read_text(encoding="utf-8")
    assert "landing deferred to v12.0.0+ SI-1" not in agents_md
    assert "v18+" in agents_md


def test_v17_0_0_r4_focus_loop_wired(project_root: Path) -> None:
    """W-18 v17.0.0 R4: session resume adapter + checkpoint composition + goal drift."""
    from devolaflow.agent_workspace import (
        ResumeDisposition,
        checkpoint_round_pass,
        goal_content_hash,
    )

    assert callable(checkpoint_round_pass) and callable(goal_content_hash)
    assert ResumeDisposition.GOAL_DRIFT.name == "GOAL_DRIFT"
    assert importlib.util.find_spec("devolaflow.hostbridge.session") is not None

    # Dogfood session hooks are wired for cursor + claude (Codex/Kimi/DSH
    # deliberately deferred per references/host-bridges.md §8).
    cursor_hooks = json.loads((project_root / ".cursor" / "hooks.json").read_text(encoding="utf-8"))
    assert "sessionStart" in cursor_hooks.get("hooks", {})
    claude_settings = json.loads(
        (project_root / ".claude" / "settings.json").read_text(encoding="utf-8")
    )
    assert "SessionStart" in claude_settings.get("hooks", {})
    for script in (
        project_root / ".cursor" / "hooks" / "devola-session.sh",
        project_root / ".claude" / "hooks" / "devola-session.sh",
    ):
        assert script.is_file() and os.access(script, os.X_OK)


def test_v17_0_0_r3_host_injection_accounting_wired(project_root: Path) -> None:
    """W-18 v17.0.0 R3: slice account + ledger fields + config-driven fold."""
    from devolaflow.agents_md_slice import cached_slice_summary, slice_account
    from devolaflow.harness.telemetry import build_dispatch_record
    from devolaflow.harness.tiers import should_fold_advisory
    from devolaflow.task_adaptive_selector import select_context

    assert callable(cached_slice_summary) and callable(slice_account)

    context = select_context("hotfix")
    assert "agents_md_slice" in context
    slice_keys = set(context["agents_md_slice"])
    assert {"full_tokens", "slice_savings_pct"} <= slice_keys or not slice_keys

    record = build_dispatch_record(
        {"to_layer": "L2", "task": {"type": "hotfix"}, "dispatch_id": "ghost-r3"},
        change_id="ghost-r3",
    )
    assert record["host_rule_tokens"] > 0
    assert record["slice_savings_pct"] > 0

    # Config-absent fold policy stays byte-identical to the v16 hardcoded set.
    assert should_fold_advisory("quality") is True
    assert should_fold_advisory("QUALITY") is False


def test_v17_0_0_r2_layer_budget_assertion_wired() -> None:
    """W-18 v17.0.0 R2: ALB001 fires through the pre_dispatch extra chain."""
    from devolaflow import lifecycle
    from devolaflow.harness.telemetry import LAYER_TOKEN_BUDGETS, stable_yaml
    from devolaflow.lifecycle.assert_layer_budget import assert_layer_token_budget

    assert callable(assert_layer_token_budget) and callable(stable_yaml)
    assert LAYER_TOKEN_BUDGETS == {"L0": 5000, "L1": 5000, "L2": 8000}

    oversized = {"to_layer": "L2", "payload": "x" * 40_000}
    result = lifecycle.run_hooks("pre_dispatch", oversized, strict=False)
    assert "ALB001" in {violation.code for violation in result.violations}

    small = {"to_layer": "L2", "payload": "tiny"}
    small_result = lifecycle.run_hooks("pre_dispatch", small, strict=False)
    assert "ALB001" not in {violation.code for violation in small_result.violations}
