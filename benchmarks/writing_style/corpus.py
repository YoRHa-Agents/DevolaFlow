"""Corpus assembly for the writing-style benchmark.

Two canonical corpora:

* ``DEVOLAFLOW_HUMAN_FACING_DOCS`` — the user-visible surface we gate
  on: README.md + 8 EN guides + 8 ZH guides + CHANGELOG.md + the demo
  landing page's prose.
* ``HUMAN_CLEAN_REFERENCE_DOCS`` — a small hand-picked corpus of
  well-edited dev-tool READMEs. Authors are humans writing about
  their own tooling; these are the target the scorer calibrates
  against.

Both corpora are addressed by path relative to the repo root so the
benchmark runs identically in CI and in local clones.

The ``HUMAN_CLEAN_REFERENCE_DOCS`` entries live under
``/home/agent/reference/`` in the research environment. In a fresh
clone those paths are absent; the runner skips missing docs and
records the skip in the output so downstream consumers can detect
partial corpora.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from devolaflow.writing_style.profiles import ToneProfile, profile_for_path

REPO_ROOT = Path(__file__).resolve().parents[2]
REFERENCE_ROOT = Path("/home/agent/reference")


@dataclass(frozen=True)
class CorpusDoc:
    """One document in a corpus."""

    label: str
    path: Path
    profile_override: ToneProfile | None = None


def _devolaflow_docs() -> list[CorpusDoc]:
    en_dir = REPO_ROOT / "workflow-system/human/en"
    zh_dir = REPO_ROOT / "workflow-system/human/zh"
    docs: list[CorpusDoc] = [
        CorpusDoc("df:README", REPO_ROOT / "README.md"),
        CorpusDoc("df:CHANGELOG", REPO_ROOT / "CHANGELOG.md"),
        CorpusDoc(
            "df:demo/index.html",
            REPO_ROOT / "workflow-system/human/demo/index.html",
        ),
    ]
    for f in sorted(en_dir.glob("*.md")):
        docs.append(CorpusDoc(f"df:en/{f.stem}", f))
    for f in sorted(zh_dir.glob("*.md")):
        docs.append(CorpusDoc(f"df:zh/{f.stem}", f))
    research = [
        (".local/research/v10.0.0_cycle_plan.md", "df:research/v10.0.0_cycle_plan"),
        (".local/research/v10.0.0_retrospective.md", "df:research/v10.0.0_retrospective"),
    ]
    for rel, label in research:
        p = REPO_ROOT / rel
        if p.exists():
            docs.append(CorpusDoc(label, p))
    return docs


def _human_clean_docs() -> list[CorpusDoc]:
    return [
        CorpusDoc("human:chezmoi", REFERENCE_ROOT / "chezmoi/README.md"),
        CorpusDoc("human:ruff", REFERENCE_ROOT / "ruff/README.md"),
        CorpusDoc("human:caveman", REFERENCE_ROOT / "caveman/README.md"),
        CorpusDoc("human:ironclaw", REFERENCE_ROOT / "ironclaw/README.md"),
    ]


DEVOLAFLOW_HUMAN_FACING_DOCS: list[CorpusDoc] = _devolaflow_docs()
HUMAN_CLEAN_REFERENCE_DOCS: list[CorpusDoc] = _human_clean_docs()


def load_corpus(name: str) -> list[CorpusDoc]:
    if name == "devolaflow":
        return list(DEVOLAFLOW_HUMAN_FACING_DOCS)
    if name == "human-clean":
        return list(HUMAN_CLEAN_REFERENCE_DOCS)
    if name == "both":
        return list(DEVOLAFLOW_HUMAN_FACING_DOCS) + list(HUMAN_CLEAN_REFERENCE_DOCS)
    raise ValueError(f"unknown corpus {name!r}; valid: devolaflow, human-clean, both")


def pick_profile(doc: CorpusDoc) -> ToneProfile:
    if doc.profile_override is not None:
        return doc.profile_override
    try:
        rel = doc.path.relative_to(REPO_ROOT)
        return profile_for_path(str(rel))
    except ValueError:
        from devolaflow.writing_style.profiles import DOCUMENTATION_NATURAL

        return DOCUMENTATION_NATURAL


def read_docs(docs: Iterable[CorpusDoc]) -> list[tuple[str, str, str, bool]]:
    """Read each doc's text. Returns ``[(label, text, profile_name, present), ...]``.

    ``present`` is False when the file is missing. The caller decides
    whether to skip or fail; the runner currently skips.
    """
    out: list[tuple[str, str, str, bool]] = []
    for doc in docs:
        profile = pick_profile(doc)
        if not doc.path.exists():
            out.append((doc.label, "", profile.name, False))
            continue
        text = doc.path.read_text(encoding="utf-8", errors="replace")
        out.append((doc.label, text, profile.name, True))
    return out


__all__ = [
    "REPO_ROOT",
    "REFERENCE_ROOT",
    "CorpusDoc",
    "DEVOLAFLOW_HUMAN_FACING_DOCS",
    "HUMAN_CLEAN_REFERENCE_DOCS",
    "load_corpus",
    "pick_profile",
    "read_docs",
]
