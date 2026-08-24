"""Hash-bound harness tuning proposals with explicit human approval."""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from collections.abc import Mapping, Sequence
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final

import yaml

_PROPOSAL_KEYS: Final[tuple[str, ...]] = (
    "schema_version",
    "proposal_id",
    "cycle",
    "generated_at",
    "source_evaluation",
    "targets",
    "apply_mode",
    "status",
)
_APPROVAL_KEYS: Final[frozenset[str]] = frozenset(
    {
        "schema_version",
        "proposal_id",
        "proposal_sha256",
        "decision",
        "approved_by",
        "approved_at",
        "approved_targets",
    }
)
_EVENT_KEYS: Final[tuple[str, ...]] = (
    "schema_version",
    "event",
    "event_id",
    "ts",
    "proposal_id",
    "proposal_ref",
    "approval_ref",
    "proposal_sha256",
    "target_digest",
)
_AUTO_CONFIG_TARGETS: Final[frozenset[str]] = frozenset(
    {
        "meta.layer_token_budgets.l0_project",
        "meta.layer_token_budgets.l1_wave",
        "meta.layer_token_budgets.l2_task",
        "meta.summary_trigger_pct",
        "meta.recency_decay_factor",
        "meta.complexity_routing.simple",
        "meta.complexity_routing.medium",
        "meta.complexity_routing.complex",
        "meta.complexity_routing.very_complex",
    }
)
_ROUTING_VALUES: Final[frozenset[str]] = frozenset({"budget", "balanced", "quality", "inherit"})
_HEX_64: Final[frozenset[str]] = frozenset("0123456789abcdef")
_DEFAULT_CONFIG = Path("workflow-system/agent/context_profiles.yaml")
_DEFAULT_LEDGER = Path(".local/telemetry/harness.jsonl")


class ProposalError(ValueError):
    """A proposal, approval, target, profile, or apply transaction is invalid."""


def build_proposal(
    evaluation: Mapping[str, Any],
    *,
    cycle: str,
    targets: Sequence[Mapping[str, Any]],
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Build a deterministic proposal; never synthesize an approval decision."""

    if not isinstance(evaluation, Mapping) or not evaluation:
        raise ProposalError("evaluation must be a non-empty mapping")
    if not isinstance(cycle, str) or not cycle.strip():
        raise ProposalError("cycle must be a non-empty string")
    if isinstance(targets, (str, bytes)) or not isinstance(targets, Sequence) or not targets:
        raise ProposalError("targets must be a non-empty sequence of mappings")

    normalized: list[dict[str, Any]] = []
    seen_paths: set[str] = set()
    for index, raw_target in enumerate(targets):
        if not isinstance(raw_target, Mapping):
            raise ProposalError(f"target {index} must be a mapping")
        target = deepcopy(dict(raw_target))
        path = target.get("path")
        if not isinstance(path, str) or not path.strip():
            raise ProposalError(f"target {index}.path must be a non-empty string")
        if path in seen_paths:
            raise ProposalError(f"duplicate target path: {path}")
        seen_paths.add(path)
        value_keys = [
            key for key in ("value", "proposed_value", "to", "new_value") if key in target
        ]
        if len(value_keys) != 1:
            raise ProposalError(
                f"target {path} must contain exactly one proposed value field "
                "(value, proposed_value, to, or new_value)"
            )
        value = target[value_keys[0]]
        if path.startswith("meta.layer_token_budgets."):
            if type(value) is not int or not 0 < value <= 8_000:
                raise ProposalError(f"target {path} must be an integer in [1, 8000]")
        elif path == "meta.summary_trigger_pct":
            if type(value) is not int or not 1 <= value <= 100:
                raise ProposalError(f"target {path} must be an integer in [1, 100]")
        elif path == "meta.recency_decay_factor":
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not 0.0 < float(value) <= 1.0
            ):
                raise ProposalError(f"target {path} must be a number in (0, 1]")
        elif path.startswith("meta.complexity_routing.") and value not in _ROUTING_VALUES:
            raise ProposalError(
                f"target {path} must be one of {', '.join(sorted(_ROUTING_VALUES))}"
            )
        try:
            json.dumps(target, allow_nan=False, sort_keys=True)
        except (TypeError, ValueError) as exc:
            raise ProposalError(f"target {path} must contain canonical JSON values") from exc
        normalized.append(target)

    sorted_targets = sorted(
        normalized,
        key=lambda item: json.dumps(
            item,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ),
    )
    try:
        evaluation_bytes = json.dumps(
            dict(evaluation),
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ProposalError("evaluation must contain canonical JSON values") from exc
    source_evaluation = hashlib.sha256(evaluation_bytes).hexdigest()
    identity = json.dumps(
        {"source_evaluation": source_evaluation, "targets": sorted_targets},
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    timestamp = generated_at or evaluation.get("sampled_at") or datetime.now(UTC).isoformat()
    if not isinstance(timestamp, str) or not timestamp.strip():
        raise ProposalError("generated_at must be a non-empty string")
    try:
        datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ProposalError("generated_at must be an ISO-8601 timestamp") from exc

    return {
        "schema_version": 1,
        "proposal_id": hashlib.sha256(identity).hexdigest(),
        "cycle": cycle,
        "generated_at": timestamp,
        "source_evaluation": source_evaluation,
        "targets": sorted_targets,
        "apply_mode": (
            "AUTO_CONFIG"
            if all(target["path"] in _AUTO_CONFIG_TARGETS for target in sorted_targets)
            else "CHANGE_REQUIRED"
        ),
        "status": "PROPOSED",
    }


def write_proposal(proposal: Mapping[str, Any], path: str | Path) -> Path:
    """Atomically install one immutable proposal without rewriting duplicates."""

    if not isinstance(proposal, Mapping) or set(proposal) != set(_PROPOSAL_KEYS):
        raise ProposalError(f"proposal keys must be exactly {', '.join(_PROPOSAL_KEYS)}")
    ordered = {key: deepcopy(proposal[key]) for key in _PROPOSAL_KEYS}
    if ordered["schema_version"] != 1:
        raise ProposalError("proposal.schema_version must equal 1")
    for field in ("proposal_id", "cycle", "generated_at", "source_evaluation"):
        if not isinstance(ordered[field], str) or not ordered[field].strip():
            raise ProposalError(f"proposal.{field} must be a non-empty string")
    if (
        len(ordered["proposal_id"]) != 64
        or set(ordered["proposal_id"]) - _HEX_64
        or len(ordered["source_evaluation"]) != 64
        or set(ordered["source_evaluation"]) - _HEX_64
    ):
        raise ProposalError("proposal hashes must be lowercase SHA-256 values")
    try:
        datetime.fromisoformat(ordered["generated_at"].replace("Z", "+00:00"))
    except ValueError as exc:
        raise ProposalError("proposal.generated_at must be an ISO-8601 timestamp") from exc
    targets = ordered["targets"]
    if (
        not isinstance(targets, list)
        or not targets
        or any(
            not isinstance(target, dict) or not isinstance(target.get("path"), str)
            for target in targets
        )
    ):
        raise ProposalError("proposal.targets must be a non-empty list of target mappings")
    sorted_targets = sorted(
        targets,
        key=lambda item: json.dumps(
            item,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ),
    )
    if targets != sorted_targets:
        raise ProposalError("proposal.targets must be canonically sorted")
    identity = json.dumps(
        {
            "source_evaluation": ordered["source_evaluation"],
            "targets": sorted_targets,
        },
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    if ordered["proposal_id"] != hashlib.sha256(identity).hexdigest():
        raise ProposalError("proposal_id does not bind source_evaluation and targets")
    expected_mode = (
        "AUTO_CONFIG"
        if all(target["path"] in _AUTO_CONFIG_TARGETS for target in targets)
        else "CHANGE_REQUIRED"
    )
    if ordered["apply_mode"] != expected_mode:
        raise ProposalError(f"proposal.apply_mode must equal {expected_mode}")
    if ordered["status"] != "PROPOSED":
        raise ProposalError("proposal.status must equal PROPOSED")

    try:
        rendered = yaml.safe_dump(
            ordered,
            allow_unicode=True,
            default_flow_style=False,
            sort_keys=False,
        ).encode("utf-8")
    except yaml.YAMLError as exc:
        raise ProposalError(f"proposal cannot be rendered as YAML: {exc}") from exc
    destination = Path(path)
    if destination.exists():
        try:
            existing = destination.read_bytes()
            if existing == rendered:
                return destination
            existing_payload = yaml.safe_load(existing)
        except (OSError, UnicodeError, yaml.YAMLError) as exc:
            raise ProposalError(f"cannot inspect existing proposal {destination}: {exc}") from exc
        if (
            isinstance(existing_payload, dict)
            and existing_payload.get("proposal_id") == ordered["proposal_id"]
            and {key: existing_payload.get(key) for key in _PROPOSAL_KEYS if key != "generated_at"}
            == {key: ordered[key] for key in _PROPOSAL_KEYS if key != "generated_at"}
        ):
            return destination
        raise ProposalError(
            f"immutable proposal already exists with different bytes: {destination}"
        )

    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.",
        suffix=".tmp",
        dir=destination.parent,
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(rendered)
            stream.flush()
            os.fsync(stream.fileno())
        try:
            os.link(temporary, destination)
        except FileExistsError:
            if destination.read_bytes() != rendered:
                raise ProposalError(
                    f"proposal changed concurrently before immutable install: {destination}"
                ) from None
        return destination
    except OSError as exc:
        raise ProposalError(f"cannot atomically write proposal {destination}: {exc}") from exc
    finally:
        temporary.unlink(missing_ok=True)


def validate_approval(
    proposal: Mapping[str, Any] | str | Path,
    approval: Mapping[str, Any] | str | Path,
    *,
    model_profile: Mapping[str, Any] | str | Path | None = None,
) -> dict[str, Any]:
    """Validate a separately authored APPROVE sidecar and optional fold evidence."""

    try:
        if isinstance(proposal, Mapping):
            proposal_payload = dict(proposal)
            proposal_bytes = yaml.safe_dump(
                {key: proposal_payload.get(key) for key in _PROPOSAL_KEYS},
                allow_unicode=True,
                default_flow_style=False,
                sort_keys=False,
            ).encode("utf-8")
        else:
            proposal_bytes = Path(proposal).read_bytes()
            proposal_payload = yaml.safe_load(proposal_bytes)
        if isinstance(approval, Mapping):
            approval_payload = dict(approval)
        else:
            approval_payload = yaml.safe_load(Path(approval).read_bytes())
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        raise ProposalError(f"cannot read proposal approval artifacts: {exc}") from exc

    if not isinstance(proposal_payload, dict) or set(proposal_payload) != set(_PROPOSAL_KEYS):
        raise ProposalError(f"proposal keys must be exactly {', '.join(_PROPOSAL_KEYS)}")
    if not isinstance(approval_payload, dict) or set(approval_payload) != _APPROVAL_KEYS:
        raise ProposalError(
            "approval keys must be exactly "
            + ", ".join(
                (
                    "schema_version",
                    "proposal_id",
                    "proposal_sha256",
                    "decision",
                    "approved_by",
                    "approved_at",
                    "approved_targets",
                )
            )
        )
    if proposal_payload["schema_version"] != 1 or approval_payload["schema_version"] != 1:
        raise ProposalError("proposal and approval schema_version must equal 1")
    if proposal_payload["status"] != "PROPOSED":
        raise ProposalError("only a PROPOSED proposal can be approved")
    proposal_id = proposal_payload["proposal_id"]
    source_evaluation = proposal_payload["source_evaluation"]
    targets = proposal_payload["targets"]
    if (
        not isinstance(proposal_id, str)
        or not isinstance(source_evaluation, str)
        or not re.fullmatch(r"[0-9a-f]{64}", proposal_id)
        or not re.fullmatch(r"[0-9a-f]{64}", source_evaluation)
    ):
        raise ProposalError("proposal hashes must be lowercase SHA-256 values")
    if (
        not isinstance(targets, list)
        or not targets
        or any(
            not isinstance(target, dict) or not isinstance(target.get("path"), str)
            for target in targets
        )
    ):
        raise ProposalError("proposal.targets must be a non-empty list of target mappings")
    try:
        sorted_targets = sorted(
            targets,
            key=lambda item: json.dumps(
                item,
                ensure_ascii=False,
                allow_nan=False,
                sort_keys=True,
                separators=(",", ":"),
            ),
        )
        identity = json.dumps(
            {"source_evaluation": source_evaluation, "targets": targets},
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ProposalError("proposal targets must contain canonical JSON values") from exc
    if targets != sorted_targets:
        raise ProposalError("proposal.targets must be canonically sorted")
    if proposal_id != hashlib.sha256(identity).hexdigest():
        raise ProposalError("proposal_id does not bind source_evaluation and targets")
    expected_mode = (
        "AUTO_CONFIG"
        if all(target["path"] in _AUTO_CONFIG_TARGETS for target in targets)
        else "CHANGE_REQUIRED"
    )
    if proposal_payload["apply_mode"] != expected_mode:
        raise ProposalError(f"proposal.apply_mode must equal {expected_mode}")
    if approval_payload["decision"] != "APPROVE":
        raise ProposalError("approval.decision must be explicitly set to APPROVE")
    if approval_payload["proposal_id"] != proposal_payload["proposal_id"]:
        raise ProposalError("approval proposal_id does not match proposal")
    proposal_sha256 = hashlib.sha256(proposal_bytes).hexdigest()
    if approval_payload["proposal_sha256"] != proposal_sha256:
        raise ProposalError("approval proposal_sha256 does not match immutable proposal bytes")
    for field in ("approved_by", "approved_at"):
        if not isinstance(approval_payload[field], str) or not approval_payload[field].strip():
            raise ProposalError(f"approval.{field} must be a non-empty string")
    try:
        datetime.fromisoformat(approval_payload["approved_at"].replace("Z", "+00:00"))
    except ValueError as exc:
        raise ProposalError("approval.approved_at must be an ISO-8601 timestamp") from exc
    if approval_payload["approved_targets"] != proposal_payload["targets"]:
        raise ProposalError("approval must bind the complete sorted proposal target set")

    fold_targets = [
        target
        for target in proposal_payload["targets"]
        if isinstance(target, dict) and "fold" in str(target.get("path", "")).lower()
    ]
    if fold_targets:
        if model_profile is None:
            raise ProposalError("fold expansion approval requires a same-cycle model profile")
        try:
            if isinstance(model_profile, Mapping):
                profile = dict(model_profile)
            else:
                profile = yaml.safe_load(Path(model_profile).read_text(encoding="utf-8"))
        except (OSError, UnicodeError, yaml.YAMLError) as exc:
            raise ProposalError(f"cannot read fold evidence profile: {exc}") from exc
        if not isinstance(profile, dict):
            raise ProposalError("fold evidence profile must be a YAML mapping")
        if profile.get("cycle") != proposal_payload["cycle"]:
            raise ProposalError("fold evidence profile must match proposal cycle")
        if profile.get("status") != "PASS":
            raise ProposalError("fold evidence profile status must equal PASS")
        if profile.get("guard_compliance") != 1.0 or profile.get("schema_validity") != 1.0:
            raise ProposalError("fold evidence requires perfect guard and schema compliance")
        fold_delta = profile.get("fold_delta")
        if (
            isinstance(fold_delta, bool)
            or not isinstance(fold_delta, (int, float))
            or float(fold_delta) < -0.10
        ):
            raise ProposalError("fold evidence profile fold_delta must be >= -0.10")
    return approval_payload


def apply_approved_proposal(
    proposal_path: str | Path,
    approval_path: str | Path,
    *,
    repo_root: str | Path = ".",
    config_path: str | Path = _DEFAULT_CONFIG,
    ledger_path: str | Path = _DEFAULT_LEDGER,
    model_profile: Mapping[str, Any] | str | Path | None = None,
) -> str:
    """Apply one approved allowlisted config patch and append one audit event."""

    root = Path(repo_root).resolve()
    proposal_file = Path(proposal_path)
    approval_file = Path(approval_path)
    if not proposal_file.is_absolute():
        proposal_file = root / proposal_file
    if not approval_file.is_absolute():
        approval_file = root / approval_file
    validate_approval(proposal_file, approval_file, model_profile=model_profile)
    try:
        proposal_bytes = proposal_file.read_bytes()
        proposal = yaml.safe_load(proposal_bytes)
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        raise ProposalError(f"cannot reload validated proposal: {exc}") from exc
    if proposal["apply_mode"] == "CHANGE_REQUIRED":
        return "CHANGE_REQUIRED"

    config = Path(config_path)
    ledger = Path(ledger_path)
    if not config.is_absolute():
        config = root / config
    if not ledger.is_absolute():
        ledger = root / ledger
    if config.resolve() != (root / _DEFAULT_CONFIG).resolve():
        raise ProposalError(
            "AUTO_CONFIG may patch only workflow-system/agent/context_profiles.yaml"
        )
    try:
        proposal_ref = proposal_file.resolve().relative_to(root).as_posix()
        approval_ref = approval_file.resolve().relative_to(root).as_posix()
    except ValueError as exc:
        raise ProposalError("proposal and approval paths must be inside repo_root") from exc

    target_digest = hashlib.sha256(
        json.dumps(
            proposal["targets"],
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    proposal_sha256 = hashlib.sha256(proposal_bytes).hexdigest()
    event_id = f"proposal_applied:{proposal['proposal_id']}"
    lock = config.with_name(f".{config.name}.proposal.lock")
    lock_descriptor: int | None = None
    temporary: Path | None = None
    rollback: Path | None = None
    config_replaced = False
    try:
        try:
            lock_descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            os.write(lock_descriptor, proposal["proposal_id"].encode("ascii"))
        except FileExistsError as exc:
            raise ProposalError(f"concurrent proposal apply is already active: {lock}") from exc

        if ledger.exists():
            try:
                for line_number, raw_line in enumerate(
                    ledger.read_text(encoding="utf-8").splitlines(), start=1
                ):
                    if not raw_line.strip():
                        raise ProposalError(f"{ledger}:{line_number}: blank JSONL line")
                    record = json.loads(raw_line)
                    if isinstance(record, dict) and record.get("event_id") == event_id:
                        if (
                            record.get("proposal_sha256") == proposal_sha256
                            and record.get("target_digest") == target_digest
                        ):
                            return "ALREADY_APPLIED"
                        raise ProposalError(
                            f"{ledger}:{line_number}: event_id collision with different binding"
                        )
            except (OSError, UnicodeError, json.JSONDecodeError) as exc:
                raise ProposalError(f"cannot inspect proposal audit ledger: {exc}") from exc

        try:
            original_bytes = config.read_bytes()
            config_payload = yaml.safe_load(original_bytes)
        except (OSError, UnicodeError, yaml.YAMLError) as exc:
            raise ProposalError(f"cannot read context profile config {config}: {exc}") from exc
        if not isinstance(config_payload, dict) or not isinstance(config_payload.get("meta"), dict):
            raise ProposalError("context profile config must contain a meta mapping")
        patched = deepcopy(config_payload)
        hard_cap = patched["meta"].get("budget_hard_cap_tokens")
        if type(hard_cap) is not int or hard_cap <= 0:
            raise ProposalError("meta.budget_hard_cap_tokens must be a positive integer")

        for target in proposal["targets"]:
            path = target["path"]
            if path not in _AUTO_CONFIG_TARGETS:
                raise ProposalError(f"target is not AUTO_CONFIG allowlisted: {path}")
            value_key = next(
                (key for key in ("value", "proposed_value", "to", "new_value") if key in target),
                None,
            )
            if value_key is None:
                raise ProposalError(f"target {path} has no proposed value")
            value = target[value_key]
            if path.startswith("meta.layer_token_budgets."):
                if type(value) is not int or not 0 < value <= hard_cap:
                    raise ProposalError(f"target {path} must be an integer in [1, {hard_cap}]")
            elif path == "meta.summary_trigger_pct":
                if type(value) is not int or not 1 <= value <= 100:
                    raise ProposalError(f"target {path} must be an integer in [1, 100]")
            elif path == "meta.recency_decay_factor":
                if (
                    isinstance(value, bool)
                    or not isinstance(value, (int, float))
                    or not 0.0 < float(value) <= 1.0
                ):
                    raise ProposalError(f"target {path} must be a number in (0, 1]")
            elif value not in _ROUTING_VALUES:
                raise ProposalError(
                    f"target {path} must be one of {', '.join(sorted(_ROUTING_VALUES))}"
                )

            parts = path.split(".")
            cursor: Any = patched
            for part in parts[:-1]:
                if not isinstance(cursor, dict) or part not in cursor:
                    raise ProposalError(f"target path does not exist in config: {path}")
                cursor = cursor[part]
            if not isinstance(cursor, dict) or parts[-1] not in cursor:
                raise ProposalError(f"target path does not exist in config: {path}")
            expected_keys = [
                key for key in ("current", "current_value", "from", "old_value") if key in target
            ]
            if len(expected_keys) > 1:
                raise ProposalError(f"target {path} contains multiple current-value fields")
            if expected_keys and cursor[parts[-1]] != target[expected_keys[0]]:
                raise ProposalError(f"post-approval config drift detected for target {path}")
            cursor[parts[-1]] = value

        rendered = yaml.safe_dump(
            patched,
            allow_unicode=True,
            default_flow_style=False,
            sort_keys=False,
        ).encode("utf-8")
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{config.name}.",
            suffix=".tmp",
            dir=config.parent,
        )
        temporary = Path(temporary_name)
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(rendered)
            stream.flush()
            os.fsync(stream.fileno())
        if config.read_bytes() != original_bytes:
            raise ProposalError("context profile config changed concurrently before commit")

        os.replace(temporary, config)
        temporary = None
        config_replaced = True
        event = {
            "schema_version": 1,
            "event": "proposal_applied",
            "event_id": event_id,
            "ts": datetime.now(UTC).isoformat(),
            "proposal_id": proposal["proposal_id"],
            "proposal_ref": proposal_ref,
            "approval_ref": approval_ref,
            "proposal_sha256": proposal_sha256,
            "target_digest": target_digest,
        }
        if tuple(event) != _EVENT_KEYS:
            raise ProposalError("internal proposal event key order drift")
        ledger.parent.mkdir(parents=True, exist_ok=True)
        try:
            with ledger.open("ab") as stream:
                stream.write(
                    (json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n").encode(
                        "utf-8"
                    )
                )
                stream.flush()
                os.fsync(stream.fileno())
        except OSError as exc:
            descriptor, rollback_name = tempfile.mkstemp(
                prefix=f".{config.name}.rollback.",
                suffix=".tmp",
                dir=config.parent,
            )
            rollback = Path(rollback_name)
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(original_bytes)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(rollback, config)
            rollback = None
            config_replaced = False
            raise ProposalError(f"cannot append proposal audit event: {exc}") from exc
        return "APPLIED"
    except OSError as exc:
        raise ProposalError(f"proposal apply transaction failed: {exc}") from exc
    finally:
        if lock_descriptor is not None:
            os.close(lock_descriptor)
            lock.unlink(missing_ok=True)
        if temporary is not None:
            temporary.unlink(missing_ok=True)
        if rollback is not None:
            rollback.unlink(missing_ok=True)
        if config_replaced and not ledger.exists():
            raise ProposalError("proposal config applied without an audit ledger")


__all__ = [
    "ProposalError",
    "apply_approved_proposal",
    "build_proposal",
    "validate_approval",
    "write_proposal",
]
