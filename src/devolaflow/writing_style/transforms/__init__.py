"""Five SAFE writing-style transforms, composable into a pipeline.

Each transform is a pure function ``(text: str, profile: ToneProfile)
-> str`` that applies a single mechanical fix inside prose regions
only. Protected regions (fenced code, inline code, markdown links,
version strings, html tags, bare URLs) are preserved byte-for-byte
via ``regions.apply_to_prose``.

The five transforms:

* ``emdash``    (T-S1) — collapse ``--`` into typographic em-dashes
                          and commute triple-em-dash asides to commas
* ``bullets``   (T-S2) — fold 1- and 2-item bullet lists into prose
* ``signposts`` (T-S3) — strip sentence-starting signpost prefixes
* ``headers``   (T-S4) — demote orphan headers shorter than 40 words
* ``cliches``   (T-S5) — delete sycophantic opener phrases

Per-profile transform toggles (``ToneProfile.transforms_enabled``)
gate which transforms run on which doc class. The Q-D CHANGELOG
policy enables only T-S1 + T-S5 on CHANGELOG entries.

The pipeline is deterministic and idempotent: a second pass over
the same input yields byte-identical output.

Design ref: v10.1.0 PV-01 research §5.1 (safe transform catalog) +
gap analysis §3.1 G-A2.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from ..profiles import DOCUMENTATION_NATURAL, ToneProfile
from . import bullets, cliches, emdash, headers, signposts

TransformFn = Callable[[str, ToneProfile], str]

TRANSFORMS: dict[str, TransformFn] = {
    "emdash": emdash.apply,
    "bullets": bullets.apply,
    "signposts": signposts.apply,
    "headers": headers.apply,
    "cliches": cliches.apply,
}

# Canonical order. Running order matters: emdash normalises typography
# first, then bullets collapse list structures, then signposts and
# cliches strip openers, and headers run last after the
# paragraph-level edits settle.
TRANSFORM_ORDER: tuple[str, ...] = (
    "emdash",
    "bullets",
    "signposts",
    "cliches",
    "headers",
)


@dataclass(frozen=True)
class TransformResult:
    """Return type for ``apply_transforms``.

    The per-transform byte-delta lets callers attribute changes to
    individual transforms — useful for debugging unexpectedly large
    edits on a doc.
    """

    before: str
    after: str
    transforms_run: tuple[str, ...]
    byte_delta: int
    per_transform_delta: dict[str, int] = field(default_factory=dict)

    @property
    def changed(self) -> bool:
        return self.before != self.after


def apply_transforms(
    text: str,
    profile: ToneProfile | None = None,
    *,
    enabled: dict[str, bool] | None = None,
) -> TransformResult:
    """Apply the five transforms in canonical order, gated by profile.

    Args:
        text: input markdown / prose.
        profile: tone profile; defaults to ``DOCUMENTATION_NATURAL``.
            ``profile.transforms_enabled`` toggles individual
            transforms.
        enabled: optional override map; if provided, it overrides
            ``profile.transforms_enabled`` for each named transform.
            Useful for testing a single transform in isolation.

    Returns:
        ``TransformResult`` carrying the before/after text + the
        byte deltas per transform.
    """
    if profile is None:
        profile = DOCUMENTATION_NATURAL

    current = text
    run: list[str] = []
    per_delta: dict[str, int] = {}
    for name in TRANSFORM_ORDER:
        if enabled is not None:
            if not enabled.get(name, False):
                continue
        elif not profile.enabled(name):
            continue
        fn = TRANSFORMS[name]
        before = current
        current = fn(current, profile)
        run.append(name)
        per_delta[name] = len(current) - len(before)

    return TransformResult(
        before=text,
        after=current,
        transforms_run=tuple(run),
        byte_delta=len(current) - len(text),
        per_transform_delta=per_delta,
    )


__all__ = [
    "TransformFn",
    "TRANSFORMS",
    "TRANSFORM_ORDER",
    "TransformResult",
    "apply_transforms",
]
