"""Validated deterministic fixtures shared by harness tests and probes."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any, Final

import yaml

from devolaflow.compressor import DispatchLayoutError, assert_dispatch_layout

MAX_PROBE_FIXTURES: Final[int] = 10

_FIXTURE_KEYS: Final[frozenset[str]] = frozenset(
    {"schema_version", "id", "provenance", "feature_tags", "dispatch", "expected"}
)
_EXPECTED_KEYS: Final[frozenset[str]] = frozenset(
    {
        "guard_ids",
        "report_required_keys",
        "report_forbidden_keys",
        "required_literals",
        "fold_sensitive",
    }
)
_LEGACY_SCORING_KEYS: Final[frozenset[str]] = frozenset(
    {"expected_sections", "unwanted_sections", "quality_thresholds"}
)
_CHANGE_PATH_FIELDS: Final[tuple[str, ...]] = (
    "active_folder",
    "owned_files_ref",
    "acceptance_ref",
)


class HarnessFixtureError(ValueError):
    """A harness fixture or fixture set violates its explicit contract."""


def _error(path: Path | str, message: str) -> HarnessFixtureError:
    return HarnessFixtureError(f"{path}: {message}")


def _string_list(value: object, *, path: Path, field: str, allow_empty: bool = False) -> list[str]:
    if not isinstance(value, list) or (not allow_empty and not value):
        qualifier = "a list" if allow_empty else "a non-empty list"
        raise _error(path, f"{field} must be {qualifier}")
    if any(not isinstance(item, str) or not item.strip() for item in value):
        raise _error(path, f"{field} must contain only non-empty strings")
    if len(set(value)) != len(value):
        raise _error(path, f"{field} must not contain duplicates")
    return value


def _walk_keys(value: object) -> Iterable[str]:
    if isinstance(value, Mapping):
        for key, child in value.items():
            if isinstance(key, str):
                yield key
            yield from _walk_keys(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_keys(child)


def _relative_path(value: object, *, path: Path, field: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise _error(path, f"{field} must be a non-empty repository-relative path")
    candidate = Path(value)
    if candidate.is_absolute() or value.startswith("~"):
        raise _error(path, f"{field} must be repository-relative, got {value!r}")


def _validate_dispatch_paths(dispatch: Mapping[str, Any], *, path: Path) -> None:
    files = dispatch.get("files")
    if not isinstance(files, list) or not files:
        raise _error(path, "dispatch.files must be a non-empty list")
    for index, value in enumerate(files):
        _relative_path(value, path=path, field=f"dispatch.files[{index}]")

    for index, predecessor in enumerate(dispatch.get("pred", [])):
        if not isinstance(predecessor, Mapping):
            raise _error(path, f"dispatch.pred[{index}] must be a mapping")
        _relative_path(
            predecessor.get("ref"),
            path=path,
            field=f"dispatch.pred[{index}].ref",
        )

    for index, repo in enumerate(dispatch.get("repos", [])):
        if not isinstance(repo, Mapping):
            raise _error(path, f"dispatch.repos[{index}] must be a mapping")
        _relative_path(
            repo.get("root_path"),
            path=path,
            field=f"dispatch.repos[{index}].root_path",
        )

    reinforcement = dispatch.get("reinforce")
    if isinstance(reinforcement, Mapping):
        for index, rule in enumerate(reinforcement.get("rules", [])):
            if not isinstance(rule, Mapping):
                raise _error(path, f"dispatch.reinforce.rules[{index}] must be a mapping")
            if "file" in rule:
                _relative_path(
                    rule["file"],
                    path=path,
                    field=f"dispatch.reinforce.rules[{index}].file",
                )

    change_context = dispatch.get("change_context")
    if isinstance(change_context, Mapping):
        for field in _CHANGE_PATH_FIELDS:
            _relative_path(
                change_context.get(field),
                path=path,
                field=f"dispatch.change_context.{field}",
            )


def _validate_acceptance(
    dispatch: Mapping[str, Any],
    expected: Mapping[str, Any],
    *,
    path: Path,
) -> None:
    criteria = dispatch.get("acceptance_criteria_v2")
    if not isinstance(criteria, list) or not criteria:
        raise _error(path, "dispatch.acceptance_criteria_v2 must be a non-empty list")

    criterion_ids: set[str] = set()
    machine_ids: set[str] = set()
    for index, criterion in enumerate(criteria):
        field = f"dispatch.acceptance_criteria_v2[{index}]"
        if not isinstance(criterion, Mapping):
            raise _error(path, f"{field} must be a mapping")
        criterion_id = criterion.get("id")
        description = criterion.get("description")
        verification_type = criterion.get("verification_type")
        if not isinstance(criterion_id, str) or not criterion_id.strip():
            raise _error(path, f"{field}.id must be a non-empty string")
        if criterion_id in criterion_ids:
            raise _error(path, f"{field}.id duplicates {criterion_id!r}")
        criterion_ids.add(criterion_id)
        if not isinstance(description, str) or not description.strip():
            raise _error(path, f"{field}.description must be a non-empty string")
        if verification_type not in {"test", "metric", "manual"}:
            raise _error(path, f"{field}.verification_type is invalid")
        if verification_type in {"test", "metric"}:
            command = criterion.get("verification_cmd")
            if not isinstance(command, str) or not command.strip():
                raise _error(path, f"{field}.verification_cmd must be non-empty")
            machine_ids.add(criterion_id)

    guard_ids = set(_string_list(expected["guard_ids"], path=path, field="expected.guard_ids"))
    if guard_ids != machine_ids:
        raise _error(
            path,
            "expected.guard_ids must exactly match machine-verifiable acceptance criterion ids",
        )


def _validate_fixture(
    payload: object,
    *,
    path: Path,
    require_matching_stem: bool,
) -> dict[str, Any]:
    if not isinstance(payload, dict) or not payload:
        raise _error(path, "fixture root must be a non-empty mapping")

    missing = sorted(_FIXTURE_KEYS - payload.keys())
    extra = sorted(payload.keys() - _FIXTURE_KEYS)
    if missing or extra:
        raise _error(path, f"fixture keys mismatch; missing={missing}, extra={extra}")
    if type(payload["schema_version"]) is not int or payload["schema_version"] != 1:
        raise _error(path, "schema_version must equal 1")

    fixture_id = payload["id"]
    if not isinstance(fixture_id, str) or not fixture_id.strip():
        raise _error(path, "id must be a non-empty string")
    if require_matching_stem and fixture_id != path.stem:
        raise _error(path, f"id {fixture_id!r} must match filename stem {path.stem!r}")

    _string_list(payload["provenance"], path=path, field="provenance")
    _string_list(payload["feature_tags"], path=path, field="feature_tags")

    dispatch = payload["dispatch"]
    if not isinstance(dispatch, dict) or not dispatch:
        raise _error(path, "dispatch must be a non-empty mapping")
    try:
        assert_dispatch_layout(dispatch)
    except DispatchLayoutError as exc:
        raise _error(path, f"dispatch layout is invalid: {exc}") from exc

    expected = payload["expected"]
    if not isinstance(expected, dict):
        raise _error(path, "expected must be a mapping")
    missing_expected = sorted(_EXPECTED_KEYS - expected.keys())
    extra_expected = sorted(expected.keys() - _EXPECTED_KEYS)
    if missing_expected or extra_expected:
        raise _error(
            path,
            f"expected keys mismatch; missing={missing_expected}, extra={extra_expected}",
        )
    for field in ("report_required_keys", "report_forbidden_keys", "required_literals"):
        _string_list(expected[field], path=path, field=f"expected.{field}", allow_empty=True)
    if "quality_score" not in expected["report_forbidden_keys"]:
        raise _error(path, "expected.report_forbidden_keys must include 'quality_score'")
    if type(expected["fold_sensitive"]) is not bool:
        raise _error(path, "expected.fold_sensitive must be a boolean")

    legacy_keys = sorted(set(_walk_keys(payload)) & _LEGACY_SCORING_KEYS)
    if legacy_keys:
        raise _error(path, f"legacy scoring keys are forbidden: {legacy_keys}")

    _validate_dispatch_paths(dispatch, path=path)
    _validate_acceptance(dispatch, expected, path=path)
    return payload


def _read_fixture(path: Path, *, require_matching_stem: bool) -> dict[str, Any]:
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError) as exc:
        raise _error(path, f"cannot read fixture: {exc}") from exc
    except yaml.YAMLError as exc:
        raise _error(path, f"invalid fixture YAML: {exc}") from exc
    return _validate_fixture(payload, path=path, require_matching_stem=require_matching_stem)


def load_harness_fixture(path: str | Path) -> dict[str, Any]:
    """Load and validate one fixture, including its filename-to-id binding."""

    return _read_fixture(Path(path), require_matching_stem=True)


def load_harness_fixtures(directory: str | Path) -> tuple[dict[str, Any], ...]:
    """Load one bounded fixture directory and return fixtures sorted by id."""

    root = Path(directory)
    try:
        if not root.is_dir():
            raise _error(root, "fixture directory does not exist or is not a directory")
        paths = sorted(
            path
            for path in root.iterdir()
            if path.is_file() and path.suffix.lower() in {".yaml", ".yml"}
        )
    except OSError as exc:
        raise _error(root, f"cannot inspect fixture directory: {exc}") from exc

    if not paths:
        raise _error(root, "fixture directory contains no YAML fixtures")
    if len(paths) > MAX_PROBE_FIXTURES:
        raise _error(
            root,
            f"fixture count {len(paths)} exceeds MAX_PROBE_FIXTURES={MAX_PROBE_FIXTURES}",
        )

    loaded: list[tuple[Path, dict[str, Any]]] = []
    seen: dict[str, Path] = {}
    for path in paths:
        fixture = _read_fixture(path, require_matching_stem=False)
        fixture_id = fixture["id"]
        if fixture_id in seen:
            raise _error(
                path,
                f"duplicate fixture id {fixture_id!r}; first declared in {seen[fixture_id]}",
            )
        seen[fixture_id] = path
        loaded.append((path, fixture))

    for path, fixture in loaded:
        if fixture["id"] != path.stem:
            raise _error(path, f"id {fixture['id']!r} must match filename stem {path.stem!r}")
    return tuple(fixture for _, fixture in sorted(loaded, key=lambda item: item[1]["id"]))


def compute_probe_set_hash(fixtures: Iterable[Mapping[str, Any]]) -> str:
    """Hash a fixture set canonically, independent of input and mapping order."""

    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, fixture in enumerate(fixtures):
        if not isinstance(fixture, Mapping):
            raise _error("<fixtures>", f"fixture at index {index} must be a mapping")
        fixture_id = fixture.get("id")
        if not isinstance(fixture_id, str) or not fixture_id.strip():
            raise _error("<fixtures>", f"fixture at index {index} has no non-empty id")
        if fixture_id in seen:
            raise _error("<fixtures>", f"duplicate fixture id {fixture_id!r}")
        seen.add(fixture_id)
        normalized.append(dict(fixture))

    if not normalized:
        raise _error("<fixtures>", "fixture set must not be empty")
    if len(normalized) > MAX_PROBE_FIXTURES:
        raise _error(
            "<fixtures>",
            f"fixture count {len(normalized)} exceeds MAX_PROBE_FIXTURES={MAX_PROBE_FIXTURES}",
        )

    try:
        canonical = json.dumps(
            sorted(normalized, key=lambda fixture: fixture["id"]),
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise _error("<fixtures>", f"fixtures must be canonical JSON values: {exc}") from exc
    return hashlib.sha256(canonical).hexdigest()


__all__ = [
    "MAX_PROBE_FIXTURES",
    "HarnessFixtureError",
    "compute_probe_set_hash",
    "load_harness_fixture",
    "load_harness_fixtures",
]
