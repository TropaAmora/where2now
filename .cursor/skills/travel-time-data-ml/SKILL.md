---
name: travel-time-data-ml
description: where2now plan for travel-time observations, caching, clustering for API budget, and future ML provider. Use when designing Epic E storage (E3), historical providers, batching Google calls, roadmap Phase 2–4, or data retention for models.
---

# Travel-time data, clustering, and ML (where2now)

## Where this is documented

- **Roadmap:** `docs/roadmap.md` — section *Travel-time data, clustering, and learning — design backlog*; also **Epic E** (E3, E4) and *Travel Time Engine: Data Sources & Rollout* phases.
- **Restrictions vs travel times:** **Epic C** — feasibility (e.g. allowed delivery days) is a **planning layer**, not a substitute for storing OD travel measurements.

## Design principles (keep data valid for years)

1. **Append-only observations**  
   Each provider response (or future ground truth) is an **immutable fact**: stable origin/destination identity, departure context, transport mode, duration/distance, traffic-aware flag, provider, `queried_at`. Aggregates and model training sets are **derived** and can be rebuilt.

2. **Time-bounded context**  
   Anything that changes — coordinates, cluster membership, business rules — should be **versioned or effective-dated**. For ML, join observations to **context as-of that observation** to avoid leakage.

3. **Clustering is operational**  
   Dynamic clusters (e.g. DBSCAN, H3) primarily **reduce Distance Matrix fan-out** (intra-cluster + bridge legs). They are **not** the only future model interface; a stronger predictor can use richer features than cluster ID alone.

4. **Suggested sequencing** (when implementing)  
   E3 schema + write path → optional clustering/batching → Phase 2 caching and dedupe → Phase 3 historical provider → Phase 4 `MLTravelTimeProvider` in the same **provider** abstraction as Google.

## Engine integration (future)

- Prefer logging or persisting observations **at the engine boundary** after a successful provider call, so all providers are observed consistently and providers stay thin.
- Fallback chain (A2) already supports putting a cheap provider first and Google second.

## Do not conflate

- **Travel time** (how long a leg takes under some conditions) vs **feasibility** (whether a stop may be served on a given day) — separate tables and concerns.
