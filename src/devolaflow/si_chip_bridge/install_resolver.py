"""Si-Chip resolver — locate the Si-Chip install directory at runtime.

Search order (first match wins):

1. ``$SI_CHIP_HOME`` environment variable, if it points to a directory
   containing ``SKILL.md``.
2. ``~/.cursor/skills/si-chip/`` — the Si-Chip v0.4.0 installer's
   *documented* destination (single-level path).
3. ``~/.cursor/skills/si-chip/si-chip/`` — the Si-Chip v0.4.0
   installer's *actual* destination on Linux due to a packaging defect
   (the tarball extracts with an extra leading directory; captured in
   `.local/research/v9.5.0_gap_analysis.md` §2 + §3.2 D-S-7).
4. ``~/.claude/skills/si-chip/`` — Claude Code parallel install.
5. ``~/.claude/skills/si-chip/si-chip/`` — Claude Code nested variant
   (same upstream defect).
6. ``$DEVOLAFLOW_SI_CHIP_FALLBACK_DIR`` — operator-controlled escape
   hatch for non-standard installs (e.g. CI that pre-clones the repo).
   Honours S-7: the fallback path is supplied by the operator at runtime,
   NOT hardcoded in this module.

The resolver returns ``None`` when no candidate directory exists; the
``runner`` module then raises :class:`SiChipUnavailable` per S-5 loud
failure. This is the canonical signal for "Si-Chip is not installed,
the dogfood evaluation must be skipped" — used by both the
:mod:`devolaflow.lifecycle.post_skill_edit` hook (PV-04) and the PV-05
self-application dogfood pass.

The resolver is a pure-read function (Path.exists + Path.is_file
probes). It performs ZERO subprocess work, ZERO network IO, ZERO
yaml parsing — it ONLY checks whether candidate paths exist. This
keeps the resolver cheap to call from the lifecycle hook's hot path
and means it can be safely invoked even when Si-Chip is unlikely to
be present (e.g. CI environments without network access).

Source: v9.5.0 PV-02 — closes D-S-2 + D-S-7 from
`.local/research/v9.5.0_gap_analysis.md` §3.1 + §3.2.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

ENV_HOME: str = "SI_CHIP_HOME"
ENV_FALLBACK: str = "DEVOLAFLOW_SI_CHIP_FALLBACK_DIR"
SKILL_MD_NAME: str = "SKILL.md"


@dataclass(frozen=True)
class SiChipInstall:
    """A located Si-Chip install directory.

    Attributes
    ----------
    root : Path
        Directory containing ``SKILL.md`` (verified at construction).
    skill_md : Path
        ``root / "SKILL.md"`` for convenience.
    scripts_dir : Path | None
        ``root / "scripts"`` if the directory exists; else ``None``.
        Set to ``None`` when the resolver finds a partial install
        (SKILL.md present but scripts missing) — surfaced loudly by the
        runner.
    references_dir : Path | None
        ``root / "references"`` if the directory exists; else ``None``.
    source : str
        Which candidate path matched. One of ``"env_home"``,
        ``"cursor_global"``, ``"cursor_global_nested"``,
        ``"claude_global"``, ``"claude_global_nested"``,
        ``"env_fallback"``. Used by debug logs and the PV-05 dogfood
        run-log to record provenance.
    """

    root: Path
    skill_md: Path
    scripts_dir: Path | None
    references_dir: Path | None
    source: str

    def script_path(self, script_name: str) -> Path | None:
        """Return ``scripts_dir / script_name`` if both exist; else ``None``.

        Used by :mod:`devolaflow.si_chip_bridge.runner` to locate
        ``profile_static.py``, ``count_tokens.py``, ``aggregate_eval.py``
        before invoking them via subprocess.
        """
        if self.scripts_dir is None:
            return None
        candidate = self.scripts_dir / script_name
        if not candidate.is_file():
            return None
        return candidate


def _candidate_dirs() -> Iterator[tuple[str, Path]]:
    """Yield ``(source, candidate_dir)`` tuples in resolver priority order.

    Each tuple is checked at runtime by :func:`find_si_chip_install`; the
    first one whose ``SKILL.md`` is present wins. Authors adding new
    candidate paths MUST append at the END to preserve the documented
    priority order (operator surface stability).
    """
    home = Path.home()

    env_home = os.environ.get(ENV_HOME, "").strip()
    if env_home:
        yield "env_home", Path(env_home)

    yield "cursor_global", home / ".cursor" / "skills" / "si-chip"
    yield "cursor_global_nested", home / ".cursor" / "skills" / "si-chip" / "si-chip"
    yield "claude_global", home / ".claude" / "skills" / "si-chip"
    yield "claude_global_nested", home / ".claude" / "skills" / "si-chip" / "si-chip"

    env_fallback = os.environ.get(ENV_FALLBACK, "").strip()
    if env_fallback:
        yield "env_fallback", Path(env_fallback)


def find_si_chip_install() -> SiChipInstall | None:
    """Locate the Si-Chip install directory or return ``None``.

    See module docstring for the search order. Returns ``None`` when
    none of the candidate paths exist OR none contain ``SKILL.md``.
    Callers (the runner module) translate ``None`` into a loud
    :class:`SiChipUnavailable` per S-5.

    Notes
    -----
    The resolver does NOT validate the SKILL.md content (no YAML parse,
    no version check). Validation is the runner's job — keeps resolver
    cheap + side-effect-free.
    """
    for source, candidate in _candidate_dirs():
        skill_md = candidate / SKILL_MD_NAME
        if not skill_md.is_file():
            logger.debug(
                "si_chip_bridge.install_resolver: candidate %r at %s missing SKILL.md",
                source,
                candidate,
            )
            continue
        scripts_dir = candidate / "scripts"
        references_dir = candidate / "references"
        return SiChipInstall(
            root=candidate,
            skill_md=skill_md,
            scripts_dir=scripts_dir if scripts_dir.is_dir() else None,
            references_dir=references_dir if references_dir.is_dir() else None,
            source=source,
        )
    return None


__all__ = [
    "ENV_FALLBACK",
    "ENV_HOME",
    "SKILL_MD_NAME",
    "SiChipInstall",
    "find_si_chip_install",
]
