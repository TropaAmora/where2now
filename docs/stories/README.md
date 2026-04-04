# Story implementation guides

Each file here is a **developer-focused** supplement to [`docs/roadmap.md`](../roadmap.md). The roadmap stays the index of epics and order; these documents hold **enough detail to implement** without re-discovering types and file names.

## How to use

1. Read the epic row in `roadmap.md` for scope and dependencies.
2. Open the matching story doc below for module paths, classes, and acceptance-style notes.
3. For the big picture (patterns, layers), see [`docs/architecture/travel-time-subsystem.md`](../architecture/travel-time-subsystem.md).

## Travel Time Engine (Epic A)

| Story | Document |
|-------|----------|
| A1 — Contracts | [a1-travel-time-contracts.md](a1-travel-time-contracts.md) |
| A2 — Provider, engine, resolver | [a2-provider-engine-resolver.md](a2-provider-engine-resolver.md) |
| A3 — Google Maps provider | [a3-google-maps-provider.md](a3-google-maps-provider.md) |
| A4 — Integrate engine into API flows | [a4-integrate-engine-into-api-flows.md](a4-integrate-engine-into-api-flows.md) |

Add new story files here as you start each story (B1, C1, …) so the roadmap does not grow into a single unmaintainable file.
