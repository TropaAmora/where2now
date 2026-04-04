# Story A5 — Provider configuration & feature flags

**Goal:** Allow operators to choose which travel-time providers are active, their order, and the engine strategy via environment variables — without touching code. New providers added in future epics slot in by registering one entry.

**Depends on:** A1 (contracts), A2 (engine + strategy), A3 (Google provider), A4 (engine wired into API)  
**Current state:** `get_travel_time_engine` in `app/dependencies.py` hard-codes `[GoogleTravelTimeProvider]` and `EngineStrategy.SINGLE`. A5 replaces those literals with config-driven construction.

---

## Product intent

Today adding a second provider (historical, ML) requires code changes in `dependencies.py`. A5 makes that operational:

- An operator sets `TRAVEL_TIME_PROVIDERS=google` (or `google,ml` when the ML provider lands) in `.env`.
- The engine is built from that list at startup; handlers never change.
- A misconfigured provider name or strategy fails **at startup**, not at the first request — so bad deploys surface immediately.

The important product boundary is: **config owns provider selection; code owns what each provider does**.

---

## Config design

### New settings (add to `app/config.py`)

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `TRAVEL_TIME_PROVIDERS` | `str` | `"google"` | Comma-separated, ordered provider names. The engine calls them in this order. |
| `TRAVEL_TIME_STRATEGY` | `str` | `"single"` | Maps directly to `EngineStrategy` values: `"single"` or `"fallback_chain"`. |

**Example `.env` combinations:**

```dotenv
# v1 — Google only, fail fast if it errors
TRAVEL_TIME_PROVIDERS=google
TRAVEL_TIME_STRATEGY=single

# Future — try Google first; fall back to ML if Google fails
TRAVEL_TIME_PROVIDERS=google,ml
TRAVEL_TIME_STRATEGY=fallback_chain
```

### Design rationale

- Comma-separated string is valid for `pydantic-settings` without extra validators; we parse it in the factory, not in `Settings`.
- `TRAVEL_TIME_STRATEGY` values match `EngineStrategy` enum values (`"single"`, `"fallback_chain"`) exactly, so coercion is trivial and no separate mapping table is needed.
- One setting for provider list, one for strategy — keeps the mental model flat. If we need per-provider weights later (Phase 4), add a third setting then.

---

## Target modules

| Path | Role |
|------|------|
| `app/config.py` | Add `TRAVEL_TIME_PROVIDERS` and `TRAVEL_TIME_STRATEGY` settings. |
| `app/travel_times_subsystem/provider_factory.py` | **New file.** Provider registry + `build_providers()` + `build_strategy()`. Validation raises `ConfigurationError` for unknown names / strategy. |
| `app/dependencies.py` | Replace hard-coded construction with a call to the factory. |
| `main.py` | Add startup validation via FastAPI `lifespan` so misconfiguration fails early. |
| `tests/test_provider_factory.py` | Unit tests for registry lookup, unknown name, empty list, strategy coercion. |
| `tests/test_api/test_travel_times.py` | Extend existing API tests — at minimum one test overriding `TRAVEL_TIME_PROVIDERS` via monkeypatch. |

---

## Provider registry

Create `app/travel_times_subsystem/provider_factory.py`.

### `ConfigurationError`

A dedicated exception (subclass of `RuntimeError`) raised when config is invalid. Makes startup failures easy to catch in tests and in the `lifespan` handler.

### Registry structure

```python
# Maps a provider name to a callable that builds the provider.
# The callable receives a shared httpx.Client.
ProviderFactory = Callable[[httpx.Client], TravelTimeProvider]
_PROVIDER_REGISTRY: dict[str, ProviderFactory]
```

Register `"google"` → `GoogleTravelTimeProvider` in module-level code. When the ML provider lands, add `"ml"` → its factory here — nothing else changes.

### `build_providers(client: httpx.Client) -> list[TravelTimeProvider]`

1. Split `settings.TRAVEL_TIME_PROVIDERS` on commas; strip whitespace; drop empty strings.
2. For each name, look it up in `_PROVIDER_REGISTRY`. Raise `ConfigurationError` with the full list of known names if not found.
3. Raise `ConfigurationError` if the resolved list is empty.
4. Return the list of built providers in config order.

### `build_strategy() -> EngineStrategy`

1. Try `EngineStrategy(settings.TRAVEL_TIME_STRATEGY)`.
2. On `ValueError`, raise `ConfigurationError` with the list of valid values.

### `build_travel_time_engine(db: Session) -> TravelTimeEngine`

Convenience function used by the FastAPI dependency:

1. `client = httpx.Client(timeout=settings.GOOGLE_DISTANCE_MATRIX_TIMEOUT)`.
2. `providers = build_providers(client)`.
3. `strategy = build_strategy()`.
4. `resolver = DbLocationResolver(db)`.
5. Return `TravelTimeEngine(providers=providers, strategy=strategy, resolver=resolver)`.

---

## Startup validation

Bad config should surface at deploy time, not at the first request.

### Add to `main.py`

Use FastAPI's `lifespan` context manager (preferred over deprecated `@app.on_event`):

```python
from contextlib import asynccontextmanager
from app.travel_times_subsystem.provider_factory import build_providers, build_strategy, ConfigurationError
import httpx

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Validate provider config at startup — raises ConfigurationError for bad config
    _client = httpx.Client()
    build_providers(_client)
    build_strategy()
    _client.close()
    yield

app = FastAPI(lifespan=lifespan, ...)
```

This makes the validation run once at startup, with no per-request cost. The `httpx.Client` used here is only for validation (we just check if providers can be constructed), so it is closed immediately.

> **Note:** The per-request dependency still creates its own client. A follow-on story (B or D) can introduce a shared, long-lived client or connection pool when that becomes relevant.

---

## `app/dependencies.py` changes

Replace the inline construction in `get_travel_time_engine` with:

```python
from app.travel_times_subsystem.provider_factory import build_travel_time_engine

def get_travel_time_engine(db: Session = Depends(get_db_session)) -> TravelTimeEngine:
    return build_travel_time_engine(db)
```

The dependency stays injected the same way. API tests continue to override `get_travel_time_engine` for route-only assertions; they do not need to know about the factory internals.

---

## Error semantics

| Scenario | Outcome |
|----------|---------|
| Unknown provider name in `TRAVEL_TIME_PROVIDERS` | `ConfigurationError` at startup |
| Empty `TRAVEL_TIME_PROVIDERS` | `ConfigurationError` at startup |
| Invalid `TRAVEL_TIME_STRATEGY` | `ConfigurationError` at startup |
| Valid config, provider runtime failure | Unchanged — engine returns `TravelTimeResult` with `errors` (A2 / A4 behaviour) |

A5 does **not** add new HTTP error codes. Runtime provider failures still return `200` with structured errors, as established in A4.

---

## Testing plan

### `tests/test_provider_factory.py` — unit tests (no HTTP)

- `TRAVEL_TIME_PROVIDERS=google` → `build_providers` returns one `GoogleTravelTimeProvider`.
- `TRAVEL_TIME_PROVIDERS=google,google` → returns two provider instances (list order preserved).
- `TRAVEL_TIME_PROVIDERS=unknown` → raises `ConfigurationError`; message includes `"unknown"` and lists known providers.
- `TRAVEL_TIME_PROVIDERS=""` → raises `ConfigurationError`.
- `TRAVEL_TIME_STRATEGY=single` → `build_strategy()` returns `EngineStrategy.SINGLE`.
- `TRAVEL_TIME_STRATEGY=fallback_chain` → `build_strategy()` returns `EngineStrategy.FALLBACK_CHAIN`.
- `TRAVEL_TIME_STRATEGY=bad_value` → raises `ConfigurationError`; message includes `"bad_value"`.

Use `monkeypatch` (pytest) to override `settings.TRAVEL_TIME_PROVIDERS` / `settings.TRAVEL_TIME_STRATEGY` per test case. Do not mutate the module-level singleton directly.

### `tests/test_api/test_travel_times.py` — extend existing suite

- Confirm that the API test using `get_travel_time_engine` override continues to pass (no regression).
- Add one test that exercises the **real** dependency with `TRAVEL_TIME_PROVIDERS=google` set, verifying the engine is constructed and the route returns the expected shape (can use a mock Google HTTP response if needed to avoid real API calls).

### Startup validation tests

- Call `build_providers` / `build_strategy` directly — these are pure functions and need no FastAPI test client.
- No need to start a full ASGI app to test config validation.

---

## Definition of done

- [ ] `TRAVEL_TIME_PROVIDERS` and `TRAVEL_TIME_STRATEGY` are declared in `app/config.py` with sensible defaults.
- [ ] `app/travel_times_subsystem/provider_factory.py` exists with `_PROVIDER_REGISTRY`, `build_providers`, `build_strategy`, `build_travel_time_engine`, and `ConfigurationError`.
- [ ] `"google"` is the only registered provider in the registry for A5; the registry is structured so future providers add one line.
- [ ] `get_travel_time_engine` in `app/dependencies.py` delegates to `build_travel_time_engine`; inline construction is gone.
- [ ] `main.py` uses a `lifespan` handler that calls `build_providers` + `build_strategy` at startup and raises on bad config.
- [ ] Unit tests for registry lookup, unknown name, empty list, valid strategy, invalid strategy all pass.
- [ ] Existing API tests pass without modification to their assertions.
- [ ] `.env.example` (if it exists) is updated with `TRAVEL_TIME_PROVIDERS` and `TRAVEL_TIME_STRATEGY`.

---

## Out of scope

- Implementing any new provider (ML, historical) — those are Phase 3/4 and later epics.
- Per-provider weights or confidence thresholds — design backlog, Phase 4.
- Migrating to `httpx.AsyncClient` — valid follow-up, not A5.
- Hot-reloading config without a restart — not needed for v1.
- Background job execution for travel times — Epic B.

---

## Known pre-existing issue (carry forward from A4)

- **`engine.py` — bare `assert` in fallback chain:** `assert last_error is not None` will raise `AssertionError` in optimised builds (`python -O`). Should be replaced with `if last_error is None: raise RuntimeError(...)`. Fix in a dedicated commit, not in A5.
