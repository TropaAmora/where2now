# Story A3 — Google Maps travel time provider

**Goal:** A production-minded `TravelTimeProvider` that calls Google’s APIs and maps responses to `TravelTimeResult`, with config-driven credentials and timeouts.

**Depends on:** A1 (schemas), A2 (engine + provider contract).  
**Planned module:** `app/travel_times_subsystem/google_provider.py` (name may vary; keep one class per file if it grows).

---

## Class to implement

### `GoogleTravelTimeProvider(TravelTimeProvider)`

| Member | Type | Notes |
|--------|------|------|
| `name` | `property` → `str` | Return `"google"` (or match `settings` if you make it configurable). |
| `get_travel_times` | `(self, request: TravelTimeRequest) -> TravelTimeResult` | Assume origins/destinations are already `LatLng`. |

**Constructor:** accept `httpx.Client` or settings object so tests can inject mocks (avoid hard-coded global client).

---

## API choice (industry default)

Use the **Distance Matrix API** for N×M legs in as few HTTP calls as practical (respect Google’s per-request element limits; batch in a follow-up if matrices are huge).

Alternative: **Directions** for single OD pairs — simpler but more HTTP calls for matrices.

Document in code:

- Which `TransportMode` values map to Google `mode`.
- How `departure_time` maps to `departure_time` / traffic parameters when using driving.

---

## Mapping rules

- Build one `TravelTimeLeg` per matrix cell in **row-major** order (same as A1 story doc).
- Google “no route” / element-level NOT_FOUND → leg with `error` set, not necessarily an exception.
- HTTP 401/403, invalid key, repeated 5xx after retries → `TravelTimeProviderError(provider_name=self.name, ...)`.

Set `TravelTimeResult.provider` to `self.name` and copy `request.metadata.request_id` into `TravelTimeResult.request_id` when present.

---

## Configuration (`app/config.py`)

Suggested settings (names illustrative — align with `.env.example`):

| Setting | Purpose |
|---------|---------|
| `GOOGLE_MAPS_API_KEY` | Server key (never commit real values). |
| `GOOGLE_DISTANCE_MATRIX_BASE_URL` | Optional override for tests or regional endpoints. |
| Timeout / max retries | Consistent with `httpx` usage elsewhere. |

---

## Tests

- Mock `httpx` responses: success matrix, partial element failure, HTTP error → `TravelTimeProviderError`.
- Do not call Google from CI.

---

## Checklist

- [ ] `GoogleTravelTimeProvider` implements `TravelTimeProvider`.
- [ ] Config + timeouts documented in `.env.example`.
- [ ] Unit tests with mocked HTTP.
- [ ] (A4) Wire engine in routes — out of scope for A3 PR if you keep stories split.
