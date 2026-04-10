## Summary

<!-- 1-3 bullet points describing what this PR does and why -->

-

## Changes

<!-- List key files/areas changed -->

-

## Testing

- [ ] `make all` passes (lint + test + validate + build + sync + drift)
- [ ] No regressions in `pytest tests/ -v --cov=devolaflow`
- [ ] Coverage >= 80%

## Checklist

- [ ] Follows [repository rules](.cursor/rules/) (CP/SF/CO rules)
- [ ] Conventional commit messages (`feat:`, `fix:`, `docs:`, `test:`, `chore:`)
- [ ] CHANGELOG.md updated if user-visible changes
- [ ] No absolute filesystem paths in agent-facing files
- [ ] Version consistency verified (if version bumped): `python -m pytest tests/test_version.py -v`

## Release Impact

<!-- If this PR is part of a release, note which version and any migration steps -->

N/A
