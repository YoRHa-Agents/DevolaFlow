"""RTK-pattern command-output mapping layer (v8.3.4 PV-04 — closes M-002).

Closes ``M-002`` from ``.local/research/v8.4.0_gap_analysis.md`` §2.1
(verbatim user ask A2): "将常见的处理命令按照 rtk 的仓库模式,在 memory 下进行
映射和处理,并单独进行调用和路由,即除了原始 rtk 支持能力以外,还拓展了结合
实际仓库中的新rtk 能力支持". Adds repo-specific compression recipes layered
ON TOP of RTK's built-in 100+ commands. Mirrors RTK's ``[filters.<name>]``
TOML schema (per ``.local/research/v8.4.0_rtk_nines_analysis.md`` §4.3 reuse)
but uses YAML for consistency with the rest of the ``.local/memory/`` tree
(see PV-03 ``schemas/memory-case.yaml`` precedent).

Precedence (verbatim from gap analysis §2.1 M-002):

1. local recipe (this module) wins
2. falls back to RTK's ``rtk rewrite`` (PV-02 default)
3. falls back to passthrough (no rewrite — original command stands)

Activation discipline (per cycle plan §5 I-7 R5 strict):

* SAME env-flag as PV-02 — ``DEVOLAFLOW_RTK_PROXY=1``. NO new env-flag is
  introduced. The local-recipe layer extends the PV-02 surface; it does not
  stand on its own.
* When the env-flag is unset, :func:`apply_local_recipe` returns the input
  unchanged. NO file IO, NO YAML parse.
* When the env-flag IS set but ``.local/memory/commands/`` is absent (fresh
  checkout / CI), :func:`load_command_mappings` returns an empty dict and
  :func:`apply_local_recipe` is a no-op — byte-identical to v8.3.3 behavior.

Public surface (consumed by :class:`devolaflow.shell_proxy.ShellProxy`,
:mod:`devolaflow.lifecycle.pre_shell_call`, and tests):

* :class:`CommandMapping` — frozen dataclass mirroring one ``<cmd>.yaml`` recipe
* :class:`CommandMappingError` — raised by :func:`build_mapping_from_dict` on
  schema breaks (loud per S-5; the loader catches and degrades)
* :func:`load_command_mappings` — discover + parse all recipes under
  ``.local/memory/commands/[<repo>/]*.yaml``
* :func:`apply_local_recipe` — apply the matching recipe to a command's
  ``(cmd, output)`` and return ``(rewritten_output, was_applied)``

External canonical URL (per S-7): https://github.com/rtk-ai/rtk
DevolaFlow canonical URL (per S-7): https://github.com/YoRHa-Agents/DevolaFlow
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, Final

import yaml

logger = logging.getLogger(__name__)


__all__ = [
    "DEFAULT_COMMANDS_DIR",
    "DEFAULT_TTL_DAYS",
    "MAX_TTL_DAYS",
    "MIN_TTL_DAYS",
    "CommandMapping",
    "CommandMappingError",
    "FilterRule",
    "apply_local_recipe",
    "build_mapping_from_dict",
    "is_command_mapping_active",
    "load_command_mappings",
]


DEFAULT_COMMANDS_DIR: Final[Path] = Path(".local/memory/commands")
"""Default discovery root, relative to ``Path.cwd()``.

Resolved at load time (NOT import time) so tests using
``monkeypatch.chdir(tmp_path)`` get fresh resolution. Mirrors the PV-03
:data:`devolaflow.memory_router.DEFAULT_INDEX_PATH` precedent.
"""

DEFAULT_TTL_DAYS: Final[int] = 30
"""TTL fallback when a recipe omits ``ttl_days`` (per ``schemas/command-mapping.yaml``)."""

MIN_TTL_DAYS: Final[int] = 1
"""Lowest accepted ``ttl_days`` — anything below 1 day is rejected loudly."""

MAX_TTL_DAYS: Final[int] = 365
"""Highest accepted ``ttl_days`` — caps the recipe's lifetime at 1 year."""

_REQUIRED_FIELDS: Final[tuple[str, ...]] = (
    "schema_version",
    "command",
    "version_stamp",
)
"""Recipe-top-level keys that MUST be present per ``schemas/command-mapping.yaml``."""

_ANSI_ESCAPE_RE: Final[re.Pattern[str]] = re.compile(
    r"\x1b\[[0-9;?]*[ -/]*[@-~]",
    flags=re.MULTILINE,
)
"""ECMA-48 / ANSI CSI escape sequence pattern for the optional strip-ansi pass.

Mirrors RTK's ``strip_ansi`` field semantics — RTK uses a similar regex
(crate ``strip-ansi-escapes``); this pattern covers the most common
CSI sequences DevolaFlow tools emit (color, cursor moves, erase). Anchored
across multiple lines via ``MULTILINE``.
"""


class CommandMappingError(ValueError):
    """Raised when a recipe is structurally malformed.

    Loud per Rule S-5 — the operator sees the offending file path AND
    the missing or invalid field. The :func:`load_command_mappings`
    loader catches this exception and falls back to dropping the recipe
    (the caller continues with the remaining recipes), but the warning
    is logged so the bad recipe can be repaired.
    """


@dataclass(frozen=True)
class FilterRule:
    """One regex-substitution rule (mirrors a ``pre_filters`` / ``post_filters`` entry).

    Frozen for in-collection use; hashable so consumers can stash rules
    in a set if they want to dedupe across recipes.

    Attributes:
        pattern: Compiled regex (Python ``re.Pattern``) — never the raw string;
            :func:`build_mapping_from_dict` compiles up-front so per-call
            apply cost is zero compile overhead.
        replacement: Verbatim replacement string; passed to
            :meth:`re.Pattern.sub`. May contain backreferences (``\\1`` etc.).
        raw_pattern: The original pattern string before compilation; preserved
            for diagnostics + serialization back to YAML.
    """

    pattern: re.Pattern[str]
    replacement: str
    raw_pattern: str


@dataclass(frozen=True)
class CommandMapping:
    """Immutable in-memory representation of a single ``<cmd>.yaml`` recipe.

    Frozen so consumers can stash a returned :class:`CommandMapping` in a
    set / use it as a dict key without copy-on-mutate worries. The fields
    mirror the ``schemas/command-mapping.yaml`` ``recipe_fields`` contract
    verbatim — adding a new field here MUST be paired with an additive
    bump to that schema.

    Attributes:
        command: Canonical command id this recipe targets (e.g. ``pytest``,
            ``ruff check``, ``git diff``). MUST match a shell-proxy whitelist
            entry when the command is supposed to be rewritten through the
            local recipe.
        version_stamp: Semver string recorded at recipe-write time; compared
            against :data:`devolaflow.__version__` for the version-stale
            invalidation check (mirrors PV-03 ``MemoryCase.version_stamp``).
        description: One-sentence verbatim summary of what the recipe
            compresses (≤200 chars, mirrors RTK's ``description`` field).
        repo_signal: Optional namespace hint disambiguating identical
            commands across repos.
        last_updated: ISO date the recipe was authored or refreshed; TTL anchor.
        ttl_days: Days the recipe stays "fresh" after ``last_updated``
            (default :data:`DEFAULT_TTL_DAYS`).
        pre_filters: Tuple of :class:`FilterRule` applied to command output
            BEFORE the post_filters pass.
        post_filters: Tuple of :class:`FilterRule` applied AFTER pre_filters.
        truncate_lines: Hard cap on output lines AFTER all filters; ``0``
            disables truncation (default).
        strip_ansi: When True, strip ANSI escape codes BEFORE filters run.
        on_empty: String to emit when the post-filter output is empty
            (mirrors RTK's ``on_empty`` field).
        tags: Free-form labels for human-faceted browsing.
        recipe_id: Stable identifier — the YAML basename without ``.yaml``
            (e.g. ``pytest`` for ``.local/memory/commands/devolaflow/pytest.yaml``).
        source_path: Repo-relative path to the recipe YAML file (diagnostics).
    """

    command: str
    version_stamp: str
    description: str = ""
    repo_signal: str = ""
    last_updated: str = ""
    ttl_days: int = DEFAULT_TTL_DAYS
    pre_filters: tuple[FilterRule, ...] = field(default_factory=tuple)
    post_filters: tuple[FilterRule, ...] = field(default_factory=tuple)
    truncate_lines: int = 0
    strip_ansi: bool = True
    on_empty: str = ""
    tags: tuple[str, ...] = field(default_factory=tuple)
    recipe_id: str = ""
    source_path: str = ""

    def __post_init__(self) -> None:
        """Validate scalar invariants at construction time.

        We deliberately keep validation tight here so callers can rely on
        a constructed :class:`CommandMapping` being well-formed.
        :func:`build_mapping_from_dict` funnels every external creation
        through ``__post_init__`` so YAML-derived recipes are validated
        identically to test-constructed instances.
        """
        if not self.command:
            raise CommandMappingError("CommandMapping.command MUST be a non-empty string")
        if not self.version_stamp:
            raise CommandMappingError(
                "CommandMapping.version_stamp MUST be a non-empty semver string"
            )
        if not (MIN_TTL_DAYS <= self.ttl_days <= MAX_TTL_DAYS):
            raise CommandMappingError(
                f"CommandMapping.ttl_days must be within [{MIN_TTL_DAYS}, {MAX_TTL_DAYS}]; "
                f"got {self.ttl_days!r} for command={self.command!r}"
            )
        if self.truncate_lines < 0:
            raise CommandMappingError(
                f"CommandMapping.truncate_lines must be >= 0; "
                f"got {self.truncate_lines!r} for command={self.command!r}"
            )


def is_command_mapping_active(env: dict[str, str] | None = None) -> bool:
    """Return True iff the existing PV-02 env-flag is set to ``"1"``.

    This module deliberately reuses :data:`devolaflow.shell_proxy.proxy._ENV_FLAG`
    (``DEVOLAFLOW_RTK_PROXY``) per the task spec — NO new env-flag is
    introduced. Pure env-flag read; no file IO, no subprocess. Suitable
    for the hot path; always early-return BEFORE touching the rest of
    this module (R5 strict per cycle plan §5 I-7).

    When *env* is ``None``, reads :data:`os.environ`.
    """
    source = env if env is not None else os.environ
    return source.get("DEVOLAFLOW_RTK_PROXY", "0") == "1"


def _today_iso() -> str:
    """Return today's UTC date as an ISO ``YYYY-MM-DD`` string.

    Wrapped in a function so tests can monkeypatch this single
    indirection without touching :mod:`datetime` globally (mirror of
    PV-03 ``memory_router.cache.today_iso`` precedent).
    """
    return datetime.now(UTC).date().isoformat()


def _parse_iso_date(value: str, *, field_name: str, command: str) -> date | None:
    """Parse an ISO ``YYYY-MM-DD`` date or return None for empty strings.

    Empty strings (the seed default) return ``None`` — a missing
    timestamp is a legitimate state, not an error. Malformed strings
    raise :class:`CommandMappingError` so the operator sees the bad row.
    """
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise CommandMappingError(
            f"CommandMapping {command!r}: field {field_name!r} is not a valid ISO date "
            f"(YYYY-MM-DD); got {value!r}"
        ) from exc


def _is_recipe_ttl_expired(mapping: CommandMapping, *, today: str | None = None) -> bool:
    """Return True iff *mapping* has aged past its ``ttl_days`` window.

    Anchor is :attr:`CommandMapping.last_updated`. When empty (a fresh seed
    that hasn't been refreshed yet), the recipe is treated as fresh-but-undated
    and we return ``False`` rather than expire it spuriously. The loader
    logs a WARNING in that case via :func:`load_command_mappings`.
    """
    if not mapping.last_updated:
        return False
    anchor = _parse_iso_date(
        mapping.last_updated,
        field_name="last_updated",
        command=mapping.command,
    )
    if anchor is None:
        return False
    today_str = today if today is not None else _today_iso()
    today_date = _parse_iso_date(today_str, field_name="today", command=mapping.command)
    if today_date is None:
        # Defensive — _today_iso() never produces an empty string.
        return False
    age_days = (today_date - anchor).days
    return age_days > mapping.ttl_days


def _is_recipe_version_stale(mapping: CommandMapping, current_version: str) -> bool:
    """Return True iff *mapping*'s ``version_stamp`` differs from *current_version*.

    String equality is intentional — pre-release tags (``8.3.4-rc.1`` vs
    ``8.3.4``) DO trigger invalidation, which is the safe behavior:
    pre-release recipes may rely on schema drafts that the GA never shipped.
    Mirror of PV-03 ``memory_router.cache.is_version_stale`` precedent.
    """
    return mapping.version_stamp != current_version


def _build_filter_rule(
    raw_rule: Any,
    *,
    field_label: str,
    command: str,
    source_path: str,
) -> FilterRule:
    """Coerce one raw ``{pattern, replacement}`` dict into a :class:`FilterRule`.

    Compiles the regex up-front so per-call apply cost is zero compile
    overhead. Loud per S-5 — invalid patterns surface a
    :class:`CommandMappingError` with the field label, the recipe id,
    and the source path so the operator can locate + repair the recipe.
    """
    if not isinstance(raw_rule, dict):
        raise CommandMappingError(
            f"{source_path}: recipe {command!r} {field_label} entry must be a mapping; "
            f"got {type(raw_rule).__name__}"
        )
    pattern_str = raw_rule.get("pattern")
    if not isinstance(pattern_str, str) or not pattern_str:
        raise CommandMappingError(
            f"{source_path}: recipe {command!r} {field_label} entry missing "
            f"non-empty 'pattern'; got {pattern_str!r}"
        )
    replacement = raw_rule.get("replacement", "")
    if not isinstance(replacement, str):
        raise CommandMappingError(
            f"{source_path}: recipe {command!r} {field_label} entry has non-string "
            f"'replacement' ({type(replacement).__name__}={replacement!r})"
        )
    try:
        # MULTILINE-only by default — lets `^` / `$` match at line boundaries
        # while keeping `.` line-bounded (matching RTK's `strip_lines_matching`
        # semantics). Recipes that need cross-line spans use `[\s\S]*?`
        # (the standard Python idiom for "any character including newline"
        # that does not pollute single-line `.*$` patterns elsewhere in the
        # same recipe). DOTALL is intentionally NOT enabled — enabling it
        # would make every `.*$` greedily span newlines and accidentally
        # eat unrelated output.
        pattern = re.compile(pattern_str, flags=re.MULTILINE)
    except re.error as exc:
        raise CommandMappingError(
            f"{source_path}: recipe {command!r} {field_label} entry has invalid regex "
            f"{pattern_str!r}: {exc}"
        ) from exc

    return FilterRule(pattern=pattern, replacement=replacement, raw_pattern=pattern_str)


def build_mapping_from_dict(
    payload: Any,
    *,
    source_path: str = "<command-mapping.yaml>",
    recipe_id: str = "",
) -> CommandMapping:
    """Coerce a parsed YAML recipe dict into a validated :class:`CommandMapping`.

    Funnels every external construction through one validator so the
    loader and the tests see identical error semantics. The
    *recipe_id* parameter is the basename-derived identifier; defaults
    to empty when unknown (test instantiation via direct call).

    Args:
        payload: Parsed YAML payload (expected to be a ``dict``).
        source_path: Path to the recipe file the payload came from;
            appears in error messages so operators can locate the offending
            recipe.
        recipe_id: Stable identifier (typically the YAML basename without
            the ``.yaml`` extension).

    Returns:
        A frozen, validated :class:`CommandMapping` instance.

    Raises:
        CommandMappingError: When the payload is not a mapping, or when any
            of :data:`_REQUIRED_FIELDS` is missing / has the wrong type, or
            when a derived constraint (``ttl_days`` bounds, regex compile)
            is violated.
    """
    if not isinstance(payload, dict):
        raise CommandMappingError(
            f"{source_path}: recipe top-level must be a YAML mapping; got {type(payload).__name__}"
        )

    missing = [name for name in _REQUIRED_FIELDS if not payload.get(name)]
    if missing:
        command_hint = payload.get("command", recipe_id or "<unknown>")
        raise CommandMappingError(
            f"{source_path}: recipe {command_hint!r} missing required fields: {', '.join(missing)}"
        )

    schema_version = payload.get("schema_version")
    if isinstance(schema_version, bool) or not isinstance(schema_version, int):
        raise CommandMappingError(
            f"{source_path}: recipe schema_version must be an int (got "
            f"{type(schema_version).__name__}={schema_version!r})"
        )
    if schema_version != 1:
        raise CommandMappingError(
            f"{source_path}: recipe schema_version {schema_version!r} not supported "
            f"(only schema_version=1 is recognized at this release)"
        )

    command = str(payload["command"])
    version_stamp = str(payload["version_stamp"])

    raw_ttl = payload.get("ttl_days", DEFAULT_TTL_DAYS)
    if isinstance(raw_ttl, bool) or not isinstance(raw_ttl, int):
        raise CommandMappingError(
            f"{source_path}: recipe {command!r} has non-int ttl_days "
            f"({type(raw_ttl).__name__!s}={raw_ttl!r})"
        )

    raw_truncate = payload.get("truncate_lines", payload.get("max_lines", 0))
    if isinstance(raw_truncate, bool) or not isinstance(raw_truncate, int):
        raise CommandMappingError(
            f"{source_path}: recipe {command!r} has non-int truncate_lines / max_lines "
            f"({type(raw_truncate).__name__!s}={raw_truncate!r})"
        )

    raw_strip_ansi = payload.get("strip_ansi", True)
    if not isinstance(raw_strip_ansi, bool):
        raise CommandMappingError(
            f"{source_path}: recipe {command!r} has non-bool strip_ansi "
            f"({type(raw_strip_ansi).__name__!s}={raw_strip_ansi!r})"
        )

    raw_tags = payload.get("tags", ())
    if not isinstance(raw_tags, list | tuple):
        raise CommandMappingError(
            f"{source_path}: recipe {command!r} has non-list tags ({type(raw_tags).__name__!s})"
        )
    tags_tuple = tuple(str(t) for t in raw_tags)

    raw_pre = payload.get("pre_filters", []) or []
    if not isinstance(raw_pre, list):
        raise CommandMappingError(
            f"{source_path}: recipe {command!r} 'pre_filters' must be a list; "
            f"got {type(raw_pre).__name__}"
        )
    pre_rules = tuple(
        _build_filter_rule(
            rule,
            field_label="pre_filters",
            command=command,
            source_path=source_path,
        )
        for rule in raw_pre
    )

    raw_post = payload.get("post_filters", []) or []
    if not isinstance(raw_post, list):
        raise CommandMappingError(
            f"{source_path}: recipe {command!r} 'post_filters' must be a list; "
            f"got {type(raw_post).__name__}"
        )
    post_rules = tuple(
        _build_filter_rule(
            rule,
            field_label="post_filters",
            command=command,
            source_path=source_path,
        )
        for rule in raw_post
    )

    return CommandMapping(
        command=command,
        version_stamp=version_stamp,
        description=str(payload.get("description", "") or ""),
        repo_signal=str(payload.get("repo_signal", "") or ""),
        last_updated=str(payload.get("last_updated", "") or ""),
        ttl_days=int(raw_ttl),
        pre_filters=pre_rules,
        post_filters=post_rules,
        truncate_lines=int(raw_truncate),
        strip_ansi=raw_strip_ansi,
        on_empty=str(payload.get("on_empty", "") or ""),
        tags=tags_tuple,
        recipe_id=recipe_id,
        source_path=source_path,
    )


def _resolve_default_commands_dir() -> Path:
    """Resolve :data:`DEFAULT_COMMANDS_DIR` against the current working directory.

    Wrapped in a function so each :func:`load_command_mappings` call picks
    up the latest cwd (necessary for tests using
    ``monkeypatch.chdir(tmp_path)``).
    """
    return Path.cwd() / DEFAULT_COMMANDS_DIR


def _resolve_current_version() -> str:
    """Read :data:`devolaflow.__version__` lazily.

    Imported inside the function (rather than at module top) to avoid
    a hard import cycle: :mod:`devolaflow.__init__` may grow imports
    that in turn import :mod:`devolaflow.shell_proxy`. The lazy import
    keeps the commands layer dependency-free.
    """
    from devolaflow import __version__  # noqa: PLC0415  (intentional lazy import)

    return __version__


def load_command_mappings(
    *,
    commands_dir: Path | str | None = None,
    repo_signal: str | None = None,
    env: dict[str, str] | None = None,
    current_version: str | None = None,
) -> dict[str, CommandMapping]:
    """Discover and parse all recipes under ``.local/memory/commands/``.

    Decision tree (cache-miss is ALWAYS the safe path per R5 strict):

    1. PV-02 env-flag unset → return ``{}`` immediately. NO file IO.
    2. Commands directory missing → return ``{}`` (INFO log — normal on
       fresh checkout / CI).
    3. Each ``<repo>/<cmd>.yaml`` parsed; malformed YAML / schema breaks
       are logged as WARNINGs and the offending recipe is dropped (the
       remaining recipes are still loaded).
    4. Per-recipe ``version_stamp`` mismatch → recipe dropped (treat as
       cache-miss; mirrors PV-03 router behavior).
    5. Per-recipe ``ttl_days`` expiry → recipe dropped.
    6. ``repo_signal`` filter (when supplied) → only recipes whose
       ``repo_signal`` matches are kept (case-sensitive equality).

    Args:
        commands_dir: Override the discovery root (defaults to
            ``Path.cwd() / .local/memory/commands``). Tests pass
            ``tmp_path / commands`` to isolate.
        repo_signal: Optional namespace filter; when supplied, narrows
            results to recipes whose ``repo_signal`` matches exactly.
            ``None`` returns recipes from all namespaces.
        env: Optional env dict for the activation check (default
            :data:`os.environ`).
        current_version: Override for the version-stamp comparison
            (default :data:`devolaflow.__version__`).

    Returns:
        A dict mapping ``command`` (the recipe's ``command:`` field) to a
        :class:`CommandMapping`. When multiple recipes target the same
        command (e.g. a ``DevolaFlow`` namespace and a ``rtk-ai/rtk``
        namespace both define ``pytest``), the first matching recipe by
        directory traversal order wins. Use *repo_signal* to disambiguate.

    Examples:
        Load every recipe::

            mappings = load_command_mappings()

        Load only DevolaFlow recipes::

            mappings = load_command_mappings(repo_signal="DevolaFlow")
    """
    if not is_command_mapping_active(env):
        # R5 strict zero-overhead path — no PATH lookup, no file IO.
        return {}

    base = Path(commands_dir) if commands_dir is not None else _resolve_default_commands_dir()
    if not base.exists():
        logger.info(
            "[shell_proxy.commands] commands directory %s not present; layer disabled, "
            "callers fall through to RTK rewrite (this is normal on a fresh checkout)",
            base,
        )
        return {}

    if not base.is_dir():
        logger.warning(
            "[shell_proxy.commands] expected directory at %s but found a file; "
            "treating as empty (no recipes loaded)",
            base,
        )
        return {}

    version = current_version if current_version is not None else _resolve_current_version()
    mappings: dict[str, CommandMapping] = {}
    for yaml_path in sorted(base.rglob("*.yaml")):
        if yaml_path.name.startswith("."):
            continue
        recipe_id = yaml_path.stem
        rel_source = _safe_relative_source(yaml_path, base)
        try:
            text = yaml_path.read_text(encoding="utf-8")
        except OSError as exc:
            logger.warning(
                "[shell_proxy.commands] cannot read recipe %s: %s — skipping",
                rel_source,
                exc,
            )
            continue
        try:
            payload = yaml.safe_load(text)
        except yaml.YAMLError as exc:
            logger.warning(
                "[shell_proxy.commands] recipe %s is not valid YAML: %s — skipping",
                rel_source,
                exc,
            )
            continue
        if payload is None:
            logger.warning(
                "[shell_proxy.commands] recipe %s is empty — skipping",
                rel_source,
            )
            continue
        try:
            mapping = build_mapping_from_dict(
                payload,
                source_path=rel_source,
                recipe_id=recipe_id,
            )
        except CommandMappingError as exc:
            logger.warning(
                "[shell_proxy.commands] dropping malformed recipe %s: %s",
                rel_source,
                exc,
            )
            continue

        if _is_recipe_version_stale(mapping, version):
            logger.info(
                "[shell_proxy.commands] recipe %s matched but version-stale "
                "(version_stamp=%s, current=%s); treating as miss",
                rel_source,
                mapping.version_stamp,
                version,
            )
            continue
        try:
            expired = _is_recipe_ttl_expired(mapping)
        except CommandMappingError as exc:
            logger.warning(
                "[shell_proxy.commands] recipe %s has malformed date field; treating as miss: %s",
                rel_source,
                exc,
            )
            continue
        if expired:
            logger.info(
                "[shell_proxy.commands] recipe %s matched but TTL-expired "
                "(ttl_days=%d, last_updated=%r); treating as miss",
                rel_source,
                mapping.ttl_days,
                mapping.last_updated,
            )
            continue

        if repo_signal is not None and mapping.repo_signal != repo_signal:
            continue

        if mapping.command in mappings:
            # First-match-wins by directory order — log the conflict so
            # the operator sees the duplicate and can disambiguate via
            # repo_signal (per the schema's `repo_signal` semantics).
            logger.info(
                "[shell_proxy.commands] recipe %s shadowed by earlier recipe for "
                "command %r (use repo_signal to disambiguate)",
                rel_source,
                mapping.command,
            )
            continue
        mappings[mapping.command] = mapping

    return mappings


def _safe_relative_source(path: Path, base: Path) -> str:
    """Return *path* relative to *base*'s parent, or fall back to the path string.

    Diagnostics-only helper — keeps WARNING messages compact + relative,
    honoring S-2 (no absolute paths in agent-facing surfaces).
    """
    try:
        return str(path.relative_to(base.parent))
    except ValueError:
        return str(path)


def _strip_ansi(text: str) -> str:
    """Remove ANSI CSI escape sequences from *text*.

    Mirrors RTK's ``strip_ansi`` field semantics. Non-destructive when the
    text contains no ANSI codes (regex matches nothing → original returned).
    """
    return _ANSI_ESCAPE_RE.sub("", text)


def _apply_filter_rules(text: str, rules: tuple[FilterRule, ...]) -> str:
    """Apply each :class:`FilterRule` in order, left-to-right."""
    out = text
    for rule in rules:
        out = rule.pattern.sub(rule.replacement, out)
    return out


def _truncate_to_lines(text: str, max_lines: int, *, recipe_id: str) -> str:
    """Cap *text* to *max_lines* lines AFTER all filters, with a footer.

    The footer mirrors RTK's truncate-line summary so operators see how
    many lines were dropped + which recipe applied. When *max_lines* is
    ``0`` (the disabled default) or *text* is already within the cap,
    returns *text* unchanged.
    """
    if max_lines <= 0:
        return text
    lines = text.splitlines(keepends=True)
    if len(lines) <= max_lines:
        return text
    dropped = len(lines) - max_lines
    head = "".join(lines[:max_lines])
    if not head.endswith("\n"):
        head = head + "\n"
    suffix = f"... (truncated {dropped} lines per {recipe_id or '<recipe>'})\n"
    return head + suffix


def apply_local_recipe(
    cmd: str,
    output: str,
    *,
    mappings: dict[str, CommandMapping] | None = None,
    env: dict[str, str] | None = None,
    commands_dir: Path | str | None = None,
    repo_signal: str | None = None,
) -> tuple[str, bool]:
    """Apply the matching local recipe (if any) to *output*.

    Decision tree (precedence per gap analysis §2.1 M-002):

    1. Env-flag (PV-02 ``DEVOLAFLOW_RTK_PROXY``) unset → return
       ``(output, False)`` IMMEDIATELY. NO file IO. R5 strict.
    2. *cmd* not a string / empty → return ``(output, False)``.
    3. *output* not a string → return ``(output, False)``.
    4. *mappings* not supplied → load via :func:`load_command_mappings`.
    5. No recipe matches *cmd*'s canonical id → return
       ``(output, False)`` (caller falls back to RTK rewrite, then to
       passthrough — the precedence chain).
    6. Recipe matches AND apply succeeds → return
       ``(rewritten_output, True)``.
    7. Recipe matches BUT regex.sub raises (defensive — pre-compiled in
       :func:`build_mapping_from_dict`, so this is rare) → log WARNING
       and return ``(output, False)``. Loud per S-5.

    The matching key is the recipe's ``command`` field, with a longest-
    prefix-wins fallback so ``git diff --stat`` matches a ``git diff``
    recipe (and not a hypothetical ``git`` recipe). Mirrors the
    :func:`devolaflow.shell_proxy.registry.match_command` discipline.

    Args:
        cmd: The shell command (post-PV-02 wrap or pre-wrap is fine —
            the matcher anchors on the command head).
        output: The command's captured stdout/stderr text to compress.
        mappings: Pre-loaded recipe dict; supply this when you've already
            called :func:`load_command_mappings` to avoid re-discovery
            (tests inject this for isolation).
        env: Optional env dict for the activation check.
        commands_dir: Override the discovery root (forwarded to
            :func:`load_command_mappings` when *mappings* is None).
        repo_signal: Optional namespace filter (forwarded to
            :func:`load_command_mappings` when *mappings* is None).

    Returns:
        A tuple ``(rewritten_output, was_applied)``. ``was_applied`` is
        True iff a recipe matched AND the substitutions ran without
        raising. False indicates the caller should fall back to the next
        precedence layer (RTK rewrite → passthrough).
    """
    if not is_command_mapping_active(env):
        return output, False
    if not isinstance(cmd, str) or not cmd:
        return output, False
    if not isinstance(output, str):
        return output, False

    if mappings is None:
        mappings = load_command_mappings(
            commands_dir=commands_dir,
            repo_signal=repo_signal,
            env=env,
        )
    if not mappings:
        return output, False

    matched = _match_recipe(cmd, mappings)
    if matched is None:
        return output, False

    try:
        rewritten = output
        if matched.strip_ansi:
            rewritten = _strip_ansi(rewritten)
        if matched.pre_filters:
            rewritten = _apply_filter_rules(rewritten, matched.pre_filters)
        if matched.post_filters:
            rewritten = _apply_filter_rules(rewritten, matched.post_filters)
        if matched.truncate_lines:
            rewritten = _truncate_to_lines(
                rewritten,
                matched.truncate_lines,
                recipe_id=matched.recipe_id,
            )
        if matched.on_empty and not rewritten.strip():
            rewritten = matched.on_empty + ("\n" if not matched.on_empty.endswith("\n") else "")
    except (re.error, ValueError) as exc:
        # Defensive — patterns are compiled at load time so this branch
        # is rare. Loud per S-5; operator sees the recipe id + the raise.
        logger.warning(
            "[shell_proxy.commands] applying recipe %r raised %s; falling back to RTK passthrough",
            matched.recipe_id or matched.command,
            exc,
        )
        return output, False

    return rewritten, True


def _match_recipe(cmd: str, mappings: dict[str, CommandMapping]) -> CommandMapping | None:
    """Return the recipe matching *cmd*'s canonical head, or None.

    Longest-prefix-wins so ``git diff --stat`` matches a ``git diff``
    recipe ahead of a hypothetical ``git`` recipe. Mirrors the
    :func:`devolaflow.shell_proxy.registry.match_command` precedent.

    The match anchor is "command head followed by EOL or whitespace" —
    e.g. ``git diff`` matches but ``git diffshow`` does NOT. This
    deliberately mirrors PV-02's regex precision so the local-recipe
    layer cannot accidentally claim commands that the proxy would
    otherwise pass through unchanged.
    """
    if not cmd:
        return None
    for prefix in sorted(mappings, key=len, reverse=True):
        head = mappings[prefix].command
        if cmd == head:
            return mappings[prefix]
        if cmd.startswith(head) and cmd[len(head) : len(head) + 1] in (" ", "\t"):
            return mappings[prefix]
    return None
