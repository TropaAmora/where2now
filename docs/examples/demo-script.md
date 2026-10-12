# Demo script — depot + stops → route plan

**When to run:** After **F1** is implemented and [`depot-and-stops.json`](../../fixtures/examples/depot-and-stops.json) has real coordinates for 1 depot and 10–20 stops.

**Goal:** Prove the POC end-to-end with one real scenario — not invented data.

---

## Prerequisites

1. API running locally (`uvicorn` or equivalent).
2. Database migrated (`alembic upgrade head`).
3. `GOOGLE_MAPS_API_KEY` set (or travel-time tests mocked — demo needs real key for live run).
4. Fixture filled: **1 depot** + **10–20 stops** with real addresses or lat/lng.

---

## Step 1 — Load delivery points

_TBD: add a small script `scripts/load_example_scenario.py` when F1 lands._

Manual option for now:

1. `POST /delivery-points` for the **depot** (note the returned `id`).
2. `POST /delivery-points` for **each stop** in the fixture (note each `id`).
3. Link stops to a client if your flow requires it (optional for route plan).

Record ID mapping in a local file (not committed) e.g. `fixtures/examples/depot-and-stops.ids.json`:

```json
{
  "depot_id": 1,
  "stop_ids": [2, 3, 4]
}
```

---

## Step 2 — Request a route plan

```http
POST /api/route-plans
Content-Type: application/json

{
  "depot": { "type": "delivery_point", "delivery_point_id": 1 },
  "stops": [
    { "type": "delivery_point", "delivery_point_id": 2 },
    { "type": "delivery_point", "delivery_point_id": 3 }
  ],
  "departure_time": null
}
```

Replace IDs with values from Step 1. Include all stop IDs from the fixture (10–20).

---

## Step 3 — Inspect the result

Check:

- [ ] `ordered_stop_ids` — does the sequence look reasonable?
- [ ] `total_duration_seconds` — compare with operator's estimate if they have one
- [ ] `legs` — any missing durations (geocoding / API errors)?

Optional: paste stop order into Google Maps "Add stop" and compare visually.

---

## Step 4 — Record outcome

Add to [`depot-and-stops.md`](depot-and-stops.md) under Notes:

- Date run
- Number of stops used
- Ordered IDs returned
- Operator reaction / "would you use this?" (1–5)
- What to improve next (constraints, UI, etc.)

---

## Failure checklist

| Problem | Likely cause |
|---------|----------------|
| 422 on route plan | Stop missing lat/lng — geocode delivery points first |
| Empty or partial legs | Google API key, quota, or mock misconfiguration |
| Bad order but valid times | Expected for v0 heuristic — note for solver upgrade later |
