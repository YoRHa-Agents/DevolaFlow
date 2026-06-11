"""Ghost audit — per-cycle W-18 feature stanzas for the v10.5 cycle.

Split from ``tests/test_no_ghost_features.py`` per v15-ADR-001
(v14.3.0). New W-18 stanzas for a v10.5.x release append HERE; the
next MINOR cycle rotates to a fresh ``test_features_v<MAJ>_<MIN>.py``.
"""

from __future__ import annotations

from pathlib import Path

from tests.ghost._helpers import _w18_research_artifact_path

# =====================================================================
# v10.5.0 PV-01..PV-05 — Architecture & Documentation Health
# =====================================================================
#
# v10.5.0 collapses 6 v11.0.0-cycle PDSs (D-A-1, D-A-2, D-A-3, D-A-4,
# D-D-3, D-D-4) into a single coherent MINOR cycle per
# `.local/research/v11.0.0_patches/`. The cycle ships:
#  1. NEW scripts/audit_layer_usage.py (D-A-1 — L0/L1/L2/L3 dispatch
#     ratio audit)
#  2. NEW scripts/audit_template_usage.py (D-A-2 Phase A — TIER-1
#     USED vs TIER-2 REGISTERED template audit)
#  3. NEW scripts/measure_reference_friction.py (D-D-3 — reference
#     comprehension cost / dense-paragraph audit)
#  4. NEW scripts/audit_w18_lint_maintenance.py (D-D-4 — W-17/W-18
#     lint maintenance trajectory audit)
#  5. NEW workflow-system/agent/examples/multi-stage-trace.md
#     (D-A-1 — 4th XL-tier example, the multi-team analyze
#     counter-case for SKILL.md §"Quick Action Decision" advisory)
#  6. NEW agent-workspace.md §3.6 "Resume After Pause" (D-A-3 —
#     pure-doc subsection)
#  7. NEW activation_verdict(force_no_change=...) parameter (D-A-4)
#  8. 16 TIER-2 yaml deprecation comment headers (D-A-2 Phase A)
#  9. 4 NEW Makefile targets (audit-layers, audit-templates,
#     measure-friction, audit-w18)
#  10. CHANGELOG `## [10.5.0]` entry; canonical 7 sync 10.4.0 -> 10.5.0
#  11. .local/research/v10.5.{0,1,2,3,4}_*.md retrospective + 4
#      audit outputs

_V10_5_0_AUDIT_LAYERS_SCRIPT: Path = Path("scripts/audit_layer_usage.py")


_V10_5_0_AUDIT_TEMPLATES_SCRIPT: Path = Path("scripts/audit_template_usage.py")


_V10_5_0_MEASURE_FRICTION_SCRIPT: Path = Path("scripts/measure_reference_friction.py")


_V10_5_0_AUDIT_W18_SCRIPT: Path = Path("scripts/audit_w18_lint_maintenance.py")


_V10_5_0_MULTI_STAGE_EXAMPLE: Path = Path("workflow-system/agent/examples/multi-stage-trace.md")


_V10_5_0_RETROSPECTIVE_DOC: Path = Path(".local/research/v10.5.0_retrospective.md")


_V10_5_0_LAYER_AUDIT_DOC: Path = Path(".local/research/v10.5.1_layer_usage_audit.md")


_V10_5_0_TEMPLATE_AUDIT_DOC: Path = Path(".local/research/v10.5.2_template_usage_audit.md")


_V10_5_0_FRICTION_DOC: Path = Path(".local/research/v10.5.3_reference_friction.md")


_V10_5_0_W18_AUDIT_DOC: Path = Path(".local/research/v10.5.4_w18_lint_audit.md")


_V10_5_0_CHANGELOG_LITERAL: str = "## [10.5.0]"


_V10_5_0_MAKEFILE_AUDIT_LAYERS_LITERAL: str = "audit-layers:"


_V10_5_0_MAKEFILE_AUDIT_TEMPLATES_LITERAL: str = "audit-templates:"


_V10_5_0_MAKEFILE_MEASURE_FRICTION_LITERAL: str = "measure-friction:"


_V10_5_0_MAKEFILE_AUDIT_W18_LITERAL: str = "audit-w18:"


_V10_5_0_DEPRECATED_TEMPLATES: tuple[str, ...] = (
    "hotfix",
    "refactoring",
    "feature-enhancement",
    "full-pipeline",
    "documentation-only",
    "research-only",
    "design-only",
    "research-design-review-refine",
    "spike-poc",
    "security-audit",
    "demo-showcase",
    "performance-optimization",
    "dependency-setup",
    "onboarding",
    "product-verification",
    "entropy-cleanup",
)


# Header text refreshed at v14.2.2 (G-017): the original "will be removed in
# v12.0.0" promise lapsed 3 majors; the headers now carry the v15-ADR-002
# Phase B decision telegraph instead of a stale removal date.
_V10_5_0_DEPRECATION_HEADER_LITERAL: str = (
    "# DEPRECATED in v11.0.0; retained for backward compat — "
    "Phase B collapse decision lands v15.0.0 per v15-ADR-002"
)


def test_v10_5_0_new_symbols_have_coverage(project_root: Path) -> None:
    """W-18 v10.5.0: every NEW v10.5.0 PV-01..PV-05 surface has presence coverage.

    Discharges the W-18 precondition for the v10.5.0 MINOR cycle. The
    CHANGELOG entry mentions:

    * 4 NEW audit scripts (audit_layer_usage, audit_template_usage,
      measure_reference_friction, audit_w18_lint_maintenance);
    * 1 NEW XL-tier example (multi-stage-trace.md, the 4th example);
    * NEW agent-workspace.md §3.6 "Resume After Pause" subsection;
    * NEW activation_verdict(force_no_change=...) parameter;
    * 16 TIER-2 yaml deprecation comment headers (D-A-2 Phase A);
    * 4 NEW Makefile targets (audit-{layers,templates,w18},
      measure-friction);
    * 4 NEW research artifacts (v10.5.{1,2,3,4} audit outputs);
    * canonical 7 sync 10.4.0 -> 10.5.0 + CHANGELOG `## [10.5.0]`.

    Each pin protects the W-18 sequencing per
    `.local/research/v9.0.0_pv05_design.md` §3 + ADR-005 D2.
    """
    for script in (
        _V10_5_0_AUDIT_LAYERS_SCRIPT,
        _V10_5_0_AUDIT_TEMPLATES_SCRIPT,
        _V10_5_0_MEASURE_FRICTION_SCRIPT,
        _V10_5_0_AUDIT_W18_SCRIPT,
    ):
        path = project_root / script
        assert path.is_file(), (
            f"W-18 v10.5.0 violation: NEW audit script missing at {script}. "
            f"v10.5.0 ships this script as part of the D-A / D-D slice. "
            f"Author the file OR remove the CHANGELOG mention."
        )

    example_path = project_root / _V10_5_0_MULTI_STAGE_EXAMPLE
    assert example_path.is_file(), (
        f"W-18 v10.5.0 violation: 4th XL-tier example missing at "
        f"{_V10_5_0_MULTI_STAGE_EXAMPLE}. v10.5.0 PV-01 ships D-A-1."
    )

    skill_text = (project_root / "workflow-system/agent/SKILL.md").read_text(encoding="utf-8")
    assert "examples/multi-stage-trace.md" in skill_text, (
        "W-18 v10.5.0 violation: SKILL.md must reference the new "
        "multi-stage-trace.md example in the Quick Action Decision "
        "advisory annotation (D-A-1)."
    )
    # v14.5.0 (G-019 / T6): the Template Quick-Reference table moved to
    # references/meta-framework.md §4 "Template Quick-Reference — Gate
    # Types" (IA demotion pass); the (legacy) annotation pin follows it.
    meta_framework_text = (
        project_root / "workflow-system/agent/references/meta-framework.md"
    ).read_text(encoding="utf-8")
    assert "(legacy)" in meta_framework_text, (
        "W-18 v10.5.0 violation: the Template Quick-Reference surface "
        "(references/meta-framework.md §4 since the v14.5.0 G-019 "
        "demotion) must carry the (legacy) annotation on TIER-2 "
        "templates (D-A-2 Phase A)."
    )

    agent_workspace_text = (
        project_root / "workflow-system/agent/references/agent-workspace.md"
    ).read_text(encoding="utf-8")
    assert "## 3.6 Resume After Pause" in agent_workspace_text, (
        "W-18 v10.5.0 violation: agent-workspace.md must include "
        "the new §3.6 Resume After Pause subsection (D-A-3)."
    )

    # D-A-4: force_no_change parameter on activation_verdict.
    change_activation_text = (
        project_root / "src/devolaflow/skills/change_activation.py"
    ).read_text(encoding="utf-8")
    assert "force_no_change" in change_activation_text, (
        "W-18 v10.5.0 violation: change_activation.py must add the "
        "force_no_change parameter to activation_verdict() (D-A-4)."
    )

    # D-A-2 Phase A: 16 TIER-2 yaml files carry the deprecation comment.
    template_dir = project_root / "workflow-system/agent/templates/builtin"
    for tmpl in _V10_5_0_DEPRECATED_TEMPLATES:
        yaml_path = template_dir / f"{tmpl}.yaml"
        assert yaml_path.is_file(), (
            f"W-18 v10.5.0 violation: TIER-2 template missing at {yaml_path}"
        )
        text = yaml_path.read_text(encoding="utf-8")
        assert _V10_5_0_DEPRECATION_HEADER_LITERAL in text, (
            f"W-18 v10.5.0 violation: TIER-2 template {tmpl}.yaml missing "
            f"the deprecation comment header (D-A-2 Phase A). Re-run "
            f"the deprecation-tagging step OR remove the CHANGELOG mention."
        )

    makefile_text = (project_root / "Makefile").read_text(encoding="utf-8")
    for marker in (
        _V10_5_0_MAKEFILE_AUDIT_LAYERS_LITERAL,
        _V10_5_0_MAKEFILE_AUDIT_TEMPLATES_LITERAL,
        _V10_5_0_MAKEFILE_MEASURE_FRICTION_LITERAL,
        _V10_5_0_MAKEFILE_AUDIT_W18_LITERAL,
    ):
        assert marker in makefile_text, (
            f"W-18 v10.5.0 violation: Makefile missing literal {marker!r} "
            f"(D-A-* / D-D-* audit targets). Author the target OR remove "
            f"the CHANGELOG mention."
        )

    _w18_research_artifact_path(project_root, _V10_5_0_RETROSPECTIVE_DOC)

    for audit_doc in (
        _V10_5_0_LAYER_AUDIT_DOC,
        _V10_5_0_TEMPLATE_AUDIT_DOC,
        _V10_5_0_FRICTION_DOC,
        _V10_5_0_W18_AUDIT_DOC,
    ):
        _w18_research_artifact_path(project_root, audit_doc)

    changelog = (project_root / "CHANGELOG.md").read_text(encoding="utf-8")
    assert _V10_5_0_CHANGELOG_LITERAL in changelog, (
        f"W-18 v10.5.0 violation: CHANGELOG entry "
        f"{_V10_5_0_CHANGELOG_LITERAL!r} missing; v10.5.0 ships this entry."
    )
