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

import re
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

import yaml

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

LAYERS: Final[tuple[str, ...]] = ("L0", "L1", "L2", "L3")
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

    Mirrors the v8.2.4 ``schemas/agent-workspace/handoff-envelope.yaml``
    schema. Required envelope-level fields are explicit attributes; the
    discriminated variant block (``dispatch`` / ``report`` /
    ``escalation``) is held as a free-form dict to avoid an N×M dataclass
    explosion — the discriminator is enforced via :meth:`validate`.
    """

    schema_version: int = 1
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
        1. ``from_layer`` / ``to_layer`` ∈ ``LAYERS`` and ``from_layer != to_layer``.
        2. ``envelope_kind`` ∈ ``ENVELOPE_KINDS``.
        3. ``change_id`` matches the kebab-case pattern.
        4. ``seq`` ∈ [1, 9999].
        5. ``created`` matches the ISO-8601 UTC pattern.
        6. The discriminated variant block exists; sibling variant blocks are absent.

        Raises :exc:`HandoffStoreError` (loud per S-5) on the first failure.
        """
        if self.from_layer not in LAYERS or self.to_layer not in LAYERS:
            raise HandoffStoreError(
                f"from_layer/to_layer must each be one of {LAYERS}; "
                f"got from_layer={self.from_layer!r}, to_layer={self.to_layer!r}"
            )
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

    def to_yaml(self) -> str:
        """Serialise to YAML in canonical key order.

        The on-disk layout matches the schema's ``instance_top_level_required``
        order verbatim: schema_version → seq → from_layer → to_layer →
        change_id → created → envelope_kind → variant_block.
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
        ordered[block_name] = self.variant_block()
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
            schema_version=int(data.get("schema_version", 1)),
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
        reader.

        Returns:
          Absolute path to the written file.

        Raises:
          EnvelopeImmutableError: when the target seq already exists.
          HandoffStoreError: when the envelope fails schema validation.
        """
        envelope.validate()
        target = self.handoff_root / envelope.filename
        if target.exists():
            raise EnvelopeImmutableError(
                f"envelope {target!s} already exists at seq={envelope.seq}; "
                f"author a new envelope at seq={envelope.seq + 1} per Rule S-9 "
                f"(append-only ledger)"
            )
        target.parent.mkdir(parents=True, exist_ok=True)
        # Atomic write: temp file + rename.
        tmp = target.with_suffix(target.suffix + ".tmp")
        tmp.write_text(envelope.to_yaml(), encoding="utf-8", newline="\n")
        tmp.replace(target)
        return target

    def next_seq(self, change_id: str) -> int:
        """Return the next seq number to author for ``change_id``.

        Returns 1 when no envelopes exist yet for that change. Returns
        ``max(existing_seqs) + 1`` otherwise. Useful for an L3 agent that
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
    schema_version: int = 1,
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
