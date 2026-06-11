"""Ghost audit — schema-manifest / layout companion lints.

Split from ``tests/test_no_ghost_features.py`` per v15-ADR-001
(v14.3.0). Category E of the original v7.5.0 ghost audit: every
schema path cited by SKILL.md / workflow-skill.yaml exists on disk
and every on-disk schema is declared in the manifest.
"""

from __future__ import annotations

import re
from pathlib import Path

from tests.ghost._helpers import _load_yaml, _read

# ── Category E: schemas ─────────────────────────────────────────────


def _skill_schema_paths(project_root: Path) -> set[str]:
    skill = _read(project_root / "workflow-system/agent/SKILL.md")
    return set(re.findall(r"`(schemas/[a-zA-Z0-9._/-]+\.yaml)`", skill))


def test_skill_schema_references_exist_on_disk(project_root: Path) -> None:
    """G-E1/E2/E3: every schema path SKILL.md cites must exist on disk.

    Closed by P-07 in v7.4.7 — SKILL.md Tier 3 paths corrected from
    ``schemas/{task-dispatch,status-report,handoff-deliverable}.yaml`` to
    the canonical ``.schema.yaml`` suffix per audit §3.E G-E1/E2/E3
    evidence; the missing ``handoff-deliverable.schema.yaml`` was authored
    as a P-07 Option α stub. xfail marker removed per the audit §6
    strict=True contract.
    """
    refs = _skill_schema_paths(project_root)
    missing = sorted(r for r in refs if not (project_root / r).exists())
    assert not missing, f"SKILL.md cites schema files that don't exist: {missing}"


def test_workflow_skill_yaml_manifest_schemas_exist(project_root: Path) -> None:
    """G-E4: every schema file declared in workflow-skill.yaml must exist.

    Closed by P-07 in v7.4.7 — the four ``stage-definition``,
    ``wave-definition``, ``task-definition``, and ``dependency-matrix``
    schemas referenced by ``workflow-skill.yaml`` were authored as P-07
    Option α stubs per audit §5 P-07 row decision; xfail marker removed
    per the audit §6 strict=True contract.
    """
    raw = _load_yaml(project_root / "workflow-system/agent/workflow-skill.yaml")
    base = project_root / "workflow-system/agent"
    missing = [
        e["file"] for e in raw["content"]["schemas"] if not (base / e["file"]).resolve().exists()
    ]
    assert not missing, f"Manifest schemas missing on disk: {missing}"


def test_existing_schemas_are_declared_in_manifest(project_root: Path) -> None:
    """G-E5/E6 (inverse): on-disk schemas must be declared in the manifest.

    Closed by P-07 in v7.4.7 — the on-disk ``feedback-report.schema.yaml``
    and ``workflow-template.schema.yaml`` were registered in the
    ``content.schemas`` block of ``workflow-skill.yaml`` per audit §3.E
    G-E5/G-E6 inverse-ghost evidence; xfail marker removed per the audit
    §6 strict=True contract.
    """
    on_disk = {p.name for p in (project_root / "schemas").glob("*.schema.yaml")}
    raw = _load_yaml(project_root / "workflow-system/agent/workflow-skill.yaml")
    declared = {Path(e["file"]).name for e in raw["content"]["schemas"]}
    undeclared = sorted(on_disk - declared)
    assert not undeclared, (
        f"Schemas exist on disk but unregistered in workflow-skill.yaml "
        f"content.schemas: {undeclared}"
    )
