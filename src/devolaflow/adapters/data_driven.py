"""Data-driven adapter — configured via YAML instead of Python.

Enables new platform adapters to be added without subclassing ``BaseAdapter``:
place a YAML config file in ``adapter_configs/`` and register via
:func:`load_data_driven_adapters`.
"""

from __future__ import annotations

import logging
import shutil
from pathlib import Path
from typing import Any

import yaml

from devolaflow.adapters.base import AdapterResult, BaseAdapter
from devolaflow.adapters.registry import AdapterRegistry

ADAPTER_CONFIGS_DIR = Path(__file__).resolve().parents[3] / "adapter_configs"

_LOG = logging.getLogger(__name__)


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
              transform: copy | copy_tree | copy_with_frontmatter | strip_frontmatter
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
            self._apply_transform(src, dst, transform)
            files.append(str(dst.relative_to(output_dir)))

        budget_ok, details = self._check_budget(output_dir)
        return AdapterResult(
            tool=self.name,
            output_dir=output_dir,
            files_created=files,
            budget_ok=budget_ok,
            budget_details=details,
        )

    def _apply_transform(self, src: Path, dst: Path, transform: str) -> None:
        if transform == "copy":
            shutil.copy2(src, dst)
        elif transform == "copy_tree":
            if dst.exists():
                shutil.rmtree(dst)
            shutil.copytree(src, dst)
        elif transform == "copy_with_frontmatter":
            content = src.read_text()
            inject = (self.config.get("frontmatter") or {}).get("inject", {}) or {}
            content = self._inject_frontmatter(content, inject)
            dst.write_text(content)
        elif transform == "strip_frontmatter":
            content = src.read_text()
            if content.startswith("---"):
                parts = content.split("---", 2)
                if len(parts) >= 3:
                    content = parts[2].lstrip("\n")
            dst.write_text(content)
        else:
            raise ValueError(f"Unknown transform: {transform!r}")

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
