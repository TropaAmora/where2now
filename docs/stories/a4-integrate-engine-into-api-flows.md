# Story A4 — Integrate travel-time engine into API flows

**Goal:** Make the API talk to `TravelTimeEngine` instead of any provider-specific code, so route handlers stay thin and future providers can be added without rewriting HTTP endpoints.

**Depends on:** A1 (contracts), A2 (engine + resolver), A3 (Google provider)  
**Current state:** the travel-time subsystem exists, but there is **no dedicated API route using it yet**. A4 should introduce that seam cleanly.

---

## Product intent

For v1, the API should expose one clear travel-time entry point that:

- accepts a `TravelTimeRequest`,
- delegates all travel-time work to `TravelTimeEngine`,
- returns a `TravelTimeResult`,
- keeps room for A5 so provider choice can move to config later.

The important product boundary is: **routes own HTTP, engine owns travel-time orchestration**.

---

## Recommended first slice

Create a dedicated endpoint instead of burying this inside `clients` or `delivery_points` CRUD routes.

### Route

- `POST /api/travel-times`

### Why this is the right slice

- Travel-time calculation is a cross-cutting query, not a client CRUD concern.
- We do not currently have an ad-hoc Google route to replace in place.
- This gives Epic B a stable synchronous endpoint before we add async job execution.

### Request / response types

Reuse the subsystem contracts directly in v1:

- request model: `app.travel_times_subsystem.schemas.TravelTimeRequest`
- response model: `app.travel_times_subsystem.schemas.TravelTimeResult`

Do **not** create duplicate API schemas unless the public HTTP contract needs to diverge later.

---

## Target modules

| Path | Role |
|------|------|
| `app/api/routes/travel_times.py` | New FastAPI route(s) for synchronous travel-time requests. |
| `app/dependencies.py` | Dependency factory for `TravelTimeEngine` and its collaborators. |
| `main.py` | Include the new router under `/api/travel-times`. |
| `tests/test_api/test_travel_times.py` | API tests for happy path, resolution failure, and provider failure mapping. |

Optional small helpers are fine if they make wiring cleaner, but keep A4 narrow. Avoid introducing a large service layer unless route logic starts repeating.

---

## Dependency wiring

The route should depend on a fully built engine, not assemble providers inline.

### Add in `app/dependencies.py`

Recommended dependency:

- `get_travel_time_engine`

Suggested construction for A4:

1. Reuse `get_db_session`.
2. Build `DbLocationResolver(db)`.
3. Build an `httpx.Client` from settings:
   - `timeout=settings.GOOGLE_DISTANCE_MATRIX_TIMEOUT`
4. Build `GoogleTravelTimeProvider(...)` with:
   - `api_key=settings.GOOGLE_MAPS_API_KEY`
   - `base_url=settings.GOOGLE_DISTANCE_MATRIX_BASE_URL`
   - `max_retries=settings.GOOGLE_DISTANCE_MATRIX_MAX_RETRIES`
5. Return `TravelTimeEngine(providers=[google_provider], strategy=EngineStrategy.SINGLE, resolver=resolver)`.

### A4 boundary

Keep provider selection hard-coded to Google in A4. The moment config starts deciding provider order/mode, that is A5 territory.

---

## Sync vs async

`TravelTimeEngine` and `GoogleTravelTimeProvider` are **synchronous** — they use a blocking `httpx.Client`. FastAPI runs `async def` routes on the event loop, so calling blocking I/O inside one starves the loop under real load.

**Write the route as a plain `def`, not `async def`.** FastAPI automatically offloads plain `def` routes to a thread pool, keeping the event loop free. No changes to the engine or provider are needed.

Migrating to `httpx.AsyncClient` is a valid future step (fits A5 or later), but is out of scope for A4.

---

## Handler flow

### `POST /api/travel-times`

Recommended handler steps:

1. Accept `payload: TravelTimeRequest`.
2. Inject `engine: TravelTimeEngine = Depends(get_travel_time_engine)`.
3. Call `engine.get_travel_times(payload)`.
4. Return the resulting `TravelTimeResult` directly.

The route must be a plain `def` (not `async def`) — see *Sync vs async* above.

This route should be intentionally boring. No Google-specific parameter mapping belongs in the route.

---

## Error semantics for v1

Because the engine already normalizes several failure modes into `TravelTimeResult.errors`, the HTTP layer should stay simple.

### Return `200 OK`

Return `200` with a normal `TravelTimeResult` when:

- travel times are computed successfully,
- one or more legs have `error`,
- the engine returns `provider="engine"` with structured `errors` for resolution/provider failures.

### Let FastAPI handle validation

- invalid request body shape -> `422`

### Avoid extra exception mapping in A4

If dependency construction fails because the server is misconfigured (for example missing API key), it is acceptable for A4 to fail fast and visibly. If you want to polish that later into a cleaner startup/config error, that fits better with A5/D3.

---

## Concrete implementation sketch

### `app/api/routes/travel_times.py`

Add one route:

- `router = APIRouter()`
- `@router.post("/", response_model=TravelTimeResult)`
- **plain `def`**, not `async def` — see *Sync vs async*
- call the engine and return its result

### `main.py`

Register:

- `app.include_router(travel_times.router, prefix="/api/travel-times", tags=["travel_times"])`

### `app/dependencies.py`

Keep the dependency self-contained so tests can override it:

- route tests can override `get_travel_time_engine`
- DB-backed resolution still works because the dependency can reuse `get_db_session`

---

## Testing plan

Add focused API tests in `tests/test_api/test_travel_times.py`.

### Minimum coverage

- `POST /api/travel-times` with concrete `LatLng` request returns `200` and the expected engine result.
- `POST /api/travel-times` with `DeliveryPointRef` resolves IDs through the DB-backed resolver.
- missing `delivery_point_id` returns `200` with `provider="engine"` and `code="location_resolution_failed"`.
- provider failure returns `200` with `provider="engine"` and `code="single_provider_failed"` when using `EngineStrategy.SINGLE`.
- invalid payload returns `422`.

### Test style

Prefer overriding `get_travel_time_engine` in API tests with a stub engine for route-only assertions. Keep one or two tests using the real dependency path when you specifically want to verify DB resolution wiring.

That split gives:

- fast, stable route tests,
- one thin integration test for the actual dependency graph.

---

## Definition of done

- [ ] `POST /api/travel-times` exists and is registered in `main.py`.
- [ ] Route depends on `TravelTimeEngine`, not directly on `GoogleTravelTimeProvider`.
- [ ] A4 uses current contracts (`TravelTimeRequest`, `TravelTimeResult`) without duplicating schemas.
- [ ] Google-specific construction lives in dependency wiring, not in the route handler.
- [ ] API tests cover success, validation failure, location resolution failure, and provider failure.
- [ ] Existing CRUD endpoints keep working unchanged.

---

## Out of scope

- Provider feature flags and ordering from env (`A5`)
- Background execution / job API (`B4`, `B5`)
- Restrictions schema expansion (`C1`-`C4`)
- Metrics and richer observability (`E1`, `E2`)
- Migrating to `httpx.AsyncClient` (valid future step, not A4)

---

## Known pre-existing issues (do not fix in A4)

These exist in the engine today and should be tracked separately to keep A4 narrow.

- **`engine.py` — bare `assert` in fallback chain:** `assert last_error is not None` will raise `AssertionError` in optimised builds (`python -O`). Should be replaced with a proper `if last_error is None: raise RuntimeError(...)` guard. Fix in a dedicated commit, not here.
