#!/usr/bin/env python3
"""Check registry-v3 template metadata ownership and derived-view parity.

``templates/registry.yaml`` owns catalog identity, seed paths, categories,
discovery tags, and catalog descriptions.  The rows in ``workflow-skill.yaml``
and the metadata blocks inside seed files remain compatibility views until all
consumers have migrated.  This check makes the safe migration boundary
explicit: identity and path drift fail, while seed-local intent and
description differences are reported without changing either consumer view.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

REGISTRY_RELATIVE = Path("workflow-system/agent/templates/registry.yaml")
WORKFLOW_SKILL_RELATIVE = Path("workflow-system/agent/workflow-skill.yaml")
SEEDS_RELATIVE = Path("workflow-system/agent/templates/seeds")
REGISTRY_SCHEMA_VERSION = "3.0"
EXPECTED_SEED_COUNT = 27
RUNTIME_NAME = "change-driven"


@dataclass(frozen=True)
class ParityIssue:
    """One blocking mismatch between the owner and a derived view."""

    surface: str
    name: str
    field: str
    expected: Any
    actual: Any


@dataclass(frozen=True)
class TemplateMetadataParity:
    """Machine-readable result of the template metadata parity check."""

    registry_count: int
    workflow_count: int
    seed_count: int
    issues: tuple[ParityIssue, ...]
    keyword_divergences: tuple[str, ...]
    runtime_keyword_divergences: tuple[str, ...]
    description_divergences: tuple[str, ...]
    source_path_gaps: tuple[str, ...]

    @property
    def passed(self) -> bool:
        """Return whether all identity/path/category checks passed."""
        return not self.issues


def _load_yaml(path: Path, root: Path) -> Any:
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        display = path.relative_to(root) if path.is_relative_to(root) else path
        raise ValueError(f"failed to read {display}: {exc}") from exc


def _mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a mapping")
    return value


def _list(value: Any, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise ValueError(f"{label} must be a list")
    return value


def _issue(
    issues: list[ParityIssue],
    surface: str,
    name: str,
    field: str,
    expected: Any,
    actual: Any,
) -> None:
    issues.append(
        ParityIssue(
            surface=surface,
            name=name,
            field=field,
            expected=expected,
            actual=actual,
        )
    )


def _index_rows(
    rows: list[Any], label: str, surface: str, issues: list[ParityIssue]
) -> dict[str, dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}
    for index, item in enumerate(rows):
        row = _mapping(item, f"{label}[{index}]")
        name = row.get("name", row.get("id"))
        if not isinstance(name, str) or not name:
            _issue(issues, surface, str(index), "name", "non-empty string", name)
            continue
        if name in indexed:
            _issue(issues, surface, name, "membership", "unique entry", "duplicate")
            continue
        indexed[name] = row
    return indexed


def check_template_metadata_parity(repo_root: Path | None = None) -> TemplateMetadataParity:
    """Return parity evidence for the registry and its retained views.

    The registry remains the only owner of catalog identity and discovery
    metadata.  Seed ``intent_keywords`` are intentionally checked as a
    diagnostic rather than required to equal registry ``tags``: aliases and
    intent matching still consume that seed-local field.
    """
    root = (repo_root or Path.cwd()).resolve()
    registry_path = root / REGISTRY_RELATIVE
    workflow_path = root / WORKFLOW_SKILL_RELATIVE
    seeds_dir = root / SEEDS_RELATIVE
    registry = _mapping(_load_yaml(registry_path, root), str(REGISTRY_RELATIVE))
    workflow = _mapping(_load_yaml(workflow_path, root), str(WORKFLOW_SKILL_RELATIVE))

    issues: list[ParityIssue] = []
    if registry.get("schema_version") != REGISTRY_SCHEMA_VERSION:
        _issue(
            issues,
            "registry",
            "*",
            "schema_version",
            REGISTRY_SCHEMA_VERSION,
            registry.get("schema_version"),
        )

    raw_entries: list[dict[str, Any]] = []
    for block_name in ("compositions", "templates"):
        for index, raw_entry in enumerate(
            _list(registry.get(block_name), f"registry.{block_name}")
        ):
            raw_entries.append(_mapping(raw_entry, f"registry.{block_name}[{index}]"))
    registry_entries = _index_rows(raw_entries, "registry.entries", "registry", issues)
    if len(raw_entries) != EXPECTED_SEED_COUNT:
        _issue(issues, "registry", "*", "count", EXPECTED_SEED_COUNT, len(raw_entries))

    content = _mapping(workflow.get("content"), "workflow-skill.content")
    template_content = _mapping(content.get("templates"), "workflow-skill.content.templates")
    workflow_rows = _list(template_content.get("seeds"), "workflow-skill.content.templates.seeds")
    workflow_entries = _index_rows(
        workflow_rows, "workflow-skill.content.templates.seeds", "workflow-skill", issues
    )
    if len(workflow_rows) != EXPECTED_SEED_COUNT:
        _issue(issues, "workflow-skill", "*", "count", EXPECTED_SEED_COUNT, len(workflow_rows))
    runtime_view = _mapping(
        template_content.get("runtime"), "workflow-skill.content.templates.runtime"
    )
    runtime_owner = next(
        (entry for entry in raw_entries if entry.get("name") == RUNTIME_NAME), None
    )
    if runtime_owner is None:
        _issue(issues, "registry", RUNTIME_NAME, "membership", "runtime entry", None)
    else:
        expected_runtime_file = f"templates/{runtime_owner.get('path')}"
        for field, expected in (
            ("id", RUNTIME_NAME),
            ("file", expected_runtime_file),
        ):
            if runtime_view.get(field) != expected:
                _issue(
                    issues,
                    "workflow-skill",
                    RUNTIME_NAME,
                    f"runtime.{field}",
                    expected,
                    runtime_view.get(field),
                )

    registry_names = set(registry_entries)
    workflow_names = set(workflow_entries)
    seed_names = {path.stem for path in seeds_dir.glob("*.yaml")}
    if len(seed_names) != EXPECTED_SEED_COUNT:
        _issue(issues, "seed", "*", "count", EXPECTED_SEED_COUNT, len(seed_names))
    for name in sorted(registry_names - workflow_names):
        _issue(issues, "workflow-skill", name, "membership", name, None)
    for name in sorted(workflow_names - registry_names):
        _issue(issues, "workflow-skill", name, "membership", None, name)
    for name in sorted(registry_names - seed_names):
        _issue(issues, "seed", name, "membership", name, None)
    for name in sorted(seed_names - registry_names):
        _issue(issues, "seed", name, "membership", None, name)

    keyword_divergences: list[str] = []
    runtime_keyword_divergences: list[str] = []
    description_divergences: list[str] = []
    source_path_gaps: list[str] = []
    for name in sorted(registry_names):
        entry = registry_entries[name]
        seed_relative = entry.get("seed")
        expected_seed = f"seeds/{name}.yaml"
        if seed_relative != expected_seed:
            _issue(issues, "registry", name, "seed", expected_seed, seed_relative)

        workflow_row = workflow_entries.get(name)
        if workflow_row is not None:
            expected_workflow_file = f"templates/{seed_relative}"
            if workflow_row.get("file") != expected_workflow_file:
                _issue(
                    issues,
                    "workflow-skill",
                    name,
                    "file",
                    expected_workflow_file,
                    workflow_row.get("file"),
                )

        seed_path = root / SEEDS_RELATIVE / f"{name}.yaml"
        if not seed_path.is_file():
            continue
        seed = _mapping(_load_yaml(seed_path, root), f"{seed_path}.yaml")
        metadata = _mapping(seed.get("metadata"), f"{name}.metadata")

        for field in ("name", "category"):
            expected = name if field == "name" else entry.get(field)
            if metadata.get(field) != expected:
                _issue(issues, "seed", name, field, expected, metadata.get(field))

        source = metadata.get("source")
        if isinstance(source, dict) and source.get("name") != name:
            _issue(issues, "seed", name, "source.name", name, source.get("name"))
        if isinstance(source, dict):
            source_path = source.get("path")
            parsed_source_path = Path(source_path) if isinstance(source_path, str) else None
            if (
                parsed_source_path is None
                or parsed_source_path.is_absolute()
                or ".." in parsed_source_path.parts
            ):
                _issue(
                    issues,
                    "seed",
                    name,
                    "source.path",
                    "repository-relative path",
                    source_path,
                )
            elif not (root / parsed_source_path).is_file():
                source_path_gaps.append(name)

        registry_tags = entry.get("tags")
        seed_keywords = metadata.get("intent_keywords")
        if registry_tags != seed_keywords:
            if name == RUNTIME_NAME:
                runtime_keyword_divergences.append(name)
            else:
                keyword_divergences.append(name)
        if entry.get("description") != metadata.get("description"):
            description_divergences.append(name)

    return TemplateMetadataParity(
        registry_count=len(registry_entries),
        workflow_count=len(workflow_entries),
        seed_count=len(seed_names),
        issues=tuple(issues),
        keyword_divergences=tuple(keyword_divergences),
        runtime_keyword_divergences=tuple(runtime_keyword_divergences),
        description_divergences=tuple(description_divergences),
        source_path_gaps=tuple(source_path_gaps),
    )


def validate_template_metadata_parity(repo_root: Path | None = None) -> TemplateMetadataParity:
    """Run the check and raise with every blocking mismatch when it fails."""
    result = check_template_metadata_parity(repo_root)
    if result.passed:
        return result
    details = "; ".join(
        f"{item.surface}:{item.name}.{item.field} expected={item.expected!r} actual={item.actual!r}"
        for item in result.issues
    )
    raise ValueError(f"template metadata parity failed: {details}")


def _format_result(result: TemplateMetadataParity) -> str:
    status = "PASS" if result.passed else "FAIL"
    lines = [
        f"[{status}] template metadata identity/path/category parity",
        (
            f"counts: registry={result.registry_count}, "
            f"workflow-skill={result.workflow_count}, seeds={result.seed_count}"
        ),
        f"diagnostic keyword divergences: {list(result.keyword_divergences)}",
        f"runtime keyword divergences: {list(result.runtime_keyword_divergences)}",
        f"seed-local description divergences: {len(result.description_divergences)}",
        f"historical source path gaps: {list(result.source_path_gaps)}",
    ]
    for issue in result.issues:
        lines.append(
            f"  - {issue.surface}:{issue.name}.{issue.field}: "
            f"expected={issue.expected!r}, actual={issue.actual!r}"
        )
    return "\n".join(lines)


def main() -> int:
    """Print parity evidence and return non-zero only for blocking drift."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    result = check_template_metadata_parity(args.repo_root)
    print(_format_result(result))
    return 0 if result.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
