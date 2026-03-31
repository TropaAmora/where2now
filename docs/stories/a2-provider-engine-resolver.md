# Story A2 — Provider interface, engine, location resolver

**Goal:** A single entry point (`TravelTimeEngine`) that resolves locations, picks providers by strategy, and normalizes failures — without coupling to Google or SQLAlchemy inside the engine.

**Implemented in:**

- `app/travel_times_subsystem/providers.py` — `TravelTimeProvider`, `TravelTimeProviderError`
- `app/travel_times_subsystem/engine.py` — `TravelTimeEngine`, `EngineStrategy`
- `app/travel_times_subsystem/resolvers.py` — `LocationResolver`, `LocationResolutionError`, `DbLocationResolver`

**Tests:** `tests/test_travel_time_engine.py`, `tests/test_travel_time_resolvers.py`

---

## Class reference

### `TravelTimeProvider` (ABC)

| Member | Type | Description |
|--------|------|-------------|
| `name` | `property` → `str` | Stable id: `"google"`, `"historical"`, etc. Must match `TravelTimeResult.provider`. |
| `get_travel_times` | `(self, request: TravelTimeRequest) -> TravelTimeResult` | Input request has **only `LatLng`** in origins/destinations (engine guarantees this). |

**Rules:**

- Partial / business failures → return `TravelTimeResult` with leg `error` or `errors` list.
- Infrastructure failures (network, auth) → raise `TravelTimeProviderError`.

### `TravelTimeProviderError` (Exception)

| Attribute | Type | Description |
|-----------|------|-------------|
| `provider_name` | `str` | Which provider failed. |
| `message` | `str` | Human-readable summary. |
| `original_error` | `Exception \| None` | Optional chained cause. |

### `TravelTimeEngine`

| Member | Type | Description |
|--------|------|-------------|
| `__init__` | `(providers, strategy, resolver)` | Stores list of providers (non-empty), `EngineStrategy`, `LocationResolver`. |
| `get_travel_times` | `(request) -> TravelTimeResult` | Resolves refs → calls provider(s) → returns result or engine-level error result. |

Private helpers (implementation detail, good for tests/readability):

- `_resolve_request_locations` — builds a copy of the request with `DeliveryPointRef` replaced by `LatLng`.
- `_resolve_location` — one ref or `LatLng` → `LatLng`.
- `_call_provider` — logging seam around `provider.get_travel_times`.

### `EngineStrategy` (`str, Enum`)

| Value | Behavior |
|-------|----------|
| `SINGLE` (`"single"`) | Use `providers[0]` only; on `TravelTimeProviderError`, return engine error result (no fallback). |
| `FALLBACK_CHAIN` (`"fallback_chain"`) | Try each provider in order until one succeeds; if all fail, return engine error result. |

### `LocationResolver` (ABC)

| Method | Signature | Description |
|--------|-----------|-------------|
| `resolve` | `(self, refs: list[DeliveryPointRef]) -> dict[int, LatLng]` | Map `delivery_point_id` → `LatLng`. |

### `LocationResolutionError` (Exception)

| Attribute | Type |
|-----------|------|
| `missing_ids` | `list[int]` |
| `message` | `str` |

### `DbLocationResolver`

| Member | Description |
|--------|-------------|
| `__init__(self, db: Session)` | SQLAlchemy session from FastAPI dependency or tests. |
| `resolve` | Loads `DeliveryPoint` rows; missing rows or null lat/lng → `LocationResolutionError`. |

For unit tests without DB, use a small stub class implementing `LocationResolver` (see `StubResolver` pattern in `tests/test_travel_time_engine.py`).

---

## Engine flow (step by step)

1. Read `request_id` from `request.metadata.request_id` if present.
2. Call `_resolve_request_locations`. On `LocationResolutionError`, return `TravelTimeResult(provider="engine", errors=[...])` with code `location_resolution_failed`.
3. If strategy is `SINGLE`, call first provider inside try/except for `TravelTimeProviderError`; on failure return engine result with e.g. `single_provider_failed`.
4. If strategy is `FALLBACK_CHAIN`, loop providers; on success return provider result; if all raise, return `all_providers_failed`.
5. Unknown strategy → `invalid_strategy` error result.

---

## Checklist

- [x] Provider ABC + error type.
- [x] Engine + strategies + resolution path.
- [x] `DbLocationResolver` + tests.
- [ ] Optional: timing metrics in `_call_provider` (can align with Epic E later).
