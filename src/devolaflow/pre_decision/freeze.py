"""Config freeze — validate then write project_config.yaml.

Design ref: design_execution_protocol.md §2 (Step 4: FREEZE)
"""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import TYPE_CHECKING

import yaml

from devolaflow.pre_decision.validate import validate_consistency

if TYPE_CHECKING:
    from devolaflow.pre_decision.checklist import PreDecisionChecklist


class FreezeError(Exception):
    """Raised when the checklist has blocking validation errors."""


def freeze_config(checklist: PreDecisionChecklist, output_path: Path) -> None:
    """Validate *checklist*, then serialise it as YAML to *output_path*.

    Raises ``FreezeError`` if any validation rule with severity ``"error"``
    fires.  Warnings and auto-fixes are included in the output as metadata.
    """
    errors = validate_consistency(checklist)
    blocking = [e for e in errors if e.severity == "error"]
    if blocking:
        messages = "; ".join(f"[{e.rule}] {e.message}" for e in blocking)
        raise FreezeError(f"Cannot freeze config — validation errors: {messages}")

    checklist.status = "frozen"

    data = asdict(checklist)

    warnings = [e for e in errors if e.severity in ("warning", "auto_fix")]
    if warnings:
        data["_validation_notes"] = [
            {"rule": w.rule, "severity": w.severity, "message": w.message} for w in warnings
        ]

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w") as fh:
        yaml.safe_dump(data, fh, default_flow_style=False, sort_keys=False)
