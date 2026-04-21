"""Data-driven adapter — configured via YAML instead of Python.

Enables new platform adapters to be added without subclassing ``BaseAdapter``:
place a YAML config file in ``adapter_configs/`` and register via
:func:`load_data_driven_adapters`.
"""

from __future__ import annotations

import logging
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from devolaflow.adapters.base import AdapterResult, BaseAdapter
from devolaflow.adapters.registry import AdapterRegistry

ADAPTER_CONFIGS_DIR = Path(__file__).resolve().parents[3] / "adapter_configs"

_LOG = logging.getLogger(__name__)

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")

VALID_TRANSFORMS = frozenset(
    {
        "copy",
        "copy_tree",
        "copy_with_frontmatter",
        "strip_frontmatter",
        "keep_sections",
    }
)


@dataclass(frozen=True)
class _Section:
    """A markdown section parsed from a document.

    ``level == 0`` denotes the preamble (text preceding the first heading).
    ``text`` includes the heading line itself (when ``level > 0``) and all
    content up to — but not including — the next heading of equal-or-higher
    level. Sub-headings deeper than ``level`` are therefore nested inside.
    """

    heading: str
    level: int
    text: str


class DataDrivenAdapter(BaseAdapter):
    """Generic adapter driven by a YAML config file.

    Config format (v1)::

        name: <id>
        display_name: <str>
        version_added: <semver>
        tier: core | high_priority | tier_1 | tier_2
        output:
          base_dir: <relative output dir under dist/<name>/>
          files:
            - source: <path under agent_dir>
              target: <path under base_dir>
              transform: copy | copy_tree | copy_with_frontmatter
                       | strip_frontmatter | keep_sections
              # keep_sections-only:
              keep_sections: [<heading substring>, ...]
              header_prefix: "<string prepended to output>"
              include_frontmatter: false
        frontmatter:
          inject:
            platform: <str>
        budget:
          type: lines | chars
          max: <int>
          target_file: <relative path>
    """

    def __init__(self, config: dict[str, Any]) -> None:
        if "name" not in config:
            raise ValueError("DataDrivenAdapter config must contain 'name'")
        self.config = config
        self.name = config["name"]

    def build(self, source: dict, agent_dir: Path, output_dir: Path) -> AdapterResult:
        """Apply the config's transform pipeline under ``output_dir``."""
        out = self.config.get("output", {}) or {}
        base_rel = (out.get("base_dir") or "").lstrip("/")
        base = output_dir / base_rel if base_rel else output_dir
        base.mkdir(parents=True, exist_ok=True)

        files: list[str] = []
        for spec in out.get("files", []) or []:
            src = agent_dir / spec["source"]
            dst = base / spec["target"]
            transform = spec.get("transform", "copy")
            if not src.exists():
                _LOG.debug("skipping missing source: %s", src)
                continue
            dst.parent.mkdir(parents=True, exist_ok=True)
            self._apply_transform(src, dst, transform, spec)
            files.append(str(dst.relative_to(output_dir)))

        budget_ok, details = self._check_budget(output_dir)
        return AdapterResult(
            tool=self.name,
            output_dir=output_dir,
            files_created=files,
            budget_ok=budget_ok,
            budget_details=details,
        )

    def _apply_transform(
        self,
        src: Path,
        dst: Path,
        transform: str,
        spec: dict[str, Any] | None = None,
    ) -> None:
        spec = spec or {}
        handler = self._TRANSFORM_HANDLERS.get(transform)
        if handler is None:
            raise ValueError(f"Unknown transform: {transform!r}")
        handler(self, src, dst, spec)

    def _xform_copy(self, src: Path, dst: Path, spec: dict[str, Any]) -> None:
        shutil.copy2(src, dst)

    def _xform_copy_tree(self, src: Path, dst: Path, spec: dict[str, Any]) -> None:
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(src, dst)

    def _xform_copy_with_frontmatter(self, src: Path, dst: Path, spec: dict[str, Any]) -> None:
        content = src.read_text()
        inject = (self.config.get("frontmatter") or {}).get("inject", {}) or {}
        content = self._inject_frontmatter(content, inject)
        dst.write_text(content)

    def _xform_strip_frontmatter(self, src: Path, dst: Path, spec: dict[str, Any]) -> None:
        content = src.read_text()
        _, body = self._split_frontmatter(content)
        dst.write_text(body)

    def _xform_keep_sections(self, src: Path, dst: Path, spec: dict[str, Any]) -> None:
        content = src.read_text()
        frontmatter, body = self._split_frontmatter(content)
        sections = self._split_by_heading(body)
        keep = list(spec.get("keep_sections", []) or [])
        selected = self._filter_sections_by_keep(sections, keep)
        output = self._assemble_keep_sections_output(
            selected,
            frontmatter,
            prefix=spec.get("header_prefix", "") or "",
            include_frontmatter=bool(spec.get("include_frontmatter")),
        )
        dst.write_text(output)

    @staticmethod
    def _filter_sections_by_keep(sections: list[_Section], keep: list[str]) -> list[_Section]:
        """Return non-preamble sections whose heading contains any keep token."""
        return [s for s in sections if s.level > 0 and any(k in s.heading for k in keep)]

    @staticmethod
    def _assemble_keep_sections_output(
        selected: list[_Section],
        frontmatter: str,
        *,
        prefix: str,
        include_frontmatter: bool,
    ) -> str:
        """Join selected sections with optional frontmatter and prefix block."""
        out_parts: list[str] = []
        if include_frontmatter and frontmatter:
            out_parts.append(frontmatter.rstrip("\n"))
        if prefix:
            out_parts.append(prefix.rstrip("\n"))
        for sec in selected:
            out_parts.append(sec.text.rstrip("\n"))
        output = "\n\n".join(out_parts).rstrip()
        if output:
            output += "\n"
        return output

    @staticmethod
    def _split_frontmatter(content: str) -> tuple[str, str]:
        """Split a markdown document into (frontmatter, body).

        Returns ``("", content)`` when no leading ``---`` frontmatter is
        present. When a frontmatter block is found, the first element is
        formatted as ``"---<yaml>---\\n"`` (matching the legacy
        ``keep_sections`` output) and the body is the post-frontmatter
        text with one leading blank line stripped.
        """
        if not content.startswith("---"):
            return "", content
        parts = content.split("---", 2)
        if len(parts) < 3:
            return "", content
        return f"---{parts[1]}---\n", parts[2].lstrip("\n")

    @staticmethod
    def _find_atx_headings(lines: list[str]) -> list[tuple[int, int, str]]:
        """Scan *lines* and return ATX headings outside fenced code blocks.

        Each entry is ``(line_index, heading_level, heading_text)``.
        Fenced code blocks opened by ``\u0060\u0060\u0060`` or ``~~~`` are
        respected: heading-looking lines within a fence are treated as
        content. A fence is closed by the same marker that opened it.
        """
        heads: list[tuple[int, int, str]] = []
        in_fence = False
        fence_marker = ""
        for i, line in enumerate(lines):
            stripped = line.lstrip()
            if stripped.startswith("```") or stripped.startswith("~~~"):
                marker = stripped[:3]
                if not in_fence:
                    in_fence = True
                    fence_marker = marker
                elif stripped.startswith(fence_marker):
                    in_fence = False
                    fence_marker = ""
                continue
            if in_fence:
                continue
            m = _HEADING_RE.match(line)
            if m:
                heads.append((i, len(m.group(1)), m.group(2).strip()))
        return heads

    @staticmethod
    def _build_sections_from_headings(
        text: str,
        lines: list[str],
        heads: list[tuple[int, int, str]],
    ) -> list[_Section]:
        """Assemble :class:`_Section` entries from line indices and heading meta."""
        sections: list[_Section] = []
        if not heads:
            if text.strip():
                sections.append(_Section(heading="", level=0, text=text.rstrip("\n")))
            return sections

        first_head_line = heads[0][0]
        if first_head_line > 0:
            preamble = "\n".join(lines[:first_head_line]).rstrip("\n")
            if preamble.strip():
                sections.append(_Section(heading="", level=0, text=preamble))

        for idx, (start, level, heading) in enumerate(heads):
            end = len(lines)
            for j in range(idx + 1, len(heads)):
                if heads[j][1] <= level:
                    end = heads[j][0]
                    break
            body = "\n".join(lines[start:end]).rstrip("\n")
            sections.append(_Section(heading=heading, level=level, text=body))
        return sections

    @staticmethod
    def _split_by_heading(text: str) -> list[_Section]:
        """Split ``text`` into sections by ATX markdown headings.

        Fenced code blocks (``` or ~~~) are respected: heading-looking lines
        inside a fence are treated as content, not section boundaries. Each
        returned section's ``text`` spans from the heading line (inclusive)
        through the next heading of equal-or-higher level (exclusive) — so
        an H2 section naturally contains its H3/H4 children.

        The first element, when present, is always the preamble (``level=0``)
        containing everything before the first heading. The preamble is
        omitted when the document starts with a heading or is empty.
        """
        lines = text.splitlines()
        heads = DataDrivenAdapter._find_atx_headings(lines)
        return DataDrivenAdapter._build_sections_from_headings(text, lines, heads)

    @staticmethod
    def _inject_frontmatter(content: str, injections: dict[str, Any]) -> str:
        if not injections:
            return content
        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                fm = parts[1].rstrip("\n")
                for k, v in injections.items():
                    if f"{k}:" not in fm:
                        fm += f"\n{k}: {v}"
                return f"---{fm}\n---{parts[2]}"
        fm_lines = [f"{k}: {v}" for k, v in injections.items()]
        return "---\n" + "\n".join(fm_lines) + "\n---\n" + content

    def _check_budget(self, output_dir: Path) -> tuple[bool, str]:
        budget = self.config.get("budget") or {}
        target_file = budget.get("target_file")
        if not target_file:
            return True, "no budget check configured"
        base_rel = (self.config.get("output", {}).get("base_dir") or "").lstrip("/")
        target = output_dir / base_rel / target_file if base_rel else output_dir / target_file
        if not target.exists():
            return False, f"budget target missing: {target_file}"
        text = target.read_text()
        btype = budget.get("type", "lines")
        max_val = int(budget.get("max", 0))
        actual = len(text.splitlines()) if btype == "lines" else len(text)
        ok = actual <= max_val if max_val > 0 else True
        return ok, f"{target_file}: {actual}/{max_val} {btype}"

    _TRANSFORM_HANDLERS: dict[str, Any] = {
        "copy": _xform_copy,
        "copy_tree": _xform_copy_tree,
        "copy_with_frontmatter": _xform_copy_with_frontmatter,
        "strip_frontmatter": _xform_strip_frontmatter,
        "keep_sections": _xform_keep_sections,
    }


def load_data_driven_adapters(
    registry: AdapterRegistry,
    configs_dir: Path | None = None,
) -> None:
    """Scan ``adapter_configs/`` for YAML files and register each adapter.

    Broken/invalid configs are logged and skipped; they never raise.
    """
    configs_dir = configs_dir or ADAPTER_CONFIGS_DIR
    if not configs_dir.exists():
        return
    for yaml_path in sorted(configs_dir.glob("*.yaml")):
        try:
            config = yaml.safe_load(yaml_path.read_text())
            if not config or "name" not in config:
                continue
            adapter = DataDrivenAdapter(config)
            registry.register(
                config["name"],
                adapter,
                tier=config.get("tier", "tier_1"),
                description=config.get("display_name", config["name"]),
            )
        except Exception as e:
            _LOG.warning("Failed to load %s: %s", yaml_path, e)
