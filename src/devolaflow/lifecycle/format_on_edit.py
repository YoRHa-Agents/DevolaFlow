"""Post-edit formatting hook — ``format_on_edit``.

Validates that a formatting command is available for modified files and
records the formatter configuration so downstream consumers (e.g. the
interview stage) can suggest tool-native hooks (.claude/settings.json
PostToolUse, .cursor/hooks.json).

This hook does NOT execute the formatter — it only checks that the
dispatch payload declares a formatter for the detected language. Actual
formatting is left to the tool-native hook layer (Claude hooks, Cursor
hooks, git pre-commit, etc.).

Registered as an extra handler on a custom ``format_on_edit`` event.
"""

from __future__ import annotations

from typing import Any

from devolaflow.lifecycle.dispatcher import HookResult, HookViolation, finalize

EVENT = "format_on_edit"

KNOWN_FORMATTERS: dict[str, list[str]] = {
    "python": ["ruff format", "black", "autopep8", "yapf"],
    "javascript": ["prettier", "biome format", "eslint --fix", "dprint"],
    "typescript": ["prettier", "biome format", "eslint --fix", "dprint"],
    "go": ["gofmt", "goimports"],
    "rust": ["rustfmt", "cargo fmt"],
    "css": ["prettier", "stylelint --fix"],
    "html": ["prettier"],
    "json": ["prettier", "biome format"],
    "yaml": ["prettier"],
    "markdown": ["prettier"],
}


_LANG_BY_EXTENSION: dict[str, str] = {
    "py": "python",
    "js": "javascript",
    "ts": "typescript",
    "go": "go",
    "rs": "rust",
    "css": "css",
    "html": "html",
    "json": "json",
    "yaml": "yaml",
    "yml": "yaml",
    "md": "markdown",
}


def _extract_files(payload: dict[str, Any]) -> list[str]:
    """Return the list of modified files declared in *payload*, or [] when absent.

    Accepts both ``"files"`` and the legacy alias ``"modified_files"``.
    Returns ``[]`` when the value is missing, empty, or not a list.
    """
    files = payload.get("files") or payload.get("modified_files") or []
    if not isinstance(files, list):
        return []
    return files


def _detect_unformatted_languages(files: list[str]) -> list[str]:
    """Return languages present in *files* without a registered formatter.

    A file contributes its language only when its extension maps to one of
    the entries in :data:`_LANG_BY_EXTENSION` AND that language is registered
    in :data:`KNOWN_FORMATTERS`. Multiple extensions sharing the same language
    (e.g. ``.yaml`` and ``.yml`` both → ``"yaml"``) intentionally yield
    duplicate entries, matching the legacy behaviour preserved as a public
    contract.
    """
    extensions = {f.rsplit(".", 1)[-1].lower() for f in files if "." in f}
    unformatted: list[str] = []
    for ext in extensions:
        lang = _LANG_BY_EXTENSION.get(ext)
        if lang and lang in KNOWN_FORMATTERS:
            unformatted.append(lang)
    return unformatted


def _build_foe001(unformatted_langs: list[str]) -> HookViolation:
    """Construct the FOE001 ``HookViolation`` for the given languages."""
    return HookViolation(
        code="FOE001",
        message=(
            f"No formatter declared for {len(unformatted_langs)} language(s): "
            f"{unformatted_langs}. Consider configuring a format-on-edit hook."
        ),
        severity="warning",
        context={
            "languages": unformatted_langs,
            "suggested_formatters": {lang: KNOWN_FORMATTERS[lang][0] for lang in unformatted_langs},
        },
    )


def _collect_violations(payload: dict[str, Any]) -> list[HookViolation]:
    if not isinstance(payload, dict):
        return []
    files = _extract_files(payload)
    if not files:
        return []
    if payload.get("formatter") or payload.get("format_command"):
        return []
    unformatted_langs = _detect_unformatted_languages(files)
    if not unformatted_langs:
        return []
    return [_build_foe001(unformatted_langs)]


def format_on_edit(payload: dict[str, Any], *, strict: bool = False) -> HookResult:
    """Check whether a formatter is declared for modified files."""
    violations = _collect_violations(payload)
    return finalize(EVENT, violations, strict=strict)


__all__ = ["EVENT", "KNOWN_FORMATTERS", "format_on_edit"]
