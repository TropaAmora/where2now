# Story F1 — Minimal route plan (POC)

**Goal:** Given a depot and ~10–20 delivery point IDs, return a **suggested visit order** and total travel time — proving the core product question without time windows or advanced constraints.

**Depends on:** A1–A5 (travel-time engine), delivery points in DB with coordinates.

**Out of scope for F1:** Time windows, capacity, multi-driver, map polyline, UI, optimal MIP/LP solver.

---

## Product intent

> *"I have ~20 deliveries to make this week — what's a sensible route?"*

Input: list of stop IDs + where the driver starts (depot).  
Output: ordered list of stops + leg durations + total duration/distance.

Constraints are **not required**. F1 ignores Epic C until C1 lands later.

---

## API (planned)

### `POST /api/route-plans`

**Request body (draft):**

```json
{
  "depot": { "type": "delivery_point", "delivery_point_id": 1 },
  "stops": [
    { "type": "delivery_point", "delivery_point_id": 2 },
    { "type": "delivery_point", "delivery_point_id": 3 }
  ],
  "departure_time": null
}
```

| Field | Required | Notes |
|-------|----------|-------|
| `depot` | Yes | `DeliveryPointRef` or `LatLng` — start and end here (round trip) |
| `stops` | Yes | 1–50 `LocationRef` items (POC target: 10–20) |
| `departure_time` | No | Passed to travel-time engine for traffic-aware matrix |

**Response body (draft):**

```json
{
  "ordered_stop_ids": [3, 7, 2, 5],
  "legs": [
    {
      "from_delivery_point_id": 1,
      "to_delivery_point_id": 3,
      "duration_seconds": 840,
      "distance_meters": 5200
    }
  ],
  "total_duration_seconds": 14400,
  "total_distance_meters": 85000
}
```

Sync endpoint is fine for POC (matrix + simple solver for 20 stops is seconds, not minutes). Async job wrapper can come in F2 if needed.

---

## Flow

```
POST /api/route-plans
  → Resolve depot + stops to LatLng (DbLocationResolver)
  → Build TravelTimeRequest (origins = all nodes, destinations = all nodes)
  → TravelTimeEngine.get_travel_times()
  → Build duration matrix from result legs
  → Run simple solver (see below)
  → Return ordered stops + leg breakdown
```

---

## Solver (v0)

Use a **simple heuristic**, not full MIP:

- Option A: **Nearest neighbor** from depot — easy to test, good enough for POC.
- Option B: **OR-Tools TSP** — better quality, still small dependency.

Pick one in implementation; document in this file when chosen.

Round trip: depot → stop₁ → … → stopₙ → depot.

---

## Planned modules

| Path | Purpose |
|------|---------|
| `app/schemas/route_plan.py` | `RoutePlanRequest`, `RoutePlanResponse`, leg models |
| `app/solver/heuristic.py` or `app/solver/tsp.py` | Ordering logic from duration matrix |
| `app/services/route_plan_service.py` | Orchestrates matrix + solver |
| `app/api/routes/route_plans.py` | `POST /api/route-plans` |
| `tests/test_api/test_route_plans.py` | API tests with mocked travel times |
| `tests/test_solver/` | Unit tests for ordering with fixed matrix |

---

## Acceptance checklist

- [ ] `POST /api/route-plans` accepts depot + stop IDs.
- [ ] Returns ordered stops and per-leg duration/distance.
- [ ] Works when all stops have lat/lng in DB.
- [ ] Clear 4xx when a stop is missing coordinates or unknown ID.
- [ ] Tests use mocked engine (no real Google calls in CI).
- [ ] Demo script (see `docs/examples/demo-script.md`) runs against `depot-and-stops` fixture (1 depot + 10–20 real addresses) once filled in.

---

## Out of scope (F1)

- Epic C restriction enforcement.
- Persisting route plans to DB.
- Celery job type (optional F2).
- Comparing plan to driver's actual route (future observability).
