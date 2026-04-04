# Product & Development Roadmap

This document tracks planned epics, stories, and design decisions for where2now. It is the single source of truth for *what* we are building and *how* we intend to get there. The README stays high-level; detailed roadmap and implementation notes live here.

### Documentation layout (read this first)

The roadmap stays **short and scannable** (epics, order, dependencies). Deeper material lives in two folders so we do not maintain one giant file:

| Location | Purpose |
|----------|---------|
| [`docs/architecture/`](architecture/) | Stable mental model: layers, patterns (strategy, provider, ports), code map, testing approach. Start here if terms like ABC or “provider” are new. |
| [`docs/stories/`](stories/) | **Per-story implementation guides**: exact module paths, class/method tables, checklists, and links to tests. Add a new file when you start a story (B1, C1, …). |

**Travel time (Epic A) today:** [architecture/travel-time-subsystem.md](architecture/travel-time-subsystem.md) · [stories/a1-travel-time-contracts.md](stories/a1-travel-time-contracts.md) · [stories/a2-provider-engine-resolver.md](stories/a2-provider-engine-resolver.md) · [stories/a3-google-maps-provider.md](stories/a3-google-maps-provider.md) · [stories/a4-integrate-engine-into-api-flows.md](stories/a4-integrate-engine-into-api-flows.md) · [stories/a5-provider-configuration.md](stories/a5-provider-configuration.md)

**Job system (Epic B) — in progress:** [stories/b1-job-domain-model.md](stories/b1-job-domain-model.md) · [stories/b2-job-lifecycle-management.md](stories/b2-job-lifecycle-management.md) · [stories/b3-celery-base-configuration.md](stories/b3-celery-base-configuration.md) · [stories/b4-travel-time-job-task.md](stories/b4-travel-time-job-task.md)

---

## Vision

- **Primary value**: Given delivery points and restrictions, the API determines a good route for a logistics planner. Even a single, consistent plan (not necessarily globally optimal) adds significant value.
- **Travel times**: We want to reduce reliance on querying the Google Maps API every time, while still using it as the main source of “real” traffic and events. We will introduce caching, historical data, and (later) an ML layer to improve quality and cost.

---

## Travel Time Engine: Data Sources & Rollout

The engine will eventually support multiple data sources. Design and implementation are staged so we can ship value early and add sophistication incrementally.

### Data sources (target state)

1. **Google Maps** — Live traffic, time-of-day, street closures, real-world events. Remains the baseline ground truth for planning. We will cache and log responses to reduce cost and to build training data.
2. **Measured historical data (own deliveries)** — Real paths and times from drivers for known delivery points. Not mandatory, but gives the model a “real sense of reality” beyond Google’s forecast. Design the system so we can ingest telemetry/actual arrival times when we integrate with real operations.
3. **Historical traffic from public datasets** — Seasonality and typical traffic on major roads. Useful as priors or for pre-training; less precise for last-mile but improves context.
4. **ML / AI estimate** — A model that predicts travel times between delivery points from the above data. Implemented as another *provider* in the engine; used as a cheap approximation with fallback to Google when confidence is low or for critical requests.

### Rollout phases

- **Phase 1 — Google-only provider, with logging**  
Single provider (Google). Every request goes through the engine; we log inputs and outputs. Delivers the core product and sets up observability.
- **Phase 2 — Caching + data collection**  
Cache Google responses; persist historical OD pairs and results (e.g. for Epic E3). Reduces repeated API calls and starts building the dataset for ML.
- **Phase 3 — Historical / public data providers**  
Provider(s) that answer from own historical data or public datasets when available. Used as hints or secondary sources; Google remains the authority where needed.
- **Phase 4 — ML provider**  
Train a model on collected data; add an `MLTravelTimeProvider`. Use ML when confidence is high and routes are typical; fall back to Google (or hybrid) otherwise.

### Travel-time data, clustering, and learning — design backlog (pick up later)

Discussion captured for when we deepen **Epic E** (especially **E3**) and Phases 2–4. Nothing here blocks A4/A5; treat as guidance so the first persistence choices stay valid for years.

- **Append-only observations.** Store each measurement as an immutable fact: stable origin/destination identity, departure context, transport mode, duration/distance, whether traffic-aware, provider, `queried_at`. Aggregates and models are derived; they can be rebuilt if definitions change.
- **Time-bounded context.** Anything that changes over time (coordinates, cluster assignment, per-stop delivery rules) should be **versioned or effective-dated**, not silently overwritten. Training and analytics join observations to **context as-of** that observation to avoid leakage. Per-stop “only certain days” and similar rules stay a **planning/feasibility** concern (**Epic C**), not a substitute for travel-time rows.
- **Dynamic clustering (budget and structure).** Recompute clusters as the network changes. Use clusters to **reduce Google Distance Matrix fan-out** (e.g. dense intra-cluster pairs + a small set of inter-cluster “bridge” legs) while still aiming for a **stronger predictor later** (Phase 4). Clustering is an operational shortcut; the long-term model can use richer features than cluster ID alone.
- **Suggested sequencing when we resume:** nail **E3** table/schema and write path → optional clustering or batching job for API cost → caching and dedupe (Phase 2) → historical provider (Phase 3) → ML provider (Phase 4).

---

## Epics & Stories (Implementation-Oriented)

Each story has a **goal**, **what** we deliver, and **how** we approach it at a high level.

---

### Epic A — Travel Time Engine v1 (multi-provider ready)

**Focus:** Core abstraction that can hide Google, future historical data, and ML behind a single interface.


| ID     | Story                                   | Goal                                                                 | What                                                                                                                                                     | How (high level)                                                                                                                                                                   |
| ------ | --------------------------------------- | -------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **A1** | Define travel time contracts            | Single, clear shape for “ask” and “answer”.                          | `TravelTimeRequest` and `TravelTimeResult` — see [stories/a1-travel-time-contracts.md](stories/a1-travel-time-contracts.md).                               | Shared Pydantic/domain classes; adapt any existing Google calls to these shapes; document in code and a short design note.                                                         |
| **A2** | Design provider and engine interfaces   | Plug in Google, historical, ML without touching the rest of the app. | `TravelTimeProvider` interface (e.g. `get_travel_times(request) -> TravelTimeResult`). `TravelTimeEngine` that selects providers, aggregates, fallbacks. | Abstract base class or protocol for providers; engine that takes a list of providers and a strategy (e.g. “Google only” for v1); normalize errors and log which provider was used. |
| **A3** | Implement Google Maps provider          | Robust, production-ready Google provider.                            | `GoogleTravelTimeProvider`; rate limits, timeouts, retries, API key from config.                                                                         | Map `TravelTimeRequest` → Google API (distance matrix or directions); map response → `TravelTimeResult`; centralize config in env.                                                 |
| **A4** | Integrate engine into current API flows | Existing endpoints use the engine instead of ad-hoc Google calls.    | Main endpoint(s) that need travel times call `TravelTimeEngine`.                                                                                         | Build `TravelTimeRequest` in handlers; call engine; return `TravelTimeResult` (or derived) in responses; keep behavior identical or better.                                        |
| **A5** | Provider configuration & feature flags  | Turn providers on/off and choose strategy without code changes.      | Config (env/settings): enabled providers, ordering, optional weights. Simple modes: `google_only`, `google_then_ml`, etc.                                | At startup, build `TravelTimeEngine` from config; document how to change provider behavior per environment.                                                                        |


---

### Epic B — Job System & Async Execution (Celery)

**Focus:** Background processing for travel-time requests and other heavy work.


| ID     | Story                     | Goal                                              | What                                                                                                                   | How (high level)                                                                                |
| ------ | ------------------------- | ------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------- |
| **B1** | Job domain model & schema | Represent any background job in a consistent way. | Fields: `id`, `type`, `status`, `input_payload`, `result_payload`, `error`, timestamps. Pydantic schema(s) + DB model. | ORM model + migration; schemas for REST.                                                        |
| **B2** | Job lifecycle management  | Clear, unambiguous state transitions.             | Transitions: `PENDING → RUNNING → SUCCESS` / `FAILED` / `CANCELLED`.                                                   | Small service layer: create job, update status, attach result/error; enforce valid transitions. |
| **B3** | Celery base configuration | Working task queue.                               | Celery app, broker, result backend, worker entrypoint.                                                                 | Env-based Celery settings; one trivial test task to prove pipeline.                             |
| **B4** | Travel time job task      | Run travel-time computation as a background job.  | Celery task: take job id or payload → call `TravelTimeEngine` → store result in `Job`.                                 | Task → job service (B2); map exceptions to `FAILED` and error message.                          |
| **B5** | Job API endpoints         | Clients can trigger and observe background work.  | Endpoints: create job (or existing endpoint returns `job_id`), `GET /jobs/{id}`, optionally `GET /jobs/{id}/result`.   | Use job service + schemas; document in README/docs.                                             |


---

### Epic C — Restrictions & Constraints

**Focus:** How users express how they want to travel and what to avoid.


| ID     | Story                                            | Goal                                                             | What                                                                                                         | How (high level)                                                              |
| ------ | ------------------------------------------------ | ---------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------ | ----------------------------------------------------------------------------- |
| **C1** | Restrictions model & schema design               | Flexible but bounded representation of constraints.              | Fields: transport modes, time windows, max route duration, max walking per leg, avoid tolls/highways, etc.   | Agree v1 set; Pydantic + DB if we persist restrictions; leave room to extend. |
| **C2** | Parsing & validation layer                       | Incoming JSON → validated restriction objects with clear errors. | Request schemas; custom validators (e.g. time window logic).                                                 | Pydantic validators; structured error responses from API.                     |
| **C3** | Integrate restrictions into engine and providers | Restrictions actually influence travel time calculation.         | `TravelTimeRequest` carries restrictions; Google provider uses what it supports (e.g. mode, departure_time). | Thread restrictions through engine; per-provider support matrix.              |
| **C4** | API routes & documentation                       | Users know how to send restrictions.                             | Endpoints accept restriction objects; docs show examples.                                                    | Backward compatibility where needed; add “recipe” examples.                   |


---

### Epic D — Runtime & Dev Foundations (Docker & env)

**Focus:** One-command run of the full stack; clear configuration story.


| ID     | Story                         | Goal                                                    | What                                                      | How (high level)                                        |
| ------ | ----------------------------- | ------------------------------------------------------- | --------------------------------------------------------- | ------------------------------------------------------- |
| **D1** | API Dockerfile                | Build and run the API in a container.                   | Dockerfile: app install, env, startup command.            | Mirror current dev setup; avoid premature optimization. |
| **D2** | docker-compose for full stack | One command: API + DB + broker (and optionally worker). | `docker-compose`: app, db, redis/rabbit, optional worker. | Env and volumes; ensure migrations/seed work.           |
| **D3** | Env & configuration alignment | One coherent story for settings (local/dev/prod).       | `.env.example` and settings docs updated.                 | Same env vars work bare-metal and in Docker.            |
| **D4** | Document “run locally” paths  | New dev can start in minutes.                           | README: “Run with Docker” and “Run without Docker”.       | Step-by-step commands; note dependencies.               |


---

### Epic E — Observability & Data for Future ML

**Focus:** Trust the system; collect data needed for a future model.


| ID     | Story                                       | Goal                               | What                                                                                          | How (high level)                                             |
| ------ | ------------------------------------------- | ---------------------------------- | --------------------------------------------------------------------------------------------- | ------------------------------------------------------------ |
| **E1** | Structured logging around travel-time flows | Debug and analyze behavior.        | Logs: incoming request, chosen provider, duration, errors.                                    | Consistent logger; correlation id / job id where applicable. |
| **E2** | Basic metrics/counters                      | Quick health view.                 | Counts: jobs by status, provider success/fail, latency buckets.                               | Logs at first; later Prometheus or similar.                  |
| **E3** | Historical travel-time storage design       | Start collecting data for a model. | Decide what to store: OD pairs, time, restrictions, provider answer, actual outcome if known. | Table or log sink; optional feature flag to start writing. Align with *Travel-time data, clustering, and learning — design backlog* (append-only observations vs. time-bounded context). |
| **E4** | Data & privacy documentation                | Clear expectations.                | Short doc: retention, anonymization, intended ML use.                                         | Doc only; optional config for retention.                     |


---

## Story A1 — Travel time contracts (summary)

**Implemented:** Pydantic models in `app/travel_times_subsystem/schemas.py` (`TravelTimeRequest`, `TravelTimeResult`, `LatLng`, `DeliveryPointRef`, legs, errors, enums).

Full field tables, matrix ordering rules, and a completion checklist: **[stories/a1-travel-time-contracts.md](stories/a1-travel-time-contracts.md)**.

---

## Story A2 — Provider, engine, resolver (summary)

**Implemented:** `TravelTimeProvider` / `TravelTimeProviderError` in `providers.py`; `TravelTimeEngine` / `EngineStrategy` in `engine.py`; `LocationResolver` / `LocationResolutionError` / `DbLocationResolver` in `resolvers.py`.

Providers receive requests where every location is already a **`LatLng`**; the engine resolves **`DeliveryPointRef`** before calling any provider. **`EngineStrategy`** controls single-provider vs fallback chain.

Full class/method tables, exception rules, and flow: **[stories/a2-provider-engine-resolver.md](stories/a2-provider-engine-resolver.md)**. Architecture context (patterns, layers): **[architecture/travel-time-subsystem.md](architecture/travel-time-subsystem.md)**.

---

## Story A3 — Google Maps provider (summary)

**Implemented:** `GoogleTravelTimeProvider` (Distance Matrix), settings in `app/config.py`, tests with mocked HTTP. Wiring through routes remains **A4**.

Spec and checklist: **[stories/a3-google-maps-provider.md](stories/a3-google-maps-provider.md)**.

---

## Story A4 — Integrate engine into API flows (summary)

**Implemented:** `POST /api/travel-times` route in `app/api/routes/travel_times.py`; `get_travel_time_engine` dependency in `app/dependencies.py` (currently hard-coded to Google + `EngineStrategy.SINGLE`). Route is a plain `def` (offloaded to thread pool by FastAPI). Provider selection moves to config in **A5**.

Full spec and checklist: **[stories/a4-integrate-engine-into-api-flows.md](stories/a4-integrate-engine-into-api-flows.md)**.

---

## Story A5 — Provider configuration & feature flags (next)

**Goal:** Operators control which providers are active, their order, and the engine strategy via `TRAVEL_TIME_PROVIDERS` and `TRAVEL_TIME_STRATEGY` env vars. A new provider (ML, historical) will register in one place in `provider_factory.py` — no handler changes.

Full spec: **[stories/a5-provider-configuration.md](stories/a5-provider-configuration.md)**.

---

## Cross-cutting conventions

### Multi-tenancy — `tenant_id` pattern

The system is currently single-tenant (one delivery company, one deployment). To avoid a costly schema migration when a second client arrives, every business table carries a `tenant_id` column from the start.

**Rules:**
- Type: `String(64)`, `nullable=False`, indexed, `server_default='default'`.
- Default value `"default"` is used for all rows during the single-tenant pilot.
- Full row-level isolation (reading `tenant_id` from the auth context and filtering queries) is **not implemented yet** — that belongs to a future auth/tenancy layer (design backlog).
- **Every new business table must include `tenant_id`.** System/operational tables (`log_entries`) are exempt.

Tables with `tenant_id` today: `clients`, `delivery_points`, `jobs` (B1, not yet created).

---

## Ordering & dependencies

- **Epic A** is the backbone: A1 → A2 → A3 → A4 → A5. Engine and contracts should be in place before we rely on them in jobs and restrictions.
- **Epic B** depends on A (at least A1–A4) so that the travel-time job task calls the engine. B1–B2 can start in parallel with A; B3–B5 after engine integration.
- **Epic C** restrictions feed into the engine (A) and into the solver; C1–C2 can progress with A; C3–C4 after request/result shapes and engine interface are stable.
- **Epic D** (Docker) is largely independent; can be done in parallel or early for dev experience.
- **Epic E** can start with E1 (logging) as soon as we have request/response flows; E3–E4 align with Phase 2 of the travel-time rollout. The *Travel-time data, clustering, and learning — design backlog* section informs E3 and later ML work without requiring immediate implementation.

---

*Last updated: 2026-04-04 — added A5 story guide; A4 noted as implemented; added B1–B4 story guides; B2 and B3 implemented. B4 story guide added (travel-time Celery task). Added tenant_id cross-cutting convention; applied to clients, delivery_points, and jobs tables.*