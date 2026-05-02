"""Naturalness scorer — the production port of the PV-01 probe.

Ports ``.local/research/v10.1.0_aivoice_probe.py`` feature extraction
and composite scoring into a stable, stdlib-only, production module.
The probe's aggregate on the DevolaFlow corpus was 69.958 against
human-clean 71.02. The port must reproduce the probe's per-doc scores
within rounding (this is pinned by the PV-05 pre-transform baseline
matching the PV-01 baseline within ±0.1).

Public API:

* ``score_text(text, profile, *, is_editorial=False) -> NaturalnessScore``
* ``score_corpus(items, profile_fn) -> CorpusScore``
* ``NaturalnessScore`` — composite + per-feature sub-scores + raw features

Design ref: v10.1.0 PV-01 research §4 (metric formula) +
``.local/research/v10.1.0_aivoice_probe.py::_compute_naturalness``.
"""

from __future__ import annotations

import re
import statistics
from collections import Counter
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field

from .errors import StyleError
from .profiles import ToneProfile

AI_TIER1: frozenset[str] = frozenset(
    {
        "delve",
        "delves",
        "delving",
        "tapestry",
        "landscape",
        "paradigm",
        "leverage",
        "leverages",
        "leveraging",
        "harness",
        "harnesses",
        "harnessing",
        "navigate",
        "navigating",
        "realm",
        "embark",
        "embarks",
        "embarking",
        "myriad",
        "plethora",
        "multifaceted",
        "groundbreaking",
        "revolutionize",
        "revolutionizes",
        "synergy",
        "ecosystem",
        "resonate",
        "resonates",
        "streamline",
        "streamlines",
        "streamlined",
        "testament",
        "enduring",
    }
)

AI_TIER2: frozenset[str] = frozenset(
    {
        "robust",
        "seamless",
        "seamlessly",
        "cutting-edge",
        "innovative",
        "innovate",
        "innovation",
        "comprehensive",
        "comprehensively",
        "pivotal",
        "nuanced",
        "compelling",
        "transformative",
        "bolster",
        "bolsters",
        "underscore",
        "underscores",
        "underscoring",
        "evolving",
        "fostering",
        "imperative",
        "intricate",
        "overarching",
        "unprecedented",
        "vibrant",
        "profound",
        "renowned",
        "stunning",
        "showcasing",
        "showcases",
        "exemplifies",
        "exemplify",
        "garner",
        "garners",
        "valuable",
        "ensures",
        "ensuring",
        "highlights",
        "supports",
        "reflects",
        "significantly",
        "effectively",
        "directly",
    }
)

SIGNPOSTS: tuple[str, ...] = (
    r"\bit'?s worth noting\b",
    r"\bit'?s important to note\b",
    r"\bit'?s crucial to (?:understand|note)\b",
    r"\bit bears mentioning\b",
    r"\bin today'?s (?:fast-paced|digital|competitive|rapidly|complex)\b",
    r"\bat its core\b",
    r"\bat the end of the day\b",
    r"\bwhen all is said and done\b",
    r"\bwhile there are certainly\b",
    r"\bto be sure\b",
    r"\bthat said\b",
    r"\bthis is not without\b",
    r"\bit remains to be seen\b",
    r"\bthe bottom line is\b",
    r"\bonly time will tell\b",
    r"\bthe future is bright\b",
    r"\bexciting times lie ahead\b",
    r"\bin order to\b",
    r"\bdue to the fact that\b",
    r"\bat this point in time\b",
    r"\bin the event that\b",
    r"\bhas the ability to\b",
    r"\bgreat question\b",
    r"\bcertainly[!]\b",
    r"\babsolutely[!]\b",
    r"\bi hope this helps\b",
    r"\blet me know if you'?d like\b",
    r"\bin conclusion\b",
    r"\bto sum up\b",
    r"\bin summary\b",
    r"\bmoreover\b",
    r"\bfurthermore\b",
    r"\b(?:additionally|also,)\b",
    r"\b(?:notably|importantly|interestingly|crucially),\b",
    r"\bdespite (?:these )?challenges\b",
    r"\blet'?s (?:break this down|unpack|explore|dive in|delve)\b",
    r"\bhere'?s (?:the thing|what i find|the kicker|the deal|why|where it gets)\b",
    r"\bimagine a world where\b",
    r"\bthink of it (?:as|like)\b",
    r"\bnavigating (?:the|this)\b",
    r"\bhighlighting the\b",
    r"\bunderscoring the\b",
    r"\breflecting (?:the|broader)\b",
    r"\bemphasizing the\b",
)

NEG_PARALLELISM: tuple[str, ...] = (
    r"\bnot just\b[^.\n]{1,80}\bbut (?:also)?\b",
    r"\bisn'?t (?:about )?\b[^.\n]{1,40}\b(?:it'?s|but) \b",
    r"\bnot only\b[^.\n]{1,80}\bbut also\b",
    r"\bit'?s not (?:about|just)\b[^.\n]{1,80}\bit'?s\b",
    r"\b(?:the answer|the question|the problem) isn'?t\b[^.\n]{0,40}\bit'?s\b",
    r"\bnot \w+\.\s+not \w+\.\s+(?:just |it'?s )?\w+",
)

COPULA_DODGES: tuple[str, ...] = (
    r"\bserves? as\b",
    r"\bstands? as\b",
    r"\brepresents? (?:a |the |an )\b",
    r"\bmarks? (?:a |the |an )\b",
    r"\bboasts? (?:a |the |an |\d)\b",
    r"\bfeatures? (?:a |the |an |\d)\b",
    r"\boffers? (?:a |the |an )\b",
)


_FENCED_CODE_RE = re.compile(r"```.*?```", re.DOTALL)
_INLINE_CODE_RE = re.compile(r"`[^`\n]+`")
_HTML_SCRIPT_STYLE_RE = re.compile(
    r"<(?:script|style)\b[^>]*>.*?</(?:script|style)>", re.DOTALL | re.IGNORECASE
)
_HTML_TAG_RE = re.compile(r"<[^>]+>")
_URL_RE = re.compile(r"https?://\S+")
_SENT_SPLIT_RE = re.compile(r"(?<=[.!?。！？])\s+(?=[A-Z\u4e00-\u9fa5])")
_WORD_RE = re.compile(r"[A-Za-z][A-Za-z'-]+")
_CJK_RE = re.compile(r"[\u4e00-\u9fa5]")
_HEADER_RE = re.compile(r"^\s*#{1,6}\s+\S", re.MULTILINE)
_BULLET_RE = re.compile(r"^\s*(?:[-*+]\s+|\d+\.\s+)\S", re.MULTILINE)
_BOLD_RE = re.compile(r"\*\*[^*\n]{1,80}\*\*")
_EMDASH_RE = re.compile(r"\u2014|(?<!-)--(?!-)")
_TABLE_ROW_RE = re.compile(r"^\s*\|.*\|\s*$", re.MULTILINE)
_TABLE_SEP_RE = re.compile(r"^\s*\|[\s\-:|]+\|\s*$", re.MULTILINE)
_MD_QUOTE_LINE_RE = re.compile(r"^\s*>\s.*$", re.MULTILINE)

_SIGNPOST_PATTERNS = tuple(re.compile(p) for p in SIGNPOSTS)
_NEG_PARALLEL_PATTERNS = tuple(re.compile(p) for p in NEG_PARALLELISM)
_COPULA_PATTERNS = tuple(re.compile(p) for p in COPULA_DODGES)


@dataclass(frozen=True)
class RawFeatures:
    """Feature extraction result before composite scoring."""

    chars: int
    words: int
    cjk_chars: int
    en_words: int
    sentences: int
    paragraphs: int
    avg_sent_len: float
    sent_len_stddev: float
    burstiness: float
    ttr: float
    headers: int
    bullets: int
    nonblank_lines: int
    header_ratio: float
    bullet_ratio: float
    bold_count: int
    emdash_count: int
    tier1_count: int
    tier2_count: int
    signposts_count: int
    neg_parallel_count: int
    copula_count: int
    bold_per_1k: float
    emdash_per_1k: float
    tier1_per_1k: float
    tier2_per_1k: float
    signposts_per_1k: float
    neg_parallel_per_1k: float
    copula_dodge_per_1k: float


@dataclass(frozen=True)
class NaturalnessScore:
    """Composite + sub-scores + raw features for one document."""

    composite: float
    features: RawFeatures
    per_feature_subscores: Mapping[str, float]
    profile_name: str

    @property
    def naturalness(self) -> float:
        return self.composite


@dataclass(frozen=True)
class CorpusScore:
    """Aggregate score across a set of documents."""

    aggregate_naturalness: float
    per_doc: dict[str, NaturalnessScore] = field(default_factory=dict)
    word_total: int = 0


def _strip_code_and_html(text: str) -> str:
    text = _HTML_SCRIPT_STYLE_RE.sub(" ", text)
    text = _FENCED_CODE_RE.sub(" ", text)
    text = _INLINE_CODE_RE.sub(" ", text)
    text = _HTML_TAG_RE.sub(" ", text)
    text = _URL_RE.sub(" ", text)
    return text


def _strip_quoted_examples(text: str) -> str:
    text = _MD_QUOTE_LINE_RE.sub(" ", text)
    text = _TABLE_SEP_RE.sub(" ", text)
    text = _TABLE_ROW_RE.sub(" ", text)
    return text


def _split_sentences(text: str) -> list[str]:
    parts = _SENT_SPLIT_RE.split(text)
    return [p.strip() for p in parts if p.strip()]


def _tokens(text: str) -> list[str]:
    return [t.lower() for t in _WORD_RE.findall(text)]


def _sliding_ttr(tokens: list[str], window: int = 200) -> float:
    """Length-controlled TTR: mean TTR over non-overlapping windows."""
    if len(tokens) < window:
        return len(set(tokens)) / len(tokens) if tokens else 0.0
    ratios: list[float] = []
    for i in range(0, len(tokens) - window + 1, window):
        chunk = tokens[i : i + window]
        ratios.append(len(set(chunk)) / window)
    return statistics.mean(ratios) if ratios else 0.0


def _clip01(x: float) -> float:
    return max(0.0, min(1.0, x))


def extract_features(text: str) -> RawFeatures:
    """Run the feature extraction pipeline on a markdown/HTML document.

    Mirrors the PV-01 probe's ``analyze`` function. Returns raw
    per-feature counts and densities; does NOT compute the composite.
    """
    chars_total = len(text)
    cjk_chars = len(_CJK_RE.findall(text))
    prose = _strip_code_and_html(text)

    nonblank_lines = sum(1 for line in prose.splitlines() if line.strip())
    headers = len(_HEADER_RE.findall(prose))
    bullets = len(_BULLET_RE.findall(prose))
    header_ratio = headers / nonblank_lines if nonblank_lines else 0.0
    bullet_ratio = bullets / nonblank_lines if nonblank_lines else 0.0

    prose_for_lex = _strip_quoted_examples(prose)
    tokens = _tokens(prose_for_lex)
    en_words = len(tokens)
    cjk_words = cjk_chars
    words = en_words + cjk_words

    if en_words >= 200:
        ttr = _sliding_ttr(tokens, 200)
    else:
        ttr = (len(set(tokens)) / en_words) if en_words else 0.0

    sents = _split_sentences(prose)
    sent_lens = [len(_tokens(s)) for s in sents if _tokens(s)]
    if sent_lens:
        avg_sent_len = statistics.mean(sent_lens)
        sent_len_stddev = statistics.pstdev(sent_lens)
        burstiness = sent_len_stddev / avg_sent_len if avg_sent_len else 0.0
    else:
        avg_sent_len = sent_len_stddev = burstiness = 0.0

    per_1k = 1000.0 / max(200, words)
    bold = len(_BOLD_RE.findall(prose))
    emdashes = len(_EMDASH_RE.findall(prose))

    counter = Counter(tokens)
    tier1_hits = sum(counter[w] for w in AI_TIER1)
    tier2_hits = sum(counter[w] for w in AI_TIER2)

    prose_lower = prose_for_lex.lower()
    signposts = sum(len(p.findall(prose_lower)) for p in _SIGNPOST_PATTERNS)
    neg_parallel = sum(len(p.findall(prose_lower)) for p in _NEG_PARALLEL_PATTERNS)
    copula = sum(len(p.findall(prose_lower)) for p in _COPULA_PATTERNS)

    paragraphs = sum(1 for blk in re.split(r"\n\s*\n", prose) if blk.strip())

    return RawFeatures(
        chars=chars_total,
        words=words,
        cjk_chars=cjk_chars,
        en_words=en_words,
        sentences=len(sents),
        paragraphs=paragraphs,
        avg_sent_len=avg_sent_len,
        sent_len_stddev=sent_len_stddev,
        burstiness=burstiness,
        ttr=ttr,
        headers=headers,
        bullets=bullets,
        nonblank_lines=nonblank_lines,
        header_ratio=header_ratio,
        bullet_ratio=bullet_ratio,
        bold_count=bold,
        emdash_count=emdashes,
        tier1_count=tier1_hits,
        tier2_count=tier2_hits,
        signposts_count=signposts,
        neg_parallel_count=neg_parallel,
        copula_count=copula,
        bold_per_1k=bold * per_1k,
        emdash_per_1k=emdashes * per_1k,
        tier1_per_1k=tier1_hits * per_1k,
        tier2_per_1k=tier2_hits * per_1k,
        signposts_per_1k=signposts * per_1k,
        neg_parallel_per_1k=neg_parallel * per_1k,
        copula_dodge_per_1k=copula * per_1k,
    )


def compute_composite(
    features: RawFeatures, profile: ToneProfile
) -> tuple[float, dict[str, float]]:
    """Apply profile weights + caps to raw features to get composite."""
    caps = profile.caps
    weights = dict(profile.weights)

    total = sum(weights.values())
    if not (0.995 <= total <= 1.005):
        raise StyleError(f"profile {profile.name!r} weights sum to {total:.4f}, must be ~1.0")

    burstiness = features.burstiness
    ttr = features.ttr
    bold = features.bold_per_1k
    emdash = features.emdash_per_1k
    tier1 = features.tier1_per_1k
    tier2 = features.tier2_per_1k
    signposts = features.signposts_per_1k
    neg = features.neg_parallel_per_1k
    bullet = features.bullet_ratio
    header = features.header_ratio

    burstiness_ai = (
        _clip01((caps.burstiness_target - burstiness) / caps.burstiness_scale)
        if burstiness > 0
        else 1.0
    )
    ttr_ai = _clip01((caps.ttr_target - ttr) / caps.ttr_scale) if ttr > 0 else 1.0

    bold_ai = (
        _clip01((bold - caps.bold_per_1k_start) / caps.bold_per_1k_scale)
        if bold > caps.bold_per_1k_start
        else 0.0
    )
    emdash_ai = (
        _clip01((emdash - caps.emdash_per_1k_start) / caps.emdash_per_1k_scale)
        if emdash > caps.emdash_per_1k_start
        else 0.0
    )
    tier1_ai = _clip01(tier1 / caps.tier1_per_1k_scale)
    tier2_ai = _clip01(tier2 / caps.tier2_per_1k_scale)
    signposts_ai = _clip01(signposts / caps.signposts_per_1k_scale)
    neg_ai = _clip01(neg / caps.neg_parallel_per_1k_scale)
    bullet_ai = (
        _clip01((bullet - caps.bullet_ratio_start) / caps.bullet_ratio_scale)
        if bullet > caps.bullet_ratio_start
        else 0.0
    )
    header_ai = (
        _clip01((header - caps.header_ratio_start) / caps.header_ratio_scale)
        if header > caps.header_ratio_start
        else 0.0
    )

    sub = {
        "burstiness": burstiness_ai,
        "ttr": ttr_ai,
        "bold": bold_ai,
        "emdash": emdash_ai,
        "tier1": tier1_ai,
        "tier2": tier2_ai,
        "signposts": signposts_ai,
        "neg_parallel": neg_ai,
        "bullet": bullet_ai,
        "header": header_ai,
    }
    ai_flavor = sum(weights[k] * sub[k] for k in weights)
    composite = round(100.0 * (1.0 - ai_flavor), 2)
    return composite, sub


def score_text(text: str, profile: ToneProfile) -> NaturalnessScore:
    """Score a single document against the given tone profile."""
    features = extract_features(text)
    composite, sub = compute_composite(features, profile)
    return NaturalnessScore(
        composite=composite,
        features=features,
        per_feature_subscores=sub,
        profile_name=profile.name,
    )


def score_corpus(
    items: Iterable[tuple[str, str]],
    profile_fn: Callable[[str], ToneProfile],
) -> CorpusScore:
    """Score a set of (label, text) tuples; aggregate is the simple mean
    of per-doc composite scores, matching the probe's aggregation.
    """
    per_doc: dict[str, NaturalnessScore] = {}
    word_total = 0
    for label, text in items:
        profile = profile_fn(label)
        score = score_text(text, profile)
        per_doc[label] = score
        word_total += score.features.words
    agg = round(statistics.mean(s.composite for s in per_doc.values()), 3) if per_doc else 0.0
    return CorpusScore(aggregate_naturalness=agg, per_doc=per_doc, word_total=word_total)


__all__ = [
    "AI_TIER1",
    "AI_TIER2",
    "SIGNPOSTS",
    "NEG_PARALLELISM",
    "COPULA_DODGES",
    "RawFeatures",
    "NaturalnessScore",
    "CorpusScore",
    "extract_features",
    "compute_composite",
    "score_text",
    "score_corpus",
]
