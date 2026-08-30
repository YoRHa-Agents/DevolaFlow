"""Human-input-write lifecycle hook — ``check_human_input_append_only``.

Designed in ``.local/research/v14.0.0_design.md`` §3c ("Immutability
mechanism") as the named, proposed enforcement surface for the durable
``.local/human/input/`` zone (``requirements.md`` / ``constitution.md``).

Contract: a ``### REQ-*`` block is frozen **iff** its ``Lifecycle`` field is
``RATIFIED`` (constitution principle blocks are frozen iff the file carries a
``**Ratified**`` stamp). Once frozen, a block MUST NOT be edited or removed
in place — a change MUST instead APPEND a dated
``input/amendments/<YYYY-MM-DD>-<slug>.md`` AND bump the file's ``**Version**``
stamp (S-9 append discipline, reused — NOT a new Soul rule). The trigger is
RATIFIED-ness, NOT the orthogonal ``Status`` enum (design finding F-1), so
this hook never inspects ``Status``; a ``Lifecycle: DRAFT`` block is exempt.

Mirrors the design shape of
:mod:`devolaflow.lifecycle.check_envelope_append_only` (S-9) +
:mod:`devolaflow.lifecycle.check_file_ownership` (S-8): a uniform
``(payload, *, strict=False) -> HookResult`` signature, permissive default
(WARNING via the lifecycle logger), strict mode re-raises the top-severity
:class:`HookViolation` (``blocker`` for in-place edits of ratified blocks,
``error`` for incomplete amendments + payload-shape problems).

Payload contract (a prior↔proposed diff of ONE input file):

* ``prior`` (``str``, required) — the prior committed text of the file.
* ``proposed`` (``str``, required) — the proposed new text of the file.
* ``amendment_added`` (``bool``, optional, default ``False``) — whether a new
  ``input/amendments/<date>-<slug>.md`` is part of the same change.
* ``path`` (``str``, optional) — file label used in violation messages.

NOTE on registration: since v15.0.0 (G-038 flip 4) this hook IS wired into
``lifecycle.DEFAULT_EVENTS`` as the canonical default handler for the
``check_human_input_write`` event (position 15 after v22 re-numbering).
The wiring is inert for non-callers — the event fires only when a caller
dispatches ``run_hooks("check_human_input_write", payload)`` — and the
hook's own ``strict=False`` permissive default is unchanged (callers opt
into the raise with ``strict=True``; ``run_hooks`` applies its own strict
policy at aggregate time). Direct invocation (like
``tests/test_human_input_immutability.py``) keeps working unchanged.
"""

from __future__ import annotations

import re
from typing import Any

from devolaflow.lifecycle.dispatcher import HookResult, HookViolation, finalize

EVENT = "check_human_input_write"

_REQ_HEADING_RE = re.compile(r"^###\s+(REQ-[A-Z0-9]+-\d+)\b.*$")
_PRINCIPLE_HEADING_RE = re.compile(r"^##\s+(Principle\b.*?)\s*$")
_ANY_HEADING_RE = re.compile(r"^#{1,6}\s+.+$")
_VERSION_RE = re.compile(r"\*\*Version\*\*\s*:\s*([0-9]+\.[0-9]+\.[0-9]+)", re.IGNORECASE)


def _version_stamp(text: str) -> str | None:
    """Return the ``**Version**: X.Y.Z`` semver stamp, or ``None`` if absent."""
    match = _VERSION_RE.search(text)
    return match.group(1) if match else None


def _block_is_ratified_req(block_text: str) -> bool:
    """True if a ``### REQ-*`` block body carries ``Lifecycle: RATIFIED``.

    Keyed on the ``Lifecycle`` field (design F-1) — the ``Status`` field is
    never consulted, so a ``RATIFIED`` REQ with ``Status: Pending`` is still
    frozen.
    """
    return any("Lifecycle" in line and "RATIFIED" in line for line in block_text.splitlines())


def _normalise_block(block_text: str) -> str:
    """Canonical comparison form for a block: drop the version footer + trailers.

    The per-file ``**Version**`` stamp can immediately follow a ratified block
    (design §8a worked example), so a pure version bump would otherwise look
    like an in-place edit. Stripping ``**Version**`` lines makes a footer-only
    change a no-op for block comparison while the bump is still detected
    globally by :func:`_version_stamp`.
    """
    kept = [line.rstrip() for line in block_text.splitlines() if "**Version**" not in line]
    while kept and not kept[-1].strip():
        kept.pop()
    return "\n".join(kept)


def _extract_blocks(text: str) -> tuple[dict[str, str], set[str]]:
    """Return ``(blocks, ratified_keys)`` for *text*.

    ``blocks`` maps a stable key (the REQ-ID for ``### REQ-*`` blocks, a
    ``Principle:<heading>`` key for ``## Principle`` blocks) to the block's
    verbatim text (heading line through the line before the next heading).
    ``ratified_keys`` is the subset of keys that are frozen in *text*:
    RATIFIED REQ blocks, plus every principle block when the file carries a
    ``**Ratified**`` stamp.
    """
    lines = text.splitlines()
    file_ratified = any("**Ratified**" in line for line in lines)

    heading_positions = [idx for idx, line in enumerate(lines) if _ANY_HEADING_RE.match(line)]
    heading_positions.append(len(lines))

    blocks: dict[str, str] = {}
    ratified: set[str] = set()

    for pos in range(len(heading_positions) - 1):
        start = heading_positions[pos]
        stop = heading_positions[pos + 1]
        heading_line = lines[start]
        block_text = "\n".join(lines[start:stop])

        req_match = _REQ_HEADING_RE.match(heading_line)
        if req_match:
            key = req_match.group(1)
            blocks[key] = block_text
            if _block_is_ratified_req(block_text):
                ratified.add(key)
            continue

        principle_match = _PRINCIPLE_HEADING_RE.match(heading_line)
        if principle_match:
            key = f"Principle:{principle_match.group(1).strip()}"
            blocks[key] = block_text
            if file_ratified:
                ratified.add(key)

    return blocks, ratified


def _collect_violations(payload: dict[str, Any]) -> list[HookViolation]:
    """Collect all :class:`HookViolation` instances for *payload*."""
    if not isinstance(payload, dict):
        return [
            HookViolation(
                code="CHI010",
                message="human-input-write payload is not a mapping",
                severity="error",
                context={"payload_type": type(payload).__name__},
            )
        ]

    prior = payload.get("prior")
    proposed = payload.get("proposed")

    if prior is None or not isinstance(prior, str):
        return [
            HookViolation(
                code="CHI011",
                message="human-input-write payload missing required string field: 'prior'",
                severity="error",
                context={"keys_present": sorted(payload.keys())},
            )
        ]
    if proposed is None or not isinstance(proposed, str):
        return [
            HookViolation(
                code="CHI012",
                message="human-input-write payload missing required string field: 'proposed'",
                severity="error",
                context={"keys_present": sorted(payload.keys())},
            )
        ]

    prior_blocks, prior_ratified = _extract_blocks(prior)
    proposed_blocks, _ = _extract_blocks(proposed)

    amendment_added = bool(payload.get("amendment_added"))
    version_bumped = _version_stamp(prior) != _version_stamp(proposed)
    label = payload.get("path") or ".local/human/input/{requirements,constitution}.md"

    violations: list[HookViolation] = []
    for key in sorted(prior_ratified):
        before = _normalise_block(prior_blocks.get(key, ""))
        proposed_text = proposed_blocks.get(key)
        # A missing key means the ratified block was removed in place (changed);
        # otherwise compare the version-footer-stripped block bodies.
        changed = proposed_text is None or _normalise_block(proposed_text) != before
        if not changed:
            continue

        if not amendment_added:
            violations.append(
                HookViolation(
                    code="CHI001",
                    message=(
                        f"human-input append-only breach: RATIFIED block '{key}' in "
                        f"'{label}' was edited/removed in place — author a new "
                        f"input/amendments/<date>-<slug>.md instead of editing the ratified text"
                    ),
                    severity="blocker",
                    context={"block": key, "path": label, "amendment_added": amendment_added},
                )
            )
        elif not version_bumped:
            violations.append(
                HookViolation(
                    code="CHI002",
                    message=(
                        f"human-input amendment incomplete: RATIFIED block '{key}' in "
                        f"'{label}' changed with a paired amendment but the file's "
                        f"**Version** stamp was not bumped"
                    ),
                    severity="error",
                    context={"block": key, "path": label, "version_bumped": version_bumped},
                )
            )

    return violations


def check_human_input_append_only(
    payload: dict[str, Any],
    *,
    strict: bool = False,
) -> HookResult:
    """Flag in-place edits of RATIFIED ``.local/human/input/`` blocks.

    Compares *payload['prior']* and *payload['proposed']* text of a single
    human-input file. A RATIFIED ``### REQ-*`` block (or, for the
    constitution, any principle block when the file is ratified) that changed
    or was removed without a paired amendment yields a ``blocker`` CHI001
    violation; a change paired with an amendment but no ``**Version**`` bump
    yields an ``error`` CHI002. A ``Lifecycle: DRAFT`` block is exempt (the
    trigger is RATIFIED-ness, not ``Status`` — design finding F-1).

    Permissive default emits a WARNING and returns a populated
    :class:`HookResult`. Strict mode raises the top-severity
    :class:`HookViolation`.

    Enforces the design §3c append-only discipline by reusing Soul Rule
    **S-9** (append, never edit-in-place) — no new Soul rule is introduced.
    """
    violations = _collect_violations(payload)
    return finalize(EVENT, violations, strict=strict)


__all__ = ["EVENT", "check_human_input_append_only"]
