"""Current-cycle ghost audit for the local-task archive contract.

The local archive is audited before any release note can claim the feature.
This file pins the runtime owner, artifact schema, seed/reference/install
wiring, protected boundary, permanent deletion boundary, and unchanged
default workspace discovery.
"""

from __future__ import annotations

from pathlib import Path

import yaml

import devolaflow.local.archive as archive
from devolaflow.workspace_context import scan_workspace
from tests.ghost.test_registries import _SF4_REFERENCE_SET


def test_v17_5_local_archive_runtime_and_schema_are_wired(project_root: Path) -> None:
    """The sole runtime owner and schema expose the bounded contract."""
    runtime_path = Path(archive.__file__).resolve()
    assert runtime_path == (project_root / "src/devolaflow/local/archive.py").resolve()
    assert {
        "inventory_tasks",
        "build_archive_plan",
        "apply_archive_plan",
        "inspect_safety",
        "render_index",
        "append_mapping_record",
    } <= set(archive.__all__)

    schema = yaml.safe_load(
        (project_root / "schemas/local-archive.schema.yaml").read_text(encoding="utf-8")
    )
    assert schema["schema_name"] == "local-archive"
    assert schema["source_boundary"] == ".local/tasks"
    assert schema["lifecycle"]["enum"] == ["active", "done", "stale", "unknown"]
    assert "protected" not in schema["lifecycle"]["enum"]
    assert schema["protection"]["enum"] == ["allowed", "protected", "unsafe", "ambiguous"]
    assert schema["actions"]["enum"] == ["move", "retain", "review", "refuse"]
    assert "delete" not in schema["actions"]["enum"]
    inspection = archive.inspect_safety(
        project_root,
        ".local/.agent/active/protected-change",
    )
    finding_codes = {finding.code for finding in inspection.findings}
    assert not inspection.safe
    assert "PROTECTED_PATH" in finding_codes
    assert not hasattr(archive, "delete")
    assert "delete" not in archive.__all__
    runtime_text = (project_root / "src/devolaflow/local/archive.py").read_text(encoding="utf-8")
    assert "There is intentionally no deletion action." in runtime_text
    assert "git clean" not in runtime_text


def test_v17_5_local_archive_seed_reference_and_install_wiring(
    project_root: Path,
) -> None:
    """Seed, reference, manifest, and SKILL surfaces are all connected."""
    templates = project_root / "workflow-system/agent/templates"
    registry = yaml.safe_load((templates / "registry.yaml").read_text(encoding="utf-8"))
    seed_entry = next(item for item in registry["compositions"] if item["name"] == "local-archive")
    assert seed_entry["seed"] == "seeds/local-archive.yaml"
    assert (templates / seed_entry["seed"]).is_file()
    seed_text = (templates / seed_entry["seed"]).read_text(encoding="utf-8")
    assert "entropy-cleanup" not in seed_text

    reference = project_root / "workflow-system/agent/references/local-archive.md"
    manifest = yaml.safe_load(
        (project_root / "workflow-system/agent/manifest.yaml").read_text(encoding="utf-8")
    )
    skill = (project_root / "workflow-system/agent/SKILL.md").read_text(encoding="utf-8")
    assert reference.is_file()
    assert "local-archive.md" in _SF4_REFERENCE_SET
    assert "references/local-archive.md" in manifest["references"]
    assert "references/local-archive.md" in skill
    assert "| local task archive or clustering | `local-archive` |" in skill


def test_v17_5_local_archive_does_not_expand_default_scan(tmp_path: Path) -> None:
    """Adding task folders does not alter the normal workspace snapshot."""
    local = tmp_path / ".local"
    local.mkdir()
    before = scan_workspace(tmp_path).to_summary_dict()
    task = local / "tasks" / "flat-task"
    task.mkdir(parents=True)
    (task / "task.yaml").write_text("status: done\n", encoding="utf-8")
    after = scan_workspace(tmp_path).to_summary_dict()

    assert before == after
    assert "tasks" not in after
    assert not any("task" in str(value) for value in after.values() if isinstance(value, str))
