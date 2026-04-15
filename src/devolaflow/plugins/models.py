"""Data models for the DevolaFlow plugin system."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class PluginSpec:
    """Specification for a registered plugin."""

    name: str
    description: str
    cli_binary: str
    version_command: str
    version_regex: str
    install_methods: dict[str, str]
    capabilities: list[str]
    role: str
    repo_url: str = ""
    min_version: str | None = None
    skill_install_command: str | None = None
    stage_mapping: dict[str, str] = field(default_factory=dict)
    workflows: list[str] = field(default_factory=list)
    update_command: str | None = None
    uninstall_command: str | None = None


@dataclass
class PluginStatus:
    """Runtime status of a plugin."""

    name: str
    available: bool = False
    version: str | None = None
    path: str | None = None
    meets_min_version: bool = True
    capabilities: list[str] = field(default_factory=list)
