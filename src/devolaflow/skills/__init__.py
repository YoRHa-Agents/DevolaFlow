"""DevolaFlow operator-facing skill surfaces (v9.1.2 PV-02+).

This package bundles thin CLI / heuristic surfaces consumed by the
operator and by L0 dispatchers when steering toward the
``change-driven`` workflow:

* :mod:`devolaflow.skills.change_activation` — pure-function
  complexity classifier + activation verdict (the heuristic codified
  by Architecture rule **A-6** "Workspace Engagement Auto-Activation"
  per ``.rules/architecture.mdc``).
* :mod:`devolaflow.skills.slash_commands` — ``/devola:propose``,
  ``/devola:apply``, ``/devola:verify``, ``/devola:archive`` thin
  wrappers around the existing
  :class:`devolaflow.agent_workspace.ChangeStore` /
  :class:`devolaflow.agent_workspace.ArchiveManager` APIs (closes
  M-007 from the v9.0.0 retrospective §3.3 — operator-facing slash
  command surface was telegraphed for v9.1.x).

Both modules are R5-strict additive:

* No existing public symbol is mutated.
* No new top-level dispatch key lands in
  ``schemas/lean-dispatch.yaml#layout_invariant`` (the heuristic is
  prompt-side only — A-2 invariant intact).
* The slash commands use ``argparse`` exit codes (``0`` happy path,
  non-zero on failure); errors are logged + re-raised per S-5
  (no silent failures).

Per W-20 (env-flag reuse-first), the activation surface honoured by
:mod:`change_activation` REUSES the existing
``DEVOLAFLOW_AGENT_WORKSPACE`` env flag (introduced by v9.1.1 PV-01
SKILL.md §"Workspace Engagement (Read at Session Start)") rather than
introducing a new flag. The same flag will be REUSED by the v9.1.3
PV-03 ``pre_handoff`` lifecycle hook so the activation contract stays
single-surface.

Source: v9.2.0 cycle plan §PV-02 — ``.cursor/plans/workspace-
capability-activation_ec560bc8.plan.md``.
"""

from __future__ import annotations

__all__: list[str] = []
