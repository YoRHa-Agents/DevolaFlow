"""Draft and transactionally authorize checklist-era preflight artifacts."""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from collections.abc import Mapping, Sequence
from copy import deepcopy
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Final, Literal

import yaml

from devolaflow.agent_workspace.change import (
    ChangeLayout,
    LegacyChangeLayoutError,
    detect_change_layout,
)
from devolaflow.agent_workspace.round_parser import (
    RoundArtifactParseError,
    parse_checklist,
    parse_frontmatter,
)
from devolaflow.pre_decision import (
    PreDecisionChecklist,
    ValidationError,
    auto_detect,
    validate_consistency,
)

PreflightDraftMode = Literal["draft", "inherited", "delta"]
PreflightDisposition = Literal[
    "verified_pass",
    "preauthorized",
    "preauthorized_fallback",
    "reserved_stop",
]

_CHANGE_ID_RE = re.compile(r"^[a-z0-9][a-z0-9.-]*[a-z0-9]$")
_HASH_RE = re.compile(r"^[0-9a-f]{64}$")
_UTC_TIMESTAMP_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
_CARD_ID_RE = re.compile(r"^PF-(A|E|X|P)[1-9][0-9]*$")
_CHECKLIST_ID_RE = re.compile(r"^C-G[1-9][0-9]*\.[1-9][0-9]*$")
_INHERITED_RE = re.compile(
    r"^- Inherited from ([a-z0-9][a-z0-9.-]*[a-z0-9]) "
    r"\(signed (\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z)\); "
    r"config hash ([0-9a-f]{64}) matches; no drift\.$"
)
_FULL_FIELD_RE = re.compile(
    r"^- ([a-z_]+): (.+) \| decision: (MANDATORY|DEFAULTED|CONFIRM) "
    r"\| source: (.+)$"
)
_DELTA_FIELD_RE = re.compile(r"^- Δ ([a-z_]+): previous=(.+) \| proposed=(.+)$")
_AUTHORIZATION_RECORD_RE = re.compile(
    r"^- (PF-(?:A|E|X|P)[1-9][0-9]*): "
    r"(verified_pass|preauthorized|preauthorized_fallback|reserved_stop) at "
    r"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z) — (.+)$"
)

_PREFLIGHT_HEADINGS: Final[tuple[str, ...]] = (
    "## 0. Project Configuration",
    "## 1. Stop Cards",
    "## 2. Authorization Record",
    "## 3. Permitted Stops",
    "## 4. Progress Snapshot",
)
_STOP_CARD_HEADER: Final[str] = "| ID | Category | Description | Checklist Items | Disposition |"
_STOP_CARD_SEPARATOR: Final[str] = "|---|---|---|---|---|"
_PENDING_AUTHORIZATION_LINE: Final[str] = "- Pending user signature; `authorized_at` remains null."
_PERMITTED_STOPS: Final[tuple[str, ...]] = (
    "1. STOP-1: A Section 1 card with disposition=reserved_stop is reached.",
    "2. STOP-2: The two-round stagnation rule fires or max_rounds is reached.",
    "3. STOP-3: A FULL_ROLLBACK exception reports state corruption or data loss.",
    "4. STOP-4: The user reopens an item and the verbatim reverted reason "
    "explicitly instructs a stop.",
)
_CARD_CATEGORY_PREFIX: Final[dict[str, str]] = {
    "human_touch": "A",
    "environment_dependency": "E",
    "external_resource": "X",
    "permission_authorization": "P",
}
_DISPOSITIONS: Final[frozenset[str]] = frozenset(
    {
        "verified_pass",
        "preauthorized",
        "preauthorized_fallback",
        "reserved_stop",
    }
)

_SECTIONS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("project", "### 0.1 Project", ("name", "purpose", "scope_keywords", "existing_codebase")),
    (
        "tech_stack",
        "### 0.2 Tech Stack",
        (
            "primary_language",
            "secondary_languages",
            "framework",
            "build_system",
            "dependency_manifest",
            "runtime_version",
            "pinned_dependencies",
            "banned_dependencies",
        ),
    ),
    (
        "repository",
        "### 0.3 Repository",
        ("mode", "remote_url", "default_branch", "branching_strategy", "features"),
    ),
    (
        "localization",
        "### 0.4 Localization",
        (
            "primary_language",
            "secondary_language",
            "bilingual_output",
            "doc_language",
            "code_comments_language",
        ),
    ),
    (
        "platforms",
        "### 0.5 Platforms",
        ("os", "architectures", "additional_targets", "min_os_versions"),
    ),
    (
        "quality",
        "### 0.6 Quality",
        (
            "coverage_target_pct",
            "quality_score_threshold",
            "lint_strictness",
            "gate_profile",
            "max_rounds",
            "security_review_required",
            "harness_evaluation_required",
        ),
    ),
    (
        "release",
        "### 0.7 Release",
        (
            "versioning",
            "initial_version",
            "channels",
            "publishing_targets",
            "signing",
            "changelog_format",
        ),
    ),
    ("workflow", "### 0.8 Workflow", ("seed_mode", "runtime_loop", "seed_overrides")),
)

_DECISIONS: dict[str, str] = {
    "project.name": "MANDATORY",
    "project.purpose": "MANDATORY",
    "project.scope_keywords": "DEFAULTED",
    "project.existing_codebase": "CONFIRM",
    "tech_stack.primary_language": "CONFIRM",
    "tech_stack.secondary_languages": "DEFAULTED",
    "tech_stack.framework": "CONFIRM",
    "tech_stack.build_system": "CONFIRM",
    "tech_stack.dependency_manifest": "CONFIRM",
    "tech_stack.runtime_version": "CONFIRM",
    "tech_stack.pinned_dependencies": "DEFAULTED",
    "tech_stack.banned_dependencies": "DEFAULTED",
    "repository.mode": "CONFIRM",
    "repository.remote_url": "CONFIRM",
    "repository.default_branch": "CONFIRM",
    "repository.branching_strategy": "CONFIRM",
    "repository.features": "DEFAULTED",
    "localization.primary_language": "CONFIRM",
    "localization.secondary_language": "DEFAULTED",
    "localization.bilingual_output": "CONFIRM",
    "localization.doc_language": "CONFIRM",
    "localization.code_comments_language": "DEFAULTED",
    "platforms.os": "CONFIRM",
    "platforms.architectures": "CONFIRM",
    "platforms.additional_targets": "DEFAULTED",
    "platforms.min_os_versions": "DEFAULTED",
    "quality.coverage_target_pct": "CONFIRM",
    "quality.quality_score_threshold": "CONFIRM",
    "quality.lint_strictness": "CONFIRM",
    "quality.gate_profile": "CONFIRM",
    "quality.max_rounds": "CONFIRM",
    "quality.security_review_required": "DEFAULTED",
    "quality.harness_evaluation_required": "DEFAULTED",
    "release.versioning": "CONFIRM",
    "release.initial_version": "DEFAULTED",
    "release.channels": "CONFIRM",
    "release.publishing_targets": "CONFIRM",
    "release.signing": "CONFIRM",
    "release.changelog_format": "DEFAULTED",
    "workflow.seed_mode": "CONFIRM",
    "workflow.runtime_loop": "DEFAULTED",
    "workflow.seed_overrides": "CONFIRM",
}

_RELIABLE_FIELDS: tuple[tuple[str, str], ...] = (
    ("project", "existing_codebase"),
    ("tech_stack", "primary_language"),
    ("tech_stack", "build_system"),
    ("tech_stack", "dependency_manifest"),
    ("repository", "mode"),
    ("repository", "remote_url"),
    ("repository", "default_branch"),
)
_MODE_FEATURES = ("ci_cd", "github_actions", "release_publishing", "merge_requests")
_TARGET_TO_SOURCE = {
    "quality.max_rounds": "quality.max_convergence_rounds",
    "quality.harness_evaluation_required": "quality.benchmark_required",
    "workflow.seed_mode": "workflow.type",
}
_SOURCE_ONLY_OVERRIDE_PATHS = {
    "quality.max_convergence_rounds",
    "quality.benchmark_required",
    "workflow.type",
    "workflow.custom_stages",
    "workflow.skip_stages",
    "workflow.stage_overrides",
}
_BASELINE_METADATA = {"version", "created_at", "status", "_validation_notes"}


class PreflightDraftError(ValueError):
    """Raised when a Section 0 draft request is malformed."""


class PreflightAuthorizationError(RuntimeError):
    """Raised when preflight authorization cannot commit safely."""


@dataclass(frozen=True)
class PreflightConfigBaseline:
    """Previously signed normalized Section 0 configuration."""

    change_id: str
    authorized_at: str
    project_config_hash: str
    config: Mapping[str, object]


@dataclass(frozen=True)
class PreflightSection0Draft:
    """Immutable result of pure Section 0 drafting."""

    mode: PreflightDraftMode
    markdown: str
    config: Mapping[str, object]
    validation_findings: tuple[ValidationError, ...]
    changed_fields: tuple[str, ...]
    config_inherited_from: str | None
    project_config_hash: str | None


@dataclass(frozen=True)
class PreflightAuthorization:
    """One user authorization corresponding to one Section 1 stop card."""

    card_id: str
    disposition: PreflightDisposition
    quote: str


@dataclass(frozen=True)
class PreflightSignature:
    """Committed preflight signature and its two artifact paths."""

    authorized_at: str
    project_config_hash: str
    authorization_hash: str
    preflight_path: Path
    mirror_path: Path


@dataclass(frozen=True)
class _PreflightSections:
    """Canonical Section 0–4 contents without their headings."""

    contents: tuple[str, str, str, str, str]

    def with_section(self, index: int, content: str) -> _PreflightSections:
        updated = list(self.contents)
        updated[index] = content
        return _PreflightSections(tuple(updated))  # type: ignore[arg-type]


@dataclass(frozen=True)
class _Section0State:
    """Parsed Section 0 shape used by signing and lint."""

    mode: PreflightDraftMode
    config: Mapping[str, object] | None
    inherited_hash: str | None


@dataclass(frozen=True)
class _StopCard:
    """Parsed canonical Section 1 row."""

    card_id: str
    category: str
    description: str
    checklist_items: tuple[str, ...]
    disposition: PreflightDisposition


@dataclass(frozen=True)
class _SignedPreflightCandidate:
    """Validated signed preflight provenance discovered on disk."""

    change_id: str
    authorized_at: str
    project_config_hash: str
    relative_path: str


def _validate_timestamp(value: object, *, field_name: str) -> str:
    if not isinstance(value, str) or _UTC_TIMESTAMP_RE.fullmatch(value) is None:
        raise PreflightAuthorizationError(
            f"{field_name} must be an ISO-8601 UTC timestamp ending in Z"
        )
    try:
        datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError as exc:
        raise PreflightAuthorizationError(f"{field_name} is not a real UTC timestamp") from exc
    return value


def _extract_preflight_sections(
    text: str,
) -> tuple[dict[str, object], _PreflightSections]:
    """Parse frontmatter and exact canonical body section order."""
    if "\r" in text:
        raise PreflightAuthorizationError("preflight.md must use canonical LF line endings")
    try:
        artifact = parse_frontmatter(text, filename="preflight.md")
    except RoundArtifactParseError as exc:
        raise PreflightAuthorizationError(exc.message) from exc

    lines = artifact.body.strip("\n").splitlines()
    if not lines or lines[0] != "# Preflight":
        raise PreflightAuthorizationError("body must start with exact '# Preflight'")
    found = [line for line in lines if line in _PREFLIGHT_HEADINGS]
    if found != list(_PREFLIGHT_HEADINGS) or any(
        lines.count(heading) != 1 for heading in _PREFLIGHT_HEADINGS
    ):
        raise PreflightAuthorizationError(
            "Sections 0 through 4 must occur exactly once in canonical order"
        )

    positions = [lines.index(heading) for heading in _PREFLIGHT_HEADINGS]
    if positions[0] <= 0:
        raise PreflightAuthorizationError("Section 0 must follow '# Preflight'")
    contents: list[str] = []
    for index, position in enumerate(positions):
        end = positions[index + 1] if index + 1 < len(positions) else len(lines)
        contents.append("\n".join(lines[position + 1 : end]).strip("\n"))
    return artifact.frontmatter, _PreflightSections(tuple(contents))  # type: ignore[arg-type]


def _canonical_sections_0_to_3(sections: _PreflightSections) -> str:
    return "\n\n".join(
        f"{heading}\n{sections.contents[index]}".rstrip()
        for index, heading in enumerate(_PREFLIGHT_HEADINGS[:4])
    )


def _authorization_digest(
    frontmatter: Mapping[str, object],
    sections: _PreflightSections,
) -> str:
    """Return the self-contained authorization seal defined by the schema."""
    metadata = {
        "parent": frontmatter.get("parent"),
        "schema_version": frontmatter.get("schema_version"),
        "authorized_at": frontmatter.get("authorized_at"),
        "config_inherited_from": frontmatter.get("config_inherited_from"),
        "project_config_hash": frontmatter.get("project_config_hash"),
    }
    metadata_bytes = json.dumps(
        metadata,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=False,
    ).encode("utf-8")
    payload = metadata_bytes + b"\n" + _canonical_sections_0_to_3(sections).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _frontmatter_shape(
    frontmatter: Mapping[str, object],
    *,
    change_id: str | None = None,
) -> None:
    required = {
        "parent",
        "schema_version",
        "authorized_at",
        "snapshot_round",
        "config_inherited_from",
        "project_config_hash",
    }
    allowed = required | {"authorization_hash"}
    if not required.issubset(frontmatter) or not set(frontmatter).issubset(allowed):
        raise PreflightAuthorizationError(
            "frontmatter must contain only the six baseline fields plus authorization_hash"
        )
    parent = frontmatter["parent"]
    if not isinstance(parent, str) or _CHANGE_ID_RE.fullmatch(parent) is None:
        raise PreflightAuthorizationError("frontmatter parent is not a valid change id")
    if change_id is not None and parent != change_id:
        raise PreflightAuthorizationError(
            f"frontmatter parent {parent!r} does not equal active change {change_id!r}"
        )
    if type(frontmatter["schema_version"]) is not int or frontmatter["schema_version"] != 1:
        raise PreflightAuthorizationError("frontmatter schema_version must equal integer 1")
    snapshot_round = frontmatter["snapshot_round"]
    if type(snapshot_round) is not int or snapshot_round < 0:
        raise PreflightAuthorizationError("frontmatter snapshot_round must be an integer >= 0")
    inherited_from = frontmatter["config_inherited_from"]
    if inherited_from is not None and (
        not isinstance(inherited_from, str) or _CHANGE_ID_RE.fullmatch(inherited_from) is None
    ):
        raise PreflightAuthorizationError(
            "frontmatter config_inherited_from must be null or a valid change id"
        )


def _yaml_value(raw: str, *, context: str) -> object:
    try:
        return yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        raise PreflightAuthorizationError(f"{context} contains invalid inline YAML") from exc


def _validate_full_section0(content: str) -> Mapping[str, object]:
    lines = content.splitlines()
    headings = [heading for _, heading, _ in _SECTIONS]
    found = [line for line in lines if line.startswith("### 0.")]
    if found != headings or any(lines.count(heading) != 1 for heading in headings):
        raise PreflightAuthorizationError(
            "full Section 0 must contain all eight configuration headings in order"
        )

    positions = [lines.index(heading) for heading in headings]
    config: dict[str, object] = {}
    for index, (section, _heading, field_names) in enumerate(_SECTIONS):
        end = positions[index + 1] if index + 1 < len(positions) else len(lines)
        entries = [line for line in lines[positions[index] + 1 : end] if line.strip()]
        parsed_names: list[str] = []
        values: dict[str, object] = {}
        for line in entries:
            match = _FULL_FIELD_RE.fullmatch(line)
            if match is None:
                raise PreflightAuthorizationError(
                    f"Section 0 field line is not canonical: {line!r}"
                )
            field_name, raw_value, decision, raw_source = match.groups()
            path = f"{section}.{field_name}"
            if field_name in parsed_names or field_name not in field_names:
                raise PreflightAuthorizationError(
                    f"Section 0 contains duplicate or unknown field {path!r}"
                )
            if _DECISIONS[path] != decision:
                raise PreflightAuthorizationError(
                    f"Section 0 field {path!r} has the wrong decision class"
                )
            source = _yaml_value(raw_source, context=f"{path} source")
            if not isinstance(source, str) or not source:
                raise PreflightAuthorizationError(
                    f"Section 0 field {path!r} source must be a non-empty YAML string"
                )
            parsed_names.append(field_name)
            values[field_name] = _yaml_value(raw_value, context=path)
        if tuple(parsed_names) != field_names:
            raise PreflightAuthorizationError(
                f"Section 0 section {section!r} fields are incomplete or out of order"
            )
        config[section] = values
    return config


def _validate_delta_section0(
    content: str,
    *,
    config_inherited_from: object,
) -> None:
    if not isinstance(config_inherited_from, str):
        raise PreflightAuthorizationError(
            "delta Section 0 requires config_inherited_from provenance"
        )
    lines = content.splitlines()
    heading_to_section = {heading: section for section, heading, _ in _SECTIONS}
    headings = [line for line in lines if line.startswith("### 0.")]
    canonical = [heading for _, heading, _ in _SECTIONS if heading in headings]
    if not headings or headings != canonical or len(headings) != len(set(headings)):
        raise PreflightAuthorizationError(
            "delta Section 0 headings must be a non-empty canonical subset"
        )

    positions = [lines.index(heading) for heading in headings]
    for index, heading in enumerate(headings):
        section = heading_to_section.get(heading)
        if section is None:
            raise PreflightAuthorizationError(f"delta Section 0 heading is unknown: {heading!r}")
        allowed_fields = next(fields for name, _, fields in _SECTIONS if name == section)
        end = positions[index + 1] if index + 1 < len(positions) else len(lines)
        entries = [line for line in lines[positions[index] + 1 : end] if line.strip()]
        seen: set[str] = set()
        if not entries:
            raise PreflightAuthorizationError(f"delta Section 0 heading {heading!r} is empty")
        for line in entries:
            match = _DELTA_FIELD_RE.fullmatch(line)
            if match is None:
                raise PreflightAuthorizationError(
                    f"delta Section 0 field line is not canonical: {line!r}"
                )
            field_name, previous, proposed = match.groups()
            if field_name in seen or field_name not in allowed_fields:
                raise PreflightAuthorizationError(
                    f"delta Section 0 contains duplicate or unknown field {section}.{field_name}"
                )
            _yaml_value(previous, context=f"{section}.{field_name} previous")
            _yaml_value(proposed, context=f"{section}.{field_name} proposed")
            seen.add(field_name)


def _validate_section0(
    content: str,
    frontmatter: Mapping[str, object],
    *,
    expected_mode: PreflightDraftMode | None = None,
) -> _Section0State:
    inherited_match = _INHERITED_RE.fullmatch(content)
    if inherited_match is not None:
        inherited_from, signed_at, inherited_hash = inherited_match.groups()
        _validate_timestamp(signed_at, field_name="inherited signature timestamp")
        if frontmatter.get("config_inherited_from") != inherited_from:
            raise PreflightAuthorizationError(
                "inherited Section 0 source does not match config_inherited_from"
            )
        project_hash = frontmatter.get("project_config_hash")
        if project_hash is not None and project_hash != inherited_hash:
            raise PreflightAuthorizationError(
                "inherited Section 0 hash does not match project_config_hash"
            )
        state = _Section0State("inherited", None, inherited_hash)
    elif any(line.startswith("- Δ ") for line in content.splitlines()):
        _validate_delta_section0(
            content,
            config_inherited_from=frontmatter.get("config_inherited_from"),
        )
        state = _Section0State("delta", None, None)
    else:
        if frontmatter.get("config_inherited_from") is not None:
            raise PreflightAuthorizationError("full Section 0 requires null config_inherited_from")
        state = _Section0State("draft", _validate_full_section0(content), None)

    if expected_mode is not None and state.mode != expected_mode:
        raise PreflightAuthorizationError(
            f"Section 0 shape {state.mode!r} does not match draft mode {expected_mode!r}"
        )
    return state


def _parse_stop_cards(
    content: str,
    *,
    checklist_ids: set[str] | None,
) -> tuple[_StopCard, ...]:
    lines = [line for line in content.splitlines() if line.strip()]
    if len(lines) < 2 or lines[:2] != [_STOP_CARD_HEADER, _STOP_CARD_SEPARATOR]:
        raise PreflightAuthorizationError("Section 1 must start with the exact stop-card table")

    cards: list[_StopCard] = []
    seen: set[str] = set()
    for line in lines[2:]:
        if not line.startswith("|") or not line.endswith("|"):
            raise PreflightAuthorizationError("Section 1 contains a non-table row")
        cells = [cell.strip() for cell in line[1:-1].split("|")]
        if len(cells) != 5:
            raise PreflightAuthorizationError("Section 1 card rows must contain five cells")
        card_id, category, description, raw_items, disposition = cells
        match = _CARD_ID_RE.fullmatch(card_id)
        if match is None or card_id in seen:
            raise PreflightAuthorizationError(
                f"Section 1 card id {card_id!r} is invalid or duplicated"
            )
        expected_prefix = _CARD_CATEGORY_PREFIX.get(category)
        if expected_prefix is None or match.group(1) != expected_prefix:
            raise PreflightAuthorizationError(
                f"Section 1 card {card_id!r} category does not match its prefix"
            )
        if not description:
            raise PreflightAuthorizationError(
                f"Section 1 card {card_id!r} description must not be empty"
            )
        if disposition not in _DISPOSITIONS:
            raise PreflightAuthorizationError(
                f"Section 1 card {card_id!r} has invalid disposition {disposition!r}"
            )
        item_ids = tuple(item.strip() for item in raw_items.split(",") if item.strip())
        if not item_ids or any(_CHECKLIST_ID_RE.fullmatch(item) is None for item in item_ids):
            raise PreflightAuthorizationError(
                f"Section 1 card {card_id!r} must reference valid checklist ids"
            )
        if len(item_ids) != len(set(item_ids)):
            raise PreflightAuthorizationError(
                f"Section 1 card {card_id!r} duplicates a checklist reference"
            )
        if checklist_ids is not None and not set(item_ids).issubset(checklist_ids):
            raise PreflightAuthorizationError(
                f"Section 1 card {card_id!r} references an unknown checklist item"
            )
        seen.add(card_id)
        cards.append(
            _StopCard(
                card_id=card_id,
                category=category,
                description=description,
                checklist_items=item_ids,
                disposition=disposition,  # type: ignore[arg-type]
            )
        )
    return tuple(cards)


def _parse_authorization_records(
    content: str,
    *,
    cards: Sequence[_StopCard],
    authorized_at: object,
) -> None:
    lines = [line for line in content.splitlines() if line.strip()]
    if authorized_at is None:
        if lines not in ([], [_PENDING_AUTHORIZATION_LINE]):
            raise PreflightAuthorizationError(
                "unsigned Section 2 must be empty or contain the canonical pending line"
            )
        return

    timestamp = _validate_timestamp(authorized_at, field_name="authorized_at")
    card_by_id = {card.card_id: card for card in cards}
    seen: set[str] = set()
    for line in lines:
        match = _AUTHORIZATION_RECORD_RE.fullmatch(line)
        if match is None:
            raise PreflightAuthorizationError(
                "signed Section 2 record does not match canonical syntax"
            )
        card_id, disposition, record_at, raw_quote = match.groups()
        card = card_by_id.get(card_id)
        if card is None or card_id in seen:
            raise PreflightAuthorizationError(
                f"signed Section 2 record {card_id!r} is orphaned or duplicated"
            )
        if disposition != card.disposition or record_at != timestamp:
            raise PreflightAuthorizationError(
                f"signed Section 2 record {card_id!r} does not match its card or timestamp"
            )
        try:
            quote = json.loads(raw_quote)
        except (json.JSONDecodeError, TypeError) as exc:
            raise PreflightAuthorizationError(
                f"signed Section 2 record {card_id!r} quote must be JSON-escaped"
            ) from exc
        if (
            not isinstance(quote, str)
            or not quote.strip()
            or "\n" in quote
            or "\r" in quote
            or json.dumps(quote, ensure_ascii=False) != raw_quote
        ):
            raise PreflightAuthorizationError(
                f"signed Section 2 record {card_id!r} quote is empty, multiline, or noncanonical"
            )
        seen.add(card_id)
    if seen != set(card_by_id):
        raise PreflightAuthorizationError(
            "signed Section 2 must contain exactly one record per Section 1 card"
        )


def _validate_permitted_stops(content: str) -> None:
    if tuple(content.splitlines()) != _PERMITTED_STOPS:
        raise PreflightAuthorizationError(
            "Section 3 must equal the closed canonical STOP-1 through STOP-4 list"
        )


def _deterministic_mirror_bytes(config: Mapping[str, object]) -> bytes:
    text = yaml.safe_dump(
        deepcopy(dict(config)),
        allow_unicode=True,
        default_flow_style=False,
        sort_keys=False,
    )
    return text.replace("\r\n", "\n").encode("utf-8")


def _render_preflight(
    frontmatter: Mapping[str, object],
    sections: _PreflightSections,
) -> bytes:
    frontmatter_yaml = yaml.safe_dump(
        dict(frontmatter),
        allow_unicode=True,
        default_flow_style=False,
        sort_keys=False,
    ).replace("\r\n", "\n")
    body = "# Preflight\n\n" + "\n\n".join(
        f"{heading}\n{sections.contents[index]}".rstrip()
        for index, heading in enumerate(_PREFLIGHT_HEADINGS)
    )
    return f"---\n{frontmatter_yaml}---\n\n{body}\n".encode()


def _replace_frontmatter_bytes(
    original: bytes,
    frontmatter: Mapping[str, object],
) -> bytes:
    text = original.decode("utf-8")
    closing_start = text.find("\n---", 4)
    if closing_start < 0:
        raise PreflightAuthorizationError("preflight frontmatter closing fence is missing")
    closing_end = text.find("\n", closing_start + 1)
    suffix = "" if closing_end < 0 else text[closing_end + 1 :]
    rendered = yaml.safe_dump(
        dict(frontmatter),
        allow_unicode=True,
        default_flow_style=False,
        sort_keys=False,
    ).replace("\r\n", "\n")
    return f"---\n{rendered}---\n{suffix}".encode()


def _stage_adjacent(path: Path, content: bytes) -> Path:
    descriptor, temp_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
    )
    temp_path = Path(temp_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
    except BaseException:
        temp_path.unlink(missing_ok=True)
        raise
    return temp_path


def _active_checklist_folder(repo_root: Path, change_id: str) -> Path:
    if _CHANGE_ID_RE.fullmatch(change_id) is None:
        raise PreflightAuthorizationError(f"invalid change_id {change_id!r}")
    folder = repo_root / ".local" / ".agent" / "active" / change_id
    try:
        layout = detect_change_layout(folder)
    except LegacyChangeLayoutError as exc:
        raise PreflightAuthorizationError(
            f"active change {change_id!r} must use the checklist layout: {exc}"
        ) from exc
    except (OSError, RuntimeError) as exc:
        raise PreflightAuthorizationError(
            f"active change {change_id!r} is missing or unreadable"
        ) from exc
    if layout is not ChangeLayout.CHECKLIST:
        raise PreflightAuthorizationError(
            f"active change {change_id!r} must use the checklist layout"
        )
    return folder


def _normalized_config(checklist: PreDecisionChecklist) -> dict[str, object]:
    threshold = checklist.quality.quality_score_threshold / 10
    if float(threshold).is_integer():
        threshold = int(threshold)
    return {
        "project": asdict(checklist.project),
        "tech_stack": asdict(checklist.tech_stack),
        "repository": {
            **asdict(checklist.repository),
            "mode": checklist.repository.mode.replace("-", "_"),
        },
        "localization": asdict(checklist.localization),
        "platforms": asdict(checklist.platforms),
        "quality": {
            "coverage_target_pct": checklist.quality.coverage_target_pct,
            "quality_score_threshold": threshold,
            "lint_strictness": checklist.quality.lint_strictness,
            "gate_profile": (
                "minimal"
                if checklist.quality.gate_profile == "relaxed"
                else checklist.quality.gate_profile
            ),
            "max_rounds": checklist.quality.max_convergence_rounds,
            "security_review_required": checklist.quality.security_review_required,
            "harness_evaluation_required": checklist.quality.benchmark_required,
        },
        "release": asdict(checklist.release),
        "workflow": {
            "seed_mode": checklist.workflow.type,
            "runtime_loop": "checklist_rounds",
            "seed_overrides": {
                "custom_stages": deepcopy(checklist.workflow.custom_stages),
                "skip_stages": deepcopy(checklist.workflow.skip_stages),
                "stage_overrides": deepcopy(checklist.workflow.stage_overrides),
            },
        },
    }


def _normalized_baseline_config(config: Mapping[str, object]) -> dict[str, object]:
    if not isinstance(config, Mapping):
        raise PreflightDraftError("baseline config must be a mapping")
    copied = deepcopy(dict(config))
    expected_sections = {section for section, _, _ in _SECTIONS}
    unexpected = set(copied).difference(expected_sections | _BASELINE_METADATA)
    missing_sections = expected_sections.difference(copied)
    if unexpected or missing_sections:
        raise PreflightDraftError(
            "baseline config must contain the eight Section 0 sections; "
            f"missing={sorted(missing_sections)!r}, unexpected={sorted(unexpected)!r}"
        )
    quality = copied["quality"]
    workflow = copied["workflow"]
    if not isinstance(quality, Mapping) or not isinstance(workflow, Mapping):
        raise PreflightDraftError("baseline quality and workflow sections must be mappings")

    if "max_rounds" in quality and "seed_mode" in workflow:
        normalized: dict[str, object] = {}
        for section, _, field_names in _SECTIONS:
            values = copied[section]
            if not isinstance(values, Mapping):
                raise PreflightDraftError(f"baseline config section {section!r} must be a mapping")
            missing = set(field_names).difference(values)
            if missing:
                raise PreflightDraftError(
                    f"baseline config section {section!r} is missing fields {sorted(missing)!r}"
                )
            normalized[section] = {
                field_name: deepcopy(values[field_name]) for field_name in field_names
            }
        return normalized

    checklist = PreDecisionChecklist()
    for section in (
        "project",
        "tech_stack",
        "localization",
        "platforms",
        "quality",
        "release",
        "workflow",
    ):
        values = copied[section]
        if not isinstance(values, Mapping):
            raise PreflightDraftError(f"baseline config section {section!r} must be a mapping")
        target = getattr(checklist, section)
        for field_name, value in values.items():
            if not hasattr(target, field_name):
                raise PreflightDraftError(f"unknown baseline field {section}.{field_name}")
            setattr(target, field_name, deepcopy(value))
    repository = copied["repository"]
    if not isinstance(repository, Mapping):
        raise PreflightDraftError("baseline config section 'repository' must be a mapping")
    for field_name, value in repository.items():
        if field_name == "features":
            if not isinstance(value, Mapping):
                raise PreflightDraftError("baseline repository.features must be a mapping")
            for feature_name, enabled in value.items():
                if not hasattr(checklist.repository.features, feature_name):
                    raise PreflightDraftError(
                        f"unknown baseline feature repository.features.{feature_name}"
                    )
                setattr(checklist.repository.features, feature_name, enabled)
        elif hasattr(checklist.repository, field_name):
            setattr(checklist.repository, field_name, deepcopy(value))
        else:
            raise PreflightDraftError(f"unknown baseline field repository.{field_name}")
    return _normalized_config(checklist)


def _baseline_to_checklist(config: Mapping[str, object]) -> PreDecisionChecklist:
    copied = deepcopy(dict(config))
    checklist = PreDecisionChecklist()
    for section, _, field_names in _SECTIONS:
        values = copied[section]
        if not isinstance(values, Mapping):
            raise PreflightDraftError(f"baseline config section {section!r} must be a mapping")
        missing = set(field_names).difference(values)
        if missing:
            raise PreflightDraftError(
                f"baseline config section {section!r} is missing fields {sorted(missing)!r}"
            )

    for section in ("project", "tech_stack", "localization", "platforms", "release"):
        target = getattr(checklist, section)
        values = copied[section]
        assert isinstance(values, Mapping)
        for field_name, value in values.items():
            if hasattr(target, field_name):
                setattr(target, field_name, deepcopy(value))

    repository = copied["repository"]
    assert isinstance(repository, Mapping)
    for field_name in ("remote_url", "default_branch", "branching_strategy"):
        setattr(checklist.repository, field_name, deepcopy(repository[field_name]))
    checklist.repository.mode = str(repository["mode"]).replace("_", "-")
    features = repository["features"]
    if not isinstance(features, Mapping):
        raise PreflightDraftError("baseline repository.features must be a mapping")
    for field_name, value in features.items():
        if not hasattr(checklist.repository.features, field_name):
            raise PreflightDraftError(f"unknown baseline feature repository.features.{field_name}")
        setattr(checklist.repository.features, field_name, value)

    quality = copied["quality"]
    assert isinstance(quality, Mapping)
    checklist.quality.coverage_target_pct = quality["coverage_target_pct"]  # type: ignore[assignment]
    checklist.quality.quality_score_threshold = quality["quality_score_threshold"] * 10  # type: ignore[operator,assignment]
    checklist.quality.lint_strictness = quality["lint_strictness"]  # type: ignore[assignment]
    profile = quality["gate_profile"]
    checklist.quality.gate_profile = "relaxed" if profile == "minimal" else profile  # type: ignore[assignment]
    checklist.quality.max_convergence_rounds = quality["max_rounds"]  # type: ignore[assignment]
    checklist.quality.security_review_required = quality["security_review_required"]  # type: ignore[assignment]
    checklist.quality.benchmark_required = quality["harness_evaluation_required"]  # type: ignore[assignment]

    workflow = copied["workflow"]
    assert isinstance(workflow, Mapping)
    checklist.workflow.type = workflow["seed_mode"]  # type: ignore[assignment]
    if workflow["runtime_loop"] != "checklist_rounds":
        raise PreflightDraftError("baseline workflow.runtime_loop must be 'checklist_rounds'")
    seed_overrides = workflow["seed_overrides"]
    if not isinstance(seed_overrides, Mapping):
        raise PreflightDraftError("baseline workflow.seed_overrides must be a mapping")
    allowed_seed_keys = {"custom_stages", "skip_stages", "stage_overrides"}
    unknown_seed_keys = set(seed_overrides).difference(allowed_seed_keys)
    if unknown_seed_keys:
        raise PreflightDraftError(f"unknown seed override keys {sorted(unknown_seed_keys)!r}")
    for field_name in allowed_seed_keys:
        if field_name in seed_overrides:
            setattr(checklist.workflow, field_name, deepcopy(seed_overrides[field_name]))
    return checklist


def _validate_baseline(baseline: PreflightConfigBaseline) -> None:
    if not _CHANGE_ID_RE.fullmatch(baseline.change_id):
        raise PreflightDraftError(f"invalid baseline change_id {baseline.change_id!r}")
    if not _UTC_TIMESTAMP_RE.fullmatch(baseline.authorized_at):
        raise PreflightDraftError(f"invalid baseline authorized_at {baseline.authorized_at!r}")
    try:
        datetime.strptime(baseline.authorized_at, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError as exc:
        raise PreflightDraftError(
            f"invalid baseline authorized_at {baseline.authorized_at!r}"
        ) from exc
    if not _HASH_RE.fullmatch(baseline.project_config_hash):
        raise PreflightDraftError(
            "baseline project_config_hash must be 64 lowercase hexadecimal characters"
        )


def _preflight_candidate_paths(repo_root: Path) -> tuple[tuple[str, Path], ...]:
    """Return deterministic active/archive preflight paths without following links."""
    candidates: list[tuple[str, Path]] = []
    surfaces = (
        ("active", repo_root / ".local" / ".agent" / "active"),
        ("archive", repo_root / ".local" / ".agent" / "archive"),
    )
    for surface, folder in surfaces:
        try:
            if not folder.exists():
                continue
            if folder.is_symlink() or not folder.is_dir():
                raise PreflightDraftError(
                    f"preflight baseline {surface} root is not a safe directory"
                )
            entries = sorted(folder.iterdir(), key=lambda path: path.name)
        except PreflightDraftError:
            raise
        except OSError as exc:
            raise PreflightDraftError(f"preflight baseline {surface} root is unreadable") from exc

        for change_folder in entries:
            try:
                if change_folder.is_symlink():
                    raise PreflightDraftError(
                        f"preflight baseline candidate {surface}/{change_folder.name} "
                        "must not be a symlink"
                    )
                if not change_folder.is_dir():
                    continue
                preflight_path = change_folder / "preflight.md"
                if not preflight_path.exists():
                    continue
                if preflight_path.is_symlink() or not preflight_path.is_file():
                    raise PreflightDraftError(
                        f"preflight baseline candidate {surface}/{change_folder.name}/"
                        "preflight.md is not a safe regular file"
                    )
            except PreflightDraftError:
                raise
            except OSError as exc:
                raise PreflightDraftError(
                    f"preflight baseline candidate {surface}/{change_folder.name} is unreadable"
                ) from exc
            candidates.append((surface, preflight_path))
    return tuple(candidates)


def _validate_candidate_binding(
    *,
    surface: str,
    folder_name: str,
    change_id: str,
) -> None:
    if surface == "active":
        valid = folder_name == change_id
    else:
        prefix = folder_name[:10]
        try:
            datetime.strptime(prefix, "%Y-%m-%d")
        except ValueError:
            valid = False
        else:
            valid = folder_name[10:] == f"-{change_id}"
    if not valid:
        raise PreflightDraftError(
            f"preflight baseline candidate {surface}/{folder_name} is orphaned "
            f"from frontmatter parent {change_id!r}"
        )


def _load_signed_candidate(
    repo_root: Path,
    *,
    surface: str,
    path: Path,
) -> _SignedPreflightCandidate | None:
    relative_path = path.relative_to(repo_root).as_posix()
    try:
        text = path.read_text(encoding="utf-8")
        frontmatter, sections = _extract_preflight_sections(text)
        _frontmatter_shape(frontmatter)
        change_id = frontmatter["parent"]
        assert isinstance(change_id, str)
        _validate_candidate_binding(
            surface=surface,
            folder_name=path.parent.name,
            change_id=change_id,
        )
        _validate_section0(sections.contents[0], frontmatter)
        cards = _parse_stop_cards(sections.contents[1], checklist_ids=None)
        authorized_at = frontmatter["authorized_at"]
        _parse_authorization_records(
            sections.contents[2],
            cards=cards,
            authorized_at=authorized_at,
        )
        _validate_permitted_stops(sections.contents[3])
        if authorized_at is None:
            if (
                frontmatter["project_config_hash"] is not None
                or frontmatter.get("authorization_hash") is not None
            ):
                raise PreflightAuthorizationError(
                    "unsigned preflight retains project or authorization hashes"
                )
            return None

        timestamp = _validate_timestamp(authorized_at, field_name="authorized_at")
        project_hash = frontmatter["project_config_hash"]
        authorization_hash = frontmatter.get("authorization_hash")
        if not isinstance(project_hash, str) or _HASH_RE.fullmatch(project_hash) is None:
            raise PreflightAuthorizationError(
                "signed preflight requires a valid project_config_hash"
            )
        if (
            not isinstance(authorization_hash, str)
            or _HASH_RE.fullmatch(authorization_hash) is None
            or authorization_hash != _authorization_digest(frontmatter, sections)
        ):
            raise PreflightAuthorizationError(
                "signed preflight authorization_hash does not seal Sections 0 through 3"
            )
    except (OSError, UnicodeError, PreflightAuthorizationError) as exc:
        raise PreflightDraftError(
            f"malformed preflight baseline candidate {relative_path}: {exc}"
        ) from exc

    return _SignedPreflightCandidate(
        change_id=change_id,
        authorized_at=timestamp,
        project_config_hash=project_hash,
        relative_path=relative_path,
    )


def discover_preflight_baseline(repo_root: Path) -> PreflightConfigBaseline | None:
    """Discover the current signed Section 0 baseline without filesystem writes.

    The machine-readable mirror supplies configuration values. The newest valid
    signed active/archive preflight supplies authorization provenance. Either
    side without the other is an explicit orphan error; malformed candidates
    are never silently skipped.
    """
    root = Path(repo_root)
    signed = tuple(
        candidate
        for surface, path in _preflight_candidate_paths(root)
        if (candidate := _load_signed_candidate(root, surface=surface, path=path)) is not None
    )
    mirror_path = root / ".local" / "project_config.yaml"
    try:
        mirror_exists = mirror_path.exists()
        if mirror_exists and (mirror_path.is_symlink() or not mirror_path.is_file()):
            raise PreflightDraftError(".local/project_config.yaml must be a safe regular file")
    except PreflightDraftError:
        raise
    except OSError as exc:
        raise PreflightDraftError(".local/project_config.yaml is unreadable") from exc

    if not mirror_exists:
        if signed:
            newest = max(signed, key=lambda item: (item.authorized_at, item.relative_path))
            raise PreflightDraftError(
                "orphaned signed preflight baseline "
                f"{newest.relative_path}: .local/project_config.yaml is missing"
            )
        return None

    try:
        mirror_bytes = mirror_path.read_bytes()
        parsed = yaml.safe_load(mirror_bytes.decode("utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        raise PreflightDraftError(
            ".local/project_config.yaml is unreadable or malformed YAML"
        ) from exc
    if not signed:
        raise PreflightDraftError(
            "orphaned .local/project_config.yaml has no signed active/archive preflight"
        )

    newest = max(signed, key=lambda item: (item.authorized_at, item.relative_path))
    mirror_hash = hashlib.sha256(mirror_bytes).hexdigest()
    if newest.project_config_hash != mirror_hash:
        raise PreflightDraftError(
            "orphaned .local/project_config.yaml does not match newest signed "
            f"preflight {newest.relative_path}"
        )
    config = _normalized_baseline_config(parsed)
    _validate_normalized(config)
    baseline = PreflightConfigBaseline(
        change_id=newest.change_id,
        authorized_at=newest.authorized_at,
        project_config_hash=mirror_hash,
        config=config,
    )
    _validate_baseline(baseline)
    return baseline


def _refresh_reliable_fields(
    resolved: PreDecisionChecklist,
    detected: PreDecisionChecklist,
) -> None:
    previous_mode = resolved.repository.mode
    for section, field_name in _RELIABLE_FIELDS:
        value = getattr(getattr(detected, section), field_name)
        if section == "tech_stack" and not value:
            continue
        setattr(getattr(resolved, section), field_name, deepcopy(value))
    if resolved.repository.mode != previous_mode:
        for field_name in _MODE_FEATURES:
            setattr(
                resolved.repository.features,
                field_name,
                getattr(detected.repository.features, field_name),
            )


def _apply_override(checklist: PreDecisionChecklist, path: str, value: object) -> None:
    if path == "workflow.runtime_loop":
        if value != "checklist_rounds":
            raise PreflightDraftError("workflow.runtime_loop must be 'checklist_rounds'")
        return
    if path == "workflow.seed_overrides":
        if not isinstance(value, Mapping):
            raise PreflightDraftError("workflow.seed_overrides must be a mapping")
        for key in value:
            if key not in {"custom_stages", "skip_stages", "stage_overrides"}:
                raise PreflightDraftError(f"unknown dotted override workflow.seed_overrides.{key}")
        for key, nested_value in value.items():
            setattr(checklist.workflow, key, deepcopy(nested_value))
        return
    if path == "repository.features":
        if not isinstance(value, Mapping):
            raise PreflightDraftError("repository.features must be a mapping")
        for key, enabled in value.items():
            if not hasattr(checklist.repository.features, key):
                raise PreflightDraftError(f"unknown dotted override repository.features.{key}")
            setattr(checklist.repository.features, key, deepcopy(enabled))
        return

    source_path = _TARGET_TO_SOURCE.get(path, path)
    parts = source_path.split(".")
    if len(parts) == 3 and parts[:2] == ["repository", "features"]:
        field_name = parts[2]
        if not hasattr(checklist.repository.features, field_name):
            raise PreflightDraftError(f"unknown dotted override {path!r}")
        setattr(checklist.repository.features, field_name, deepcopy(value))
        return
    if path not in _DECISIONS and path not in _SOURCE_ONLY_OVERRIDE_PATHS:
        raise PreflightDraftError(f"unknown dotted override {path!r}")
    if len(parts) != 2 or not hasattr(checklist, parts[0]):
        raise PreflightDraftError(f"unknown dotted override {path!r}")
    section = getattr(checklist, parts[0])
    if not hasattr(section, parts[1]):
        raise PreflightDraftError(f"unknown dotted override {path!r}")
    if source_path == "repository.mode":
        value = str(value).replace("_", "-")
    setattr(section, parts[1], deepcopy(value))


def _validate_normalized(config: Mapping[str, object]) -> None:
    repository = config["repository"]
    quality = config["quality"]
    workflow = config["workflow"]
    assert isinstance(repository, Mapping)
    assert isinstance(quality, Mapping)
    assert isinstance(workflow, Mapping)
    if repository["mode"] not in {"local", "github", "gitlab", "other_git"}:
        raise PreflightDraftError(f"unsupported repository.mode {repository['mode']!r}")
    threshold = quality["quality_score_threshold"]
    if isinstance(threshold, bool) or not isinstance(threshold, (int, float)):
        raise PreflightDraftError("quality.quality_score_threshold must be numeric")
    if not 0 <= threshold <= 10:
        raise PreflightDraftError("quality.quality_score_threshold must be between 0 and 10")
    if quality["gate_profile"] not in {"minimal", "standard", "strict"}:
        raise PreflightDraftError(f"unsupported quality.gate_profile {quality['gate_profile']!r}")
    max_rounds = quality["max_rounds"]
    if isinstance(max_rounds, bool) or not isinstance(max_rounds, int) or max_rounds < 1:
        raise PreflightDraftError("quality.max_rounds must be an integer >= 1")
    if workflow["runtime_loop"] != "checklist_rounds":
        raise PreflightDraftError("workflow.runtime_loop must be 'checklist_rounds'")


def _yaml_inline(value: object) -> str:
    rendered = yaml.safe_dump(
        value,
        allow_unicode=True,
        default_flow_style=True,
        sort_keys=False,
        width=10_000,
    ).strip()
    return rendered.removesuffix("\n...")


def _render_full(config: Mapping[str, object]) -> str:
    lines: list[str] = []
    for section, heading, field_names in _SECTIONS:
        values = config[section]
        assert isinstance(values, Mapping)
        lines.append(heading)
        for field_name in field_names:
            path = f"{section}.{field_name}"
            lines.append(
                f"- {field_name}: {_yaml_inline(values[field_name])} | "
                f'decision: {_DECISIONS[path]} | source: "auto-detect/default"'
            )
        lines.append("")
    return "\n".join(lines).rstrip()


def _changed_fields(
    previous: Mapping[str, object],
    proposed: Mapping[str, object],
) -> tuple[str, ...]:
    changed: list[str] = []
    for section, _, field_names in _SECTIONS:
        previous_values = previous[section]
        proposed_values = proposed[section]
        assert isinstance(previous_values, Mapping)
        assert isinstance(proposed_values, Mapping)
        for field_name in field_names:
            if previous_values[field_name] != proposed_values[field_name]:
                changed.append(f"{section}.{field_name}")
    return tuple(changed)


def _render_delta(
    previous: Mapping[str, object],
    proposed: Mapping[str, object],
    changed_fields: tuple[str, ...],
) -> str:
    changed_set = set(changed_fields)
    lines: list[str] = []
    for section, heading, field_names in _SECTIONS:
        section_fields = [
            field_name for field_name in field_names if f"{section}.{field_name}" in changed_set
        ]
        if not section_fields:
            continue
        previous_values = previous[section]
        proposed_values = proposed[section]
        assert isinstance(previous_values, Mapping)
        assert isinstance(proposed_values, Mapping)
        lines.append(heading)
        for field_name in section_fields:
            lines.append(
                f"- Δ {field_name}: previous={_yaml_inline(previous_values[field_name])} | "
                f"proposed={_yaml_inline(proposed_values[field_name])}"
            )
        lines.append("")
    return "\n".join(lines).rstrip()


def draft_preflight_section0(
    repo_root: Path,
    *,
    project_name: str | None = None,
    project_purpose: str | None = None,
    seed_mode: str | None = None,
    inherited: PreflightConfigBaseline | None = None,
    overrides: Mapping[str, object] | None = None,
) -> PreflightSection0Draft:
    """Draft Section 0 without signing, mirror creation, or filesystem writes."""
    detected = auto_detect(repo_root)
    if inherited is None:
        resolved = detected
        previous: Mapping[str, object] | None = None
    else:
        _validate_baseline(inherited)
        previous = _normalized_baseline_config(inherited.config)
        _validate_normalized(previous)
        resolved = _baseline_to_checklist(previous)
        _refresh_reliable_fields(resolved, detected)

    named_values = {
        "project.name": project_name,
        "project.purpose": project_purpose,
        "workflow.type": seed_mode,
    }
    for path, value in named_values.items():
        if value is not None:
            _apply_override(resolved, path, value)
    if overrides is not None:
        if not isinstance(overrides, Mapping):
            raise PreflightDraftError("overrides must be a dotted-path mapping")
        for path, value in overrides.items():
            if not isinstance(path, str) or "." not in path:
                raise PreflightDraftError(f"invalid dotted override {path!r}")
            _apply_override(resolved, path, value)

    try:
        findings = tuple(validate_consistency(resolved))
    except (TypeError, ValueError) as exc:
        raise PreflightDraftError(f"invalid override value: {exc}") from exc
    proposed = _normalized_config(resolved)
    _validate_normalized(proposed)

    if previous is None:
        return PreflightSection0Draft(
            mode="draft",
            markdown=_render_full(proposed),
            config=deepcopy(proposed),
            validation_findings=findings,
            changed_fields=(),
            config_inherited_from=None,
            project_config_hash=None,
        )

    changed = _changed_fields(previous, proposed)
    if not changed:
        assert inherited is not None
        markdown = (
            f"- Inherited from {inherited.change_id} (signed {inherited.authorized_at}); "
            f"config hash {inherited.project_config_hash} matches; no drift."
        )
        return PreflightSection0Draft(
            mode="inherited",
            markdown=markdown,
            config=deepcopy(proposed),
            validation_findings=findings,
            changed_fields=(),
            config_inherited_from=inherited.change_id,
            project_config_hash=inherited.project_config_hash,
        )

    assert inherited is not None
    return PreflightSection0Draft(
        mode="delta",
        markdown=_render_delta(previous, proposed, changed),
        config=deepcopy(proposed),
        validation_findings=findings,
        changed_fields=changed,
        config_inherited_from=inherited.change_id,
        project_config_hash=None,
    )


def sign_preflight(
    repo_root: Path,
    change_id: str,
    *,
    draft: PreflightSection0Draft,
    authorizations: Sequence[PreflightAuthorization],
    authorized_at: str,
) -> PreflightSignature:
    """Validate and atomically commit a preflight signature and config mirror.

    The mirror is replaced first and ``preflight.md`` second, making the signed
    preflight the transaction's commit marker. Any ordinary failure before that
    second replacement restores the prior mirror bytes.
    """
    folder = _active_checklist_folder(repo_root, change_id)
    preflight_path = folder / "preflight.md"
    checklist_path = folder / "checklist.md"
    mirror_path = repo_root / ".local" / "project_config.yaml"

    try:
        original_preflight = preflight_path.read_bytes()
        original_text = original_preflight.decode("utf-8")
        checklist_text = checklist_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise PreflightAuthorizationError(
            f"active change {change_id!r} preflight/checklist is unreadable"
        ) from exc

    frontmatter, sections = _extract_preflight_sections(original_text)
    _frontmatter_shape(frontmatter, change_id=change_id)
    if frontmatter["authorized_at"] is not None:
        raise PreflightAuthorizationError("preflight is already signed")
    if (
        frontmatter["project_config_hash"] is not None
        or frontmatter.get("authorization_hash") is not None
    ):
        raise PreflightAuthorizationError(
            "unsigned preflight must not retain project or authorization hashes"
        )
    if sections.contents[0] != draft.markdown:
        raise PreflightAuthorizationError(
            "current Section 0 does not equal the supplied draft; redraft before signing"
        )
    blocking = [finding for finding in draft.validation_findings if finding.severity == "error"]
    if blocking:
        messages = "; ".join(f"[{item.rule}] {item.message}" for item in blocking)
        raise PreflightAuthorizationError(
            f"Section 0 draft has blocking validation findings: {messages}"
        )
    timestamp = _validate_timestamp(authorized_at, field_name="authorized_at")

    try:
        checklist = parse_checklist(checklist_text, filename="checklist.md")
    except RoundArtifactParseError as exc:
        raise PreflightAuthorizationError(
            f"checklist cannot authorize stop-card references: {exc.message}"
        ) from exc
    checklist_ids = {item.item_id for item in checklist.items}
    cards = _parse_stop_cards(sections.contents[1], checklist_ids=checklist_ids)
    _parse_authorization_records(
        sections.contents[2],
        cards=cards,
        authorized_at=None,
    )
    _validate_permitted_stops(sections.contents[3])

    authorization_by_id: dict[str, PreflightAuthorization] = {}
    for authorization in authorizations:
        if not isinstance(authorization, PreflightAuthorization):
            raise PreflightAuthorizationError(
                "authorizations must contain PreflightAuthorization values"
            )
        if (
            not isinstance(authorization.card_id, str)
            or _CARD_ID_RE.fullmatch(authorization.card_id) is None
            or authorization.card_id in authorization_by_id
        ):
            raise PreflightAuthorizationError(
                f"authorization id {authorization.card_id!r} is invalid or duplicated"
            )
        if (
            not isinstance(authorization.disposition, str)
            or authorization.disposition not in _DISPOSITIONS
        ):
            raise PreflightAuthorizationError(
                f"authorization {authorization.card_id!r} has an invalid disposition"
            )
        if (
            not isinstance(authorization.quote, str)
            or not authorization.quote.strip()
            or "\n" in authorization.quote
            or "\r" in authorization.quote
        ):
            raise PreflightAuthorizationError(
                f"authorization {authorization.card_id!r} quote must be non-empty and single-line"
            )
        authorization_by_id[authorization.card_id] = authorization

    card_by_id = {card.card_id: card for card in cards}
    if set(authorization_by_id) != set(card_by_id):
        raise PreflightAuthorizationError(
            "authorizations must contain exactly one entry per Section 1 card"
        )
    for card_id, authorization in authorization_by_id.items():
        if authorization.disposition != card_by_id[card_id].disposition:
            raise PreflightAuthorizationError(
                f"authorization {card_id!r} disposition does not match its Section 1 card"
            )

    if draft.mode == "inherited":
        if (
            draft.project_config_hash is None
            or _HASH_RE.fullmatch(draft.project_config_hash) is None
        ):
            raise PreflightAuthorizationError(
                "inherited draft must carry a valid project_config_hash"
            )
        try:
            mirror_bytes = mirror_path.read_bytes()
        except OSError as exc:
            raise PreflightAuthorizationError(
                "inherited draft requires the existing project_config.yaml mirror"
            ) from exc
        mirror_hash = hashlib.sha256(mirror_bytes).hexdigest()
        if mirror_hash != draft.project_config_hash:
            raise PreflightAuthorizationError(
                "inherited draft hash does not match existing mirror bytes"
            )
    else:
        mirror_bytes = _deterministic_mirror_bytes(draft.config)
        mirror_hash = hashlib.sha256(mirror_bytes).hexdigest()

    try:
        parsed_mirror = yaml.safe_load(mirror_bytes.decode("utf-8"))
    except (UnicodeError, yaml.YAMLError) as exc:
        raise PreflightAuthorizationError("project configuration mirror is invalid YAML") from exc
    if parsed_mirror != deepcopy(dict(draft.config)):
        raise PreflightAuthorizationError(
            "project configuration mirror does not equal the normalized Section 0 config"
        )

    prospective_frontmatter = dict(frontmatter)
    prospective_frontmatter["config_inherited_from"] = draft.config_inherited_from
    prospective_frontmatter["project_config_hash"] = mirror_hash
    section0_state = _validate_section0(
        sections.contents[0],
        prospective_frontmatter,
        expected_mode=draft.mode,
    )
    if section0_state.config is not None and section0_state.config != draft.config:
        raise PreflightAuthorizationError(
            "full Section 0 values do not equal the normalized draft configuration"
        )

    authorization_lines = [
        f"- {card.card_id}: {card.disposition} at {timestamp} — "
        f"{json.dumps(authorization_by_id[card.card_id].quote, ensure_ascii=False)}"
        for card in cards
    ]
    signed_sections = sections.with_section(2, "\n".join(authorization_lines))
    signed_frontmatter = dict(prospective_frontmatter)
    signed_frontmatter["authorized_at"] = timestamp
    signed_frontmatter["authorization_hash"] = _authorization_digest(
        signed_frontmatter,
        signed_sections,
    )
    signed_bytes = _render_preflight(signed_frontmatter, signed_sections)

    final_frontmatter, final_sections = _extract_preflight_sections(signed_bytes.decode("utf-8"))
    _frontmatter_shape(final_frontmatter, change_id=change_id)
    _validate_section0(
        final_sections.contents[0],
        final_frontmatter,
        expected_mode=draft.mode,
    )
    final_cards = _parse_stop_cards(
        final_sections.contents[1],
        checklist_ids=checklist_ids,
    )
    _parse_authorization_records(
        final_sections.contents[2],
        cards=final_cards,
        authorized_at=timestamp,
    )
    _validate_permitted_stops(final_sections.contents[3])
    authorization_hash = final_frontmatter.get("authorization_hash")
    if (
        not isinstance(authorization_hash, str)
        or _HASH_RE.fullmatch(authorization_hash) is None
        or authorization_hash != _authorization_digest(final_frontmatter, final_sections)
    ):
        raise PreflightAuthorizationError("rendered preflight authorization seal is invalid")

    prior_mirror: bytes | None
    try:
        prior_mirror = mirror_path.read_bytes() if mirror_path.exists() else None
    except OSError as exc:
        raise PreflightAuthorizationError("existing mirror cannot be read for rollback") from exc

    mirror_temp: Path | None = None
    preflight_temp: Path | None = None
    rollback_temp: Path | None = None
    mirror_replaced = False
    preflight_replaced = False
    try:
        mirror_temp = _stage_adjacent(mirror_path, mirror_bytes)
        preflight_temp = _stage_adjacent(preflight_path, signed_bytes)
        if prior_mirror is not None:
            rollback_temp = _stage_adjacent(mirror_path, prior_mirror)

        if preflight_path.read_bytes() != original_preflight:
            raise PreflightAuthorizationError(
                "preflight changed concurrently before authorization commit"
            )
        os.replace(mirror_temp, mirror_path)
        mirror_temp = None
        mirror_replaced = True
        os.replace(preflight_temp, preflight_path)
        preflight_temp = None
        preflight_replaced = True
    except Exception as exc:
        rollback_error: Exception | None = None
        if mirror_replaced and not preflight_replaced:
            try:
                if prior_mirror is None:
                    mirror_path.unlink(missing_ok=True)
                else:
                    assert rollback_temp is not None
                    os.replace(rollback_temp, mirror_path)
                    rollback_temp = None
            except Exception as restore_exc:  # pragma: no cover - catastrophic filesystem failure
                rollback_error = restore_exc
        if rollback_error is not None:
            raise PreflightAuthorizationError(
                f"authorization failed and mirror rollback also failed: {rollback_error}"
            ) from exc
        if isinstance(exc, PreflightAuthorizationError):
            raise
        raise PreflightAuthorizationError(f"authorization transaction failed: {exc}") from exc
    finally:
        for temporary in (mirror_temp, preflight_temp, rollback_temp):
            if temporary is not None:
                temporary.unlink(missing_ok=True)

    assert preflight_replaced
    return PreflightSignature(
        authorized_at=timestamp,
        project_config_hash=mirror_hash,
        authorization_hash=authorization_hash,
        preflight_path=preflight_path,
        mirror_path=mirror_path,
    )


def invalidate_preflight(repo_root: Path, change_id: str) -> bool:
    """Atomically clear a signed preflight's authorization fields.

    The body, snapshot metadata, inheritance provenance, and config mirror are
    preserved. ``False`` is returned without a write when already unsigned.
    """
    folder = _active_checklist_folder(repo_root, change_id)
    preflight_path = folder / "preflight.md"
    try:
        original = preflight_path.read_bytes()
        text = original.decode("utf-8")
    except (OSError, UnicodeError) as exc:
        raise PreflightAuthorizationError("preflight.md is unreadable") from exc

    frontmatter, _sections = _extract_preflight_sections(text)
    _frontmatter_shape(frontmatter, change_id=change_id)
    if frontmatter["authorized_at"] is None:
        return False

    invalidated = dict(frontmatter)
    invalidated["authorized_at"] = None
    invalidated["project_config_hash"] = None
    invalidated["authorization_hash"] = None
    invalidated_bytes = _replace_frontmatter_bytes(original, invalidated)
    try:
        parsed, _ = _extract_preflight_sections(invalidated_bytes.decode("utf-8"))
        _frontmatter_shape(parsed, change_id=change_id)
    except (UnicodeError, PreflightAuthorizationError) as exc:
        raise PreflightAuthorizationError("invalidated preflight failed validation") from exc

    temporary: Path | None = None
    try:
        temporary = _stage_adjacent(preflight_path, invalidated_bytes)
        if preflight_path.read_bytes() != original:
            raise PreflightAuthorizationError(
                "preflight changed concurrently before invalidation commit"
            )
        os.replace(temporary, preflight_path)
        temporary = None
    except Exception as exc:
        if isinstance(exc, PreflightAuthorizationError):
            raise
        raise PreflightAuthorizationError(f"preflight invalidation failed: {exc}") from exc
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return True
