---
name: travel-time-subsystem
description: where2now travel-time engine, providers, resolvers, and schemas. Use when editing app/travel_times_subsystem, wiring TravelTimeEngine into routes or jobs, implementing Epic A stories, or debugging travel-time flows.
---

# Travel time subsystem (where2now)

## Canonical docs

- Architecture: `docs/architecture/travel-time-subsystem.md`
- Stories: `docs/stories/a1-travel-time-contracts.md`, `a2-provider-engine-resolver.md`, `a3-google-maps-provider.md`, `a4-integrate-engine-into-api-flows.md`

## Code map

| Path | Role |
|------|------|
| `app/travel_times_subsystem/schemas.py` | `TravelTimeRequest`, `TravelTimeResult`, `LatLng`, `DeliveryPointRef`, legs, errors, `TransportMode` |
| `app/travel_times_subsystem/providers.py` | `TravelTimeProvider` (ABC), `TravelTimeProviderError` |
| `app/travel_times_subsystem/resolvers.py` | `LocationResolver`, `LocationResolutionError`, `DbLocationResolver` |
| `app/travel_times_subsystem/engine.py` | `TravelTimeEngine`, `EngineStrategy` |
| `app/travel_times_subsystem/google_provider.py` | `GoogleTravelTimeProvider` (Google Distance Matrix) |

## Rules the agent must follow

1. **Handlers and workers depend on `TravelTimeEngine`**, not on a concrete Google class or raw DB access for location resolution. The engine owns orchestration.

2. **Providers receive requests where every location is already `LatLng`.** The engine resolves `DeliveryPointRef` via `LocationResolver` before calling any provider. Do not push resolution into `GoogleTravelTimeProvider` unless the story explicitly changes that contract.

3. **Errors are layered:**
   - **`TravelTimeProviderError`** — raised by providers for transport/auth/repeated upstream failures; the engine catches this and returns a `TravelTimeResult` with `provider="engine"` and structured errors (see `engine.py`).
   - **Per-leg issues** — Google element `NOT_FOUND` / similar → `TravelTimeLeg.error` string; not necessarily an exception.
   - **`LocationResolutionError`** — engine returns a result with `code=location_resolution_failed` without calling providers.

4. **`EngineStrategy`:** `SINGLE` uses the first provider only; `FALLBACK_CHAIN` tries providers in order until one succeeds.

5. **Match existing patterns** in `tests/test_travel_time_engine.py` for stubs (resolver + provider) when adding integration tests.

## When adding a new provider

- Implement `TravelTimeProvider`: `@property name`, `get_travel_times(request) -> TravelTimeResult`.
- Set `TravelTimeResult.provider` to `self.name` and copy `request.metadata.request_id` when present (per story specs).
- Prefer **injectable** `httpx.Client` or explicit settings for testability.
