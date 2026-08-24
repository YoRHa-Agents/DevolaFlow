"""Declarative checklist-seed models, registry parsing, and validation."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from devolaflow.template_engine.models import VALID_PRIMITIVES

REGISTRY_SCHEMA_V3 = "3.0"
SEED_SCHEMA_VERSION = "1.0"

_NAME_RE = re.compile(r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$")
_PLACEHOLDER_KEY_RE = re.compile(r"^[a-z][a-z0-9_]*$")
_PLACEHOLDER_REF_RE = re.compile(r"\{\{ ([a-z][a-z0-9_]*) \}\}")
_ANY_PLACEHOLDER_RE = re.compile(r"\{\{.*?\}\}")
_VERSION_RE = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")
_CATEGORIES = frozenset({"discover", "shape", "build", "deliver", "composite", "control"})
_FORBIDDEN_EXECUTABLE_KEYS = frozenset(
    {
        "stages",
        "composition",
        "loops",
        "gates",
        "team",
        "duration_class",
        "input_mapping",
        "skip_condition",
    }
)


class ChecklistSeedError(Exception):
    """Raised when a registered checklist seed is missing or malformed."""


@dataclass(frozen=True)
class ChecklistSeedSource:
    """Describe the historical registry/template source of a seed."""

    kind: str
    name: str
    path: str
    schema_version: str


@dataclass(frozen=True)
class ChecklistSeedMetadata:
    """Catalog metadata for a checklist seed."""

    name: str
    version: str
    description: str
    category: str
    intent_keywords: tuple[str, ...]
    source: ChecklistSeedSource
    applicable_scenarios: tuple[str, ...] = ()


@dataclass(frozen=True)
class ChecklistSeedPlaceholder:
    """Declare one value that must be resolved during materialization."""

    description: str
    required: bool
    example: str | None = None


@dataclass(frozen=True)
class ChecklistSeedSourceStage:
    """Retain one historical stage id/primitive pair as provenance only."""

    id: str
    primitive: str


@dataclass(frozen=True)
class ChecklistSeedVerification:
    """Describe the non-executed verification recipe for an assertion."""

    mode: str
    template: str | None = None


@dataclass(frozen=True)
class ChecklistSeedAssertion:
    """Represent one assertion template within a seed partition."""

    key: str
    statement_template: str
    suggested_priority: str
    verify: ChecklistSeedVerification


@dataclass(frozen=True)
class ChecklistSeedPartition:
    """Group provenance stages and assertion templates for presentation."""

    key: str
    title_template: str
    source_stages: tuple[ChecklistSeedSourceStage, ...]
    assertions: tuple[ChecklistSeedAssertion, ...]


@dataclass(frozen=True)
class ChecklistSeed:
    """Top-level declarative checklist decomposition seed."""

    schema_version: str
    kind: str
    metadata: ChecklistSeedMetadata
    placeholders: dict[str, ChecklistSeedPlaceholder] = field(default_factory=dict)
    partitions: tuple[ChecklistSeedPartition, ...] = ()

    def source_stage_sequence(self) -> list[tuple[str, str]]:
        """Return the complete provenance sequence in presentation order."""
        return [
            (stage.id, stage.primitive)
            for partition in self.partitions
            for stage in partition.source_stages
        ]


@dataclass(frozen=True)
class RegistrySeedEntry:
    """Describe one v3 registry entry that points to a checklist seed."""

    name: str
    seed: str
    category: str
    tags: tuple[str, ...]
    description: str
    path: str | None = None


def _error(path: Path, message: str) -> ChecklistSeedError:
    return ChecklistSeedError(f"{path}: {message}")


def _require_mapping(value: Any, path: Path, field_name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise _error(path, f"'{field_name}' must be a mapping")
    return value


def _require_list(value: Any, path: Path, field_name: str) -> list[Any]:
    if not isinstance(value, list):
        raise _error(path, f"'{field_name}' must be a list")
    return value


def _check_keys(
    raw: dict[str, Any],
    *,
    required: set[str],
    allowed: set[str],
    path: Path,
    field_name: str,
) -> None:
    missing = required - raw.keys()
    extra = raw.keys() - allowed
    if missing:
        raise _error(path, f"'{field_name}' missing required fields {sorted(missing)}")
    if extra:
        raise _error(path, f"'{field_name}' has unsupported fields {sorted(extra)}")


def _check_no_executable_keys(value: Any, path: Path) -> None:
    if isinstance(value, dict):
        forbidden = value.keys() & _FORBIDDEN_EXECUTABLE_KEYS
        if forbidden:
            raise _error(path, f"seed contains executable fields {sorted(forbidden)}")
        for child in value.values():
            _check_no_executable_keys(child, path)
    elif isinstance(value, list):
        for child in value:
            _check_no_executable_keys(child, path)


def _parse_source(raw: Any, path: Path) -> ChecklistSeedSource:
    source = _require_mapping(raw, path, "metadata.source")
    fields = {"kind", "name", "path", "schema_version"}
    _check_keys(source, required=fields, allowed=fields, path=path, field_name="metadata.source")
    if source["kind"] not in {"composition", "template"}:
        raise _error(path, "metadata.source.kind must be 'composition' or 'template'")
    source_path = source["path"]
    if not isinstance(source_path, str) or not source_path:
        raise _error(path, "metadata.source.path must be a non-empty string")
    parsed_path = Path(source_path)
    if parsed_path.is_absolute() or ".." in parsed_path.parts:
        raise _error(path, "metadata.source.path must be repository-relative")
    return ChecklistSeedSource(
        kind=str(source["kind"]),
        name=str(source["name"]),
        path=source_path,
        schema_version=str(source["schema_version"]),
    )


def _parse_metadata(raw: Any, path: Path) -> ChecklistSeedMetadata:
    metadata = _require_mapping(raw, path, "metadata")
    required = {"name", "version", "description", "category", "intent_keywords", "source"}
    allowed = required | {"applicable_scenarios"}
    _check_keys(metadata, required=required, allowed=allowed, path=path, field_name="metadata")
    name = metadata["name"]
    version = metadata["version"]
    category = metadata["category"]
    if not isinstance(name, str) or not _NAME_RE.fullmatch(name):
        raise _error(path, "metadata.name must be kebab-case")
    if not isinstance(version, str) or not _VERSION_RE.fullmatch(version):
        raise _error(path, "metadata.version must be semantic version text")
    if category not in _CATEGORIES:
        raise _error(path, f"metadata.category must be one of {sorted(_CATEGORIES)}")
    keywords = _require_list(metadata["intent_keywords"], path, "metadata.intent_keywords")
    if not keywords or any(not isinstance(item, str) or not item for item in keywords):
        raise _error(path, "metadata.intent_keywords must contain non-empty strings")
    if len(keywords) != len(set(keywords)):
        raise _error(path, "metadata.intent_keywords must be unique")
    scenarios = _require_list(
        metadata.get("applicable_scenarios", []), path, "metadata.applicable_scenarios"
    )
    source = _parse_source(metadata["source"], path)
    if source.name != name:
        raise _error(path, "metadata.source.name must equal metadata.name")
    return ChecklistSeedMetadata(
        name=name,
        version=version,
        description=str(metadata["description"]),
        category=str(category),
        intent_keywords=tuple(keywords),
        applicable_scenarios=tuple(str(item) for item in scenarios),
        source=source,
    )


def _parse_placeholders(
    raw: Any, path: Path
) -> tuple[dict[str, ChecklistSeedPlaceholder], set[str]]:
    placeholders_raw = _require_mapping(raw, path, "placeholders")
    placeholders: dict[str, ChecklistSeedPlaceholder] = {}
    for key, value in placeholders_raw.items():
        if not isinstance(key, str) or not _PLACEHOLDER_KEY_RE.fullmatch(key):
            raise _error(path, f"invalid placeholder key {key!r}")
        item = _require_mapping(value, path, f"placeholders.{key}")
        required = {"description", "required"}
        allowed = required | {"example"}
        _check_keys(
            item,
            required=required,
            allowed=allowed,
            path=path,
            field_name=f"placeholders.{key}",
        )
        if not isinstance(item["required"], bool):
            raise _error(path, f"placeholders.{key}.required must be boolean")
        example = item.get("example")
        if example is not None and not isinstance(example, str):
            raise _error(path, f"placeholders.{key}.example must be a string")
        placeholders[key] = ChecklistSeedPlaceholder(
            description=str(item["description"]),
            required=item["required"],
            example=example,
        )
    return placeholders, set(placeholders)


def _validate_placeholder_refs(text: str, declared: set[str], path: Path, field_name: str) -> None:
    all_refs = _ANY_PLACEHOLDER_RE.findall(text)
    exact_refs = _PLACEHOLDER_REF_RE.findall(text)
    if len(all_refs) != len(exact_refs):
        raise _error(path, f"{field_name} uses invalid placeholder syntax")
    undeclared = set(exact_refs) - declared
    if undeclared:
        raise _error(path, f"{field_name} references undeclared placeholders {sorted(undeclared)}")


def _parse_verification(
    raw: Any,
    *,
    path: Path,
    field_name: str,
    declared_placeholders: set[str],
) -> ChecklistSeedVerification:
    verify = _require_mapping(raw, path, field_name)
    _check_keys(
        verify,
        required={"mode"},
        allowed={"mode", "template"},
        path=path,
        field_name=field_name,
    )
    mode = verify["mode"]
    template = verify.get("template")
    if mode not in {"command", "metric", "manual"}:
        raise _error(path, f"{field_name}.mode is invalid")
    if mode == "manual" and template is not None:
        raise _error(path, f"{field_name}.template is forbidden for manual verification")
    if mode != "manual" and (not isinstance(template, str) or not template):
        raise _error(path, f"{field_name}.template is required for {mode} verification")
    if isinstance(template, str):
        _validate_placeholder_refs(template, declared_placeholders, path, f"{field_name}.template")
    return ChecklistSeedVerification(mode=str(mode), template=template)


def _parse_partitions(
    raw: Any, path: Path, declared_placeholders: set[str]
) -> tuple[ChecklistSeedPartition, ...]:
    partitions_raw = _require_list(raw, path, "partitions")
    if not 1 <= len(partitions_raw) <= 15:
        raise _error(path, "partitions count must be 1..15")
    partitions: list[ChecklistSeedPartition] = []
    partition_keys: set[str] = set()
    source_stage_ids: set[str] = set()
    assertion_total = 0
    for partition_index, raw_partition in enumerate(partitions_raw):
        field_name = f"partitions[{partition_index}]"
        partition = _require_mapping(raw_partition, path, field_name)
        fields = {"key", "title_template", "source_stages", "assertions"}
        _check_keys(partition, required=fields, allowed=fields, path=path, field_name=field_name)
        key = partition["key"]
        if not isinstance(key, str) or not _NAME_RE.fullmatch(key):
            raise _error(path, f"{field_name}.key must be kebab-case")
        if key in partition_keys:
            raise _error(path, f"duplicate partition key '{key}'")
        partition_keys.add(key)
        title = str(partition["title_template"])
        _validate_placeholder_refs(
            title, declared_placeholders, path, f"{field_name}.title_template"
        )

        stages_raw = _require_list(partition["source_stages"], path, f"{field_name}.source_stages")
        if not stages_raw:
            raise _error(path, f"{field_name}.source_stages must not be empty")
        stages: list[ChecklistSeedSourceStage] = []
        for stage_index, raw_stage in enumerate(stages_raw):
            stage_field = f"{field_name}.source_stages[{stage_index}]"
            stage = _require_mapping(raw_stage, path, stage_field)
            _check_keys(
                stage,
                required={"id", "primitive"},
                allowed={"id", "primitive"},
                path=path,
                field_name=stage_field,
            )
            stage_id = stage["id"]
            primitive = stage["primitive"]
            if not isinstance(stage_id, str) or not stage_id:
                raise _error(path, f"{stage_field}.id must be a non-empty string")
            if stage_id in source_stage_ids:
                raise _error(path, f"source stage '{stage_id}' appears more than once")
            if primitive not in VALID_PRIMITIVES:
                raise _error(path, f"source stage '{stage_id}' has invalid primitive '{primitive}'")
            source_stage_ids.add(stage_id)
            stages.append(ChecklistSeedSourceStage(id=stage_id, primitive=str(primitive)))

        assertions_raw = _require_list(partition["assertions"], path, f"{field_name}.assertions")
        if not 1 <= len(assertions_raw) <= 15:
            raise _error(path, f"{field_name}.assertions count must be 1..15")
        assertion_total += len(assertions_raw)
        assertion_keys: set[str] = set()
        assertions: list[ChecklistSeedAssertion] = []
        for assertion_index, raw_assertion in enumerate(assertions_raw):
            assertion_field = f"{field_name}.assertions[{assertion_index}]"
            assertion = _require_mapping(raw_assertion, path, assertion_field)
            fields = {"key", "statement_template", "suggested_priority", "verify"}
            _check_keys(
                assertion,
                required=fields,
                allowed=fields,
                path=path,
                field_name=assertion_field,
            )
            assertion_key = assertion["key"]
            statement = str(assertion["statement_template"])
            priority = assertion["suggested_priority"]
            if not isinstance(assertion_key, str) or not _NAME_RE.fullmatch(assertion_key):
                raise _error(path, f"{assertion_field}.key must be kebab-case")
            if assertion_key in assertion_keys:
                raise _error(path, f"duplicate assertion key '{assertion_key}' in '{key}'")
            assertion_keys.add(assertion_key)
            if len(statement.split()) > 25:
                raise _error(path, f"{assertion_field}.statement_template exceeds 25 words")
            _validate_placeholder_refs(
                statement,
                declared_placeholders,
                path,
                f"{assertion_field}.statement_template",
            )
            if priority not in {"P0", "P1", "P2"}:
                raise _error(path, f"{assertion_field}.suggested_priority is invalid")
            assertions.append(
                ChecklistSeedAssertion(
                    key=assertion_key,
                    statement_template=statement,
                    suggested_priority=str(priority),
                    verify=_parse_verification(
                        assertion["verify"],
                        path=path,
                        field_name=f"{assertion_field}.verify",
                        declared_placeholders=declared_placeholders,
                    ),
                )
            )
        partitions.append(
            ChecklistSeedPartition(
                key=key,
                title_template=title,
                source_stages=tuple(stages),
                assertions=tuple(assertions),
            )
        )
    if not 1 <= assertion_total <= 60:
        raise _error(path, "total assertion count must be 1..60")
    return tuple(partitions)


def load_checklist_seed(seed_path: Path) -> ChecklistSeed:
    """Load and strictly validate one checklist-seed YAML file."""
    if not seed_path.is_file():
        raise ChecklistSeedError(f"Checklist seed not found: {seed_path}")
    try:
        raw = yaml.safe_load(seed_path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ChecklistSeedError(f"Failed to read checklist seed {seed_path}: {exc}") from exc
    if not isinstance(raw, dict):
        raise _error(seed_path, "seed root must be a mapping")
    _check_no_executable_keys(raw, seed_path)
    top_fields = {"schema_version", "kind", "metadata", "placeholders", "partitions"}
    _check_keys(raw, required=top_fields, allowed=top_fields, path=seed_path, field_name="root")
    if raw["schema_version"] != SEED_SCHEMA_VERSION:
        raise _error(seed_path, f"schema_version must be {SEED_SCHEMA_VERSION!r}")
    if raw["kind"] != "checklist-seed":
        raise _error(seed_path, "kind must be 'checklist-seed'")
    metadata = _parse_metadata(raw["metadata"], seed_path)
    if seed_path.stem != metadata.name:
        raise _error(seed_path, "seed filename stem must equal metadata.name")
    placeholders, declared = _parse_placeholders(raw["placeholders"], seed_path)
    partitions = _parse_partitions(raw["partitions"], seed_path, declared)
    return ChecklistSeed(
        schema_version=SEED_SCHEMA_VERSION,
        kind="checklist-seed",
        metadata=metadata,
        placeholders=placeholders,
        partitions=partitions,
    )


def load_seed_registry(registry_yaml: Path) -> dict[str, RegistrySeedEntry]:
    """Load and validate the seed-bearing entries of a registry v3 manifest."""
    if not registry_yaml.is_file():
        return {}
    try:
        raw = yaml.safe_load(registry_yaml.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as exc:
        raise ChecklistSeedError(f"Failed to read registry {registry_yaml}: {exc}") from exc
    if not isinstance(raw, dict):
        raise ChecklistSeedError(f"{registry_yaml}: registry root must be a mapping")
    if raw.get("schema_version") != REGISTRY_SCHEMA_V3:
        raise ChecklistSeedError(
            f"{registry_yaml}: seed registry requires schema_version {REGISTRY_SCHEMA_V3!r}"
        )
    entries: dict[str, RegistrySeedEntry] = {}
    for block_name in ("compositions", "templates"):
        raw_entries = _require_list(raw.get(block_name), registry_yaml, block_name)
        for index, raw_entry in enumerate(raw_entries):
            field_name = f"{block_name}[{index}]"
            entry = _require_mapping(raw_entry, registry_yaml, field_name)
            required = {"name", "seed", "category", "tags", "description"}
            allowed = required if block_name == "compositions" else required | {"path"}
            _check_keys(
                entry,
                required=required,
                allowed=allowed,
                path=registry_yaml,
                field_name=field_name,
            )
            name = entry["name"]
            seed = entry["seed"]
            if not isinstance(name, str) or not _NAME_RE.fullmatch(name):
                raise _error(registry_yaml, f"{field_name}.name must be kebab-case")
            if name in entries:
                raise _error(registry_yaml, f"duplicate registry name '{name}'")
            if seed != f"seeds/{name}.yaml":
                raise _error(registry_yaml, f"{field_name}.seed must equal 'seeds/{name}.yaml'")
            if entry["category"] not in _CATEGORIES:
                raise _error(registry_yaml, f"{field_name}.category is invalid")
            tags = _require_list(entry["tags"], registry_yaml, f"{field_name}.tags")
            path_value = entry.get("path")
            if block_name == "compositions" and path_value is not None:
                raise _error(registry_yaml, f"{field_name} must not declare an executable path")
            if block_name == "templates":
                if name == "change-driven":
                    if path_value != "builtin/change-driven.yaml":
                        raise _error(
                            registry_yaml,
                            "change-driven must declare path 'builtin/change-driven.yaml'",
                        )
                elif path_value is not None:
                    raise _error(
                        registry_yaml,
                        f"{field_name} must not declare an executable path",
                    )
            entries[name] = RegistrySeedEntry(
                name=name,
                seed=seed,
                category=str(entry["category"]),
                tags=tuple(str(tag) for tag in tags),
                description=str(entry["description"]),
                path=path_value,
            )
    return entries
