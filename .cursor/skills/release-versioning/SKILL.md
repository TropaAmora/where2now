---
name: release-versioning
description: Handles version bumps, release branches, and tagging for where2now. Use when bumping version, planning a release, deciding between same-PR vs release branch, or when the user asks about release workflow, SemVer, or tag creation.
---

# Release and Versioning (where2now)

Version is in **pyproject.toml** (`version = "X.Y.Z"`). Tags are created automatically when `pyproject.toml` changes on push to `main` (see `.github/workflows/tag-release.yml`). Tags are only created if they don't already exist.

## SemVer (MAJOR.MINOR.PATCH)

- **MAJOR**: Breaking changes.
- **MINOR**: New, backward-compatible feature (e.g. new endpoints).
- **PATCH**: Bug fixes, no new API surface.

For a new feature (e.g. client–delivery-point endpoints), bump **MINOR**: `0.1.0` → `0.2.0`.

## When to bump version

- **Do not** bump on the feature branch at the start of work.
- **Bump on main** when you are ready to release (when the change is merged or about to be merged).

So: implement on the feature branch; add the version bump in the same PR as the feature (recommended) or in a follow-up commit on main.

## One feature → one release (default)

- Add the version bump (e.g. `0.2.0`) in the **same PR** as the feature, as the last commit (or included in the PR).
- Merge to main → push → CI creates tag `v0.2.0`.
- No separate release branch or release-only PR.

## When to use a release branch / release PR

Use a **dedicated release branch or PR** (only changing `pyproject.toml`) when:

- You are **batching several features**: multiple branches merged to main, then one "Release X.Y.Z" step that bumps version and triggers the tag.
- You want "releasing" to be an explicit, separate step (e.g. with release notes or changelog in that PR).

For **one feature = one release**, a release branch is not needed; bump in the feature PR instead.

## Workflow summary

| Scenario | Action |
|----------|--------|
| Single feature, one release | Bump version in the feature PR (e.g. last commit). Merge to main → tag created. |
| Several features, one release | Merge feature PRs to main (no bump). Then open a release PR or commit on main that only bumps `pyproject.toml` → push → tag created. |

## Tag creation (CI)

- **Trigger**: Push to `main` (or `master`) that changes `pyproject.toml`, or manual "Tag release" workflow dispatch.
- **Result**: Tag `vX.Y.Z` is created from current `version` in `pyproject.toml`, only if that tag does not already exist.
