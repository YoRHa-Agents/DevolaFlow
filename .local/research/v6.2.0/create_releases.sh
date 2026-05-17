#!/usr/bin/env bash
# Create GitHub Releases for each v6.x tag.
# Extracts notes from CHANGELOG.md (between `## [X.Y.Z]` and the next `## [`).
# Run from repo root.

set -euo pipefail

VERSIONS=(6.0.1 6.0.2 6.0.3 6.0.4 6.0.5 6.1.0 6.1.1 6.1.2 6.1.3 6.1.4 6.1.5 6.2.0)

extract_notes() {
    local version="$1"
    awk -v ver="$version" '
        $0 ~ "^## \\[" ver "\\]" { capture = 1; next }
        capture && $0 ~ "^## \\[" { exit }
        capture { print }
    ' CHANGELOG.md
}

for v in "${VERSIONS[@]}"; do
    tag="v$v"
    title="DevolaFlow $tag"

    tmpfile="$(mktemp)"
    extract_notes "$v" > "$tmpfile"

    # If notes are empty (extraction failed), use tag annotation
    if [ ! -s "$tmpfile" ]; then
        echo "WARNING: empty notes for $tag, using tag annotation as fallback"
        git tag -l --format='%(contents)' "$tag" > "$tmpfile"
    fi

    # v6.0.2 is BREAKING — flag it
    flags=()
    case "$v" in
        6.0.2) flags+=(--notes-file "$tmpfile") ;;
        6.2.0) flags+=(--notes-file "$tmpfile" --latest) ;;
        *)     flags+=(--notes-file "$tmpfile") ;;
    esac

    echo "Creating release $tag..."
    if gh release view "$tag" >/dev/null 2>&1; then
        echo "  $tag already exists, skipping"
    else
        gh release create "$tag" --title "$title" "${flags[@]}" 2>&1 | tail -1
    fi

    rm -f "$tmpfile"
done

echo "Done."
gh release list --limit 15
