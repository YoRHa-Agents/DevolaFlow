"""Per-host stdin normalization — host tool-event JSON → :class:`BridgeEvent`.

v17.0.0 R2 (G17-B1 closure, design §D-R2-1). Each of the six supported
hosts (Cursor, Claude Code, Codex, KimiCode, DSH, Copilot) delivers its
pre-tool-use payload as one JSON object on stdin, but the field
spellings differ. This module is deliberately LIBERAL in what it
accepts (unknown shapes fail-open as ``kind="unknown"``) and strict in
what it emits (a frozen :class:`BridgeEvent`).

Documented precedence order (highest wins):

1. An explicit ``--event`` CLI override (``event_override`` argument).
2. DSH's explicit ``kind`` field (our own plugin authors it — trusted).
3. Tool-name classification: ``tool_name`` is consulted before ``tool``;
   the name is matched against the known write-tool / shell-tool sets.
   Codex ``apply_patch`` is special-cased (see below).
4. Host hook-event hints: a ``hook_event_name`` of
   ``beforeShellExecution`` forces shell-kind.
5. Shape inference: a resolvable path → ``file_write``; a resolvable
   command with no path → ``shell``.
6. Anything else → ``kind="unknown"`` (the decision layer fail-opens).

Path key precedence inside ``tool_input`` (then the top level):
``path`` > ``file_path`` > ``target_file``.

Codex ``apply_patch``: the patch text (any string value in
``tool_input``, or the top-level ``input`` / ``patch`` field) is
scanned for ``*** Update File:`` / ``*** Add File:`` /
``*** Delete File:`` markers. Extracted targets become a multi-path
``file_write`` event; when NO path is extractable the event degrades
to shell-kind (advisory allow per design §D-R2-1 step 3).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

KNOWN_HOSTS: tuple[str, ...] = ("cursor", "claude", "codex", "kimi", "dsh", "copilot")

KIND_FILE_WRITE = "file_write"
KIND_SHELL = "shell"
KIND_UNKNOWN = "unknown"

# Union of write-tool spellings across the six hosts. Matching is exact
# (host tool names are stable ids).
_WRITE_TOOLS = frozenset(
    {
        "Write",
        "StrReplace",
        "Edit",
        "MultiEdit",
        "WriteFile",
        "StrReplaceFile",
        "write",
        "edit",
        "str_replace_editor",
    }
)
_SHELL_TOOLS = frozenset({"Bash", "Shell", "bash", "shell", "exec"})
_APPLY_PATCH_TOOL = "apply_patch"

# tool_input path-key precedence (documented above).
_PATH_KEYS: tuple[str, ...] = ("path", "file_path", "target_file")

_PATCH_MARKER_RE = re.compile(
    r"^\*\*\* (?:Update|Add|Delete) File: (?P<target>.+?)\s*$",
    re.MULTILINE,
)


@dataclass(frozen=True)
class BridgeEvent:
    """A normalized host tool event.

    ``path`` carries the primary write target; ``extra_paths`` carries
    additional targets for multi-file events (Codex ``apply_patch``).
    The decision layer checks EVERY target against the owned set.
    """

    host: str
    kind: str
    path: str | None = None
    extra_paths: tuple[str, ...] = field(default=())
    command: str | None = None
    cwd: str | None = None
    tool: str | None = None

    @property
    def all_paths(self) -> tuple[str, ...]:
        """Primary + extra write targets, in order."""
        if self.path is None:
            return self.extra_paths
        return (self.path, *self.extra_paths)


def _first_str(mapping: dict[str, Any], keys: tuple[str, ...]) -> str | None:
    for key in keys:
        value = mapping.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def _extract_patch_targets(tool_input: dict[str, Any], data: dict[str, Any]) -> tuple[str, ...]:
    """Harvest ``*** Update/Add/Delete File:`` targets from patch text."""
    candidates: list[str] = []
    for source in (tool_input, data):
        for value in source.values():
            if isinstance(value, str) and "*** " in value:
                candidates.append(value)
    targets: list[str] = []
    for text in candidates:
        for match in _PATCH_MARKER_RE.finditer(text):
            target = match.group("target").strip()
            if target and target not in targets:
                targets.append(target)
    return tuple(targets)


def _normalize_dsh(data: dict[str, Any]) -> BridgeEvent:
    """DSH payloads come from our own plugin — explicit ``kind`` field."""
    kind = data.get("kind")
    tool = data.get("tool") if isinstance(data.get("tool"), str) else None
    if kind == KIND_FILE_WRITE:
        path = _first_str(data, _PATH_KEYS)
        if path is not None:
            return BridgeEvent(host="dsh", kind=KIND_FILE_WRITE, path=path, tool=tool)
    elif kind == KIND_SHELL:
        command = data.get("command")
        if isinstance(command, str):
            return BridgeEvent(host="dsh", kind=KIND_SHELL, command=command, tool=tool)
    return BridgeEvent(host="dsh", kind=KIND_UNKNOWN, tool=tool)


def _normalize_copilot(data: dict[str, Any]) -> dict[str, Any]:
    """Map Copilot's native camelCase hook payload to the common spelling."""
    if "toolName" not in data and "toolArgs" not in data:
        return data
    normalized = dict(data)
    normalized["tool_name"] = data.get("toolName")
    normalized["tool_input"] = data.get("toolArgs")
    return normalized


def normalize_event(
    host: str,
    data: Any,
    *,
    event_override: str | None = None,
) -> BridgeEvent:
    """Normalize one host stdin payload into a :class:`BridgeEvent`.

    Tolerant by contract: non-mapping / unparseable payloads yield
    ``kind="unknown"`` so the decision layer can fail-open + audit
    (never raise). See the module docstring for the precedence order.
    """
    if not isinstance(data, dict):
        return BridgeEvent(host=host, kind=KIND_UNKNOWN)

    if host == "dsh" and isinstance(data.get("kind"), str):
        return _normalize_dsh(data)
    if host == "copilot":
        data = _normalize_copilot(data)

    tool_input_raw = data.get("tool_input")
    tool_input: dict[str, Any] = tool_input_raw if isinstance(tool_input_raw, dict) else {}
    tool_name = data.get("tool_name") if isinstance(data.get("tool_name"), str) else None
    if tool_name is None and isinstance(data.get("tool"), str):
        tool_name = data["tool"]

    path = _first_str(tool_input, _PATH_KEYS) or _first_str(data, _PATH_KEYS)
    command = tool_input.get("command") if isinstance(tool_input.get("command"), str) else None
    if command is None and isinstance(data.get("command"), str):
        command = data["command"]
    cwd = data.get("cwd") if isinstance(data.get("cwd"), str) else None
    hook_event = data.get("hook_event_name")
    hook_event = hook_event if isinstance(hook_event, str) else ""

    kind_hint: str | None = None
    if event_override in (KIND_FILE_WRITE, KIND_SHELL):
        kind_hint = event_override
    elif tool_name == _APPLY_PATCH_TOOL:
        targets = _extract_patch_targets(tool_input, data)
        if targets:
            return BridgeEvent(
                host=host,
                kind=KIND_FILE_WRITE,
                path=targets[0],
                extra_paths=targets[1:],
                cwd=cwd,
                tool=tool_name,
            )
        # No extractable target → shell-kind advisory allow (§D-R2-1).
        return BridgeEvent(
            host=host,
            kind=KIND_SHELL,
            command=command or _APPLY_PATCH_TOOL,
            cwd=cwd,
            tool=tool_name,
        )
    elif tool_name in _WRITE_TOOLS:
        kind_hint = KIND_FILE_WRITE
    elif tool_name in _SHELL_TOOLS or hook_event == "beforeShellExecution":
        kind_hint = KIND_SHELL
    elif path is not None:
        kind_hint = KIND_FILE_WRITE
    elif command is not None:
        kind_hint = KIND_SHELL

    if kind_hint == KIND_FILE_WRITE and path is not None:
        return BridgeEvent(
            host=host, kind=KIND_FILE_WRITE, path=path, command=command, cwd=cwd, tool=tool_name
        )
    if kind_hint == KIND_SHELL and command is not None:
        return BridgeEvent(host=host, kind=KIND_SHELL, command=command, cwd=cwd, tool=tool_name)

    return BridgeEvent(host=host, kind=KIND_UNKNOWN, cwd=cwd, tool=tool_name)


__all__ = [
    "KIND_FILE_WRITE",
    "KIND_SHELL",
    "KIND_UNKNOWN",
    "KNOWN_HOSTS",
    "BridgeEvent",
    "normalize_event",
]
