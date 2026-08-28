#!/usr/bin/env python3
"""Fail-closed contract gate for the offline functional-test matrix."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tests.functional.runner import (  # noqa: E402
    MATRIX_RELATIVE_PATH,
    MatrixDiagnostic,
    validate_matrix_file,
)


def check_functional_matrix(
    matrix_path: Path | None = None,
    repo_root: Path | None = None,
) -> tuple[MatrixDiagnostic, ...]:
    """Return deterministic diagnostics for a supplied or default matrix."""
    root = (repo_root or REPO_ROOT).resolve()
    path = matrix_path or MATRIX_RELATIVE_PATH
    return validate_matrix_file(Path(path), root)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "matrix_path",
        nargs="?",
        type=Path,
        help="repository-relative or absolute matrix path",
    )
    parser.add_argument(
        "--matrix",
        dest="matrix_option",
        type=Path,
        help="matrix path (alternative to the positional path)",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=REPO_ROOT,
        help="repository root used for relative paths",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="emit a deterministic JSON diagnostic document",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the matrix contract gate and return a process status."""
    args = _parser().parse_args(argv)
    if args.matrix_path is not None and args.matrix_option is not None:
        _parser().error("matrix path may be supplied positionally or with --matrix, not both")
    matrix_path = args.matrix_option or args.matrix_path or MATRIX_RELATIVE_PATH
    repo_root = args.repo_root.resolve()
    diagnostics = check_functional_matrix(matrix_path, repo_root)

    if args.json:
        payload = {
            "status": "PASS" if not diagnostics else "FAIL",
            "diagnostics": [item.to_dict() for item in diagnostics],
        }
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2))
    else:
        if diagnostics:
            print("[FAIL] functional matrix contract")
            for item in diagnostics:
                print(f"  - {item}")
        else:
            print("[PASS] functional matrix contract")
    return 0 if not diagnostics else 1


if __name__ == "__main__":
    raise SystemExit(main())
