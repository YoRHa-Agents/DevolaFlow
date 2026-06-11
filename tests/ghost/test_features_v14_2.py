"""Ghost audit — per-cycle W-18 feature stanzas for the v14.2 cycle.

Split from ``tests/test_no_ghost_features.py`` per v15-ADR-001
(v14.3.0). New W-18 stanzas for a v14.2.x release append HERE; the
next MINOR cycle rotates to a fresh ``test_features_v<MAJ>_<MIN>.py``.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path


def test_v14_2_0_digest_budget_blocking_symbols(project_root: Path) -> None:
    """W-18 v14.2.0: the REQ-OUT-01 advisory→blocking promotion has coverage.

    Discharges the W-18 precondition for the v14.2.0 CHANGELOG entry. The
    v14.0.0 design (§8b) telegraphed verbatim: "REQ-OUT-01 lint is advisory
    this cycle; promote to blocking in v14.2.0". The stanza asserts the
    load-bearing surfaces of that promotion:

    (a) lint.py declares enforce_digest_budget + HumanBudgetExceededError.
    (b) reporter.py enforces the budget on both emission paths
        (regenerate_all + the --human CLI) via _check_digest_budget.
    (c) the agent_workspace package re-exports the new public symbols.
    (d) references/human-surface.md states blocking-since-v14.2.0.
    (e) companion test coverage exists.

    Source: .local/research/v14.0.0_design.md §8b (advisory finding).
    """
    # --- (a) lint.py enforcement symbols ------------------------------
    lint_text = (project_root / "src/devolaflow/agent_workspace/lint.py").read_text(
        encoding="utf-8"
    )
    assert "def enforce_digest_budget(" in lint_text, (
        "W-18 v14.2.0 violation: lint.py missing enforce_digest_budget()."
    )
    assert "class HumanBudgetExceededError(" in lint_text, (
        "W-18 v14.2.0 violation: lint.py missing HumanBudgetExceededError."
    )

    # --- (b) reporter.py emission-path enforcement --------------------
    reporter_text = (project_root / "src/devolaflow/agent_workspace/reporter.py").read_text(
        encoding="utf-8"
    )
    assert "enforce_digest_budget" in reporter_text, (
        "W-18 v14.2.0 violation: reporter.py does not consume enforce_digest_budget."
    )
    # def + the regenerate_all call site + the --human CLI call site.
    assert reporter_text.count("_check_digest_budget(") >= 3, (
        "W-18 v14.2.0 violation: reporter.py must enforce the digest budget on "
        "BOTH emission paths (regenerate_all + the --human CLI)."
    )

    # --- (c) package __all__ re-exports ------------------------------
    init_text = (project_root / "src/devolaflow/agent_workspace/__init__.py").read_text(
        encoding="utf-8"
    )
    for sym in ("enforce_digest_budget", "HumanBudgetExceededError"):
        assert f'"{sym}"' in init_text, (
            f"W-18 v14.2.0 violation: agent_workspace/__init__.py __all__ missing {sym!r}."
        )

    # --- (d) reference doc states the promotion ----------------------
    ref_text = (project_root / "workflow-system/agent/references/human-surface.md").read_text(
        encoding="utf-8"
    )
    assert "BLOCKING since v14.2.0" in ref_text, (
        "W-18 v14.2.0 violation: references/human-surface.md no longer/never "
        "states REQ-OUT-01 is BLOCKING since v14.2.0."
    )

    # --- (e) companion test coverage ---------------------------------
    reporter_test = (project_root / "tests/test_reporter.py").read_text(encoding="utf-8")
    assert "HumanBudgetExceededError" in reporter_test, (
        "W-18 v14.2.0 violation: tests/test_reporter.py lacks blocking-emission coverage."
    )
    lint_test = (project_root / "tests/test_lint_human.py").read_text(encoding="utf-8")
    assert "enforce_digest_budget" in lint_test, (
        "W-18 v14.2.0 violation: tests/test_lint_human.py lacks enforce_digest_budget coverage."
    )


# ---------------------------------------------------------------------------
# G-024 (v14.2.2) — env-flag inventory is machine-checkable.
#
# `references/env-flags.md` §2.0 defines the counting basis: "active runtime
# flags" = the §2 table rows; the count is NEVER hand-pinned in rule prose
# (W-22.4 / W-24.4 cite the inventory instead). The lints below keep the
# inventory truthful against the actual `src/devolaflow/` env-read surface.
# ---------------------------------------------------------------------------

_G024_FLAG_NAME_RE = re.compile(r"^DEVOLAFLOW_[A-Z0-9_]+$")


_G024_ENV_FLAGS_DOC = Path("workflow-system/agent/references/env-flags.md")


def _g024_runtime_env_reads(src_root: Path) -> set[str]:
    """AST-derive the set of ``DEVOLAFLOW_*`` env vars READ by runtime code.

    A flag counts as read when its name (a string literal, directly or via
    a module-level/local string-constant) is the first argument of an
    env-read expression:

    * ``os.environ.get(X)`` / ``os.environ[X]`` / ``os.getenv(X)``
    * ``<recv>.get(X)`` where ``<recv>`` was bound from an expression
      containing ``os.environ`` (the repo-idiomatic
      ``source = env if env is not None else os.environ`` test-injection
      pattern, including ``self._env = ... os.environ ...`` attributes).

    Deliberately NOT collected: docstring/comment mentions (retired or
    telegraphed-only names), names inside operator-facing message strings,
    and dict-valued indirections (e.g. ``_API_KEY_ENV_VARS[provider]`` —
    the §3 mock-key fixture path).
    """
    found: set[str] = set()
    for py_file in sorted(src_root.rglob("*.py")):
        tree = ast.parse(py_file.read_text(encoding="utf-8"))
        const_map: dict[str, str] = {}
        env_receivers: set[str] = set()
        for node in ast.walk(tree):
            value = getattr(node, "value", None)
            is_str_const = isinstance(value, ast.Constant) and isinstance(value.value, str)
            if isinstance(node, ast.Assign):
                if is_str_const and _G024_FLAG_NAME_RE.match(value.value):
                    for tgt in node.targets:
                        if isinstance(tgt, ast.Name):
                            const_map[tgt.id] = value.value
                elif value is not None and "os.environ" in ast.unparse(value):
                    for tgt in node.targets:
                        if isinstance(tgt, ast.Name):
                            env_receivers.add(tgt.id)
                        elif isinstance(tgt, ast.Attribute):
                            env_receivers.add(tgt.attr)
            elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                if is_str_const and _G024_FLAG_NAME_RE.match(value.value):
                    const_map[node.target.id] = value.value
                elif value is not None and "os.environ" in ast.unparse(value):
                    env_receivers.add(node.target.id)

        def _resolve(arg: ast.expr, *, consts: dict[str, str] = const_map) -> str | None:
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                return arg.value if _G024_FLAG_NAME_RE.match(arg.value) else None
            if isinstance(arg, ast.Name):
                return consts.get(arg.id)
            return None

        for node in ast.walk(tree):
            flag: str | None = None
            if isinstance(node, ast.Call) and node.args:
                func = node.func
                if isinstance(func, ast.Attribute) and func.attr in {"get", "pop", "setdefault"}:
                    recv = func.value
                    recv_is_env = (
                        "environ" in ast.unparse(recv)
                        or (isinstance(recv, ast.Name) and recv.id in env_receivers)
                        or (isinstance(recv, ast.Attribute) and recv.attr in env_receivers)
                    )
                    if recv_is_env:
                        flag = _resolve(node.args[0])
                elif (isinstance(func, ast.Attribute) and func.attr == "getenv") or (
                    isinstance(func, ast.Name) and func.id == "getenv"
                ):
                    flag = _resolve(node.args[0])
            elif isinstance(node, ast.Subscript) and "environ" in ast.unparse(node.value):
                flag = _resolve(node.slice)
            if flag:
                found.add(flag)
    return found


def _g024_parse_inventory(doc_text: str) -> tuple[dict[str, str], set[str], set[str]]:
    """Parse env-flags.md → (§2 rows {flag: surface}, §3 fixtures, §4 fwd-declared).

    The §2 surface is ``"code-read"`` unless the row body carries an
    explicit ``**Read surface**`` field saying ``prompt-side`` / ``unwired``
    (the only two exemption markers §2.0 defines).
    """
    section2: dict[str, str] = {}
    heading_re = re.compile(r"^### 2\.\d+ `(DEVOLAFLOW_[A-Z0-9_]+)`", re.MULTILINE)
    matches = list(heading_re.finditer(doc_text))
    section3_start = doc_text.index("\n## 3.")
    for i, m in enumerate(matches):
        body_end = matches[i + 1].start() if i + 1 < len(matches) else section3_start
        body = doc_text[m.end() : body_end]
        surface = "code-read"
        surface_field = re.search(r"\*\*Read surface\*\*\s*\|\s*(\S+)", body)
        if surface_field:
            marker = surface_field.group(1).rstrip("—- ").lower()
            assert marker in {"prompt-side", "unwired"}, (
                f"G-024: §2 row {m.group(1)} carries unknown Read-surface marker "
                f"{marker!r}; §2.0 defines only 'prompt-side' and 'unwired'."
            )
            surface = marker
        section2[m.group(1)] = surface

    section3 = set(re.findall(r"^### 3\.\d+ `(DEVOLAFLOW_[A-Z0-9_]+)`", doc_text, re.MULTILINE))
    section4_block = doc_text[doc_text.index("\n## 4.") : doc_text.index("\n## 5.")]
    section4 = set(
        re.findall(r"^\| \d+ \| `(DEVOLAFLOW_[A-Z0-9_]+)`", section4_block, re.MULTILINE)
    )
    return section2, section3, section4


def test_v14_2_2_g024_env_flag_inventory_matches_runtime(project_root: Path) -> None:
    """G-024: env-flags.md §2 row names == the runtime env-read set.

    Replaces the hand-pinned "8 per v11.x baseline" counts that W-22.4 /
    W-24.4 used to carry (26 distinct ``DEVOLAFLOW_*`` identifiers exist
    repo-wide — distinct-identifier grep is a DIFFERENT measure per the
    §2.0 counting basis). Contract:

    1. every §2 code-read row is genuinely read by ``src/devolaflow/``;
    2. every runtime env read has a §2 row (or is a §3 test-fixture id);
    3. prompt-side / unwired §2 rows have NO Python read site;
    4. §3 test-fixture ids and §4 forward-declared ids never overlap §2,
       and §4 ids are not silently wired without promotion to §2.
    """
    doc_text = (project_root / _G024_ENV_FLAGS_DOC).read_text(encoding="utf-8")
    section2, section3, section4 = _g024_parse_inventory(doc_text)
    derived = _g024_runtime_env_reads(project_root / "src" / "devolaflow")

    code_rows = {flag for flag, surface in section2.items() if surface == "code-read"}
    exempt_rows = set(section2) - code_rows

    assert code_rows == derived - section3, (
        f"G-024 violation: env-flags.md §2 code-read rows drifted from the "
        f"AST-derived runtime env-read set.\n"
        f"  documented-but-not-read: {sorted(code_rows - (derived - section3))}\n"
        f"  read-but-undocumented:   {sorted((derived - section3) - code_rows)}\n"
        f"Add/remove the §2 row in the same PR as the runtime read (W-20 §7 "
        f"checklist step 4), or mark the row prompt-side/unwired per §2.0."
    )
    assert not (exempt_rows & derived), (
        f"G-024 violation: §2 rows marked prompt-side/unwired ARE read by "
        f"src/devolaflow/: {sorted(exempt_rows & derived)}. Re-mark them code-read."
    )
    assert not (section3 & set(section2)), (
        f"G-024 violation: §3 test-fixture ids duplicated as §2 rows: "
        f"{sorted(section3 & set(section2))}"
    )
    assert not (section4 & set(section2)) and not (section4 & derived), (
        f"G-024 violation: §4 forward-declared ids overlap §2 rows or are "
        f"already wired in runtime without §2 promotion: "
        f"{sorted((section4 & set(section2)) | (section4 & derived))}"
    )


def test_v14_2_2_g024_rule_prose_cites_inventory_not_numerals(project_root: Path) -> None:
    """G-024: W-22.4 / W-24.4 cite the §2 inventory; no hand-pinned counts.

    The stale "env-flag count remains/stays at 8 per v11.x baseline"
    literals were replaced at v14.2.2; the canonical count lives ONLY in
    env-flags.md §2 (counting basis §2.0). Guards the canonical source AND
    both compiled outputs so a recompile cannot resurrect the numeral.
    """
    hand_pin = re.compile(r"count (?:remains|stays) at \d+")
    for rel in (".rules/workflow.mdc", ".cursor/rules/repo-governance.mdc", "AGENTS.md"):
        text = (project_root / rel).read_text(encoding="utf-8")
        for rule_id in ("W-22.4", "W-24.4"):
            start = text.index(f"### {rule_id}")
            next_heading = re.search(r"\n##+ ", text[start + 4 :])
            end = start + 4 + next_heading.start() if next_heading else len(text)
            section = text[start:end]
            assert "references/env-flags.md" in section, (
                f"G-024 violation: {rel} {rule_id} no longer cites the canonical "
                f"env-flag inventory (references/env-flags.md §2)."
            )
            assert not hand_pin.search(section), (
                f"G-024 violation: {rel} {rule_id} hand-pins a numeric env-flag "
                f"count again; cite references/env-flags.md §2 instead."
            )
