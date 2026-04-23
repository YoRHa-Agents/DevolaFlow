"""Single source of truth for the RTK shell-proxy whitelist (v8.3.2 PV-02).

Mirrors the design pattern of RTK's own ``src/discover/registry.rs``
(Rust source, single-source-of-truth for all rewrite rules) per
``.local/research/v8.4.0_rtk_nines_analysis.md`` §4.1 — one module owns
the regex + tier mapping; the proxy + the hook delegate to it.

Tier model (matches the SI-2 §6.1 whitelist table — verbatim):

* **Tier 1 (default whenever the proxy is enabled):** the 5 commands
  the W-9 / SI-10 6-step gate exercises every PV (`pytest`, `ruff
  check`, `git diff`, `git log`, `git status`) — these have the
  highest cumulative token impact across DevolaFlow workflows.
* **Tier 2 (opt-in via ``DEVOLAFLOW_RTK_PROXY_TIER2=1``):** larger /
  less verbose-by-default commands (`git add`, `git commit`, `git
  show`, `cargo test`, `npm test`, `make`).

R5 strict: when the proxy is OFF, the registry is purely declarative —
:func:`match_command` is never reached because :class:`ShellProxy`
short-circuits on the env-flag check. See
``.local/research/v8.4.0_gap_analysis.md`` §2.1 R-002.

Rationale for the regex precision (per task spec):

* ``pytest tests/...`` matches but ``pytest-style-runner`` does NOT
  (anchor: ``^pytest($|\\s)``).
* ``git diff`` matches but ``git diffshow`` does NOT (anchor: subcommand
  followed by EOL, whitespace, or a flag).
* ``ruff check`` matches but ``ruff-check-helper`` does NOT (the same
  anchor pattern protects ruff).
"""

from __future__ import annotations

import re
from typing import Literal

Tier = Literal[1, 2]
"""Whitelist tier — Tier 1 ships default-on (when proxy enabled); Tier 2
requires the secondary opt-in flag ``DEVOLAFLOW_RTK_PROXY_TIER2=1``."""


WHITELIST: dict[str, Tier] = {
    # Tier 1 — W-9 / SI-10 6-step gate commands (highest cumulative impact)
    "pytest": 1,
    "ruff check": 1,
    "git diff": 1,
    "git log": 1,
    "git status": 1,
    # Tier 2 — opt-in via DEVOLAFLOW_RTK_PROXY_TIER2=1 per task spec
    "git add": 2,
    "git commit": 2,
    "git show": 2,
    "cargo test": 2,
    "npm test": 2,
    "make": 2,
}
"""Whitelist mapping — command prefix → tier. Single source of truth.

Adding a new entry here is the ONLY surface that needs to change to
extend the proxy whitelist. The proxy + the hook + the tests all read
from this dict. Mirrors RTK's ``RULES`` / ``IGNORED_EXACT`` /
``IGNORED_PREFIXES`` triplet under ``src/discover/rules.rs`` — one
table, all consumers delegate.
"""


def _build_pattern(prefix: str) -> re.Pattern[str]:
    """Return a precompiled anchored regex for *prefix*.

    The pattern matches when *prefix* appears at the start of the
    command followed by either end-of-string OR whitespace. This
    deliberately excludes:

    * Hyphen continuations (``pytest-style-runner`` does NOT match
      ``pytest`` — the next character would be ``-``, not whitespace).
    * Subcommand glue (``git diffshow`` does NOT match ``git diff`` —
      the next character would be ``s``, not whitespace).
    * Flag attachments (``pytest-x`` does NOT match — but ``pytest -x``
      DOES; the second case is the desired Tier 1 invocation).

    The prefix itself may contain whitespace (e.g. ``"git diff"``),
    in which case the internal whitespace is matched literally.
    """
    return re.compile(rf"^{re.escape(prefix)}($|\s)")


# Precompiled pattern cache — built once at import time, not per-call.
_COMPILED_PATTERNS: dict[str, re.Pattern[str]] = {
    prefix: _build_pattern(prefix) for prefix in WHITELIST
}


def match_command(cmd: str, *, tier2_enabled: bool = False) -> Tier | None:
    """Return the tier for *cmd*, or ``None`` if not whitelisted / out-of-tier.

    Tier 2 entries are returned ONLY when *tier2_enabled* is True; with
    the default (Tier 2 opt-out), a Tier 2 command returns ``None``
    so the caller passes it through unchanged. Tier 1 entries always
    match when the prefix anchor is satisfied.

    Longest-prefix-wins: ``git diff --stat`` matches ``git diff`` (Tier
    1), NOT ``git`` (which is not in the registry). The caller does NOT
    need to know about overlap because the registry is hand-curated and
    each entry's prefix is non-overlapping with every other (e.g.
    there is no bare ``git`` entry — only ``git diff`` / ``git log`` /
    ``git status`` / ``git add`` / ``git commit`` / ``git show``).
    """
    if not isinstance(cmd, str) or not cmd:
        return None

    # Sort by prefix length descending so the longest-matching prefix wins
    # in the rare case where two prefixes share a common head (defensive —
    # the current registry is non-overlapping but the iteration order
    # would otherwise depend on dict insertion).
    for prefix in sorted(WHITELIST, key=len, reverse=True):
        if _COMPILED_PATTERNS[prefix].match(cmd):
            tier = WHITELIST[prefix]
            if tier == 2 and not tier2_enabled:
                return None
            return tier

    return None


__all__ = ["WHITELIST", "Tier", "match_command"]
