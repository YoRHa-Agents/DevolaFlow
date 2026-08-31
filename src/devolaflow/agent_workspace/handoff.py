"""HandoffEnvelope + HandoffStore for ``.local/.agent/handoff/``.

Closes M-005 (Python half) per ``.local/research/v8.3.0_gap_analysis.md`` §2.3.
The schema is declared verbatim in ``schemas/agent-workspace/handoff-envelope.yaml``
(landed v8.2.4 PV-04); this module is the runtime API that consumes it.

Append-only invariant (Rule S-9):

* Once an envelope file exists at sequence N, the next message MUST be
  authored at sequence N+1.
* :meth:`HandoffStore.write_envelope` raises
  :exc:`EnvelopeImmutableError` when the requested ``seq`` already exists
  on disk — never overwrites silently (S-5: no silent failures).
* :meth:`HandoffStore.read_envelopes` returns chronologically-ordered
  envelopes for a given change-id.

Discriminated union (``envelope_kind``):

* ``TaskDispatch``    → ``dispatch`` block present, ``report``/``escalation`` absent
* ``StatusReport``    → ``report`` block present, others absent
* ``EscalationEvent`` → ``escalation`` block present, others absent

The discriminator is enforced at ``write_envelope`` time; reads are
permissive (we trust the schema validator to catch malformed payloads
before they reach disk in the first place — but ``read_envelopes`` does
re-check the discriminator and ``seq`` ↔ filename consistency).

Public API:

* :class:`HandoffEnvelope` — dataclass mirroring the YAML schema.
* :class:`HandoffStore` — write_envelope + read_envelopes.
* :exc:`EnvelopeImmutableError` — raised on seq-collision write.
* :exc:`HandoffStoreError` — generic store-side error.
"""

from __future__ import annotations

import copy
import logging
import os
import re
import tempfile
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

import yaml

from devolaflow.agent_workspace.layers import (
    CURRENT_HANDOFF_SCHEMA_VERSION,
    CURRENT_LAYER_TOKENS,
    normalize_layer,
)

__all__ = [
    "ENVELOPE_DISCRIMINATOR_TO_BLOCK",
    "ENVELOPE_KINDS",
    "EnvelopeImmutableError",
    "HANDOFF_DIR_DEFAULT",
    "HandoffEnvelope",
    "HandoffStore",
    "HandoffStoreError",
    "LAYERS",
]


HANDOFF_DIR_DEFAULT: Final[Path] = Path(".local") / ".agent" / "handoff"

# Backward-compatible export; v16's semantic owner is ``layers.py``.
LAYERS: Final[tuple[str, ...]] = CURRENT_LAYER_TOKENS
ENVELOPE_KINDS: Final[tuple[str, ...]] = ("TaskDispatch", "StatusReport", "EscalationEvent")
ENVELOPE_DISCRIMINATOR_TO_BLOCK: Final[dict[str, str]] = {
    "TaskDispatch": "dispatch",
    "StatusReport": "report",
    "EscalationEvent": "escalation",
}

_FILENAME_RE: Final[re.Pattern[str]] = re.compile(
    r"^(?P<from>L[0-3])__(?P<to>L[0-3])__(?P<change_id>[a-z0-9][a-z0-9.-]*[a-z0-9])__(?P<seq>\d{4})\.yaml$"
)
_CHANGE_ID_RE: Final[re.Pattern[str]] = re.compile(r"^[a-z0-9][a-z0-9.-]*[a-z0-9]$")


class HandoffStoreError(RuntimeError):
    """Generic error raised by :class:`HandoffStore`."""


class EnvelopeImmutableError(HandoffStoreError):
    """Raised when an envelope write would overwrite an existing seq.

    Per Rule S-9 (append-only ledger), once
    ``<from>__<to>__<change-id>__<seq>.yaml`` exists, the next message
    MUST be authored at ``seq+1``. Catching this exception is the
    canonical way for an agent to detect a concurrent-author race.
    """


@dataclass
class HandoffEnvelope:
    """In-memory representation of a handoff envelope.

    Mirrors the v16 ``schemas/agent-workspace/handoff-envelope.yaml``
    schema. Required envelope-level fields are explicit attributes; the
    discriminated variant block (``dispatch`` / ``report`` /
    ``escalation``) is held as a free-form dict to avoid an N×M dataclass
    explosion — the discriminator is enforced via :meth:`validate`.
    """

    schema_version: int = CURRENT_HANDOFF_SCHEMA_VERSION
    seq: int = 0
    from_layer: str = ""
    to_layer: str = ""
    change_id: str = ""
    created: str = ""
    envelope_kind: str = ""
    dispatch: dict | None = None
    report: dict | None = None
    escalation: dict | None = None

    @property
    def normalized_from_layer(self) -> str:
        """Return ``from_layer`` in the current v16 token space."""

        return normalize_layer(
            self.from_layer,
            schema_version=self.schema_version,
            context="handoff.from_layer",
        )

    @property
    def normalized_to_layer(self) -> str:
        """Return ``to_layer`` in the current v16 token space."""

        return normalize_layer(
            self.to_layer,
            schema_version=self.schema_version,
            context="handoff.to_layer",
        )

    @property
    def filename(self) -> str:
        """Compute the canonical envelope filename per the schema contract.

        Pattern: ``<from>__<to>__<change-id>__<seq:04d>.yaml``. Raises
        :exc:`HandoffStoreError` when the dataclass values would
        produce a non-conforming name (caller should call :meth:`validate`
        first if they want a single error point).
        """
        if not (1 <= self.seq <= 9999):
            raise HandoffStoreError(
                f"seq {self.seq!r} is out of range; envelope filenames are "
                "zero-padded to 4 digits (range 0001..9999)"
            )
        return f"{self.from_layer}__{self.to_layer}__{self.change_id}__{self.seq:04d}.yaml"

    def variant_block_name(self) -> str:
        """Return the block-attribute name matching ``envelope_kind``."""
        try:
            return ENVELOPE_DISCRIMINATOR_TO_BLOCK[self.envelope_kind]
        except KeyError as exc:
            raise HandoffStoreError(
                f"unknown envelope_kind {self.envelope_kind!r}; expected one of {ENVELOPE_KINDS}"
            ) from exc

    def variant_block(self) -> dict:
        """Return the variant block dict (``dispatch``/``report``/``escalation``)."""
        block = getattr(self, self.variant_block_name())
        if block is None:
            raise HandoffStoreError(
                f"envelope_kind={self.envelope_kind!r} but the corresponding "
                f"{self.variant_block_name()!r} block is absent"
            )
        return block

    def validate(self) -> None:
        """Verify the envelope satisfies the schema contract.

        Checks (in order):
        1. Layer tokens are valid for the envelope's explicit schema
           provenance and ``from_layer != to_layer``.
        2. ``envelope_kind`` ∈ ``ENVELOPE_KINDS``.
        3. ``change_id`` matches the kebab-case pattern.
        4. ``seq`` ∈ [1, 9999].
        5. ``created`` matches the ISO-8601 UTC pattern.
        6. The discriminated variant block exists; sibling variant blocks are absent.

        Raises :exc:`HandoffStoreError` (loud per S-5) on the first failure.
        """
        try:
            for token, context in (
                (self.from_layer, "handoff.from_layer"),
                (self.to_layer, "handoff.to_layer"),
            ):
                normalize_layer(
                    token,
                    schema_version=self.schema_version,
                    context=context,
                )
        except ValueError as exc:
            raise HandoffStoreError(
                f"invalid layer provenance for schema_version={self.schema_version!r}: {exc}"
            ) from exc
        if self.from_layer == self.to_layer:
            raise HandoffStoreError(
                f"from_layer == to_layer == {self.from_layer!r}; self-handoff is forbidden"
            )
        if self.envelope_kind not in ENVELOPE_KINDS:
            raise HandoffStoreError(f"envelope_kind {self.envelope_kind!r} not in {ENVELOPE_KINDS}")
        if not _CHANGE_ID_RE.match(self.change_id or ""):
            raise HandoffStoreError(
                f"change_id {self.change_id!r} does not match kebab-case pattern "
                f"^[a-z0-9][a-z0-9.-]*[a-z0-9]$"
            )
        if not (1 <= self.seq <= 9999):
            raise HandoffStoreError(f"seq {self.seq!r} is out of range [1, 9999]")
        if not re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$", self.created or ""):
            raise HandoffStoreError(
                f"created timestamp {self.created!r} does not match "
                f"ISO-8601 UTC pattern YYYY-MM-DDTHH:MM:SSZ"
            )
        # Discriminated union — exactly one variant block present, matching kind.
        present = {
            "dispatch": self.dispatch is not None,
            "report": self.report is not None,
            "escalation": self.escalation is not None,
        }
        expected_block = self.variant_block_name()
        for block_name, is_present in present.items():
            if block_name == expected_block and not is_present:
                raise HandoffStoreError(
                    f"envelope_kind={self.envelope_kind!r} requires the "
                    f"{expected_block!r} block to be present"
                )
            if block_name != expected_block and is_present:
                raise HandoffStoreError(
                    f"envelope_kind={self.envelope_kind!r} forbids the "
                    f"{block_name!r} block; got presence of multiple variant blocks"
                )

    def to_yaml(self, *, repo_root: str | Path | None = None) -> str:
        """Serialise to YAML in canonical key order.

        The on-disk layout matches the schema's ``instance_top_level_required``
        order verbatim: schema_version → seq → from_layer → to_layer →
        change_id → created → envelope_kind → variant_block.

        StatusReport evidence is normalized at this serializer boundary:
        small blocks remain inline, while oversized blocks are stored under the
        active change's evidence directory and represented by an
        ``evidence_ref``. The envelope object is never mutated.
        """
        ordered: dict = {
            "schema_version": self.schema_version,
            "seq": self.seq,
            "from_layer": self.from_layer,
            "to_layer": self.to_layer,
            "change_id": self.change_id,
            "created": self.created,
            "envelope_kind": self.envelope_kind,
        }
        block_name = self.variant_block_name()
        variant = self.variant_block()
        if self.envelope_kind == "StatusReport":
            from devolaflow.compressor import prepare_status_report_evidence

            variant = prepare_status_report_evidence(
                variant,
                repo_root=repo_root if repo_root is not None else Path.cwd(),
                change_id=self.change_id,
            )
        ordered[block_name] = variant
        return yaml.safe_dump(
            ordered, sort_keys=False, default_flow_style=False, allow_unicode=True
        )

    @classmethod
    def from_yaml(cls, text: str) -> HandoffEnvelope:
        """Parse a YAML string into a :class:`HandoffEnvelope`.

        Loud on malformed input — never returns a partial/corrupt envelope.
        """
        data = yaml.safe_load(text)
        if not isinstance(data, dict):
            raise HandoffStoreError(
                f"envelope YAML must parse as a mapping; got {type(data).__name__}"
            )
        # Pull only the recognised top-level keys; ignore extras (forward-compat).
        envelope = cls(
            schema_version=int(data.get("schema_version", CURRENT_HANDOFF_SCHEMA_VERSION)),
            seq=int(data.get("seq", 0)),
            from_layer=str(data.get("from_layer", "")),
            to_layer=str(data.get("to_layer", "")),
            change_id=str(data.get("change_id", "")),
            created=str(data.get("created", "")),
            envelope_kind=str(data.get("envelope_kind", "")),
            dispatch=data.get("dispatch"),
            report=data.get("report"),
            escalation=data.get("escalation"),
        )
        envelope.validate()
        return envelope

    def asdict(self) -> dict:
        """Return the envelope as a plain dict (for diagnostics + tests)."""
        return asdict(self)


def _fire_task_stop_hook(envelope: HandoffEnvelope, *, repo_root: Path) -> None:
    """Fire the ``task_stop`` lifecycle hook for a StatusReport envelope.

    Production call site for
    :func:`devolaflow.lifecycle.runtime_wiring.fire_task_stop` per
    ADR-003 (``docs/cycle-archive/adr/v15-ADR-003-output-closure-
    enforcement-locus.md``): ``HandoffStore.write_envelope`` with
    ``envelope_kind == "StatusReport"`` IS the L2 report emission
    surface. The payload is a shallow copy of the envelope's ``report``
    block (so a hook handler can never mutate the envelope about to be
    written); the default ``test_on_complete`` handler reads the
    block's in-memory ``metrics`` evidence — no subprocesses spawned.

    STRICT by default since v15.0.0 (G-038 graduation per ADR-003
    §Decision 3): the call defers to ``fire_task_stop``'s own strict
    default, so a failing report (``tests_failed > 0`` / lint not
    clean) raises :class:`HookViolation` (block + escalate per S-8
    "mode: full" / the P4 retry trigger) and the envelope is NOT
    written. Opt-out is the adapter's explicit ``strict=False``
    parameter (S-8 "mode: lite"). Still a byte-identical zero-IO no-op
    when ``DEVOLAFLOW_AGENT_WORKSPACE`` != "1" (W-20 flag reuse — the
    activation gate is UNCHANGED). Per the S-5 isolation pattern from
    ``feedback_emit._fire_hook_chain``, a buggy hook handler (any
    exception OTHER than the strict-mode :class:`HookViolation`) is
    logged at WARNING and the envelope write proceeds. Lazy import
    preserves the no-cycle property between ``agent_workspace`` and
    ``lifecycle``.
    """
    from devolaflow.lifecycle.dispatcher import HookViolation
    from devolaflow.lifecycle.runtime_wiring import fire_task_stop

    try:
        report = dict(envelope.report or {})
        # ``change_id`` belongs to the envelope schema, while the lifecycle
        # hook consumes the report block. Carry it across only for this
        # in-memory check so active-workspace resolution has explicit context.
        report.setdefault("change_id", envelope.change_id)
        fire_task_stop(report, repo_root=repo_root)
    except HookViolation:
        # v15.0.0 strict graduation: block the envelope write + escalate.
        raise
    except Exception as exc:  # noqa: BLE001
        logging.getLogger(__name__).warning(
            "task_stop hook raised %s for change_id=%r seq=%d; envelope "
            "write proceeds unchanged (S-5 isolation for non-violation "
            "hook bugs per ADR-003)",
            exc,
            envelope.change_id,
            envelope.seq,
        )


@dataclass
class HandoffStore:
    """Append-only filesystem-backed handoff envelope ledger.

    The store enforces the Rule S-9 invariant at write time and provides
    chronological / per-change reads. It does NOT compact archived
    envelopes (that is the job of :class:`ArchiveManager.archive` which
    moves them into ``handoff_chain.yaml`` per design.md §1.1).

    Attributes:
      repo_root: Repo root used to resolve the default ``handoff_dir``.
      handoff_dir: Override for the handoff folder root (relative to
        ``repo_root``). Defaults to ``.local/.agent/handoff``.
    """

    repo_root: Path = field(default_factory=Path.cwd)
    handoff_dir: Path = field(default_factory=lambda: Path(HANDOFF_DIR_DEFAULT))

    @property
    def handoff_root(self) -> Path:
        """Absolute (or repo-rooted) path to the handoff folder."""
        return (
            self.handoff_dir
            if self.handoff_dir.is_absolute()
            else self.repo_root / self.handoff_dir
        )

    def write_envelope(self, envelope: HandoffEnvelope) -> Path:
        """Write ``envelope`` to disk; raise :exc:`EnvelopeImmutableError` on collision.

        The file is created atomically via temp-file + rename so a partial
        write cannot leave a half-formed envelope visible to a concurrent
        reader. New writes are schema v2 only; schema-v1 envelopes are a
        read-only compatibility surface and remain untouched on disk.

        Returns:
          Absolute path to the written file.

        Raises:
          EnvelopeImmutableError: when the target seq already exists.
          HandoffStoreError: when the envelope fails schema validation.
        """
        if envelope.schema_version != CURRENT_HANDOFF_SCHEMA_VERSION:
            raise HandoffStoreError(
                "new handoff writes require schema_version=2 and v16 layer tokens; "
                "schema-v1 envelopes are read-only history and MUST NOT be migrated "
                "or re-emitted (S-9)"
            )
        envelope.validate()
        # ADR-003 task_stop wiring (v14.3.0): a StatusReport envelope IS the
        # framework-level finalisation of an L2 task's report, so the
        # ``task_stop`` (``test_on_complete``) hook fires here BEFORE the
        # envelope is materialised. STRICT by default since v15.0.0
        # (failing report → HookViolation raises; envelope NOT written)
        # and a byte-identical zero-IO no-op when
        # ``DEVOLAFLOW_AGENT_WORKSPACE`` != "1".
        if envelope.envelope_kind == "StatusReport":
            _fire_task_stop_hook(envelope, repo_root=self.repo_root)
        target = self.handoff_root / envelope.filename
        target.parent.mkdir(parents=True, exist_ok=True)
        # Write to a unique sibling, then atomically install it with a hard
        # link.  Unlike replace/rename, link creation is exclusive: a
        # concurrent author cannot clobber an envelope that won the race.
        fd, tmp_name = tempfile.mkstemp(
            prefix=f".{target.name}.",
            suffix=".tmp",
            dir=target.parent,
        )
        tmp = Path(tmp_name)
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
                stream.write(envelope.to_yaml(repo_root=self.repo_root))
                stream.flush()
                os.fsync(stream.fileno())
            try:
                os.link(tmp, target)
            except FileExistsError as exc:
                raise EnvelopeImmutableError(
                    f"envelope {target!s} already exists at seq={envelope.seq}; "
                    f"author a new envelope at seq={envelope.seq + 1} per Rule S-9 "
                    f"(append-only ledger)"
                ) from exc
            return target
        finally:
            tmp.unlink(missing_ok=True)

    def next_seq(self, change_id: str) -> int:
        """Return the next seq number to author for ``change_id``.

        Returns 1 when no envelopes exist yet for that change. Returns
        ``max(existing_seqs) + 1`` otherwise. Useful for an agent that
        wants to append without race-checking.
        """
        existing = self.list_envelope_files_for(change_id)
        if not existing:
            return 1
        return max(_seq_from_filename(p.name) for p in existing) + 1

    def list_envelope_files_for(self, change_id: str) -> list[Path]:
        """Return all envelope file paths for ``change_id`` (unsorted)."""
        if not self.handoff_root.is_dir():
            return []
        return [
            p
            for p in self.handoff_root.iterdir()
            if p.is_file()
            and p.suffix == ".yaml"
            and (match := _FILENAME_RE.match(p.name))
            and match.group("change_id") == change_id
        ]

    def read_envelopes(self, change_id: str) -> list[HandoffEnvelope]:
        """Return ``change_id``'s envelopes in chronological (seq-ascending) order.

        Each envelope is re-validated on load (schema conformance + seq ↔
        filename consistency); a malformed envelope raises
        :exc:`HandoffStoreError` (loud per S-5) — silent skipping would
        violate the audit-trail contract.
        """
        files = self.list_envelope_files_for(change_id)
        files.sort(key=lambda p: _seq_from_filename(p.name))
        envelopes: list[HandoffEnvelope] = []
        for path in files:
            envelope = HandoffEnvelope.from_yaml(path.read_text(encoding="utf-8"))
            filename_seq = _seq_from_filename(path.name)
            if filename_seq != envelope.seq:
                raise HandoffStoreError(
                    f"envelope file {path!s} has filename seq {filename_seq} but "
                    f"body seq {envelope.seq}; mismatch is a schema violation"
                )
            envelopes.append(envelope)
        # Append-only contract: sequences should be a prefix of {1, 2, 3, ...}.
        # We do NOT enforce contiguity (an agent may legitimately skip a seq
        # in flight if multiple parallel writes raced and one lost) but we DO
        # surface duplicates — those would have raised at write time.
        seen: set[int] = set()
        for env in envelopes:
            if env.seq in seen:
                raise HandoffStoreError(
                    f"duplicate seq={env.seq} for change_id={change_id!r}; "
                    f"the append-only ledger has been corrupted"
                )
            seen.add(env.seq)
        return envelopes


def _seq_from_filename(filename: str) -> int:
    """Extract the int seq from an envelope filename (defensive)."""
    match = _FILENAME_RE.match(filename)
    if match is None:
        raise HandoffStoreError(
            f"filename {filename!r} does not match the handoff envelope pattern "
            f"<from>__<to>__<change-id>__<seq>.yaml"
        )
    return int(match.group("seq"))


def make_envelope(
    *,
    seq: int,
    from_layer: str,
    to_layer: str,
    change_id: str,
    envelope_kind: str,
    payload: dict,
    created: str | None = None,
    schema_version: int = CURRENT_HANDOFF_SCHEMA_VERSION,
) -> HandoffEnvelope:
    """Convenience constructor for a fully-validated :class:`HandoffEnvelope`.

    ``payload`` is the variant block contents (e.g. for ``TaskDispatch`` the
    ``dispatch`` block dict). The function dispatches it to the correct
    attribute based on ``envelope_kind`` and runs :meth:`HandoffEnvelope.validate`
    before returning.
    """
    if envelope_kind not in ENVELOPE_KINDS:
        raise HandoffStoreError(f"envelope_kind {envelope_kind!r} not in {ENVELOPE_KINDS}")
    block_name = ENVELOPE_DISCRIMINATOR_TO_BLOCK[envelope_kind]
    kwargs = {block_name: payload}
    envelope = HandoffEnvelope(
        schema_version=schema_version,
        seq=seq,
        from_layer=from_layer,
        to_layer=to_layer,
        change_id=change_id,
        created=created or _now_iso(),
        envelope_kind=envelope_kind,
        **kwargs,
    )
    envelope.validate()
    return envelope


__all__.append("make_envelope")


def _now_iso() -> str:
    """ISO-8601 UTC timestamp matching the schema's ``created`` pattern."""
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# v12.5.0 PV-05 D-3 — strip_l0_only_metadata helper
# ---------------------------------------------------------------------------
#
# Companion to the v12.4.0 PV-05 ``reject_subagent_banner_emission``
# lifecycle hook (``src/devolaflow/lifecycle/reject_subagent_banner_emission.py``).
# The PV-05 hook DETECTS banner literals + ``quality_score`` keys in
# subagent (L1/L2) dispatch payloads and emits a WARNING via
# HookViolation; operators previously had to manually scrub these
# literals before authoring an envelope. This helper closes the
# auto-cleanup loop telegraphed in the v12.4.0 retrospective §3 row 4
# ("Handoff envelope auto-strip helper") + §6 telegraph item 2.
#
# Contract (per .local/research/v12.5.0_gap_analysis.md §2 D-3):
#
# * Pure function — operates on a deep-copy of the input dict; never
#   mutates the input dict; never touches disk (S-9 append-only
#   preserved — handoff envelopes on disk are written by callers, not
#   by this helper).
# * Idempotent — applying the helper twice produces the same output as
#   applying it once.
# * Permissive on absent keys — a dict without banner / quality_score
#   keys returns a deep-copy unchanged.
# * S-5 explicit warn — malformed input (non-dict) logs a WARNING via
#   ``logging.getLogger(__name__)`` rather than raising or silently
#   dropping; the caller receives the input unchanged.
#
# Source: .local/research/v12.5.0_gap_analysis.md §2 D-3 +
# .local/research/v12.4.0_retrospective.md §6 telegraph item 2.
# ---------------------------------------------------------------------------

_logger_v12_5_0 = logging.getLogger(__name__)


# Banner literal patterns per
# `src/devolaflow/lifecycle/reject_subagent_banner_emission.py` —
# the same regex shape that hook uses for DETECTION; this helper uses
# them for STRIPPING. Kept verbatim-aligned to that hook so a
# single-source-of-truth pattern surface emerges in v12.6.0+ if needed.
_L0_ONLY_BANNER_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"🌸\s*DevolaFlow\s+v\d+\.\d+\.\d+\b[^\n]*", re.MULTILINE),
    re.compile(r"📊[^\n]*Task\s+Quality\s+Score[^\n]*", re.MULTILINE | re.IGNORECASE),
)

_L0_ONLY_KEYS: frozenset[str] = frozenset(
    {
        "quality_score",
        "task_quality_score",
        "session_banner",
    }
)


def _strip_banner_literals_from_string(text: str) -> str:
    """Remove banner literal substrings from *text*; idempotent."""
    out = text
    for pat in _L0_ONLY_BANNER_PATTERNS:
        out = pat.sub("", out)
    # Collapse the run-of-empty-lines artifact left after stripping
    # multi-line banner/footer blocks (defensive, idempotent).
    out = re.sub(r"\n{3,}", "\n\n", out)
    return out


def _strip_recursive(node):
    """Recursive walker — strips banner literals + L0-only keys.

    Operates on the in-memory dict / list / scalar tree. Pure (no IO,
    no logging). Caller wraps invocation in :func:`strip_l0_only_metadata`
    which guards the malformed-input + deep-copy contracts.
    """
    if isinstance(node, dict):
        cleaned: dict[str, object] = {}
        for key, value in node.items():
            if key in _L0_ONLY_KEYS:
                continue
            cleaned[key] = _strip_recursive(value)
        return cleaned
    if isinstance(node, list):
        return [_strip_recursive(item) for item in node]
    if isinstance(node, str):
        return _strip_banner_literals_from_string(node)
    return node


def strip_l0_only_metadata(envelope: dict) -> dict:
    """Strip L0-only banner literals + ``quality_score`` keys from *envelope*.

    Closes v12.5.0 PV-05 D-3 (handoff envelope auto-strip helper).
    Companion to the v12.4.0 PV-05 ``reject_subagent_banner_emission``
    hook: the hook DETECTS L0-only metadata in subagent dispatches and
    emits a WARNING; this helper performs the actual cleanup so the
    handoff writer can scrub envelopes before write.

    Contract:

    * **Pure** — operates on a deep-copy; never mutates *envelope*; never
      touches disk. Verified by ``tests/test_handoff_strip_metadata.py``.
    * **Idempotent** — calling twice produces a byte-equal result to
      calling once.
    * **Permissive on absent keys** — a dict without banner /
      ``quality_score`` keys returns a deep-copy unchanged.
    * **Permissive on empty dict** — ``{}`` in → ``{}`` out.
    * **S-5 explicit warn** — non-dict input logs a WARNING and returns
      the input unchanged (preserves caller invariants).

    Args:
        envelope: A dict-shaped envelope payload (typically a
            :class:`HandoffEnvelope` ``asdict()`` result OR a
            ``run_hooks("pre_dispatch", payload, ...)`` payload prior to
            envelope authoring).

    Returns:
        A NEW dict (deep-copy of input) with L0-only metadata removed.
        Banner literals are stripped from string values throughout the
        tree; ``quality_score`` / ``task_quality_score`` /
        ``session_banner`` keys are removed at every nesting depth.
        Empty / null inputs return a deep-copy unchanged.

    v12.5.0 PV-05 D-3: closes the v12.4.0 PV-05 detection-only auto-
    cleanup gap. Pairs with
    ``src/devolaflow/lifecycle/reject_subagent_banner_emission.py``.
    """
    if not isinstance(envelope, dict):
        _logger_v12_5_0.warning(
            "strip_l0_only_metadata received non-dict input "
            "(type=%s); returning input unchanged per S-5 "
            "explicit-warn contract",
            type(envelope).__name__,
        )
        return envelope
    # Deep-copy guards the caller's input dict from mutation.
    working = copy.deepcopy(envelope)
    return _strip_recursive(working)


__all__.append("strip_l0_only_metadata")
