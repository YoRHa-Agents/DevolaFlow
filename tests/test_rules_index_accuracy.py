"""Lint `.rules/index.md` ↔ `.rules/compile-config.yaml` consistency (closes G-013).

Background
----------
G-003 documented that `.rules/index.md` had stale token budgets (8000/6000)
while `.rules/compile-config.yaml` had 12000/12000 (the v9.0.0 PV-07 bump
per ADR-007 D5). v9.1.0 W1-03 fixed the documentation drift by updating
the markdown ``## Targets`` table + adding the inline footnote. W2-03
(this module) prevents the drift from ever recurring by lifting the
consistency check into CI.

Lint contract
-------------
This module enforces four invariants on the docs surface:

1. Token budgets in the ``## Targets`` markdown table match the
   ``targets.<name>.token_budget`` values in ``.rules/compile-config.yaml``.
2. The number of data rows in the layer table (the markdown table whose
   header includes "Rule count") equals ``len(cfg["layers"])``.
3. Every configured layer's ``file:`` value (e.g. ``soul.mdc``) appears
   verbatim somewhere in ``.rules/index.md``.
4. The documented compile command (``from devolaflow.local.compiler import
   RuleCompiler``) is present so the operator-facing recipe cannot
   silently disappear from the docs.

Future bumps of ``compile-config.yaml.targets.<X>.token_budget`` MUST also
update ``.rules/index.md`` or one of the tests below fails. Same contract
applies to layer add/remove churn under ``compile-config.yaml.layers``.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
INDEX_MD = REPO_ROOT / ".rules" / "index.md"
COMPILE_CONFIG = REPO_ROOT / ".rules" / "compile-config.yaml"


def _load_config() -> dict:
    """Return the parsed `.rules/compile-config.yaml` structure."""
    return yaml.safe_load(COMPILE_CONFIG.read_text(encoding="utf-8"))


def _read_index() -> str:
    """Return the `.rules/index.md` text."""
    return INDEX_MD.read_text(encoding="utf-8")


def _find_token_budget_in_index(target_name: str) -> int:
    """Parse the ``| <target> | <output> | <format> | <budget> |`` row.

    The ``## Targets`` table currently has shape::

        | Target    | Output                              | Format   | Token Budget |
        |-----------|-------------------------------------|----------|--------------|
        | cursor    | `.cursor/rules/repo-governance.mdc` | MDC      | 12000        |
        | agents_md | `AGENTS.md`                         | Markdown | 12000        |

    The regex tolerates whitespace around cell content but assumes the
    column ordering is fixed. If the column ordering is reshuffled, the
    test fails loudly at the row-not-found assertion below.
    """
    text = _read_index()
    pattern = rf"\|\s*{re.escape(target_name)}\s*\|[^|]+\|[^|]+\|\s*(\d+)\s*\|"
    match = re.search(pattern, text)
    if match is None:
        raise AssertionError(
            f"target {target_name!r} not found in .rules/index.md ## Targets table"
        )
    return int(match.group(1))


def test_token_budgets_match_compile_config() -> None:
    """G-013: token budgets in `index.md` must match `compile-config.yaml`.

    Failure means ``.rules/index.md`` documents a stale ``token_budget`` —
    re-run the documentation update that should accompany every
    ``targets.<X>.token_budget`` bump in ``.rules/compile-config.yaml``.
    """
    cfg = _load_config()
    for target_name in ("cursor", "agents_md", "style_md"):
        expected = cfg["targets"][target_name]["token_budget"]
        actual = _find_token_budget_in_index(target_name)
        assert actual == expected, (
            f"G-013: .rules/index.md ## Targets row for {target_name!r} shows "
            f"token_budget={actual} but the source-of-truth in "
            f".rules/compile-config.yaml.targets.{target_name}.token_budget = {expected}. "
            f"Update the markdown row to match (or update both deliberately)."
        )


def test_layer_count_matches_layers_section() -> None:
    """G-013: the layer-table data-row count must equal ``len(cfg['layers'])``.

    Walks the markdown table whose header row contains "Rule count" (the
    layer table — the only table in `index.md` with that column) and counts
    data rows, skipping the header + separator row.
    """
    cfg = _load_config()
    expected_layer_count = len(cfg["layers"])
    text = _read_index()

    lines = text.splitlines()
    header_idx = next(
        (i for i, line in enumerate(lines) if line.startswith("|") and "Rule count" in line),
        None,
    )
    assert header_idx is not None, (
        "G-013: .rules/index.md is missing the layer table (no header row "
        "with the 'Rule count' column)"
    )

    data_rows = 0
    for line in lines[header_idx + 2 :]:
        stripped = line.strip()
        if not stripped.startswith("|"):
            break
        if set(stripped) <= set("|-: "):
            continue
        data_rows += 1

    assert data_rows == expected_layer_count, (
        f"G-013: .rules/index.md layer table has {data_rows} data rows but "
        f".rules/compile-config.yaml declares {expected_layer_count} layers. "
        f"Add or remove the markdown row to match."
    )


def test_index_md_lists_every_configured_layer_by_filename() -> None:
    """G-013: every layer's ``file:`` value must appear in `index.md`.

    The mention may be inside backticks or any other markdown context — we
    only check substring presence. Failure means a layer was added to
    ``compile-config.yaml`` without a corresponding row in the markdown.
    """
    cfg = _load_config()
    text = _read_index()
    missing = [layer["file"] for layer in cfg["layers"] if layer["file"] not in text]
    assert not missing, (
        f"G-013: .rules/index.md is missing rows for layer file(s) {missing}. "
        f"Each layer in .rules/compile-config.yaml must have a corresponding "
        f"row mentioning its `file:` value verbatim."
    )


def test_compile_command_is_present() -> None:
    """G-013 (BONUS): the documented compile command must remain in `index.md`.

    Pins the verbatim ``from devolaflow.local.compiler import RuleCompiler``
    import path so the operator-facing compile recipe cannot silently
    disappear from the docs.
    """
    text = _read_index()
    needle = "from devolaflow.local.compiler import RuleCompiler"
    assert needle in text, (
        f"G-013: .rules/index.md must contain the verbatim compile command "
        f"snippet ({needle!r}) — operators rely on this snippet for the "
        f"regenerate-corpus recipe."
    )
