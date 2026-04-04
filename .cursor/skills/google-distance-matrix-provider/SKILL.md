---
name: google-distance-matrix-provider
description: Google Distance Matrix integration for where2now travel times. Use when editing google_provider.py, configuring Google Maps env vars, mapping TransportMode or departure_time, or writing tests that mock Distance Matrix JSON.
---

# Google Distance Matrix provider (where2now)

## Module

- `app/travel_times_subsystem/google_provider.py` — `GoogleTravelTimeProvider`

## API choice

- Use the **Distance Matrix API** for N×M legs in one HTTP call (within Google’s per-request element limits; batch in follow-up work if matrices are huge).
- Alternative **Directions** is one OD per call — avoid for matrices.

## Request mapping

- **Origins / destinations:** pipe-separated `lat,lng` strings (assume inputs are already `LatLng` after engine resolution).
- **`mode`:** project `TransportMode` values (`driving`, `walking`, `bicycling`, `transit`) match Google’s `mode` parameter.
- **`departure_time`:** for **driving only**, send Unix epoch seconds so Google can return traffic-aware estimates; prefer `duration_in_traffic` in the response when present, else `duration`.

## Response mapping

- **Row-major legs:** `rows[i].elements[j]` → `TravelTimeLeg(origin_index=i, destination_index=j, ...)`.
- **Element `status == OK`:** fill `duration_seconds`, `distance_meters`, set confidence as appropriate (e.g. `HIGH` when values present).
- **Element no-route style statuses** (e.g. `NOT_FOUND`, `ZERO_RESULTS`): set `TravelTimeLeg.error`; do not necessarily raise.
- **HTTP 401 / 403:** raise `TravelTimeProviderError` (auth).
- **HTTP 5xx:** retry up to configured max, then `TravelTimeProviderError`.
- **Top-level JSON `status`:** `OK` with per-element errors is normal; `REQUEST_DENIED` and similar → `TravelTimeProviderError`.

## Construction and config

- **Inject `httpx.Client`** (no global client). Tests use `httpx.MockTransport`.
- Settings live in `app/config.py` / `.env.example`: `GOOGLE_MAPS_API_KEY`, `GOOGLE_DISTANCE_MATRIX_BASE_URL`, `GOOGLE_DISTANCE_MATRIX_TIMEOUT`, `GOOGLE_DISTANCE_MATRIX_MAX_RETRIES`.
- `GoogleTravelTimeProvider.name` must return `"google"` (property on the ABC).

## Tests

- Do not call Google from CI; mock JSON bodies and HTTP status codes.
- See `tests/test_google_provider.py` for patterns.

## Story spec

- `docs/stories/a3-google-maps-provider.md`
