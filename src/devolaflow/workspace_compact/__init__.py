"""Non-destructive compaction of one task or change folder (v24.0.0).

Design ref: `.local/research/v24.0.0_design_adr.md`.

Compaction relocates settled content into `compact/archived/<seq>/` inside
the same folder, appends a hashed before/after row to `compact/mappings.yaml`,
and leaves a generated `compact/DIGEST.md` in its place. Nothing is deleted,
nothing is rewritten, and every relocated byte stays reachable — deletion
remains operator-only per W-26.

The unit of operation is one folder that the operator names. This domain does
not roam the repository: `devola-local-archive` owns cross-surface folder
relocation, and this tool owns shrinking the inside of one folder.
"""

from __future__ import annotations

from devolaflow.workspace_compact.bloat import (
    DEFAULT_THRESHOLD_TOKENS,
    BloatFinding,
    scan_bloat,
    suggestion_text,
)
from devolaflow.workspace_compact.digest import (
    audit_digest,
    check_anchors,
    render_digest,
    set_agent_section,
    write_digest,
)
from devolaflow.workspace_compact.engine import (
    apply_plan,
    archived_root,
    build_plan,
    compact_root,
    digest_path,
    load_mappings,
    locate,
    mappings_path,
    restore,
    verify_integrity,
)
from devolaflow.workspace_compact.handoff_index import (
    collect_envelopes,
    render_handoff_index,
    write_handoff_index,
)
from devolaflow.workspace_compact.metering import (
    PathMeasurement,
    measure_file,
    measure_path,
    resident_tokens,
)
from devolaflow.workspace_compact.models import (
    DIGEST_MARKER,
    HANDOFF_INDEX_MARKER,
    Action,
    Category,
    CompactEntry,
    CompactError,
    CompactPlan,
    CompactResult,
    LocateHit,
)

__all__ = [
    "DEFAULT_THRESHOLD_TOKENS",
    "DIGEST_MARKER",
    "HANDOFF_INDEX_MARKER",
    "Action",
    "BloatFinding",
    "Category",
    "CompactEntry",
    "CompactError",
    "CompactPlan",
    "CompactResult",
    "LocateHit",
    "PathMeasurement",
    "apply_plan",
    "archived_root",
    "audit_digest",
    "build_plan",
    "check_anchors",
    "collect_envelopes",
    "compact_root",
    "digest_path",
    "load_mappings",
    "locate",
    "mappings_path",
    "measure_file",
    "measure_path",
    "render_digest",
    "render_handoff_index",
    "resident_tokens",
    "restore",
    "scan_bloat",
    "set_agent_section",
    "suggestion_text",
    "verify_integrity",
    "write_digest",
    "write_handoff_index",
]
