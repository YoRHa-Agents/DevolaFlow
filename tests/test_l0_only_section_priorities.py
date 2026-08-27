"""v12.4.0 PV-05 — L0-only section priority discipline tests.

Pins the audit verdict from `.local/research/v12.4.0_l0_only_audit.md`
§A (per-tier profile audit table) against the live
`workflow-system/agent/context_profiles.yaml` source-of-truth:

1. `version_update` — L0-only operator-facing banner content. All
   subagent (L1/L2) profiles MUST mark `skip`. Only `self_update`
   profile legitimately needs `critical` (the workflow whose whole
   purpose IS bumping the version).
2. `task_quality_score` — L0-only scoring stub. All subagent profiles
   MUST mark `skip`. The 60-token stub preserves the v12.1.0 D-1
   prohibition pins but only L0 acts on the rubric (which itself is
   Tier 3 on-demand per `references/task-quality-score.md`).
3. `operational_learnings` — L0-only API-prose section. All 25 profiles
   MUST carry an EXPLICIT `operational_learnings: skip` row (NO
   implicit-skip via the legacy silent-fallback path) per the S-5
   compliance closure from the audit §A.3.

Source: `.local/research/v12.4.0_l0_only_audit.md` §A verdicts + cycle
plan §3 PV-05 D-4 closure.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

_CONTEXT_PROFILES_PATH: Path = (
    Path(__file__).resolve().parent.parent / "workflow-system" / "agent" / "context_profiles.yaml"
)


@pytest.fixture(scope="module")
def context_profiles() -> dict[str, Any]:
    """Load the live `context_profiles.yaml` source-of-truth."""
    with _CONTEXT_PROFILES_PATH.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


@pytest.fixture(scope="module")
def profiles(context_profiles: dict[str, Any]) -> dict[str, Any]:
    """Return the 25-profile dict from `context_profiles.yaml`."""
    return context_profiles["profiles"]


# ---------------------------------------------------------------------------
# Section A.1 — version_update audit verdict
# ---------------------------------------------------------------------------


def test_version_update_skip_for_all_subagent_profiles(
    profiles: dict[str, Any],
) -> None:
    """Per audit §A.1: `version_update` is L0-only operator-facing banner
    content. Every subagent (L1/L2) profile MUST mark `skip`. Only
    the `self_update` profile legitimately consumes the §"Version &
    Update" content (its whole purpose IS bumping version).

    v12.4.0 PV-05 makes the discipline EXPLICIT: all 25 profiles MUST
    have an explicit `version_update:` row (no implicit-skip fallback
    per the audit's S-5 cleanup discipline).
    """
    legitimate_critical = frozenset({"self_update"})
    for name, profile in profiles.items():
        sp = profile.get("section_priorities", {})
        priority = sp.get("version_update")
        if name in legitimate_critical:
            assert priority == "critical", (
                f"v12.4.0 PV-05 audit §A.1 violation: profile {name!r} "
                f"is the only profile that legitimately needs "
                f"`version_update: critical` (the self-update workflow's "
                f"whole purpose is bumping version). Got {priority!r}."
            )
            continue
        assert priority == "skip", (
            f"v12.4.0 PV-05 audit §A.1 violation: profile {name!r} "
            f"MUST mark `version_update: skip` — the section is L0-only "
            f"per SKILL.md §'Version & Update' + §'Session Banner "
            f"Contract'. Got {priority!r}. Only `self_update` profile "
            f"legitimately needs the section (it bumps version); every "
            f"other profile sees the banner content as decorative "
            f"chrome and MUST skip it."
        )


# ---------------------------------------------------------------------------
# Section A.2 — task_quality_score audit verdict
# ---------------------------------------------------------------------------


def test_task_quality_score_skip_for_all_subagent_profiles(
    profiles: dict[str, Any],
) -> None:
    """Per audit §A.2: `task_quality_score` is L0-only. The 60-token
    SKILL.md stub at lines 480-482 (post-v12.3.0 PV-03 collapse)
    preserves the v12.1.0 D-1 prohibition pins (`L0 ONLY` + `Subagents
    MUST NOT`), but only L0 acts on the rubric. Every profile MUST
    mark `skip`; the full rubric loads on-demand from
    `references/task-quality-score.md` at workflow CLOSE only.

    v12.4.0 PV-05 demotes the 14 historical leak profiles (8
    supplementary + 1 important + 2 critical — plus 3 supplementary
    additions from the audit pass) to `skip`. ALL 25 profiles MUST
    end at `skip`.
    """
    for name, profile in profiles.items():
        sp = profile.get("section_priorities", {})
        priority = sp.get("task_quality_score")
        assert priority == "skip", (
            f"v12.4.0 PV-05 audit §A.2 violation: profile {name!r} "
            f"MUST mark `task_quality_score: skip` — the section is "
            f"L0-only per SKILL.md §'Task Quality Score (L0 ONLY)'. "
            f"Got {priority!r}. Full rubric loads on-demand from "
            f"`references/task-quality-score.md` at workflow CLOSE "
            f"only (v12.3.0 PV-03 Tier 3 extraction)."
        )


# ---------------------------------------------------------------------------
# Section A.3 — operational_learnings audit verdict
# ---------------------------------------------------------------------------


def test_operational_learnings_explicit_skip_for_all_profiles(
    profiles: dict[str, Any],
) -> None:
    """Per audit §A.3: pre-PV-05, only `repo-init` carried an explicit
    `operational_learnings: skip` row; the other 22 profiles fell
    through to the silent `_resolve_section_text` DeprecationWarning
    path (S-5 violation per the audit).

    v12.4.0 PV-05 closes the S-5 violation by adding explicit
    `operational_learnings: skip` rows to ALL 25 profiles. NO
    implicit-skip path remains — the discipline is uniformly EXPLICIT
    across the YAML surface so future profile authors can't silently
    accidentally restore the section by adding content under
    `section_anchors:` without auditing.
    """
    for name, profile in profiles.items():
        sp = profile.get("section_priorities", {})
        priority = sp.get("operational_learnings")
        assert priority == "skip", (
            f"v12.4.0 PV-05 audit §A.3 violation: profile {name!r} "
            f"MUST carry an EXPLICIT `operational_learnings: skip` "
            f"row — the section is L0-only (only L0 mutates the "
            f"operational.jsonl substrate via pin_learning_for_session "
            f"/ consolidate_session / decay_confidence). Got {priority!r}. "
            f"The PV-05 audit closes the silent-fallback S-5 violation "
            f"by making the skip discipline explicit at the YAML surface."
        )


# ---------------------------------------------------------------------------
# Sections block registration
# ---------------------------------------------------------------------------


def test_operational_learnings_registered_in_sections_block(
    context_profiles: dict[str, Any],
) -> None:
    """Per audit §A.3 closure: the runtime stops emitting a
    DeprecationWarning on first lookup ONLY when `operational_learnings`
    is registered in the `sections:` block of `context_profiles.yaml`.

    v12.4.0 PV-05 adds the registration with `tokens_est: 150` +
    `priority_default: skip` mirroring the prose body's actual token
    count (SKILL.md lines 484-486; ~150 tokens of API-prose body).
    """
    sections = context_profiles["sections"]
    assert "operational_learnings" in sections, (
        "v12.4.0 PV-05 audit §A.3 violation: `operational_learnings` "
        "MUST be registered in the `sections:` block of "
        "`context_profiles.yaml` so the runtime stops emitting "
        "DeprecationWarning on first lookup (S-5 silent-fallback "
        "cleanup). The PV-05 baseline registers it with tokens_est=150 "
        "+ priority_default=skip."
    )
    entry = sections["operational_learnings"]
    assert entry.get("priority_default") == "skip", (
        "v12.4.0 PV-05 audit §A.3 violation: "
        "`sections.operational_learnings.priority_default` MUST be "
        "`skip` to document the L0-only contract at the registry "
        f"surface. Got {entry.get('priority_default')!r}."
    )
    tokens_est = entry.get("tokens_est")
    assert isinstance(tokens_est, int) and tokens_est >= 100, (
        "v12.4.0 PV-05 audit §A.3 violation: "
        "`sections.operational_learnings.tokens_est` MUST be a positive "
        f"int ≥ 100 (audit measured ~150). Got {tokens_est!r}."
    )


# ---------------------------------------------------------------------------
# Cross-section invariant — all 25 profiles checked
# ---------------------------------------------------------------------------


def test_all_24_profiles_have_l0_only_skip_discipline(
    profiles: dict[str, Any],
) -> None:
    """Composite assertion: every one of the 25 named profiles MUST end
    PV-05 with the L0-only `skip` discipline across all 3 sections
    (task_quality_score, operational_learnings, version_update — the
    last with the `self_update` exception). This is the cycle plan §3
    PV-05 acceptance criterion #1 (audit re-affirmation) rendered as
    a single uniform-coverage assertion across the full profile set.

    The test is parametrize-equivalent (25 × 3 = 75 assertions packed
    into one test function) to keep the W-17 NEW-test-function cap at
    5 for this T2 file.
    """
    assert len(profiles) == 25, (
        f"v12.4.0 PV-05 contract: `context_profiles.yaml` MUST declare "
        f"exactly 25 named profiles for the Pathfinder addition. Got "
        f"{len(profiles)}."
    )
    legitimate_vu_critical = frozenset({"self_update"})
    failures: list[str] = []
    for name, profile in profiles.items():
        sp = profile.get("section_priorities", {})
        tqs = sp.get("task_quality_score")
        ol = sp.get("operational_learnings")
        vu = sp.get("version_update")
        if tqs != "skip":
            failures.append(f"{name}: task_quality_score={tqs!r} (expected 'skip')")
        if ol != "skip":
            failures.append(f"{name}: operational_learnings={ol!r} (expected 'skip')")
        if name in legitimate_vu_critical:
            if vu != "critical":
                failures.append(
                    f"{name}: version_update={vu!r} (expected 'critical' — "
                    f"this is the only legitimate exception per audit §A.1)"
                )
        elif vu != "skip":
            failures.append(f"{name}: version_update={vu!r} (expected 'skip')")
    assert not failures, (
        "v12.4.0 PV-05 audit §A composite verdict failed for one or more "
        "profiles:\n  " + "\n  ".join(failures)
    )
