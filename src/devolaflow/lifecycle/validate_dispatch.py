"""Pre-dispatch lifecycle hook — ``validate_dispatch``.

Documented in ``workflow-system/agent/SKILL.md`` §"Lifecycle Hooks".
Bound to the ``pre_dispatch`` event by :mod:`devolaflow.lifecycle.__init__`.

Contract: a dispatch payload (lean format per
``schemas/lean-dispatch.yaml``) MUST carry at least one **testable**
acceptance criterion before being released to an L3 task agent. The
hook recognises both the lean ``accept`` key and the verbose
``acceptance_criteria`` key for backward compatibility.

v14.3.0 — when the payload carries the OPT-IN ``acceptance_criteria_v2``
block (canonical_order position 15 per
``schemas/lean-dispatch.yaml#lean_format_spec.acceptance_criteria_v2``),
the hook additionally validates its STRUCTURE (permissive default):

* the block must be a non-empty list (VD005);
* each entry must be a mapping carrying a non-empty ``id``, a non-empty
  criterion text (the schema-canonical ``description`` field; the
  ``criterion`` spelling is also accepted), and a ``verification_type``
  in ``{"test", "metric", "manual"}`` (VD006);
* ``verification_type == "test"`` entries must carry a non-empty
  ``verification_cmd`` (VD007 — downstream
  ``gate.scorer.evaluate_acceptance_criteria_v2`` cannot run a test
  criterion without one);
* entry ids must be unique (VD008 — duplicates raise ``ValueError`` in
  the downstream evaluator).

Payloads WITHOUT ``acceptance_criteria_v2`` see byte-identical
behaviour to v14.2.x (the block is OPT-IN per the v8.0.0 P-10 schema).

Permissive default — emits a WARNING via the lifecycle logger and
returns a :class:`HookResult` with the violations attached. Strict mode
re-raises the top-severity :class:`HookViolation`.
"""

from __future__ import annotations

from typing import Any

from devolaflow.agent_workspace.layers import (
    CURRENT_HANDOFF_SCHEMA_VERSION,
    LEGACY_HANDOFF_SCHEMA_VERSION,
    normalize_hdr_layer,
)
from devolaflow.lifecycle.dispatcher import HookResult, HookViolation, finalize
from devolaflow.lifecycle.preflight_authorization import (
    collect_preflight_authorization_violations,
)

EVENT = "pre_dispatch"

# Tokens that are explicitly NOT testable acceptance criteria. Lower-cased
# verbatim form is checked against ``criterion.strip().lower()``.
_NON_TESTABLE_TOKENS: frozenset[str] = frozenset(
    {
        "",
        "tbd",
        "to be determined",
        "to be defined",
        "todo",
        "todo:",
        "n/a",
        "na",
        "various",
        "see above",
        "see below",
        "see design",
        "(none)",
    }
)


def _is_testable(criterion: object) -> bool:
    """Return True iff *criterion* is a non-trivial testable string.

    A criterion is testable when it is a non-empty string whose stripped
    lower-case form is not in :data:`_NON_TESTABLE_TOKENS` AND has at
    least 4 characters of substantive text. The 4-char floor catches
    placeholders like "ok" / "yes" that slip past the explicit deny set.
    """
    if not isinstance(criterion, str):
        return False
    stripped = criterion.strip()
    if len(stripped) < 4:
        return False
    return stripped.lower() not in _NON_TESTABLE_TOKENS


def _collect_violations(payload: dict[str, Any]) -> list[HookViolation]:
    """Collect all :class:`HookViolation` instances for *payload*.

    Separated from :func:`validate_dispatch` so :func:`run_hooks` can
    invoke this directly without the wrapper's logging/strict logic.

    v14.3.0 — composes the legacy ``accept`` checks with the OPT-IN
    ``acceptance_criteria_v2`` structural checks. Payloads without the
    AC-v2 block produce a byte-identical violation list to v14.2.x.
    """
    if not isinstance(payload, dict):
        return [
            HookViolation(
                code="VD001",
                message="dispatch payload is not a mapping",
                severity="error",
                context={"payload_type": type(payload).__name__},
            )
        ]

    violations = _collect_accept_violations(payload)
    violations.extend(_collect_ac_v2_violations(payload))
    violations.extend(_collect_hdr_layer_violations(payload))
    violations.extend(collect_preflight_authorization_violations(payload))
    return violations


def _collect_accept_violations(payload: dict[str, Any]) -> list[HookViolation]:
    """Legacy ``accept`` / ``acceptance_criteria`` checks (pre-v14.3.0 body)."""
    accept_value = payload.get("accept")
    if accept_value is None:
        accept_value = payload.get("acceptance_criteria")

    if accept_value is None:
        return [
            HookViolation(
                code="VD002",
                message=(
                    "dispatch payload missing required field: 'accept' (or 'acceptance_criteria')"
                ),
                severity="blocker",
                context={"keys_present": sorted(payload.keys())},
            )
        ]

    if not isinstance(accept_value, list):
        return [
            HookViolation(
                code="VD003",
                message="'accept' field must be a list of acceptance criteria",
                severity="error",
                context={"accept_type": type(accept_value).__name__},
            )
        ]

    testable = [c for c in accept_value if _is_testable(c)]
    if not testable:
        return [
            HookViolation(
                code="VD004",
                message=(
                    "dispatch must include ≥1 testable acceptance criterion "
                    "(non-empty string ≥4 chars, not in placeholder set)"
                ),
                severity="blocker",
                context={
                    "received_count": len(accept_value),
                    "received_values": list(accept_value),
                },
            )
        ]

    return []


def _collect_hdr_layer_violations(payload: dict[str, Any]) -> list[HookViolation]:
    """Validate ``hdr.layer`` without mutating the dispatch payload.

    ``stage`` is the only retired header token and therefore carries
    unambiguous legacy-v1 provenance.  Current ``project``/``wave`` values
    are validated as v16.  The normalizer emits the once-per-context/token
    legacy warning required by S-5.
    """

    hdr = payload.get("hdr")
    if not isinstance(hdr, dict) or "layer" not in hdr:
        return []

    token = hdr["layer"]
    schema_version = (
        LEGACY_HANDOFF_SCHEMA_VERSION if token == "stage" else CURRENT_HANDOFF_SCHEMA_VERSION
    )
    try:
        normalize_hdr_layer(
            token,
            schema_version=schema_version,
            context="validate_dispatch.hdr.layer",
        )
    except ValueError as exc:
        return [
            HookViolation(
                code="VD009",
                message=f"invalid hdr.layer value: {exc}",
                severity="error",
                context={"hdr_layer": token},
            )
        ]
    return []


# Allowed values for ``acceptance_criteria_v2[*].verification_type`` —
# verbatim from ``schemas/lean-dispatch.yaml#lean_format_spec.
# acceptance_criteria_v2.per_entry.verification_type``.
_AC_V2_VERIFICATION_TYPES: frozenset[str] = frozenset({"test", "metric", "manual"})


def _is_nonempty_str(value: object) -> bool:
    """True iff *value* is a string with non-whitespace content."""
    return isinstance(value, str) and bool(value.strip())


def _collect_ac_v2_entry_violations(idx: int, item: object) -> list[HookViolation]:
    """Structural checks for ONE ``acceptance_criteria_v2`` entry (v14.3.0)."""
    if not isinstance(item, dict):
        return [
            HookViolation(
                code="VD006",
                message=(f"acceptance_criteria_v2[{idx}] must be a mapping"),
                severity="error",
                context={"index": idx, "entry_type": type(item).__name__},
            )
        ]

    violations: list[HookViolation] = []
    missing: list[str] = []
    if not _is_nonempty_str(item.get("id")):
        missing.append("id")
    # Schema-canonical criterion-text field is `description`; the
    # `criterion` spelling is accepted for the v14.3.0 task contract.
    if not (_is_nonempty_str(item.get("description")) or _is_nonempty_str(item.get("criterion"))):
        missing.append("description/criterion")
    vtype = item.get("verification_type")
    if vtype not in _AC_V2_VERIFICATION_TYPES:
        missing.append("verification_type ∈ {test, metric, manual}")
    if missing:
        violations.append(
            HookViolation(
                code="VD006",
                message=(
                    f"acceptance_criteria_v2[{idx}] missing/invalid required "
                    f"field(s): {', '.join(missing)}"
                ),
                severity="error",
                context={"index": idx, "missing": missing, "entry_keys": sorted(item.keys())},
            )
        )

    if vtype == "test" and not _is_nonempty_str(item.get("verification_cmd")):
        violations.append(
            HookViolation(
                code="VD007",
                message=(
                    f"acceptance_criteria_v2[{idx}] has verification_type='test' "
                    f"but no verification_cmd"
                ),
                severity="error",
                context={"index": idx, "id": item.get("id")},
            )
        )

    return violations


def _collect_ac_v2_violations(payload: dict[str, Any]) -> list[HookViolation]:
    """v14.3.0 structural checks for the OPT-IN ``acceptance_criteria_v2`` block.

    Returns ``[]`` when the key is absent (R5 — payloads without the
    block see byte-identical pre-v14.3.0 behaviour). Permissive/strict
    escalation is centralised on the caller (:func:`finalize` /
    :func:`run_hooks`) like every other check in this module.
    """
    if "acceptance_criteria_v2" not in payload:
        return []

    ac_v2 = payload["acceptance_criteria_v2"]
    if not isinstance(ac_v2, list) or not ac_v2:
        return [
            HookViolation(
                code="VD005",
                message=("'acceptance_criteria_v2' must be a non-empty list when present"),
                severity="error",
                context={"ac_v2_type": type(ac_v2).__name__},
            )
        ]

    violations: list[HookViolation] = []
    seen_ids: set[str] = set()
    for idx, item in enumerate(ac_v2):
        violations.extend(_collect_ac_v2_entry_violations(idx, item))
        if isinstance(item, dict):
            item_id = item.get("id")
            if _is_nonempty_str(item_id):
                if item_id in seen_ids:
                    violations.append(
                        HookViolation(
                            code="VD008",
                            message=(
                                f"acceptance_criteria_v2[{idx}] duplicates id {item_id!r} "
                                f"(ids must be unique)"
                            ),
                            severity="error",
                            context={"index": idx, "id": item_id},
                        )
                    )
                else:
                    seen_ids.add(item_id)

    return violations


def validate_dispatch(payload: dict[str, Any], *, strict: bool = False) -> HookResult:
    """Validate that *payload* carries at least one testable acceptance criterion.

    See module docstring for the contract. Returns a :class:`HookResult`
    in both modes; raises the top :class:`HookViolation` only when
    ``strict=True`` AND a violation was found.
    """
    violations = _collect_violations(payload)
    return finalize(EVENT, violations, strict=strict)


__all__ = ["EVENT", "validate_dispatch"]
