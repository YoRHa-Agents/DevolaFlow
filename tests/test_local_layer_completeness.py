"""Layer-completeness lint for the rule compiler — closes gap G-014.

Contract
--------
Every layer declared in ``.rules/compile-config.yaml#layers[*].name``
MUST surface in every compile target's output that includes it via
``targets.<name>.include_layers``.

Why this matters
----------------
``src/devolaflow/local/compiler.py::RuleCompiler._truncate_to_budget``
silently drops non-``always_include`` layers when the rendered output
estimate exceeds ``token_budget``. The pre-existing CI hash check
(``tests/test_no_ghost_features.py::test_rule_surfaces_compile_only``)
only verifies the OUTPUT matches the pinned hash — a "consistently
truncated" output passes those hashes silently because the hash file
was regenerated against the truncated state.

This test elevates the "all configured layers must surface" invariant
from prompt-only to deterministic CI check. Two complementary signals:

1. Per-layer signature presence — for every layer in each target's
   ``include_layers``, the layer's first ``## `` heading line MUST
   appear verbatim in the compiled output. Catches whole-layer drops.
2. ``## `` heading count parity — the compiled output's count of
   ``^## `` headings MUST equal the sum of ``^## `` heading counts
   across the source ``.rules/<layer>.mdc`` files for every included
   layer. Catches partial-layer truncation that the per-signature
   check might miss when only the trailing rules were dropped.

Both signals fire against the live repo state (no tmp_path needed).
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from devolaflow.local.compiler import RuleCompiler

REPO_ROOT = Path(__file__).resolve().parents[1]
COMPILE_CONFIG_PATH = REPO_ROOT / ".rules" / "compile-config.yaml"
RULES_DIR = REPO_ROOT / ".rules"
CURSOR_OUTPUT = REPO_ROOT / ".cursor" / "rules" / "repo-governance.mdc"
AGENTS_MD_OUTPUT = REPO_ROOT / "AGENTS.md"

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def _load_config() -> dict[str, Any]:
    """Read and parse ``.rules/compile-config.yaml``."""
    return yaml.safe_load(COMPILE_CONFIG_PATH.read_text(encoding="utf-8"))


def _layer_source_body(layer_name: str) -> str:
    """Return the source ``.rules/<layer>.mdc`` body, stripping YAML frontmatter.

    Mirrors ``compiler._parse_mdc`` so the body we count headings against
    here is byte-identical to what the compiler ingests.
    """
    raw = (RULES_DIR / f"{layer_name}.mdc").read_text(encoding="utf-8")
    match = _FRONTMATTER_RE.match(raw)
    if match:
        return raw[match.end() :]
    return raw


def _first_h2_signature(layer_name: str) -> str:
    """Return the first ``## `` heading line in the layer body.

    Used as a stable per-layer signature: every compile target that
    includes the layer MUST emit this exact line. Style-layer's first
    ``## `` is a grouping header (``## Documentation Sync (DS-*)``)
    rather than a numbered rule, but it is still stable and unique
    across the five-layer corpus, so it serves as a valid signature.
    """
    for line in _layer_source_body(layer_name).splitlines():
        if line.startswith("## "):
            return line
    msg = f"layer {layer_name!r} has no `## ` heading in its source body"
    raise AssertionError(msg)


def _count_h2_headings(text: str) -> int:
    """Count ``^## `` heading lines in a body.

    The compiler concatenates layer bodies verbatim, so the heading
    count in the compiled output equals the sum of heading counts across
    the included source layers if and only if no layer was truncated.
    """
    return sum(1 for line in text.splitlines() if line.startswith("## "))


def _expected_h2_count_for_target(target_name: str, cfg: dict[str, Any]) -> int:
    """Sum of ``^## `` heading counts across all included layers."""
    included = cfg["targets"][target_name]["include_layers"]
    return sum(_count_h2_headings(_layer_source_body(layer)) for layer in included)


def test_cursor_target_contains_all_included_layers() -> None:
    """Per-layer signature check for the cursor compile target.

    For every layer in ``targets.cursor.include_layers``, the layer's
    first ``## `` heading MUST appear verbatim in the compiled
    ``.cursor/rules/repo-governance.mdc``. A missing signature means
    that layer was silently dropped by ``_truncate_to_budget`` (or
    excluded at load time because the source file was missing/empty).
    """
    cfg = _load_config()
    cursor_layers = cfg["targets"]["cursor"]["include_layers"]
    compiled = CURSOR_OUTPUT.read_text(encoding="utf-8")

    for layer in cursor_layers:
        signature = _first_h2_signature(layer)
        assert signature in compiled, (
            f"layer {layer!r} dropped from cursor compile output: "
            f"signature heading {signature!r} missing from "
            f"{CURSOR_OUTPUT.relative_to(REPO_ROOT)}"
        )


def test_agents_md_target_contains_all_included_layers() -> None:
    """Per-layer signature check for the agents_md compile target.

    Same contract as ``test_cursor_target_contains_all_included_layers``
    but against ``AGENTS.md`` and ``targets.agents_md.include_layers``.
    Note: the agents_md target intentionally excludes the ``style``
    layer per ``compile-config.yaml`` — that exclusion is enforced
    through the include_layers list, not through truncation, so it
    does not violate this invariant.
    """
    cfg = _load_config()
    agents_layers = cfg["targets"]["agents_md"]["include_layers"]
    compiled = AGENTS_MD_OUTPUT.read_text(encoding="utf-8")

    for layer in agents_layers:
        signature = _first_h2_signature(layer)
        assert signature in compiled, (
            f"layer {layer!r} dropped from agents_md compile output: "
            f"signature heading {signature!r} missing from "
            f"{AGENTS_MD_OUTPUT.relative_to(REPO_ROOT)}"
        )


def test_no_layer_silently_dropped_via_truncate() -> None:
    """Recompile in-memory and verify zero layers were dropped under budget.

    Two checks per target:

    1. ``CompileResult.layers_included`` MUST equal the configured
       ``include_layers`` (set equality). Catches load-time exclusions
       (missing source files / empty bodies).
    2. The compiled output's ``^## `` heading count MUST equal the
       expected sum across all included source layers. Catches the
       ``_truncate_to_budget`` silent-drop path: when a layer is
       dropped to fit the token budget, the compiled output loses
       ALL of that layer's ``## `` headings, so the count diverges.

    Uses ``rc.compile()`` (in-memory) rather than ``rc.compile_all()``
    so this test does not mutate the on-disk compiled artifacts.
    """
    cfg = _load_config()
    rc = RuleCompiler(COMPILE_CONFIG_PATH)
    rc.load_layers(RULES_DIR)
    by_target = {r.target: r for r in rc.compile()}

    for target_name, target_spec in cfg["targets"].items():
        result = by_target[target_name]
        configured = set(target_spec["include_layers"])
        included = set(result.layers_included)
        assert included == configured, (
            f"target {target_name!r} dropped layers at load time: "
            f"configured={sorted(configured)}, included={sorted(included)}, "
            f"missing={sorted(configured - included)}"
        )

        actual = _count_h2_headings(result.content)
        expected = _expected_h2_count_for_target(target_name, cfg)
        assert actual == expected, (
            f"target {target_name!r} `## ` heading count drift: "
            f"compiled output has {actual} `## ` headings but the "
            f"included source layers contain {expected}. Likely cause: "
            "`_truncate_to_budget` dropped a layer to fit token_budget="
            f"{target_spec.get('token_budget')}."
        )


def test_layer_count_consistent_across_targets() -> None:
    """Sanity floor: every FULL-CORPUS target MUST include >= 4 layers.

    Prevents accidental config that ships a 1-layer corpus (e.g. a
    misguided optimization that strips conventions/workflow/style from
    the compiled output, leaving only soul + architecture). Cursor
    currently ships 5 layers; agents_md ships 4 (style intentionally
    excluded).

    v15.0.x clean_repo C2-1 (decision D2): the ``style_md`` target is a
    deliberate SINGLE-LAYER dedicated view (``docs/STYLE-RULES.md`` —
    the P4 Style layer rendered tool-agnostically, discovered via the
    agents_md postscript pointer). It is pinned to exactly ``[style]``
    here rather than exempted silently: a full-corpus target dropping
    below 4 layers still fails, and the dedicated view growing extra
    layers (scope creep) also fails.
    """
    cfg = _load_config()
    assert cfg.get("targets"), "compile-config.yaml has no targets defined"
    single_layer_views = {"style_md": ["style"]}
    for target_name, target_spec in cfg["targets"].items():
        layers = target_spec.get("include_layers", [])
        if target_name in single_layer_views:
            assert layers == single_layer_views[target_name], (
                f"dedicated view target {target_name!r} must ship exactly "
                f"{single_layer_views[target_name]}, got {layers} (D2 scope)"
            )
            continue
        n = len(layers)
        assert n >= 4, (
            f"target {target_name!r} ships only {n} layer(s); the sanity "
            "floor is 4. If this is intentional, update this test and "
            "document the rationale in `.local/research/`."
        )
