#!/usr/bin/env python3
"""Section-anchor registry for SKILL.md / reference doc section discovery.

v8.2.0 (PV-05) — closes the v8.0.x SI-1 entry point per
``.local/research/v8.0.0_retrospective.md`` §3.3 and gap analysis B1
in ``.local/research/v8.1.0_gap_analysis.md`` §3.2. Replaces the
line-anchored section registry used by the v8.0.0 task adaptive selector
with a symbolic anchor → file path mapping. Decouples section references
from concrete line numbers so SKILL.md edits no longer cascade through
``workflow-system/agent/context_profiles.yaml`` and trigger unrelated
built-in harness fixture drift.

Design contract (per ``.local/research/v8.2.0_patch_plan.md`` §3 PV-05
AC #1/#3/#4):

* ``register(anchor, file)`` — symbolic name → file path mapping (NO line
  numbers). The file path is repo-root-relative per S-2 / SF-5.
* ``lookup(anchor) -> str`` returns the file path. The consumer
  dynamically discovers section content within the resolved file (e.g.
  via markdown heading match in :func:`extract_section_by_heading`).
* ``register_from_yaml(profile_yaml)`` parses the
  ``section_anchors:`` top-level mapping in the profiles YAML and
  registers every entry. Two YAML forms are accepted::

      section_anchors:
        # Short form — anchor → file path
        behavioral_guidelines: "workflow-system/agent/references/behavioral-guidelines.md"

        # Extended form — anchor → {file, heading}
        mode_detection:
          file: "workflow-system/agent/SKILL.md"
          heading: "## Mode Awareness"

  The extended form is for the (rare) cases where the SKILL.md heading
  text differs from the snake-cased anchor name (e.g. the canonical
  ``mode_detection`` anchor maps to the ``## Mode Awareness`` heading).

Backward compatibility: callers that look up an unregistered anchor
receive a :class:`KeyError`. The companion refactor in
``src/devolaflow/task_adaptive_selector.py`` catches the missing-anchor
case and falls back to the legacy line-based ``sections:`` registry
with a one-shot ``DeprecationWarning`` per S-5 (No Silent Failures).

P6-safe: this module is purely a config / runtime helper and adds no
new dispatch field. ``schemas/lean-dispatch.yaml`` ``canonical_order``
length stays 15 and version stays 4 throughout v8.2.0 PV-05.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


_REPO_ROOT = Path(__file__).resolve().parents[2]


class SectionAnchorRegistry:
    """Registry mapping symbolic anchor names to file paths.

    Each anchor is the canonical name of a SKILL.md / reference-doc
    section consumed by :func:`devolaflow.task_adaptive_selector.select_context`.
    The registry decouples those names from the concrete line numbers
    they used to be bound to in ``context_profiles.yaml``: SKILL.md
    edits now only need to update the section heading (if at all),
    never the registry.
    """

    def __init__(self) -> None:
        self._files: dict[str, str] = {}
        self._headings: dict[str, str] = {}

    def register(self, anchor: str, file: str, heading: str | None = None) -> None:
        """Register a symbolic anchor mapped to a file path.

        Parameters
        ----------
        anchor:
            Canonical anchor name (e.g. ``"quick_action_decision"``).
            Must be a non-empty string. Re-registering an existing
            anchor overwrites the previous entry (the typical YAML-load
            workflow registers each anchor exactly once).
        file:
            Repo-root-relative file path (e.g.
            ``"workflow-system/agent/SKILL.md"``). Absolute paths are
            rejected per S-2 / SF-5.
        heading:
            Optional explicit markdown heading override. When omitted,
            consumers derive the heading from the anchor name via
            snake_case → Title Case (see
            :func:`extract_section_by_heading`).
        """
        if not anchor:
            raise ValueError("anchor must be a non-empty string")
        if not file:
            raise ValueError("file must be a non-empty string")
        if file.startswith("/"):
            raise ValueError(
                f"file must be repo-root-relative, not absolute: {file!r} (S-2 / SF-5)"
            )
        self._files[anchor] = file
        if heading:
            self._headings[anchor] = heading
        elif anchor in self._headings:
            del self._headings[anchor]

    def lookup(self, anchor: str) -> str:
        """Return the registered file path for *anchor*.

        Raises :class:`KeyError` when the anchor is not registered so the
        consumer can decide whether to fall back to the deprecated
        line-based registry (per S-5 No Silent Failures — never silently
        swallow the lookup miss).
        """
        if anchor not in self._files:
            raise KeyError(f"section anchor not registered: {anchor!r}")
        return self._files[anchor]

    def heading(self, anchor: str) -> str | None:
        """Return the optional explicit heading override, or ``None``.

        Consumers should fall back to the snake_case → Title Case
        derivation when this returns ``None``.
        """
        return self._headings.get(anchor)

    def has(self, anchor: str) -> bool:
        """Return True iff *anchor* is registered."""
        return anchor in self._files

    def anchors(self) -> list[str]:
        """Return the sorted list of registered anchor names."""
        return sorted(self._files.keys())

    def __len__(self) -> int:
        return len(self._files)

    def __contains__(self, anchor: object) -> bool:
        return isinstance(anchor, str) and self.has(anchor)

    def register_from_yaml(self, profile_yaml: dict[str, Any]) -> int:
        """Parse a context_profiles.yaml-style dict and register all anchors.

        Reads the top-level ``section_anchors:`` mapping. Returns the
        number of anchors registered. Both the short and extended YAML
        forms (see module docstring) are honoured. An empty / missing
        ``section_anchors:`` block registers zero anchors and returns
        ``0`` (no error — the caller may rely on the legacy line-based
        fallback during the migration window).

        Raises :class:`ValueError` when an anchor entry is malformed
        (e.g. extended form missing ``file`` key) — never silently
        skipped per S-5.
        """
        anchors_block = profile_yaml.get("section_anchors") or {}
        if not isinstance(anchors_block, dict):
            raise ValueError(
                f"section_anchors must be a mapping, got {type(anchors_block).__name__}"
            )
        count = 0
        for anchor, value in anchors_block.items():
            if isinstance(value, str):
                self.register(anchor, value)
            elif isinstance(value, dict):
                file_path = value.get("file")
                heading = value.get("heading")
                if not file_path:
                    raise ValueError(
                        f"section_anchors[{anchor!r}] extended form requires 'file' key"
                    )
                self.register(anchor, file_path, heading=heading)
            else:
                raise ValueError(
                    f"section_anchors[{anchor!r}] must be str or dict, got {type(value).__name__}"
                )
            count += 1
        return count


_HEADING_RE = re.compile(r"^(#+)\s+(.+?)\s*$")


def _anchor_to_title(anchor: str) -> str:
    """Convert ``snake_case_anchor`` to ``"Snake Case Anchor"`` heading text.

    Used as the default heading-match candidate when a registry entry
    omits an explicit ``heading`` override.
    """
    return " ".join(word.capitalize() for word in anchor.split("_"))


_FENCE_RE = re.compile(r"^(```|~~~)")


def _heading_indices(lines: list[str]) -> list[tuple[int, int, str]]:
    """Return ``(line_idx, level, title)`` for every real markdown heading.

    Lines inside fenced code blocks (triple-backtick or triple-tilde
    fences) are deliberately skipped — they are content, not document
    structure. Without this guard, code samples like SKILL.md's
    plan-mode-template fenced block (which contains ``## Overview``
    examples) would prematurely terminate the parent ``### PLAN MODE``
    section and starve downstream harness fixtures of expected content
    (this was the root cause of the v8.2.0 PV-05 first-iteration
    composite drift before the fix).
    """
    out: list[tuple[int, int, str]] = []
    in_fence = False
    for idx, line in enumerate(lines):
        fence = _FENCE_RE.match(line.lstrip())
        if fence is not None:
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        m = _HEADING_RE.match(line)
        if m is None:
            continue
        out.append((idx, len(m.group(1)), m.group(2).strip()))
    return out


def extract_section_by_heading(file_text: str, heading: str) -> str:
    """Extract a markdown section identified by *heading*.

    The section starts at the first heading line whose text matches
    *heading* (case-insensitive — exact match preferred, substring
    fallback). Headings inside fenced code blocks are ignored (they
    are content, not document structure). The section ends at the
    next heading (outside fenced blocks) at the same or higher level
    (so a ``## Foo`` section ends at the next ``## Bar`` or ``# Top``,
    but ``### Sub`` headings inside it are preserved).

    *heading* may be either:
      * ``"## Mode Awareness"`` — full ``#``-prefixed form (level
        constrains the end-of-section detection), or
      * ``"Mode Awareness"`` — title-only form (any heading level
        matches; section ends at the next heading at any level).

    Returns ``""`` when the heading cannot be located. Per S-5 the
    consumer MUST treat the empty return as a deliberate "section not
    found" signal (never confused with a successfully-extracted empty
    section because such a section would contain at least the heading
    line itself).
    """
    if not heading or not file_text:
        return ""

    target_level = 0
    target_title = heading.strip()
    target_match = _HEADING_RE.match(target_title)
    if target_match:
        target_level = len(target_match.group(1))
        target_title = target_match.group(2).strip()
    target_title_lower = target_title.lower()

    lines = file_text.splitlines()
    headings = _heading_indices(lines)

    start_idx: int | None = None
    start_level = 0
    exact: int | None = None
    substring: int | None = None
    for pos, (_idx, level, title) in enumerate(headings):
        if target_level and level != target_level:
            continue
        title_lower = title.lower()
        if title_lower == target_title_lower and exact is None:
            exact = pos
        elif target_title_lower in title_lower and substring is None:
            substring = pos

    chosen_pos = exact if exact is not None else substring
    if chosen_pos is None:
        return ""

    start_idx, start_level, _ = headings[chosen_pos]

    end_idx = len(lines)
    for next_idx, level, _ in headings[chosen_pos + 1 :]:
        if level <= start_level:
            end_idx = next_idx
            break

    return "\n".join(lines[start_idx:end_idx])


def discover_section_content(
    anchor: str,
    registry: SectionAnchorRegistry,
    repo_root: Path | None = None,
) -> str:
    """Discover section content for *anchor* using the registry.

    Algorithm (per PV-05 design):
      1. Lookup the file path from the registry (raises ``KeyError``
         when the anchor is not registered — the caller is expected to
         catch this and fall back to the legacy line-based registry).
      2. Read the file content from ``repo_root / file_path`` (defaults
         to the DevolaFlow checkout root).
      3. Resolve the heading: use ``registry.heading(anchor)`` when
         present, else derive from the anchor name via
         :func:`_anchor_to_title`.
      4. Extract section content via
         :func:`extract_section_by_heading`. When the heading cannot be
         located AND the file appears to be a single-section reference
         document (e.g. ``references/behavioral-guidelines.md``), fall
         back to returning the full file content.

    Returns ``""`` when the file does not exist (caller is expected to
    treat this as an explicit not-found signal per S-5).
    """
    file_path = registry.lookup(anchor)
    root = repo_root if repo_root is not None else _REPO_ROOT
    full_path = root / file_path
    if not full_path.exists():
        logger.debug(
            "section anchor file missing: anchor=%s file=%s root=%s",
            anchor,
            file_path,
            root,
        )
        return ""

    text = full_path.read_text(encoding="utf-8")
    heading = registry.heading(anchor) or _anchor_to_title(anchor)
    extracted = extract_section_by_heading(text, heading)
    if extracted:
        return extracted

    # Single-section reference docs (e.g. references/behavioral-guidelines.md)
    # surface their entire content when the heading cannot be located —
    # that's the v8.0.0 P-08 contract for behavioral-guidelines and we
    # preserve it across the PV-05 refactor.
    if file_path.startswith("workflow-system/agent/references/"):
        return text
    return ""
