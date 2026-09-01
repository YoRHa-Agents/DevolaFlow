"""Declared vocabulary with no production writer (v24.3.0).

v24.1.0 found `bypassed` in the compaction telemetry vocabulary: declared as a
constant, collected into the frozenset that validates outcomes, documented in
the module docstring, exercised by tests — and never once produced by
production code. The CHANGELOG had announced it. The fix was one line; the
class of defect was unguarded, which is what this module closes.

A declared value is *written* when production code puts it somewhere. The
declaration itself does not count, and neither does membership in the very set
that validates it, because both of those exist whether or not anything ever
emits the value. Imports do not count either — a re-export is not a use, which
is the same rule `scripts/detect_dead_apis.py` applies to symbols.

Two shapes of vocabulary are covered:

* members of an ``Enum`` subclass, including ``StrEnum``;
* module-level ``NAME: Final[str] = "..."`` constants that the same module
  gathers into a set or frozenset literal — the shape that hid `bypassed`.

Tests are deliberately excluded from the search. A vocabulary value that only
a test produces is exactly the finding: the test proves the value can be
written, not that anything writes it.

Known limit: an enum member is matched by attribute name, not by
``Class.MEMBER`` pair, so a member whose name collides with an unrelated
attribute elsewhere reads as written. The scan is deliberately biased that way
— a false exemption is quieter than a false accusation, and the defect this
catches is vocabulary nothing writes *at all*.
"""

from __future__ import annotations

import ast
import logging
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final

logger = logging.getLogger(__name__)

#: Directories searched for production writers. `tests/` is absent by design.
PRODUCTION_ROOTS: Final[tuple[str, ...]] = ("src/devolaflow", "scripts", "benchmarks")

#: The package whose declarations are audited.
DECLARATION_ROOT: Final[str] = "src/devolaflow"

_ENUM_BASES: Final[frozenset[str]] = frozenset(
    {"Enum", "StrEnum", "IntEnum", "IntFlag", "Flag", "ReprEnum"}
)

_TEMPLATE_ENUM_REASON: Final[str] = (
    "the declaring class is already exempted in scripts/detect_dead_apis.py as a "
    "public API with no in-repo caller (A-5.2); a class nothing calls cannot have "
    "a member anything writes, and re-litigating that belongs with the class"
)

#: Vocabulary that is legitimately read-only, each with the reason it is.
#:
#: An entry here is a claim that nothing in this repository should ever write
#: the value — because an external producer does, or because it is a reserved
#: slot with a dated owner. "We have not got round to it" is not a reason; that
#: is the finding.
ALLOWLIST: Final[dict[str, str]] = {
    "JoinStrategy.ALL": _TEMPLATE_ENUM_REASON,
    "JoinStrategy.ANY": _TEMPLATE_ENUM_REASON,
    "JoinStrategy.N_OF": _TEMPLATE_ENUM_REASON,
    "OnExhaustion.ABORT": _TEMPLATE_ENUM_REASON,
    "GateFailAction.LOOP_BACK": _TEMPLATE_ENUM_REASON,
    "GateFailAction.ABORT": _TEMPLATE_ENUM_REASON,
}


@dataclass(frozen=True)
class VocabularyFinding:
    """One declared value that no production code writes."""

    qualified_name: str
    declared_in: str
    line: int
    kind: str

    def __str__(self) -> str:
        return (
            f"UNWRITTEN_{self.kind.upper()}: {self.qualified_name} ({self.declared_in}:{self.line})"
        )


@dataclass(frozen=True)
class _Declaration:
    qualified_name: str
    attribute: str | None
    name: str | None
    declared_in: str
    line: int
    kind: str


def _parse(path: Path) -> ast.Module | None:
    try:
        return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (OSError, SyntaxError, UnicodeError) as exc:
        logger.warning("vocabulary audit could not parse %s: %s", path, exc)
        return None


def _python_files(root: Path, relative: str) -> list[Path]:
    base = root / relative
    if not base.is_dir():
        return []
    return sorted(p for p in base.rglob("*.py") if "__pycache__" not in p.parts)


def _is_enum_class(node: ast.ClassDef) -> bool:
    for base in node.bases:
        if isinstance(base, ast.Name) and base.id in _ENUM_BASES:
            return True
        if isinstance(base, ast.Attribute) and base.attr in _ENUM_BASES:
            return True
    return False


def _string_constant_name(node: ast.stmt) -> str | None:
    """Return the target name of a module-level ``NAME: ... = "literal"``."""

    if not isinstance(node, ast.AnnAssign) or not isinstance(node.target, ast.Name):
        return None
    if not isinstance(node.value, ast.Constant) or not isinstance(node.value.value, str):
        return None
    return node.target.id


def _vocabulary_set_members(module: ast.Module) -> set[str]:
    """Return names gathered into a module-level set or frozenset literal.

    These are the declaration's own bookkeeping: the set that validates a value
    mentions it whether or not anything writes it, so such a mention must not
    be mistaken for a writer.
    """

    members: set[str] = set()
    for node in ast.walk(module):
        if isinstance(node, ast.Set):
            elements: Iterable[ast.expr] = node.elts
        elif (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id in {"frozenset", "set"}
            and node.args
        ):
            argument = node.args[0]
            elements = argument.elts if isinstance(argument, ast.Set | ast.List) else ()
        else:
            continue
        members.update(item.id for item in elements if isinstance(item, ast.Name))
    return members


def collect_declarations(repo_root: str | Path) -> tuple[_Declaration, ...]:
    """Collect every enum member and vocabulary constant declared in the package."""

    root = Path(repo_root)
    declarations: list[_Declaration] = []
    for path in _python_files(root, DECLARATION_ROOT):
        module = _parse(path)
        if module is None:
            continue
        relative = path.relative_to(root).as_posix()
        for node in module.body:
            if isinstance(node, ast.ClassDef) and _is_enum_class(node):
                for member in node.body:
                    member_name = _string_constant_name(member) or _assign_name(member)
                    if member_name is None or member_name.startswith("_"):
                        continue
                    declarations.append(
                        _Declaration(
                            qualified_name=f"{node.name}.{member_name}",
                            attribute=member_name,
                            name=None,
                            declared_in=relative,
                            line=member.lineno,
                            kind="enum_member",
                        )
                    )
        gathered = _vocabulary_set_members(module)
        for node in module.body:
            constant = _string_constant_name(node)
            if constant is None or constant.startswith("_") or constant not in gathered:
                continue
            declarations.append(
                _Declaration(
                    qualified_name=constant,
                    attribute=None,
                    name=constant,
                    declared_in=relative,
                    line=node.lineno,
                    kind="vocabulary_constant",
                )
            )
    return tuple(declarations)


def _assign_name(node: ast.stmt) -> str | None:
    if isinstance(node, ast.Assign) and len(node.targets) == 1:
        target = node.targets[0]
        if isinstance(target, ast.Name):
            return target.id
    return None


def _write_sites(repo_root: str | Path) -> tuple[set[str], set[str]]:
    """Return attribute names and bare names referenced by production code.

    Import statements are skipped: re-exporting a value is not writing it.
    A declaration's own set-membership bookkeeping is skipped for the same
    reason, which is why the sets are collected per module and subtracted.
    """

    root = Path(repo_root)
    attributes: set[str] = set()
    names: set[str] = set()
    for relative in PRODUCTION_ROOTS:
        for path in _python_files(root, relative):
            module = _parse(path)
            if module is None:
                continue
            bookkeeping = _vocabulary_set_members(module)
            enum_bodies = {
                id(member)
                for node in module.body
                if isinstance(node, ast.ClassDef) and _is_enum_class(node)
                for member in node.body
            }
            for node in ast.walk(module):
                if isinstance(node, ast.Import | ast.ImportFrom):
                    continue
                if id(node) in enum_bodies:
                    continue
                if isinstance(node, ast.Attribute):
                    attributes.add(node.attr)
                elif isinstance(node, ast.Name) and node.id not in bookkeeping:
                    names.add(node.id)
    return attributes, names


def find_unwritten_vocabulary(
    repo_root: str | Path = ".",
    *,
    allowlist: Sequence[str] | None = None,
) -> tuple[VocabularyFinding, ...]:
    """Report declared values that no production code writes."""

    permitted = set(ALLOWLIST if allowlist is None else allowlist)
    attributes, names = _write_sites(repo_root)
    findings: list[VocabularyFinding] = []
    for declaration in collect_declarations(repo_root):
        if declaration.qualified_name in permitted:
            continue
        written = (
            declaration.attribute in attributes
            if declaration.attribute is not None
            else declaration.name in names
        )
        if not written:
            findings.append(
                VocabularyFinding(
                    qualified_name=declaration.qualified_name,
                    declared_in=declaration.declared_in,
                    line=declaration.line,
                    kind=declaration.kind,
                )
            )
    return tuple(sorted(findings, key=lambda item: (item.declared_in, item.line)))


def unused_allowlist_entries(repo_root: str | Path = ".") -> tuple[str, ...]:
    """Report allowlist entries whose declaration no longer exists (A-5.2).

    An exemption that outlives the thing it exempts is a claim nobody can
    check, and it silently widens the next scan's blind spot.
    """

    declared = {item.qualified_name for item in collect_declarations(repo_root)}
    return tuple(sorted(set(ALLOWLIST) - declared))


__all__ = [
    "ALLOWLIST",
    "DECLARATION_ROOT",
    "PRODUCTION_ROOTS",
    "VocabularyFinding",
    "collect_declarations",
    "find_unwritten_vocabulary",
    "unused_allowlist_entries",
]
