"""Rule compiler: .rules/ → multiple AI tool formats."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass
class RuleLayer:
    name: str
    priority: int
    content: str
    always_include: bool = False


@dataclass
class TargetConfig:
    name: str
    output: str
    format: str  # "mdc" | "markdown" | "markdown_append"
    token_budget: int
    include_layers: list[str]
    frontmatter: dict[str, Any] | None = None
    append_marker: str | None = None
    append_end: str | None = None


@dataclass
class CompileResult:
    target: str
    content: str
    tokens_used: int
    tokens_budget: int
    layers_included: list[str]
    content_hash: str


def _estimate_tokens(text: str) -> int:
    """Rough token estimate: ~4 chars per token."""
    return len(text) // 4


def _parse_mdc(text: str) -> tuple[dict[str, Any], str]:
    """Parse MDC frontmatter (YAML between --- delimiters) and body."""
    pattern = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
    m = pattern.match(text)
    if m:
        fm = yaml.safe_load(m.group(1)) or {}
        body = text[m.end() :]
        return fm, body
    return {}, text


def _render_frontmatter(fm: dict[str, Any]) -> str:
    """Render YAML frontmatter block."""
    lines = ["---"]
    for key, value in fm.items():
        if isinstance(value, bool):
            lines.append(f"{key}: {'true' if value else 'false'}")
        elif isinstance(value, str):
            lines.append(f'{key}: "{value}"')
        else:
            lines.append(f"{key}: {value}")
    lines.append("---")
    return "\n".join(lines)


class RuleCompiler:
    """Compile .rules/ layer files into target-specific outputs."""

    def __init__(self, config_path: str | Path) -> None:
        self.config_path = Path(config_path)
        self._raw = yaml.safe_load(self.config_path.read_text(encoding="utf-8"))
        self.source_dir = self.config_path.parent
        if self._raw.get("source_dir"):
            candidate = Path(self._raw["source_dir"])
            if candidate.is_absolute():
                self.source_dir = candidate
        self.layers: list[RuleLayer] = []
        self.targets: dict[str, TargetConfig] = {}
        self._load_config()

    def _load_config(self) -> None:
        """Parse compile-config.yaml into layer specs and target configs."""
        for layer_spec in self._raw.get("layers", []):
            self.layers.append(
                RuleLayer(
                    name=layer_spec["name"],
                    priority=layer_spec["priority"],
                    content="",
                    always_include=layer_spec.get("always_include", False),
                )
            )

        for target_name, target_spec in self._raw.get("targets", {}).items():
            self.targets[target_name] = TargetConfig(
                name=target_name,
                output=target_spec["output"],
                format=target_spec["format"],
                token_budget=target_spec.get("token_budget", 8000),
                include_layers=target_spec.get("include_layers", []),
                frontmatter=target_spec.get("frontmatter"),
                append_marker=target_spec.get("append_marker"),
                append_end=target_spec.get("append_end"),
            )

    def load_layers(self, rules_dir: str | Path | None = None) -> list[RuleLayer]:
        """Read .mdc files from rules_dir, parse frontmatter, populate layers."""
        rules_dir = Path(rules_dir) if rules_dir else self.source_dir

        for layer in self.layers:
            layer_file = rules_dir / f"{layer.name}.mdc"
            if layer_file.exists():
                raw = layer_file.read_text(encoding="utf-8")
                _fm, body = _parse_mdc(raw)
                layer.content = body.strip()

        return self.layers

    def compile(self, target: str | None = None) -> list[CompileResult]:
        """Compile for a specific target or all targets.

        Layers are loaded from source_dir if not already loaded.
        """
        if not any(layer.content for layer in self.layers):
            self.load_layers()

        if target:
            if target not in self.targets:
                msg = f"Unknown target: {target}"
                raise ValueError(msg)
            return [self._compile_target(self.targets[target])]

        return [self._compile_target(tc) for tc in self.targets.values()]

    def compile_all(self) -> list[CompileResult]:
        """Compile all targets and write outputs to disk.

        v9.0.0 PV-07 (ADR-007 D2 + D5): when drift detection is enabled
        AND the v9.0.0 stub fingerprints exist, the saved hash store
        also includes ``stub_<name>`` entries pinning the deprecated
        cursor-rule stubs (`.cursor/rules/devola-flow-rules.mdc` +
        `.cursor/rules/workflow-rules.mdc`). Operators MUST NOT
        hand-edit either stub — drift detection via
        :func:`devolaflow.local.drift.check_stub_drift` (CI-enforced
        by ``tests/test_no_ghost_features.py::test_rule_surfaces_compile_only``)
        will fail.
        """
        results = self.compile()
        repo_root = self.config_path.parent.parent

        for result in results:
            tc = self.targets[result.target]
            out_path = repo_root / tc.output
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(result.content, encoding="utf-8")

        drift_cfg = self._raw.get("drift_detection", {})
        if drift_cfg.get("enabled"):
            from devolaflow.local.drift import save_hashes

            hash_file = repo_root / drift_cfg["hash_file"]
            save_hashes(results, hash_file, repo_root=repo_root)

        return results

    def _compile_target(self, tc: TargetConfig) -> CompileResult:
        """Compile a single target, respecting token budgets.

        v12.0.0 PV-05 cleanup-absorption fix: when truncation runs,
        ``layers_included`` is now derived from the post-truncation
        retained layer list returned by :meth:`_truncate_to_budget`,
        not from the pre-truncation ``selected`` list. The happy-path
        branch (no truncation) still uses ``selected`` directly so the
        existing byte-stable reporting is preserved. Closes the
        v11.4.0 retrospective §3 deferred bug + §4 key learning 3.
        """
        selected = [
            layer for layer in self.layers if layer.name in tc.include_layers and layer.content
        ]
        selected.sort(key=lambda layer: layer.priority)

        if tc.format == "mdc":
            content = self._format_mdc(selected, tc)
        else:
            content = self._format_markdown(selected, tc)

        tokens = _estimate_tokens(content)

        retained: list[RuleLayer] | None = None
        if tokens > tc.token_budget:
            content, retained = self._truncate_to_budget(selected, tc)
            tokens = _estimate_tokens(content)

        content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]

        layers_for_report = retained if retained is not None else selected
        return CompileResult(
            target=tc.name,
            content=content,
            tokens_used=tokens,
            tokens_budget=tc.token_budget,
            layers_included=[ly.name for ly in layers_for_report if ly.content],
            content_hash=content_hash,
        )

    def _format_mdc(self, layers: list[RuleLayer], tc: TargetConfig) -> str:
        """Format as MDC with frontmatter + concatenated layers."""
        parts: list[str] = []
        if tc.frontmatter:
            parts.append(_render_frontmatter(tc.frontmatter))
            parts.append("")

        for layer in layers:
            if layer.content:
                parts.append(layer.content)
                parts.append("")

        return "\n".join(parts).rstrip() + "\n"

    def _format_markdown(self, layers: list[RuleLayer], tc: TargetConfig) -> str:
        """Format as Markdown with heading per layer."""
        parts: list[str] = []
        parts.append("<!-- Auto-generated by devolaflow rule compiler. Do not edit manually. -->")
        parts.append("")

        for layer in layers:
            if layer.content:
                parts.append(layer.content)
                parts.append("")

        return "\n".join(parts).rstrip() + "\n"

    def _truncate_to_budget(
        self, layers: list[RuleLayer], tc: TargetConfig
    ) -> tuple[str, list[RuleLayer]]:
        """Drop lowest-priority non-always_include layers until within budget.

        Returns a ``(content, retained_layers)`` tuple. ``retained_layers``
        is the post-truncation list — the actual ``RuleLayer`` instances
        that rendered into ``content`` after the priority-ordered drop
        loop converged. Callers MUST use ``retained_layers`` (not the
        pre-truncation input ``layers``) when populating
        ``CompileResult.layers_included``; otherwise the audit surface
        misreports truncation outcomes.

        v12.0.0 PV-05 cleanup-absorption: pre-fix the function returned
        only ``content`` and the dispatcher-side caller reported
        ``layers_included`` from the pre-truncation ``selected`` list,
        which silently masked the v11.4.0 cursor 11979/12000 saturation
        (the Style Rules layer was dropped here but the audit reported
        all 5 layers). See v11.4.0 retrospective §3 deferred bug + §4
        key learning 3 for the original incident.
        """
        included = list(layers)

        while included and _estimate_tokens(self._render_layers(included, tc)) > tc.token_budget:
            droppable = [ly for ly in included if not ly.always_include]
            if not droppable:
                break
            droppable.sort(key=lambda ly: ly.priority, reverse=True)
            included.remove(droppable[0])

        return self._render_layers(included, tc), included

    def _render_layers(self, layers: list[RuleLayer], tc: TargetConfig) -> str:
        """Render layers for a target (used during truncation)."""
        if tc.format == "mdc":
            return self._format_mdc(layers, tc)
        return self._format_markdown(layers, tc)


def compile_prefs(prefs_path: Path, output_path: Path) -> CompileResult | None:
    """Compile ``.local/memory/prefs.md`` into ``CLAUDE.local.md``.

    Reads personal preferences and wraps them in a CLAUDE.local.md format
    that Claude Code loads alongside the project CLAUDE.md. Returns None
    if the prefs file doesn't exist or is empty.
    """
    if not prefs_path.exists():
        return None

    content = prefs_path.read_text(encoding="utf-8").strip()
    if not content:
        return None

    lines = [
        "# Personal Preferences",
        "",
        "> Auto-compiled from .local/memory/prefs.md by DevolaFlow.",
        "> This file is gitignored. Edit prefs.md to change preferences.",
        "",
        content.split("\n", 1)[-1].strip() if "\n" in content else content,
        "",
    ]
    compiled = "\n".join(lines) + "\n"

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(compiled, encoding="utf-8")

    content_hash = hashlib.sha256(compiled.encode("utf-8")).hexdigest()[:16]
    return CompileResult(
        target="claude_local",
        content=compiled,
        tokens_used=_estimate_tokens(compiled),
        tokens_budget=2000,
        layers_included=["prefs"],
        content_hash=content_hash,
    )
