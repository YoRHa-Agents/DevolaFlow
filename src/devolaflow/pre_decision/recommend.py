"""Workflow type auto-recommendation engine.

Design ref: design_meta_framework.md §6
"""

from __future__ import annotations

from dataclasses import dataclass, field

# ── Data tables ──────────────────────────────────────────────────────────

WORKFLOW_KEYWORDS: dict[str, dict[str, list[str]]] = {
    "research-only": {
        "primary": [
            "research",
            "compare",
            "evaluate",
            "survey",
            "investigate",
            "benchmark",
            "analysis",
        ],
        "secondary": ["alternatives", "options", "tradeoffs", "best"],
        "negative": ["implement", "build", "code", "deploy"],
    },
    "design-only": {
        "primary": ["design", "architect", "schema", "wireframe"],
        "secondary": ["specification", "blueprint", "diagram", "api"],
        "negative": ["code", "deploy", "fix", "test", "research"],
    },
    "hotfix": {
        "primary": [
            "fix",
            "bug",
            "broken",
            "error",
            "crash",
            "incident",
            "sev1",
            "sev2",
            "regression",
            "hotfix",
        ],
        "secondary": ["production", "urgent", "patch", "emergency"],
        "negative": ["design", "research", "plan", "feature"],
    },
    "refactoring": {
        "primary": ["refactor", "restructure", "simplify", "clean up", "tech debt"],
        "secondary": [
            "complexity",
            "coupling",
            "duplication",
            "smell",
            "separation",
            "improve",
        ],
        "negative": ["new feature", "new project", "deploy"],
    },
    "migration": {
        "primary": ["migrate", "upgrade", "convert", "port", "transition", "move", "replace"],
        "secondary": ["legacy", "deprecated", "compatibility", "from"],
        "negative": [],
    },
    "spike-poc": {
        "primary": [
            "try",
            "experiment",
            "prototype",
            "spike",
            "proof of concept",
            "is it possible",
        ],
        "secondary": ["risk", "unknown", "feasibility"],
        "negative": ["production", "deploy", "release"],
    },
    "documentation-only": {
        "primary": ["document", "docs", "readme", "tutorial", "guide", "api reference"],
        "secondary": ["onboarding", "changelog", "release notes", "update"],
        "negative": ["implement", "code", "fix"],
    },
    "security-audit": {
        "primary": [
            "security",
            "vulnerability",
            "audit",
            "cve",
            "penetration",
            "compliance",
            "sast",
            "dast",
        ],
        "secondary": ["threat", "remediate", "dependencies"],
        "negative": ["new feature"],
    },
    "feature-enhancement": {
        "primary": ["extend", "enhance", "additional"],
        "secondary": ["modify", "expand", "existing", "endpoint", "add"],
        "negative": ["new project", "from scratch"],
    },
    "performance-optimization": {
        "primary": [
            "slow",
            "performance",
            "optimize",
            "bottleneck",
            "latency",
            "throughput",
            "memory",
        ],
        "secondary": ["profile", "benchmark", "cache", "improve", "better"],
        "negative": ["new feature"],
    },
    "research-design-review-refine": {
        "primary": ["system design", "architecture decision", "research then design"],
        "secondary": ["adr", "design review", "iterate design", "design", "research"],
        "negative": ["implement", "code", "deploy"],
    },
    "full-pipeline": {
        "primary": [
            "from scratch",
            "new project",
            "implement feature",
            "full development",
            "end to end",
        ],
        "secondary": ["greenfield", "build"],
        "negative": [],
    },
}

_URGENCY_TOKENS = {"urgent", "immediately", "asap", "production down"}
_FROM_SCRATCH_PHRASES = ["from scratch", "new project", "greenfield"]
_QUESTION_PREFIXES = ("what ", "how ", "which ", "should we ", "can we ")
_WORKFLOW_TYPE_NAMES = set(WORKFLOW_KEYWORDS.keys())

# ── Scoring helpers ──────────────────────────────────────────────────────

_NORM_K = 0.7  # saturation constant for score normalisation


def _kw_in_text(kw: str, text_words: set[str]) -> bool:
    """True when *kw* (single word) appears in *text_words* or as a prefix."""
    if kw in text_words:
        return True
    return any(w.startswith(kw) for w in text_words)


def _phrase_matches(phrase: str, text_words: set[str]) -> bool:
    """True when every word of *phrase* is found (or prefix-found) in *text_words*."""
    return all(_kw_in_text(w, text_words) for w in phrase.split())


def _score_workflow(
    text_lower: str,
    text_words: set[str],
    keywords: dict[str, list[str]],
) -> tuple[float, int, int, int]:
    """Return (raw_score, primary_hits, secondary_hits, negative_hits)."""
    primary = sum(1 for k in keywords["primary"] if _phrase_matches(k, text_words))
    secondary = sum(1 for k in keywords["secondary"] if _phrase_matches(k, text_words))
    negative = sum(1 for k in keywords["negative"] if _phrase_matches(k, text_words))
    raw = primary * 1.0 + secondary * 0.5 + negative * (-0.5)
    return raw, primary, secondary, negative


def _score_all_workflows(
    text_lower: str,
    text_words: set[str],
) -> tuple[dict[str, float], dict[str, list[str]]]:
    """Score every workflow type and collect matched keywords."""
    raw_scores: dict[str, float] = {}
    matched_kws: dict[str, list[str]] = {}
    for wf_type, keywords in WORKFLOW_KEYWORDS.items():
        raw, _p, _s, _n = _score_workflow(text_lower, text_words, keywords)
        raw_scores[wf_type] = raw
        matched_kws[wf_type] = [
            k
            for group in ("primary", "secondary")
            for k in keywords[group]
            if _phrase_matches(k, text_words)
        ]
    return raw_scores, matched_kws


# ── Heuristic boosts (§6.3) ─────────────────────────────────────────────


def _boost_urgency(text_words: set[str], raw_scores: dict[str, float]) -> None:
    """R1 — urgency tokens boost hotfix."""
    if text_words & _URGENCY_TOKENS:
        raw_scores["hotfix"] = raw_scores.get("hotfix", 0) + 0.3


def _boost_from_scratch(text_words: set[str], raw_scores: dict[str, float]) -> None:
    """R2 — 'from scratch' / 'new project' / 'greenfield' boost full-pipeline."""
    for phrase in _FROM_SCRATCH_PHRASES:
        if _phrase_matches(phrase, text_words):
            raw_scores["full-pipeline"] = raw_scores.get("full-pipeline", 0) + 0.4
            return


def _boost_question_form(text_lower: str, raw_scores: dict[str, float]) -> None:
    """R3 — question-form input boosts research-only."""
    if any(text_lower.startswith(p) for p in _QUESTION_PREFIXES):
        raw_scores["research-only"] = raw_scores.get("research-only", 0) + 0.2


def _boost_multi_match(raw_scores: dict[str, float]) -> None:
    """R4 — matching >= 3 types boosts full-pipeline."""
    positive = sum(1 for v in raw_scores.values() if v > 0)
    if positive >= 3:
        raw_scores["full-pipeline"] = raw_scores.get("full-pipeline", 0) + 0.1


def _boost_explicit_name(text_words: set[str], raw_scores: dict[str, float]) -> None:
    """R5 — explicit workflow-type name in text gets a strong boost."""
    for wf_name in _WORKFLOW_TYPE_NAMES:
        name_words = set(wf_name.replace("-", " ").replace("_", " ").split())
        if name_words.issubset(text_words):
            raw_scores[wf_name] = raw_scores.get(wf_name, 0) + 1.0


def _apply_heuristics(
    text_lower: str,
    text_words: set[str],
    raw_scores: dict[str, float],
) -> None:
    """Mutate *raw_scores* with heuristic boosts (§6.3)."""
    _boost_urgency(text_words, raw_scores)
    _boost_from_scratch(text_words, raw_scores)
    _boost_question_form(text_lower, raw_scores)
    _boost_multi_match(raw_scores)
    _boost_explicit_name(text_words, raw_scores)


def _normalise(raw: float) -> float:
    """Saturating normalisation: raw / (raw + K), clipped to [0, 1]."""
    if raw <= 0:
        return 0.0
    return min(1.0, raw / (raw + _NORM_K))


def confidence_level(score: float) -> str:
    """Map a normalised score to High / Medium / Low / None (§6.4)."""
    if score >= 0.65:
        return "high"
    if score >= 0.30:
        return "medium"
    if score >= 0.10:
        return "low"
    return "none"


# ── Public API ───────────────────────────────────────────────────────────


@dataclass
class Recommendation:
    """Represent a scored workflow-type recommendation with matched keywords."""

    workflow_type: str
    score: float  # normalised 0-1
    confidence: str  # high | medium | low | none
    matched_keywords: list[str] = field(default_factory=list)


# ── Candidate building ───────────────────────────────────────────────────


def _build_candidates(
    raw_scores: dict[str, float],
    matched_kws: dict[str, list[str]],
) -> list[Recommendation]:
    """Convert raw scores into sorted Recommendation list."""
    candidates: list[Recommendation] = []
    for wf_type, raw in raw_scores.items():
        score = _normalise(raw)
        if score > 0:
            candidates.append(
                Recommendation(
                    workflow_type=wf_type,
                    score=round(score, 3),
                    confidence=confidence_level(score),
                    matched_keywords=matched_kws.get(wf_type, []),
                )
            )
    candidates.sort(key=lambda r: r.score, reverse=True)
    return candidates


def _inject_fallback(candidates: list[Recommendation]) -> list[Recommendation]:
    """When top confidence is low/none, inject full-pipeline as a safe fallback."""
    top_conf = candidates[0].confidence if candidates else "none"
    if top_conf not in ("low", "none"):
        return candidates
    fp_exists = any(c.workflow_type == "full-pipeline" for c in candidates)
    if not fp_exists:
        candidates.append(
            Recommendation(
                workflow_type="full-pipeline",
                score=0.1,
                confidence="low",
                matched_keywords=[],
            )
        )
    candidates.sort(key=lambda r: r.score, reverse=True)
    return candidates


def recommend_workflow(
    purpose: str,
    context: dict[str, object] | None = None,
) -> list[Recommendation]:
    """Return top-3 workflow-type candidates sorted by score (§6.1-§6.4).

    *context* is reserved for future structured signals (repo mode, language, etc.).
    """
    if context is None:
        context = {}
    text_lower = purpose.lower()
    text_words = set(text_lower.split())

    raw_scores, matched_kws = _score_all_workflows(text_lower, text_words)
    _apply_heuristics(text_lower, text_words, raw_scores)
    candidates = _build_candidates(raw_scores, matched_kws)
    candidates = _inject_fallback(candidates)
    return candidates[:3]
