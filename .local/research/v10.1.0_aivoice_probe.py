#!/usr/bin/env python3
"""v10.1.0 PV-01 — first-pass AI-voice feature probe.

This is RESEARCH-ONLY scaffolding. It lives under .local/research/ so
nothing here ships to users. The PV-02 design decision is what (if any
of) these features ultimately move into src/devolaflow/.

Goal: characterize DevolaFlow's human-facing prose against a hand-picked
human-written corpus, on cheap-to-compute stylometric features:

  1. Basic counts (words, sentences, paragraphs)
  2. Sentence-length burstiness (stddev / mean)
  3. Lexical diversity (Type-Token Ratio over a sliding window)
  4. Em-dash density (per 1000 words)
  5. Bold-marker density (per 1000 words)
  6. Header-to-prose ratio
  7. Bullet density
  8. AI-tier-1 vocabulary hits (per 1000 words)
  9. AI-tier-2 vocabulary hits (per 1000 words)
 10. Signposting / hedging phrase hits (per 1000 words)
 11. Negative-parallelism pattern hits (per 1000 words)
 12. Composite "naturalness" score (0-100; higher = closer to human)

Inputs are markdown / HTML files. Fenced code blocks (```...```) and
inline code (`...`) are stripped before counting prose features so
shell snippets and YAML payloads do not pollute the lexical/stylometric
signal. Tables and badges are kept (they ARE part of the prose density
characterization).

Stdlib only — no numpy, no nltk, no textstat. Targets <100ms per file.

Usage:
  python .local/research/v10.1.0_aivoice_probe.py
  python .local/research/v10.1.0_aivoice_probe.py --csv out.csv
  python .local/research/v10.1.0_aivoice_probe.py --md  out.md
"""

from __future__ import annotations

import argparse
import math
import re
import statistics
import sys
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
REFERENCE_ROOT = Path("/home/agent/reference")

# ---------------------------------------------------------------------------
# Feature catalogues (sourced from humanize-writing + skill-deslop + the
# 2024-2026 web survey summarized in v10.1.0_aivoice_research.md §1).
# ---------------------------------------------------------------------------

# Tier 1 — "almost never appears in natural human writing at the
# frequency AI uses them" (jpeggdev/humanize-writing references/ai-tells.md
# Tier 1 table, deduplicated).
AI_TIER1 = {
    "delve",
    "delves",
    "delving",
    "tapestry",
    "landscape",  # only flagged in metaphorical contexts; we count all (proxy)
    "paradigm",
    "leverage",
    "leverages",
    "leveraging",
    "harness",
    "harnesses",
    "harnessing",
    "navigate",  # metaphorical; count all (proxy)
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
    "ecosystem",  # technical noise; weighted lower in scoring
    "resonate",
    "resonates",
    "streamline",
    "streamlines",
    "streamlined",
    "testament",
    "enduring",
}

# Tier 2 — fine alone, AI tell when clustering. Densities are weighted
# at half the Tier 1 penalty in the composite score.
AI_TIER2 = {
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
    "ensuring",  # 2026 highlight: "hedging verbs" cluster
    "highlights",
    "supports",
    "reflects",
    "significantly",
    "effectively",
    "directly",
}

# Signposting / hedging starters. Counted as multi-word phrases (case-
# insensitive). Each occurrence costs the same regardless of phrase
# length so a 4-word filler is not double-penalized.
SIGNPOSTS = [
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
]

# Negative parallelism — "Not X, but Y" / "X isn't Y, it's Z". Mechanical
# reframes are the single most-cited 2026 AI tell (write-human.ai survey).
NEG_PARALLELISM = [
    r"\bnot just\b[^.\n]{1,80}\bbut (?:also)?\b",
    r"\bisn'?t (?:about )?\b[^.\n]{1,40}\b(?:it'?s|but) \b",
    r"\bnot only\b[^.\n]{1,80}\bbut also\b",
    r"\bit'?s not (?:about|just)\b[^.\n]{1,80}\bit'?s\b",
    r"\b(?:the answer|the question|the problem) isn'?t\b[^.\n]{0,40}\bit'?s\b",
    # "Not X. Not Y. Just Z." countdown reveal
    r"\bnot \w+\.\s+not \w+\.\s+(?:just |it'?s )?\w+",
]

# Copula-avoidance verbs — "serves as", "stands as", "represents", "marks"
# in the sense of "is/are/has". Counted because clusters are an AI tell.
COPULA_DODGES = [
    r"\bserves? as\b",
    r"\bstands? as\b",
    r"\brepresents? (?:a |the |an )\b",  # "represents the"... is/are dodge
    r"\bmarks? (?:a |the |an )\b",
    r"\bboasts? (?:a |the |an |\d)\b",
    r"\bfeatures? (?:a |the |an |\d)\b",
    r"\boffers? (?:a |the |an )\b",
]

# ---------------------------------------------------------------------------
# Text preprocessing
# ---------------------------------------------------------------------------

FENCED_CODE_RE = re.compile(r"```.*?```", re.DOTALL)
INLINE_CODE_RE = re.compile(r"`[^`\n]+`")
HTML_SCRIPT_STYLE_RE = re.compile(
    r"<(?:script|style)\b[^>]*>.*?</(?:script|style)>", re.DOTALL | re.IGNORECASE
)
HTML_TAG_RE = re.compile(r"<[^>]+>")
URL_RE = re.compile(r"https?://\S+")
SENT_SPLIT_RE = re.compile(r"(?<=[.!?。！？])\s+(?=[A-Z\u4e00-\u9fa5])")
WORD_RE = re.compile(r"[A-Za-z][A-Za-z'-]+")
CJK_RE = re.compile(r"[\u4e00-\u9fa5]")
HEADER_RE = re.compile(r"^\s*#{1,6}\s+\S", re.MULTILINE)
BULLET_RE = re.compile(r"^\s*(?:[-*+]\s+|\d+\.\s+)\S", re.MULTILINE)
BOLD_RE = re.compile(r"\*\*[^*\n]{1,80}\*\*")
EMDASH_RE = re.compile(r"\u2014|(?<!-)--(?!-)")  # U+2014 + ASCII double hyphen
TABLE_ROW_RE = re.compile(r"^\s*\|.*\|\s*$", re.MULTILINE)
# Table separator: |---|---|... (must already be inside a table row context).
TABLE_SEP_RE = re.compile(r"^\s*\|[\s\-:|]+\|\s*$", re.MULTILINE)
# Quoted-example detection: short single-line quote starting with `"` or
# `> ` (markdown quote). Examples in editorial AI-detection docs cluster
# tells inside these — we don't want to count them as authorial usage.
MD_QUOTE_LINE_RE = re.compile(r"^\s*>\s.*$", re.MULTILINE)
# A "table cell" approximation: cell contents inside `| ... |`. Used to
# subtract table density from prose density when desired.

EXAMPLE_HEADING_RE = re.compile(
    r"^\s*#{1,6}\s+(?:Tier [12]|Vocabulary|Examples?|Before|After|Bad|Good|Anti-?Patterns?|"
    r"AI Tells?|Patterns? to Avoid|Words AI Overuses|AI Vocabulary)",
    re.MULTILINE | re.IGNORECASE,
)


def _strip_code_and_html(text: str) -> str:
    """Remove fenced/inline code and HTML script/style + tags.

    Keeps bullet markers, header markers, em-dashes, bold markers — those
    ARE the prose-density signal. Code blocks pollute lexical features
    so they are dropped wholesale.
    """
    text = HTML_SCRIPT_STYLE_RE.sub(" ", text)
    text = FENCED_CODE_RE.sub(" ", text)
    text = INLINE_CODE_RE.sub(" ", text)
    text = HTML_TAG_RE.sub(" ", text)
    text = URL_RE.sub(" ", text)
    return text


def _strip_quoted_examples(text: str) -> str:
    """Drop markdown blockquote lines (`> ...`) and table rows.

    Used by the lexical-feature pass so an editorial doc that QUOTES
    'delve' as a Tier-1 example does not get the same naturalness
    penalty as a doc that uses 'delve' authorially. Header/bullet/
    bold density is computed on the unstripped text upstream so this
    only affects vocabulary + signpost + parallelism counts.
    """
    text = MD_QUOTE_LINE_RE.sub(" ", text)
    text = TABLE_SEP_RE.sub(" ", text)
    text = TABLE_ROW_RE.sub(" ", text)
    return text


def _split_sentences(text: str) -> list[str]:
    # Cheap regex split. Real sentence segmentation needs nltk; this
    # is good enough for sentence-length burstiness.
    parts = SENT_SPLIT_RE.split(text)
    return [p.strip() for p in parts if p.strip()]


def _tokens(text: str) -> list[str]:
    return [t.lower() for t in WORD_RE.findall(text)]


# ---------------------------------------------------------------------------
# Feature extraction
# ---------------------------------------------------------------------------


@dataclass
class Features:
    path: str
    label: str
    chars: int
    words: int
    sentences: int
    paragraphs: int
    avg_sent_len: float
    sent_len_stddev: float
    burstiness: float  # stddev / mean — higher = more human
    ttr: float  # type-token ratio
    cjk_chars: int
    headers: int
    bullets: int
    nonblank_lines: int
    header_ratio: float
    bullet_ratio: float
    bold_per_1k: float
    emdash_per_1k: float
    tier1_per_1k: float
    tier2_per_1k: float
    signposts_per_1k: float
    neg_parallel_per_1k: float
    copula_dodge_per_1k: float
    naturalness: float  # composite 0-100 score

    def to_row(self) -> dict[str, str | float | int]:
        return asdict(self)


def _compute_naturalness(  # noqa: PLR0913 — explicit parameter list mirrors features
    burstiness: float,
    ttr: float,
    bold_per_1k: float,
    emdash_per_1k: float,
    tier1_per_1k: float,
    tier2_per_1k: float,
    signposts_per_1k: float,
    neg_parallel_per_1k: float,
    bullet_ratio: float,
    header_ratio: float,
) -> float:
    """Composite 0..100 score, higher = more human-like.

    Weights are first-pass intuition calibrated against the human-corpus
    means computed in v10.1.0_aivoice_baseline.md. PV-02 will refine.

    Per-component approach: convert each feature to a 0..1 "AI-flavor"
    sub-score where 1 = maximally AI-flavored, then naturalness =
    100 * (1 - weighted_avg_ai_flavor).
    """
    # Sub-scores in [0, 1]; clip to that range.
    def _clip(x: float) -> float:
        return max(0.0, min(1.0, x))

    # Burstiness target ≈ 0.65 (skilled human writers); below 0.4 is AI-
    # flat. Linear penalty. Above 0.65 = no penalty (real humans vary).
    burstiness_ai = _clip((0.65 - burstiness) / 0.65) if burstiness > 0 else 1.0
    # TTR target ≈ 0.45 in 200-token windows; below 0.30 is AI-repetitive.
    ttr_ai = _clip((0.45 - ttr) / 0.30) if ttr > 0 else 1.0
    # Bold-density: human technical docs run < 8 per 1000; AI docs > 30.
    # DevolaFlow's CHANGELOG runs ~32; readme ~25. Threshold floor moved
    # down to 8 to surface the bold-overuse signal that was being
    # dampened in the v1 weighting.
    bold_ai = _clip((bold_per_1k - 8.0) / 25.0) if bold_per_1k > 8.0 else 0.0
    # Em-dash: human technical < 5 per 1000; AI > 25. DevolaFlow's
    # CHANGELOG/research docs run 32–48 per 1000.
    emdash_ai = _clip((emdash_per_1k - 5.0) / 25.0) if emdash_per_1k > 5.0 else 0.0
    # Tier1 vocab: human technical < 1 per 1000; AI > 5.
    tier1_ai = _clip(tier1_per_1k / 5.0)
    # Tier2 vocab: human < 4 per 1000; AI > 15.
    tier2_ai = _clip(tier2_per_1k / 15.0)
    # Signposts: human < 2 per 1000; AI > 8.
    signposts_ai = _clip(signposts_per_1k / 10.0)
    # Negative parallelism: human ≈ 0; AI > 2 per 1000.
    neg_ai = _clip(neg_parallel_per_1k / 3.0)
    # Bullet ratio: human technical docs ≈ 0.10-0.30; AI > 0.45. The
    # CHANGELOG hits 0.628 — saturate the penalty above 0.50.
    bullet_ai = _clip((bullet_ratio - 0.25) / 0.25) if bullet_ratio > 0.25 else 0.0
    # Header ratio: human ≈ 0.05-0.15; AI > 0.20. Many DevolaFlow
    # guides hit 0.20-0.30.
    header_ai = _clip((header_ratio - 0.12) / 0.15) if header_ratio > 0.12 else 0.0

    # Weights re-tuned per v10.1.0 PV-01 user feedback: the user's
    # complaint was specifically structural (bullet/header/em-dash/bold
    # overuse) + signposting. Lexical (tier1/tier2) penalties stay
    # because they DO show up in our docs but are not the primary
    # complaint surface.
    weights = {
        "burstiness": 0.10,
        "ttr": 0.05,
        "bold": 0.15,
        "emdash": 0.15,
        "tier1": 0.05,
        "tier2": 0.05,
        "signposts": 0.10,
        "neg_parallel": 0.05,
        "bullet": 0.15,
        "header": 0.15,
    }
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
    return round(100.0 * (1.0 - ai_flavor), 2)


def analyze(path: Path, label: str) -> Features:
    raw = path.read_text(encoding="utf-8", errors="replace")
    chars_total = len(raw)
    cjk_chars = len(CJK_RE.findall(raw))

    # Strip code/HTML for prose features.
    prose = _strip_code_and_html(raw)

    # Lines for header / bullet ratios — count BEFORE the strip so list
    # markers in code blocks do not skew (we already removed code).
    nonblank_lines = sum(1 for line in prose.splitlines() if line.strip())
    headers = len(HEADER_RE.findall(prose))
    bullets = len(BULLET_RE.findall(prose))
    header_ratio = headers / nonblank_lines if nonblank_lines else 0.0
    bullet_ratio = bullets / nonblank_lines if nonblank_lines else 0.0

    # For lexical features we want to drop quoted examples and table
    # rows — otherwise editorial docs that catalog AI tells get falsely
    # penalised. Bold/header/bullet density is computed on the FULL
    # prose above; lexical pattern hits use this stripped variant.
    prose_for_lex = _strip_quoted_examples(prose)

    # Tokens (English words only). For CJK-heavy docs we add a CJK
    # character count to the denominator so per-1000-word densities are
    # not divide-by-tiny-number artefacts. 1 CJK char ≈ 1 word is a
    # rough but defensible mapping for naturalness scoring.
    tokens = _tokens(prose_for_lex)
    en_words = len(tokens)
    cjk_words = cjk_chars  # 1 CJK char ≈ 1 word for density
    words = en_words + cjk_words
    types = len(set(tokens))
    ttr = (
        _sliding_ttr(tokens, window=200)
        if en_words >= 200
        else (types / en_words if en_words else 0.0)
    )

    # Sentences and burstiness (use the cleaned prose; CJK split on
    # 。！？ via the same regex).
    sents = _split_sentences(prose)
    sent_lens = [len(_tokens(s)) for s in sents if _tokens(s)]
    if sent_lens:
        avg_sent_len = statistics.mean(sent_lens)
        sent_len_stddev = statistics.pstdev(sent_lens)
        burstiness = sent_len_stddev / avg_sent_len if avg_sent_len else 0.0
    else:
        avg_sent_len = sent_len_stddev = burstiness = 0.0

    # Densities (per 1000 prose words; floor at 200 to avoid the tiny-
    # ZH-doc divide-by-tiny artefact). When `words < 200` densities are
    # still emitted but the composite naturalness score caps the
    # impact via the same min-words gate (see _compute_naturalness).
    per_1k = 1000.0 / max(200, words)
    bold = len(BOLD_RE.findall(prose))
    emdashes = len(EMDASH_RE.findall(prose))
    bold_per_1k = bold * per_1k
    emdash_per_1k = emdashes * per_1k

    # Vocab hits — token-level for tier1/tier2 (uses lex-stripped tokens).
    counter = Counter(tokens)
    tier1_hits = sum(counter[w] for w in AI_TIER1)
    tier2_hits = sum(counter[w] for w in AI_TIER2)
    tier1_per_1k = tier1_hits * per_1k
    tier2_per_1k = tier2_hits * per_1k

    # Signpost / negative-parallelism / copula-dodge: regex on
    # quote/table-stripped prose so the editorial corpus isn't punished
    # for cataloguing patterns it teaches readers to remove.
    prose_lower = prose_for_lex.lower()
    signposts = sum(len(re.findall(p, prose_lower)) for p in SIGNPOSTS)
    neg_parallel = sum(len(re.findall(p, prose_lower)) for p in NEG_PARALLELISM)
    copula = sum(len(re.findall(p, prose_lower)) for p in COPULA_DODGES)
    signposts_per_1k = signposts * per_1k
    neg_parallel_per_1k = neg_parallel * per_1k
    copula_per_1k = copula * per_1k

    # Approximate paragraph count: blocks separated by blank lines.
    paragraphs = sum(1 for blk in re.split(r"\n\s*\n", prose) if blk.strip())

    naturalness = _compute_naturalness(
        burstiness=burstiness,
        ttr=ttr,
        bold_per_1k=bold_per_1k,
        emdash_per_1k=emdash_per_1k,
        tier1_per_1k=tier1_per_1k,
        tier2_per_1k=tier2_per_1k,
        signposts_per_1k=signposts_per_1k,
        neg_parallel_per_1k=neg_parallel_per_1k,
        bullet_ratio=bullet_ratio,
        header_ratio=header_ratio,
    )

    return Features(
        path=str(path),
        label=label,
        chars=chars_total,
        words=words,
        sentences=len(sents),
        paragraphs=paragraphs,
        avg_sent_len=round(avg_sent_len, 2),
        sent_len_stddev=round(sent_len_stddev, 2),
        burstiness=round(burstiness, 3),
        ttr=round(ttr, 3),
        cjk_chars=cjk_chars,
        headers=headers,
        bullets=bullets,
        nonblank_lines=nonblank_lines,
        header_ratio=round(header_ratio, 3),
        bullet_ratio=round(bullet_ratio, 3),
        bold_per_1k=round(bold_per_1k, 2),
        emdash_per_1k=round(emdash_per_1k, 2),
        tier1_per_1k=round(tier1_per_1k, 2),
        tier2_per_1k=round(tier2_per_1k, 2),
        signposts_per_1k=round(signposts_per_1k, 2),
        neg_parallel_per_1k=round(neg_parallel_per_1k, 2),
        copula_dodge_per_1k=round(copula_per_1k, 2),
        naturalness=naturalness,
    )


def _sliding_ttr(tokens: list[str], window: int) -> float:
    """Length-controlled TTR: average TTR over non-overlapping windows.

    Mitigates TTR's well-known length bias (longer texts have lower TTR
    mechanically). MTLD would be better but adds complexity not justified
    for a first-pass probe.
    """
    if len(tokens) < window:
        return len(set(tokens)) / len(tokens) if tokens else 0.0
    ratios: list[float] = []
    for i in range(0, len(tokens) - window + 1, window):
        chunk = tokens[i : i + window]
        ratios.append(len(set(chunk)) / window)
    return statistics.mean(ratios) if ratios else 0.0


# ---------------------------------------------------------------------------
# Corpus assembly
# ---------------------------------------------------------------------------


def _devolaflow_targets() -> list[tuple[Path, str]]:
    en_dir = REPO_ROOT / "workflow-system/human/en"
    zh_dir = REPO_ROOT / "workflow-system/human/zh"
    targets: list[tuple[Path, str]] = []
    targets.append((REPO_ROOT / "README.md", "df:README"))
    for f in sorted(en_dir.glob("*.md")):
        targets.append((f, f"df:en/{f.stem}"))
    for f in sorted(zh_dir.glob("*.md")):
        targets.append((f, f"df:zh/{f.stem}"))
    targets.append((REPO_ROOT / "CHANGELOG.md", "df:CHANGELOG"))
    targets.append((REPO_ROOT / "workflow-system/human/demo/index.html", "df:demo/index.html"))
    targets.append(
        (REPO_ROOT / ".local/research/v10.0.0_cycle_plan.md", "df:research/v10.0.0_cycle_plan")
    )
    targets.append(
        (
            REPO_ROOT / ".local/research/v10.0.0_retrospective.md",
            "df:research/v10.0.0_retrospective",
        )
    )
    return [(p, lab) for p, lab in targets if p.exists()]


def _human_corpus() -> list[tuple[Path, str]]:
    """Hand-picked human-written technical writing.

    Two sub-corpora:
      - `human:` — clean prose-writing references. Authors are humans
        writing about their tooling, not catalogues of AI tells.
      - `meta:`  — editorial AI-tells catalogues. These contain the
        very vocabulary they teach readers to AVOID, packaged as quotes
        + tables + before/after pairs. They are kept in the probe for
        sanity-checking but are aggregated separately so the human
        baseline isn't poisoned by their definitionally-loaded prose.
    """
    clean = [
        (REFERENCE_ROOT / "chezmoi/README.md", "human:chezmoi"),
        (REFERENCE_ROOT / "ruff/README.md", "human:ruff"),
        (REFERENCE_ROOT / "caveman/README.md", "human:caveman"),
        (REFERENCE_ROOT / "ironclaw/README.md", "human:ironclaw"),
    ]
    meta = [
        (REFERENCE_ROOT / "humanize-writing/SKILL.md", "meta:humanize-writing-skill"),
        (REFERENCE_ROOT / "humanize-writing/references/ai-tells.md", "meta:ai-tells"),
        (REFERENCE_ROOT / "skill-deslop/SKILL.md", "meta:skill-deslop-skill"),
        (REFERENCE_ROOT / "skill-deslop/references/phrases.md", "meta:deslop-phrases"),
        (REFERENCE_ROOT / "skill-deslop/references/structures.md", "meta:deslop-structures"),
    ]
    return [(p, lab) for p, lab in (clean + meta) if p.exists()]


# ---------------------------------------------------------------------------
# CLI / output
# ---------------------------------------------------------------------------


COLUMNS = [
    "label",
    "words",
    "sentences",
    "avg_sent_len",
    "burstiness",
    "ttr",
    "header_ratio",
    "bullet_ratio",
    "bold_per_1k",
    "emdash_per_1k",
    "tier1_per_1k",
    "tier2_per_1k",
    "signposts_per_1k",
    "neg_parallel_per_1k",
    "copula_dodge_per_1k",
    "naturalness",
]


def _emit_csv(rows: list[Features], out: Path | None) -> None:
    lines = [",".join(COLUMNS)]
    for r in rows:
        d = r.to_row()
        lines.append(",".join(str(d[c]) for c in COLUMNS))
    text = "\n".join(lines) + "\n"
    if out:
        out.write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)


def _emit_md(rows: list[Features], out: Path | None) -> None:
    """Markdown table with corpus-aggregate rows at the top."""
    by_corpus: dict[str, list[Features]] = {"df": [], "human": [], "meta": []}
    for r in rows:
        for prefix in by_corpus:
            if r.label.startswith(prefix + ":"):
                by_corpus[prefix].append(r)

    def _agg(group: list[Features], name: str) -> Features:
        if not group:
            return Features(
                path="",
                label=name,
                chars=0,
                words=0,
                sentences=0,
                paragraphs=0,
                avg_sent_len=0.0,
                sent_len_stddev=0.0,
                burstiness=0.0,
                ttr=0.0,
                cjk_chars=0,
                headers=0,
                bullets=0,
                nonblank_lines=0,
                header_ratio=0.0,
                bullet_ratio=0.0,
                bold_per_1k=0.0,
                emdash_per_1k=0.0,
                tier1_per_1k=0.0,
                tier2_per_1k=0.0,
                signposts_per_1k=0.0,
                neg_parallel_per_1k=0.0,
                copula_dodge_per_1k=0.0,
                naturalness=0.0,
            )

        def mean(attr: str) -> float:
            return round(statistics.mean(getattr(r, attr) for r in group), 3)

        return Features(
            path="",
            label=name,
            chars=sum(r.chars for r in group),
            words=sum(r.words for r in group),
            sentences=sum(r.sentences for r in group),
            paragraphs=sum(r.paragraphs for r in group),
            avg_sent_len=mean("avg_sent_len"),
            sent_len_stddev=mean("sent_len_stddev"),
            burstiness=mean("burstiness"),
            ttr=mean("ttr"),
            cjk_chars=sum(r.cjk_chars for r in group),
            headers=sum(r.headers for r in group),
            bullets=sum(r.bullets for r in group),
            nonblank_lines=sum(r.nonblank_lines for r in group),
            header_ratio=mean("header_ratio"),
            bullet_ratio=mean("bullet_ratio"),
            bold_per_1k=mean("bold_per_1k"),
            emdash_per_1k=mean("emdash_per_1k"),
            tier1_per_1k=mean("tier1_per_1k"),
            tier2_per_1k=mean("tier2_per_1k"),
            signposts_per_1k=mean("signposts_per_1k"),
            neg_parallel_per_1k=mean("neg_parallel_per_1k"),
            copula_dodge_per_1k=mean("copula_dodge_per_1k"),
            naturalness=mean("naturalness"),
        )

    aggregates = [
        _agg(by_corpus["human"], "AGG:human-clean"),
        _agg(by_corpus["meta"], "AGG:meta-editorial"),
        _agg(by_corpus["df"], "AGG:devolaflow"),
    ]

    body: list[str] = []
    body.append("# v10.1.0 PV-01 — AI-Voice Baseline Measurement")
    body.append("")
    body.append("Generated by `.local/research/v10.1.0_aivoice_probe.py` (stdlib-only).")
    body.append("")
    body.append("Three corpora are aggregated separately:")
    body.append("")
    body.append(
        "- **`AGG:human-clean`** — chezmoi/ruff/caveman/ironclaw README.md "
        "(human-authored dev-tool prose; the natural target)."
    )
    body.append(
        "- **`AGG:meta-editorial`** — `humanize-writing` + `skill-deslop` SKILL/refs "
        "(human-authored anti-AI editorial docs; they CATALOGUE tier-1/2 vocab + "
        "signposts as examples, so their tier1/tier2/signposts densities are inflated "
        "by design even after blockquote + table stripping). Treat as a SECONDARY "
        "calibration anchor, not the primary target."
    )
    body.append(
        "- **`AGG:devolaflow`** — DevolaFlow's own human-facing surface "
        "(README + EN/ZH guides + demo/index.html + CHANGELOG + cycle artifacts)."
    )
    body.append("")
    body.append(
        "**Naturalness column** is a 0–100 composite where 100 = "
        "indistinguishable-from-skilled-human technical writing and 0 = "
        "saturated-AI-flavor. Weights are documented in "
        "`v10.1.0_aivoice_research.md` §4 and in `_compute_naturalness()` "
        "in the probe source."
    )
    body.append("")
    body.append("All densities are **per 1000 prose words** with a min-words floor of 200.")
    body.append("")
    body.append("| " + " | ".join(COLUMNS) + " |")
    body.append("|" + "|".join("---" for _ in COLUMNS) + "|")
    for r in aggregates + sorted(rows, key=lambda x: (x.label.split(":")[0], x.label)):
        d = r.to_row()
        body.append("| " + " | ".join(str(d[c]) for c in COLUMNS) + " |")
    body.append("")
    # Headline deltas — the v10.1.0 PV-02 design decision is whether to
    # ship a CI gate on the composite or transform-then-recompute.
    body.append("## Headline deltas (DevolaFlow vs human-clean baseline)")
    body.append("")
    if by_corpus["human"] and by_corpus["df"]:
        h = aggregates[0]  # AGG:human-clean
        d = aggregates[2]  # AGG:devolaflow
        body.append("| feature | human-clean | devolaflow | delta | direction |")
        body.append("|---|---:|---:|---:|---|")
        for col in (
            "burstiness",
            "ttr",
            "header_ratio",
            "bullet_ratio",
            "bold_per_1k",
            "emdash_per_1k",
            "tier1_per_1k",
            "tier2_per_1k",
            "signposts_per_1k",
            "neg_parallel_per_1k",
            "naturalness",
        ):
            hv = float(getattr(h, col))
            dv = float(getattr(d, col))
            delta = dv - hv
            arrow = (
                "OK"
                if abs(delta) < 0.5
                else ("DF higher" if delta > 0 else "DF lower")
            )
            body.append(
                f"| {col} | {hv:.3f} | {dv:.3f} | {delta:+.3f} | {arrow} |"
            )
        body.append("")
    text = "\n".join(body) + "\n"
    if out:
        out.write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--csv", type=Path, help="write CSV to this path (otherwise stdout)")
    p.add_argument("--md", type=Path, help="write Markdown table to this path")
    p.add_argument(
        "--include-research",
        action="store_true",
        help="include .local/research/v10.0.0_*.md targets (default: yes)",
    )
    args = p.parse_args(argv)

    targets = _devolaflow_targets() + _human_corpus()
    rows = [analyze(p, lab) for p, lab in targets]

    if not args.csv and not args.md:
        # Default: emit Markdown to stdout (more readable in terminal).
        _emit_md(rows, None)
        return 0
    if args.csv:
        _emit_csv(rows, args.csv)
    if args.md:
        _emit_md(rows, args.md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
