#!/usr/bin/env python3
"""Humanize a document — write mode + check mode.

Usage:

  # apply transforms in place (writes to disk)
  python scripts/humanize_doc.py apply README.md

  # apply and print the diff on stderr
  python scripts/humanize_doc.py apply README.md --verbose

  # check mode: print naturalness score + would-write byte delta
  # WITHOUT modifying the file; exit 0 if clean, 1 if below advisory,
  # 2 if below hard floor.
  python scripts/humanize_doc.py check README.md

  # score a file without running transforms
  python scripts/humanize_doc.py score README.md

The profile for each doc is picked by path via
`devolaflow.writing_style.profile_for_path`. Override with
`--profile documentation_natural` / `technical_concise` /
`marketing_warm`.

Exit codes:

* 0 — success (apply wrote the file; check / score passed)
* 1 — below advisory floor (check only; content not modified)
* 2 — below hard floor (check only; content not modified)
* 3 — CLI / IO error
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from devolaflow.writing_style import (
    StyleError,
    apply_transforms,
    load_profile,
    profile_for_path,
    score_text,
)


REPO_ROOT = Path(__file__).resolve().parent.parent


def _resolve_profile(path: Path, override: str | None):
    if override is not None:
        return load_profile(override)
    try:
        rel = path.resolve().relative_to(REPO_ROOT)
        return profile_for_path(str(rel))
    except (ValueError, OSError):
        return profile_for_path(path.name)


def _cmd_apply(args: argparse.Namespace) -> int:
    path = Path(args.path)
    if not path.exists():
        print(f"file not found: {path}", file=sys.stderr)
        return 3
    profile = _resolve_profile(path, args.profile)
    before = path.read_text(encoding="utf-8")
    try:
        result = apply_transforms(before, profile)
    except StyleError as e:
        print(f"transform error: {e}", file=sys.stderr)
        return 3
    if result.after == before:
        if args.verbose:
            print(f"no changes on {path} (profile={profile.name})", file=sys.stderr)
        return 0
    if not args.dry_run:
        path.write_text(result.after, encoding="utf-8")
    summary = (
        f"{'would write' if args.dry_run else 'wrote'} {path} "
        f"(profile={profile.name}, transforms={','.join(result.transforms_run)}, "
        f"byte_delta={result.byte_delta:+d})"
    )
    print(summary, file=sys.stderr)
    if args.verbose:
        for name, delta in result.per_transform_delta.items():
            print(f"  {name}: {delta:+d} bytes", file=sys.stderr)
    return 0


def _cmd_check(args: argparse.Namespace) -> int:
    path = Path(args.path)
    if not path.exists():
        print(f"file not found: {path}", file=sys.stderr)
        return 3
    profile = _resolve_profile(path, args.profile)
    text = path.read_text(encoding="utf-8")
    try:
        pre_score = score_text(text, profile)
        result = apply_transforms(text, profile)
        post_score = score_text(result.after, profile)
    except StyleError as e:
        print(f"check error: {e}", file=sys.stderr)
        return 3

    delta = post_score.composite - pre_score.composite
    print(
        f"{path}: profile={profile.name} "
        f"pre={pre_score.composite:.2f} post={post_score.composite:.2f} "
        f"delta={delta:+.2f} byte_delta={result.byte_delta:+d}"
    )

    if post_score.composite < profile.hard_floor:
        print(
            f"  BLOCK: below hard floor {profile.hard_floor}",
            file=sys.stderr,
        )
        return 2
    if post_score.composite < profile.advisory_floor:
        print(
            f"  WARN: below advisory floor {profile.advisory_floor}",
            file=sys.stderr,
        )
        return 1
    return 0


def _cmd_score(args: argparse.Namespace) -> int:
    path = Path(args.path)
    if not path.exists():
        print(f"file not found: {path}", file=sys.stderr)
        return 3
    profile = _resolve_profile(path, args.profile)
    text = path.read_text(encoding="utf-8")
    try:
        result = score_text(text, profile)
    except StyleError as e:
        print(f"score error: {e}", file=sys.stderr)
        return 3
    print(
        f"{path}: profile={profile.name} naturalness={result.composite:.2f} "
        f"words={result.features.words}"
    )
    if args.verbose:
        for name, sub in sorted(result.per_feature_subscores.items()):
            print(f"  {name}: {sub:.3f}")
    return 0


def _add_common(p: argparse.ArgumentParser) -> None:
    p.add_argument("--profile", default=None, help="override profile selection")
    p.add_argument("-v", "--verbose", action="store_true")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_apply = sub.add_parser("apply", help="run transforms and write result")
    p_apply.add_argument("path")
    p_apply.add_argument("--dry-run", action="store_true", help="don't write")
    _add_common(p_apply)
    p_apply.set_defaults(func=_cmd_apply)

    p_check = sub.add_parser("check", help="compute pre/post scores without writing")
    p_check.add_argument("path")
    _add_common(p_check)
    p_check.set_defaults(func=_cmd_check)

    p_score = sub.add_parser("score", help="compute naturalness score only")
    p_score.add_argument("path")
    _add_common(p_score)
    p_score.set_defaults(func=_cmd_score)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
