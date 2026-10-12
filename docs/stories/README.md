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
| A5 — Provider configuration | [a5-provider-configuration.md](a5-provider-configuration.md) |

## Job system (Epic B)

| Story | Document |
|-------|----------|
| B1 — Job domain model | [b1-job-domain-model.md](b1-job-domain-model.md) |
| B2 — Job lifecycle | [b2-job-lifecycle-management.md](b2-job-lifecycle-management.md) |
| B3 — Celery base | [b3-celery-base-configuration.md](b3-celery-base-configuration.md) |
| B4 — Travel time job task | [b4-travel-time-job-task.md](b4-travel-time-job-task.md) |
| B5 — Job API endpoints | [b5-job-api-endpoints.md](b5-job-api-endpoints.md) |

## Route plan POC (Epic F)

| Story | Document |
|-------|----------|
| F1 — Minimal route plan | [f1-minimal-route-plan.md](f1-minimal-route-plan.md) |

Example: [../examples/depot-and-stops.md](../examples/depot-and-stops.md) (depot + 10–20 stops)

## Restrictions (Epic C)

| Story | Document |
|-------|----------|
| C1 — Restrictions model | [c1-restrictions-model.md](c1-restrictions-model.md) |

Add new story files here as you start each story so the roadmap does not grow into a single unmaintainable file.
