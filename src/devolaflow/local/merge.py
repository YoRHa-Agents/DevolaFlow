"""Progressive merge: diff-suggest for existing files.

When repo-init encounters existing CLAUDE.md, AGENTS.md, or .rules/ files,
this module generates a merge proposal showing what would change, letting
the user choose: merge / overwrite / skip.
"""

from __future__ import annotations

import difflib
from dataclasses import dataclass
from pathlib import Path


@dataclass
class MergeProposal:
    """A proposed merge of new content into an existing file."""

    path: Path
    exists: bool
    current_content: str
    proposed_content: str
    diff_lines: list[str]
    action: str = "pending"

    @property
    def has_changes(self) -> bool:
        return self.current_content != self.proposed_content

    @property
    def diff_summary(self) -> str:
        additions = sum(
            1 for line in self.diff_lines if line.startswith("+") and not line.startswith("+++")
        )
        deletions = sum(
            1 for line in self.diff_lines if line.startswith("-") and not line.startswith("---")
        )
        return f"+{additions}/-{deletions} lines"


def propose_merge(path: Path, new_content: str) -> MergeProposal:
    """Create a merge proposal for *path* with *new_content*.

    If the file doesn't exist, the proposal is a simple create (no diff).
    If the file exists and content differs, generates a unified diff.
    If the file exists and content matches, the proposal has no changes.
    """
    if not path.exists():
        return MergeProposal(
            path=path,
            exists=False,
            current_content="",
            proposed_content=new_content,
            diff_lines=[],
            action="create",
        )

    current = path.read_text(encoding="utf-8")
    if current == new_content:
        return MergeProposal(
            path=path,
            exists=True,
            current_content=current,
            proposed_content=new_content,
            diff_lines=[],
            action="skip",
        )

    diff = list(
        difflib.unified_diff(
            current.splitlines(keepends=True),
            new_content.splitlines(keepends=True),
            fromfile=str(path),
            tofile=f"{path} (proposed)",
        )
    )

    return MergeProposal(
        path=path,
        exists=True,
        current_content=current,
        proposed_content=new_content,
        diff_lines=diff,
    )


def apply_merge(proposal: MergeProposal, action: str = "merge") -> bool:
    """Apply a merge proposal. Returns True if the file was written.

    Actions:
      - ``merge`` / ``overwrite``: write proposed_content to path
      - ``skip``: do nothing
    """
    if action in ("skip",) or not proposal.has_changes:
        proposal.action = "skip"
        return False

    proposal.path.parent.mkdir(parents=True, exist_ok=True)
    proposal.path.write_text(proposal.proposed_content, encoding="utf-8")
    proposal.action = action
    return True


def format_diff_for_review(proposal: MergeProposal) -> str:
    """Format a merge proposal as a human-readable review string."""
    if not proposal.exists:
        return f"CREATE {proposal.path} ({len(proposal.proposed_content)} bytes)"

    if not proposal.has_changes:
        return f"SKIP {proposal.path} (no changes)"

    header = f"MODIFY {proposal.path} ({proposal.diff_summary})"
    diff_text = "".join(proposal.diff_lines)
    return f"{header}\n{diff_text}"


__all__ = [
    "MergeProposal",
    "apply_merge",
    "format_diff_for_review",
    "propose_merge",
]
