---
name: where2now-docs-roadmap
description: where2now documentation layout, roadmap conventions, and story file expectations. Use when editing docs/roadmap.md, adding or changing docs/stories, or pointing contributors to architecture vs story depth.
---

# where2now docs and roadmap

## Layout (single structure)

| Location | Purpose |
|----------|---------|
| `docs/roadmap.md` | **Short and scannable:** vision, epic tables, story order, dependencies, brief summaries. Not a full design dump. |
| `docs/architecture/` | Stable mental model: subsystems, layers, patterns, code map. One topic per file where possible. |
| `docs/stories/` | **Per-story implementation guides:** goal, dependencies, module paths, class/method tables, checklists, links to tests. |

The README stays high-level; deep detail lives under `docs/`.

## When adding a new story file

1. Create `docs/stories/<id>-short-slug.md` (e.g. `a4-integrate-engine-into-api-flows.md`).
2. Include: goal, depends-on, planned modules, checklist, out-of-scope pointers (e.g. “A5 does flags”).
3. Add a link from `docs/roadmap.md` in the epic table and in the “Travel time (Epic A) today” (or relevant) bullet list.
4. Optionally add a one-line summary section at the bottom of the roadmap when the story lands (implemented / next).

## Roadmap edits

- Prefer **adding a subsection** for design backlog or phased rollout rather than inflating epic table cells.
- Cross-reference epics in tables (e.g. E3 → design backlog) instead of duplicating long prose.
- Update *Last updated* at the bottom when the roadmap meaningfully changes.

## Stories index

- `docs/stories/README.md` — if present, keep it aligned when new story files are added.
