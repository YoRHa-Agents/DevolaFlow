"""Init-chain dependency tiering + unified capability probe (Track C-4).

R5 F4 root cause (full_review_and_improve): the init/scaffold chain
implicitly depended on external tools (node/npm for codegraph and curl for
remote install) and surfaced their absence DEEP in the flow with
low-signal errors — the user-visible symptom was "固定脚本无法生成".

This module is the SINGLE OWNER (A-5 discipline) of the init-chain
dependency tier table and the unified pre-flight probe:

* ``required`` — missing means the init entry point reports one explicit
  error UP FRONT and exits (S-5); nothing is scaffolded half-way.
* ``optional`` — missing means a documented degraded path; the probe
  prints exactly ONE hint line per missing dependency, never a stack
  trace mid-flow.
* ``situational`` — needed only for specific entry points (e.g. ``curl``
  for the remote ``install.sh`` path); absence is informational.

Per-plugin RICH probes stay in their owner modules
(:func:`devolaflow.codegraph.is_codegraph_available`) — this module performs a uniform
``$PATH`` presence scan for the init capability table only; it never
invokes any binary (zero subprocess, hot-path safe).

Stdlib-only by design (Track C-4 dependency-minimisation principle —
the deterministic init chain must not add third-party imports).
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass

_VALID_TIERS: frozenset[str] = frozenset({"required", "optional", "situational"})


@dataclass(frozen=True)
class DependencySpec:
    """One init-chain external dependency and its degradation contract."""

    name: str
    tier: str  # "required" | "optional" | "situational"
    purpose: str
    absent_hint: str  # the ONE line shown when the binary is missing


# The init-chain dependency tier table (Track C-4 D-12). Single owner:
# consumers (install_local / doctor / tests) import THIS tuple — a second
# hand-maintained dependency list anywhere in the init chain is a
# regression (same anti-second-list discipline as the C-2 structure
# contract).
INIT_DEPENDENCIES: tuple[DependencySpec, ...] = (
    DependencySpec(
        name="git",
        tier="required",
        purpose="repo detection + gitignore semantics + branch workflow (S-6)",
        absent_hint="install git (e.g. `apt install git` / `brew install git`) and re-run",
    ),
    DependencySpec(
        name="node",
        tier="optional",
        purpose="runtime for the codegraph CLI (npm-distributed)",
        absent_hint="codegraph index unavailable — analyze degrades to Read/Glob/Grep",
    ),
    DependencySpec(
        name="npm",
        tier="optional",
        purpose="installs @colbymchenry/codegraph when opted in",
        absent_hint="`npm i -g @colbymchenry/codegraph` unavailable — codegraph stays absent",
    ),
    DependencySpec(
        name="codegraph",
        tier="optional",
        purpose="pre-indexed code knowledge graph (suggest-tier per Track C-3 D-11)",
        absent_hint="skipping codegraph init — `npm i -g @colbymchenry/codegraph` to enable",
    ),
    DependencySpec(
        name="curl",
        tier="situational",
        purpose="remote `install.sh` download path only (local pip installs don't need it)",
        absent_hint="remote install.sh unavailable — use `pip install -e .` from a clone",
    ),
)


# Import-time tier validation (mirrors detect_dead_apis'
# _check_allowlist_domain_overlap pattern): a typo'd tier would silently
# bypass the required-gate — fail loudly instead (S-5).
for _spec in INIT_DEPENDENCIES:
    if _spec.tier not in _VALID_TIERS:
        raise ValueError(
            f"INIT_DEPENDENCIES: {_spec.name!r} declares invalid tier {_spec.tier!r}; "
            f"valid tiers: {sorted(_VALID_TIERS)}"
        )


@dataclass(frozen=True)
class CapabilityFinding:
    """Probe result for one dependency."""

    spec: DependencySpec
    present: bool
    resolved_path: str | None


class MissingRequiredDependencyError(RuntimeError):
    """A required init-chain dependency is absent (S-5 explicit up-front error)."""


def probe_capabilities() -> list[CapabilityFinding]:
    """Scan ``$PATH`` once for every registered init-chain dependency.

    Pure ``shutil.which`` presence scan — no subprocess, no file IO
    beyond the PATH lookup. Order follows :data:`INIT_DEPENDENCIES`
    (required first) so the rendered table reads top-down by severity.
    """
    findings: list[CapabilityFinding] = []
    for spec in INIT_DEPENDENCIES:
        path = shutil.which(spec.name)
        findings.append(CapabilityFinding(spec=spec, present=path is not None, resolved_path=path))
    return findings


def missing_required(findings: list[CapabilityFinding]) -> list[CapabilityFinding]:
    """Return the required-tier findings whose binary is absent."""
    return [f for f in findings if f.spec.tier == "required" and not f.present]


def format_capability_table(findings: list[CapabilityFinding]) -> str:
    """Render the capability table (one line per dependency, one hint per gap).

    Missing optional/situational dependencies get their single
    ``absent_hint`` line inline — the acceptance contract is "one clear
    hint instead of a deep stack trace" per missing dependency.
    """
    lines = ["  Capability probe (init chain):"]
    for f in findings:
        status = f"ok ({f.resolved_path})" if f.present else f"missing — {f.spec.absent_hint}"
        lines.append(f"    {f.spec.tier:<12} {f.spec.name:<10} {status}")
    return "\n".join(lines)


def assert_required_present(findings: list[CapabilityFinding]) -> None:
    """Raise :class:`MissingRequiredDependencyError` when a required dep is absent.

    The message enumerates every missing required dependency with its
    hint so the operator fixes ALL of them in one pass (S-5 — explicit,
    up-front, before any scaffold write).
    """
    gaps = missing_required(findings)
    if not gaps:
        return
    details = "; ".join(f"{f.spec.name} ({f.spec.absent_hint})" for f in gaps)
    raise MissingRequiredDependencyError(
        f"required init dependency missing: {details}. "
        "Nothing was scaffolded — fix the dependency and re-run."
    )


__all__ = [
    "INIT_DEPENDENCIES",
    "CapabilityFinding",
    "DependencySpec",
    "MissingRequiredDependencyError",
    "assert_required_present",
    "format_capability_table",
    "missing_required",
    "probe_capabilities",
]
