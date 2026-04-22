"""Agent legibility scoring (v8.2.0 PV-02).

Pure-function code-quality intelligence for the gate suite. Three
sub-scorers (naming consistency / comment-to-code ratio / cyclomatic
flow) yield a 0-100 legibility score per file. Designed to plug into
:func:`devolaflow.gate.scorer.evaluate_gate` as an *opt-in* dimension —
when ``legibility_enabled=False`` (the default in STANDARD/RELAXED
profiles, controlled by ``GateProfile.legibility_weight == 0.0``), the
scorer is never invoked and the gate output is byte-identical to the
v8.1.0-rc.1 baseline (per ``.local/research/v8.2.0_patch_plan.md`` §3
PV-02 AC-2 / AC-5).

Design notes
------------
* No LLM, no subprocess, no network — strictly deterministic so the
  scorer inherits the same "deterministic primitive" character as the
  v8.0.0 gate primitives (P-04 fence, P-05 ladder, P-07 ratchet,
  P-09 complexity_detector).
* `radon` powers the cyclomatic flow sub-scorer when available; an
  indentation-based heuristic is used as a graceful fallback so the
  module remains importable on installations that omit the optional
  dependency (S-5 No Silent Failures: the report flags the fallback
  via the ``cyclomatic_method`` finding).
* Naming-convention recognition is file-extension driven: snake_case
  for ``.py`` / ``.pyi``, camelCase / PascalCase for JS/TS, kebab-case
  for filenames in ``.md`` / ``.yaml`` / ``.yml``.

Public surface (re-exported from the package root):

* :class:`LegibilityScorer` — entry point with ``score(file_path)``.
* :class:`LegibilityReport` — 0-100 score plus the 3 dimension
  breakdown and human-readable findings list.
"""

from devolaflow.legibility.scorer import (
    DEFAULT_DIMENSION_WEIGHTS,
    LegibilityReport,
    LegibilityScorer,
)

__all__ = [
    "DEFAULT_DIMENSION_WEIGHTS",
    "LegibilityReport",
    "LegibilityScorer",
]
