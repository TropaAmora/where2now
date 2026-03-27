# Product & Development Roadmap

This document tracks planned epics, stories, and design decisions for where2now. It is the single source of truth for *what* we are building and *how* we intend to get there. The README stays high-level; detailed roadmap and implementation notes live here.

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

---

## Epics & Stories (Implementation-Oriented)

Each story has a **goal**, **what** we deliver, and **how** we approach it at a high level.

---

### Epic A — Travel Time Engine v1 (multi-provider ready)

**Focus:** Core abstraction that can hide Google, future historical data, and ML behind a single interface.


| ID     | Story                                   | Goal                                                                 | What                                                                                                                                                     | How (high level)                                                                                                                                                                   |
| ------ | --------------------------------------- | -------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **A1** | Define travel time contracts            | Single, clear shape for “ask” and “answer”.                          | `TravelTimeRequest` and `TravelTimeResult` (see [Story A1 — Concrete definition](#story-a1--concrete-definition-travel-time-contracts) below).           | Shared Pydantic/domain classes; adapt any existing Google calls to these shapes; document in code and a short design note.                                                         |
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
| **E3** | Historical travel-time storage design       | Start collecting data for a model. | Decide what to store: OD pairs, time, restrictions, provider answer, actual outcome if known. | Table or log sink; optional feature flag to start writing.   |
| **E4** | Data & privacy documentation                | Clear expectations.                | Short doc: retention, anonymization, intended ML use.                                         | Doc only; optional config for retention.                     |


---

## Story A1 — Concrete definition (Travel Time Contracts)

Defined here so implementation can start later without re-deciding the core shapes. Adjust as we learn.

### TravelTimeRequest

Represents a single logical request for travel time information. All providers receive the same structure; they may ignore unsupported fields.


| Field            | Type                  | Required | Description                                                                                            |
| ---------------- | --------------------- | -------- | ------------------------------------------------------------------------------------------------------ |
| `origins`        | list of location refs | yes      | One or more origins (e.g. `{"lat": float, "lng": float}` or `{"delivery_point_id": int}`).             |
| `destinations`   | list of location refs | yes      | One or more destinations (same shape as origins).                                                      |
| `departure_time` | datetime or null      | no       | When the trip departs; `null` = “now” or “unspecified”. Affects live traffic where supported.          |
| `transport_mode` | enum/string           | no       | e.g. `driving`, `walking`, `bicycling`, `transit`. Default TBD (e.g. `driving`).                       |
| `restrictions`   | object or null        | no       | Optional restrictions bundle (time windows, avoid tolls, max duration, etc.). Shape defined in Epic C. |
| `metadata`       | object or null        | no       | Optional: `scenario_id`, `user_id`, `request_id` for logging and analytics.                            |


**Location ref:** Either `{"lat": float, "lng": float}` or a reference like `{"delivery_point_id": int}` that the engine resolves before calling providers. Resolution can happen inside the engine so providers only see coordinates if we want.

### TravelTimeResult

Represents the result of a travel-time request. One result per request; matrix results are flattened or keyed by (origin_index, destination_index).


| Field        | Type                | Description                                                                                                |
| ------------ | ------------------- | ---------------------------------------------------------------------------------------------------------- |
| `request_id` | string or null      | Optional correlation id from the request.                                                                  |
| `provider`   | string              | Which provider answered (e.g. `google`, `historical`, `ml`).                                               |
| `legs`       | list of leg results | One entry per (origin, destination) pair in the same order as the implied matrix (origins × destinations). |
| `errors`     | list of error items | Per-leg or global errors (e.g. no route, provider timeout).                                                |


**Leg result** (one per origin–destination pair):


| Field               | Type           | Description                                                        |
| ------------------- | -------------- | ------------------------------------------------------------------ |
| `origin_index`      | int            | Index into `request.origins`.                                      |
| `destination_index` | int            | Index into `request.destinations`.                                 |
| `duration_seconds`  | int or null    | Travel time in seconds; `null` if unknown or error.                |
| `distance_meters`   | int or null    | Distance in meters; `null` if not provided.                        |
| `confidence`        | string or null | Optional: e.g. `high`, `medium`, `low`, `unknown`. For ML/caching. |
| `error`             | string or null | If this leg failed, a short message; otherwise `null`.             |


**Error item:** e.g. `{"leg": (origin_index, destination_index) or null, "message": str, "code": str optional}`.

### Design notes for A1

- **Matrix vs single:** The same contract supports “one origin, one destination” (list length 1) or N×M matrix. Providers that only support 1:1 can be called in a loop or batched by the engine.
- **Restrictions:** In v1, request carries an opaque `restrictions` object; Epic C will define its shape. Providers document which restrictions they support.
- **Provider attribution:** Every result identifies the provider so we can log, compare, and fall back correctly.
- **Extensibility:** Later we can add `alternatives`, `polyline`, or `raw_response` without breaking the core fields.

---

## Story A2 — Concrete definition (Provider & Engine Interfaces)

Defined here so implementation can start without re-deciding the architecture. Adjust as we learn.

### TravelTimeProvider (ABC)

Every provider implements this abstract base class. The engine calls providers through this interface — the rest of the app never touches a provider directly.


| Member             | Kind              | Signature                                          | Description                                                                                                                                                                                     |
| ------------------ | ----------------- | -------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `name`             | abstract property | `-> str`                                           | Unique identifier (e.g. `"google"`, `"historical"`, `"ml"`). Used in logs, results, and config.                                                                                                 |
| `get_travel_times` | abstract method   | `(request: TravelTimeRequest) -> TravelTimeResult` | Compute travel times. Receives a request where **all locations are already resolved to `LatLng*`* (no `DeliveryPointRef`). Must return a `TravelTimeResult` with `provider` set to `self.name`. |


**Provider rules:**

- Providers receive only `LatLng` coordinates — the engine resolves `DeliveryPointRef` before calling any provider.
- A provider that cannot handle part of the request (e.g. unsupported transport mode) should return legs with `error` set, not raise an exception.
- Unrecoverable failures (network down, invalid API key) raise a `TravelTimeProviderError` so the engine can catch and fall back or report.
- Providers must set `TravelTimeResult.provider` to their own `name`.

### TravelTimeProviderError

A custom exception that providers raise for unrecoverable failures.


| Field            | Type              | Description                               |
| ---------------- | ----------------- | ----------------------------------------- |
| `provider_name`  | str               | Which provider failed.                    |
| `message`        | str               | Human-readable description.               |
| `original_error` | Exception or None | The wrapped underlying exception, if any. |


### TravelTimeEngine

The single entry point for the rest of the app. Orchestrates provider selection, location resolution, error handling, and logging.


| Member             | Kind   | Signature                                                                                     | Description                                                                                                         |
| ------------------ | ------ | --------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------- |
| `__init__`         | method | `(providers: list[TravelTimeProvider], strategy: EngineStrategy, resolver: LocationResolver)` | Accepts an ordered list of providers, a strategy, and a resolver for `DeliveryPointRef` lookups.                    |
| `get_travel_times` | method | `(request: TravelTimeRequest) -> TravelTimeResult`                                            | Public entry point. Resolves locations, selects provider(s) per strategy, calls them, and returns a unified result. |


**Engine responsibilities:**

1. **Location resolution** — Walk `request.origins` and `request.destinations`; replace every `DeliveryPointRef` with its resolved `LatLng` via the `LocationResolver`. If resolution fails for any ref, return early with an error result (no provider is called).
2. **Provider selection** — Use the configured `EngineStrategy` to decide which provider(s) to call and in what order.
3. **Execution** — Call the selected provider's `get_travel_times`. Catch `TravelTimeProviderError` and either fall back to the next provider (if strategy allows) or return an error result.
4. **Logging** — Log: which provider was selected, whether it succeeded or failed, and the duration of the call. Use the request's `metadata.request_id` as correlation id when available.

### EngineStrategy (enum)

Controls how the engine selects and calls providers. Start small, extend later.


| Value            | Behavior                                                                                                                                                        |
| ---------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `single`         | Call the first provider in the list. No fallback. This is the v1 default (single Google provider).                                                              |
| `fallback_chain` | Try providers in order; if one raises `TravelTimeProviderError`, try the next. Return the first successful result. (Planned for when we add a second provider.) |


### LocationResolver (ABC)

Responsible for turning `DeliveryPointRef` into `LatLng`. Defined as an ABC so the engine doesn't depend on the database directly — easier to test and to swap implementations.


| Member    | Kind            | Signature                                             | Description                                                                                                                                                                    |
| --------- | --------------- | ----------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `resolve` | abstract method | `(refs: list[DeliveryPointRef]) -> dict[int, LatLng]` | Takes a list of delivery-point refs, returns a mapping of `delivery_point_id → LatLng`. Raises `LocationResolutionError` for any ID that can't be found or has no coordinates. |


**Implementations (planned):**

- `DbLocationResolver` — Queries the `delivery_points` table. This is the real implementation used at runtime.
- A simple dict-based stub for unit tests.

### LocationResolutionError

Raised by a `LocationResolver` when one or more delivery points can't be resolved.


| Field         | Type      | Description                                                    |
| ------------- | --------- | -------------------------------------------------------------- |
| `missing_ids` | list[int] | Delivery-point IDs that were not found or have no coordinates. |
| `message`     | str       | Human-readable description.                                    |


### Design notes for A2

- **Sync for v1.** The provider interface and engine are synchronous. Async execution is scoped to Epic B (Celery). If we later need concurrent provider calls, we can introduce an async variant or run sync providers in a thread pool.
- **Engine does not depend on DB directly.** The `LocationResolver` abstraction keeps the engine testable — unit tests inject a stub resolver, production injects `DbLocationResolver`.
- **One result, one provider.** In v1, a single `TravelTimeResult` comes from a single provider. Multi-provider aggregation (e.g. averaging ML + Google) is a future concern — the contracts support it, but the engine doesn't implement it yet.
- **Strategy is deliberately simple.** `single` covers v1 (Google only). `fallback_chain` is the first multi-provider mode. More sophisticated strategies (weighted, confidence-based routing) can be added as new enum values without changing the engine's public interface.
- **Providers are stateless per call.** Any caching, connection pooling, or rate limiting lives inside the provider implementation, not in the engine.

---

## Ordering & dependencies

- **Epic A** is the backbone: A1 → A2 → A3 → A4 → A5. Engine and contracts should be in place before we rely on them in jobs and restrictions.
- **Epic B** depends on A (at least A1–A4) so that the travel-time job task calls the engine. B1–B2 can start in parallel with A; B3–B5 after engine integration.
- **Epic C** restrictions feed into the engine (A) and into the solver; C1–C2 can progress with A; C3–C4 after request/result shapes and engine interface are stable.
- **Epic D** (Docker) is largely independent; can be done in parallel or early for dev experience.
- **Epic E** can start with E1 (logging) as soon as we have request/response flows; E3–E4 align with Phase 2 of the travel-time rollout.

---

*Last updated: 2025-03 (roadmap created). Adjust this document as we implement and learn.*