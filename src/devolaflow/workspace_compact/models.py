"""Record types for non-destructive workspace compaction (v24.0.0).

Design ref: `.local/research/v24.0.0_design_adr.md` §2, §4.4.

Compaction here means *relocate and index*, never *rewrite and discard*.
Every entry that moves carries a content hash into the mapping ledger, so
"nothing was lost" is a checkable claim rather than an assurance.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from devolaflow.workspace_ledger import sha256_bytes

COMPACT_DIRNAME: Final[str] = "compact"
ARCHIVED_DIRNAME: Final[str] = "archived"
MAPPINGS_FILENAME: Final[str] = "mappings.yaml"
DIGEST_FILENAME: Final[str] = "DIGEST.md"

DIGEST_MARKER: Final[str] = "<!-- devolaflow: generated compact digest -->"
HANDOFF_INDEX_MARKER: Final[str] = "<!-- devolaflow: generated handoff index -->"


class Category(StrEnum):
    """Why an entry is or is not eligible for relocation."""

    CLOSED_RISK = "closed_risk"
    HISTORICAL_OUTPUT = "historical_output"
    OPERATOR_NAMED = "operator_named"
    PROTECTED = "protected"
    LIVE = "live"


class Action(StrEnum):
    """What the plan proposes for one entry."""

    MOVE = "move"
    RETAIN = "retain"


#: Artifacts that are never relocated automatically. The judgment ledger is
#: the strongest case: it is the only durable record of what the operator
#: decided, so it is never compacted at any size.
PROTECTED_NAMES: Final[frozenset[str]] = frozenset(
    {
        "goal.md",
        "checklist.md",
        "stage.md",
        "preflight.md",
        "spec.md",
        "STATUS.yaml",
        "owned_files.txt",
        "entrance.md",
        "learnings.jsonl",
        "harness_preflight.md",
        "pathfinder_report.md",
        "judgments.yaml",
        "events.yaml",
        "INDEX.md",
        "judge.md",
        "DIGEST.md",
    }
)

#: Directory names whose contents are accumulated historical output.
HISTORICAL_DIRS: Final[frozenset[str]] = frozenset({"loops", "rounds", "history", "logs"})


@dataclass(frozen=True)
class CompactEntry:
    """One classified path in a compaction plan."""

    source: str
    destination: str
    category: Category
    action: Action
    reason: str
    bytes: int
    tokens_estimated: int
    sha256: str
    subject: str | None = None
    summary: str = ""
    """Human-recognisable subject, so the digest can be read without `locate`.

    A digest of paths and hashes answers "where did it go" but not "what was
    it about", which forces a search for every question and undoes the point
    of a compact index.
    """

    @property
    def key(self) -> tuple[str, str]:
        """Return the immutable source/destination approval identity."""

        return self.source, self.destination


@dataclass(frozen=True)
class CompactPlan:
    """Report-only compaction proposal for one task or change folder."""

    folder: str
    entries: tuple[CompactEntry, ...]
    retained_tokens: int
    movable_tokens: int
    findings: tuple[str, ...] = ()

    @property
    def movable(self) -> tuple[CompactEntry, ...]:
        """Return only the entries the plan proposes to relocate."""

        return tuple(entry for entry in self.entries if entry.action is Action.MOVE)

    @property
    def fingerprint(self) -> str:
        """Return the digest an approval must cite to authorise this plan."""

        payload = "\n".join(
            f"{entry.source}\x1f{entry.destination}\x1f{entry.sha256}" for entry in self.movable
        )
        return sha256_bytes(f"{self.folder}\x1e{payload}".encode())

    @property
    def projected_reduction(self) -> float:
        """Return the fraction of resident tokens the plan would relocate."""

        total = self.retained_tokens + self.movable_tokens
        return 0.0 if total == 0 else self.movable_tokens / total

    @property
    def candidates(self) -> tuple[CompactEntry, ...]:
        """Return retained entries an operator could still name with `--include`.

        Automatic classification only moves closed risks and accumulated
        historical output, which in practice is not where a real folder's
        weight sits — it sits in one large hand-written document. Without this
        list the operator reads "0 movable" and has nowhere to go, so the
        heaviest retained non-canonical files are surfaced as the next step.
        """

        return tuple(
            sorted(
                (
                    entry
                    for entry in self.entries
                    if entry.action is Action.RETAIN and entry.category is Category.LIVE
                ),
                key=lambda entry: -entry.tokens_estimated,
            )
        )

    @property
    def digest_tokens(self) -> int:
        """Return the token cost of the digest this plan would write.

        Zero when nothing moves: `apply` refuses an empty approval, so no
        digest is written and charging for one would misreport the choice.
        """

        from devolaflow.workspace_compact.digest import estimate_digest_tokens

        movable = self.movable
        return estimate_digest_tokens(movable) if movable else 0

    @property
    def net_tokens(self) -> int:
        """Return tokens saved after paying for the digest.

        Negative means the move costs the reader more than it saves.
        """

        return self.movable_tokens - self.digest_tokens

    @property
    def pays_for_itself(self) -> bool:
        """Return whether relocating actually reduces what an agent must read."""

        return self.net_tokens > 0


@dataclass(frozen=True)
class CompactResult:
    """Outcome of an approved apply attempt.

    ``findings`` covers the relocation itself and is what ``refused``
    reflects. ``digest_findings`` is kept separate because the digest is
    re-rendered after every move has already committed: a narration whose
    anchors no longer resolve is a real problem, but reporting it as a
    refusal tells an operator that nothing moved when in fact everything did.
    """

    applied: tuple[CompactEntry, ...] = ()
    findings: tuple[str, ...] = ()
    refused: bool = False
    digest_path: str | None = None
    tokens_before: int = 0
    tokens_after: int = 0
    digest_findings: tuple[str, ...] = ()

    @property
    def success(self) -> bool:
        """Return true only when the requested relocation fully completed.

        A stale or unanchored digest does not make this false: the moves are
        durable and the ledger records them. Read :attr:`digest_current` for
        the state of the index.
        """

        return not self.refused and not self.findings

    @property
    def digest_current(self) -> bool:
        """Return whether the regenerated digest is clean and on disk."""

        return not self.digest_findings

    @property
    def reduction(self) -> float:
        """Return the measured fraction of resident tokens relocated."""

        if self.tokens_before == 0:
            return 0.0
        return (self.tokens_before - self.tokens_after) / self.tokens_before


@dataclass(frozen=True)
class LocateHit:
    """One match from a query against the archived originals."""

    archived_path: str
    original_source: str
    line: int
    excerpt: str


class CompactError(RuntimeError):
    """Raised for malformed compaction input or an unsafe request."""


__all__ = [
    "ARCHIVED_DIRNAME",
    "COMPACT_DIRNAME",
    "DIGEST_FILENAME",
    "DIGEST_MARKER",
    "HANDOFF_INDEX_MARKER",
    "HISTORICAL_DIRS",
    "MAPPINGS_FILENAME",
    "PROTECTED_NAMES",
    "Action",
    "Category",
    "CompactEntry",
    "CompactError",
    "CompactPlan",
    "CompactResult",
    "LocateHit",
]
