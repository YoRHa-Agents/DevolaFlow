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


def _collect_violations(payload: dict[str, Any]) -> list[HookViolation]:
    if not isinstance(payload, dict):
        return []

    files = payload.get("files") or payload.get("modified_files") or []
    if not isinstance(files, list) or not files:
        return []

    formatter = payload.get("formatter") or payload.get("format_command")
    if formatter:
        return []

    extensions = {f.rsplit(".", 1)[-1].lower() for f in files if "." in f}
    lang_map = {
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

    unformatted_langs = []
    for ext in extensions:
        lang = lang_map.get(ext)
        if lang and lang in KNOWN_FORMATTERS:
            unformatted_langs.append(lang)

    if not unformatted_langs:
        return []

    return [
        HookViolation(
            code="FOE001",
            message=(
                f"No formatter declared for {len(unformatted_langs)} language(s): "
                f"{unformatted_langs}. Consider configuring a format-on-edit hook."
            ),
            severity="warning",
            context={
                "languages": unformatted_langs,
                "suggested_formatters": {
                    lang: KNOWN_FORMATTERS[lang][0] for lang in unformatted_langs
                },
            },
        )
    ]


def format_on_edit(payload: dict[str, Any], *, strict: bool = False) -> HookResult:
    """Check whether a formatter is declared for modified files."""
    violations = _collect_violations(payload)
    return finalize(EVENT, violations, strict=strict)


__all__ = ["EVENT", "KNOWN_FORMATTERS", "format_on_edit"]
