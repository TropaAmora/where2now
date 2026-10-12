# Story C1 — Restrictions model & schema design

**Goal:** Define typed, **optional** Pydantic models for delivery rules — so the API and future UI speak a stable language instead of ad-hoc JSON blobs.

**Depends on:** A1 (travel-time contracts exist; `TravelTimeRequest.restrictions` is today `dict | None`).

**Does NOT depend on:** Real constraint values, a UI, or the route-plan feature (F1). C1 is **shape only** — every field is optional and can be empty.

---

## What C1 is trying to achieve (plain language)

Today, if a client sends `"restrictions": {"avoid_tolls": true}`, nothing validates that shape. Epic C1 answers one question:

> *When someone **does** configure a rule, what fields are allowed and how are they named?*

C1 is **not**:

- Filling in time windows or other values for your friend's route (that comes from the real-world example + later UI/config).
- Making Google or the solver obey every rule (that is C3 and future solver work).
- Blocking the POC — F1 (route plan) can ship with **no** restrictions attached.

C1 **is**:

- A shared vocabulary: `TimeWindow`, `TravelRestrictions`, `RouteConstraints`, etc.
- Replacing `dict | None` on `TravelTimeRequest.restrictions` with a typed model (or nested models).
- Deciding what is **stored on a delivery point** (defaults) vs **sent per route-plan request** (overrides for one day).

Think of C1 like defining the empty form fields on a settings page — not filling the form in.

---

## Two layers (do not mix them)

| Layer | Purpose | Example fields | Used by |
|-------|---------|----------------|---------|
| **TravelRestrictions** | How to *compute* leg times | `avoid_tolls`, `avoid_highways`, `transport_mode` | Travel Time Engine / Google (C3) |
| **RouteConstraints** | How to *order* stops on a route | optional `time_windows`, `max_route_duration_seconds`, `must_visit_first`, `must_visit_last` | Route solver (F1+, later MIP) |

Both are optional on every request. Empty `{}` or omitted = no extra rules.

---

## Planned modules (implementation — after F1 POC)

| Path | Purpose |
|------|---------|
| `app/schemas/restrictions.py` | Pydantic models: `TimeWindow`, `TravelRestrictions`, `RouteConstraints`, `StopConstraints` |
| `app/travel_times_subsystem/schemas.py` | Change `TravelTimeRequest.restrictions` from `dict \| None` to `TravelRestrictions \| None` |
| `app/schemas/route_plan.py` (F1) | `RoutePlanRequest` includes optional `RouteConstraints` |

**DB persistence (optional in C1):** If we store default rules on a delivery point, add columns or a JSON column on `delivery_points` — decide in C1, implement in a follow-up migration if needed.

---

## v1 field list (all optional)

### `TimeWindow`

| Field | Type | Notes |
|-------|------|-------|
| `start` | `time` or `datetime` | TBD: time-of-day vs absolute — pick one in C1 implementation |
| `end` | `time` or `datetime` | Must be after `start` (C2 validator) |

### `TravelRestrictions`

| Field | Type | Notes |
|-------|------|-------|
| `avoid_tolls` | `bool \| None` | Google supports |
| `avoid_highways` | `bool \| None` | Google supports |
| `transport_mode` | `TransportMode \| None` | May duplicate top-level request field — document precedence |

### `RouteConstraints`

| Field | Type | Notes |
|-------|------|-------|
| `max_route_duration_seconds` | `int \| None` | Shift / day length cap |
| `departure_time` | `datetime \| None` | May live on route request instead — align with F1 |

### `StopConstraints` (per delivery point, optional)

| Field | Type | Notes |
|-------|------|-------|
| `delivery_point_id` | `int` | Which stop |
| `time_window` | `TimeWindow \| None` | Only if configured |
| `precedence` | `"first" \| "last" \| None` | Optional ordering hint |

---

## Acceptance checklist

- [ ] Pydantic models exist in `app/schemas/restrictions.py`.
- [ ] Every constraint field is optional; empty request validates.
- [ ] `TravelTimeRequest.restrictions` uses `TravelRestrictions` (migration from `dict` documented).
- [ ] Short comment in models: values come from config / measurement / real examples — not hardcoded in code.
- [ ] Tests: round-trip JSON, empty object, invalid time window rejected (basic — full validation is C2).

---

## Out of scope (C1)

- Wiring restrictions into Google provider (C3).
- Solver enforcement of time windows (future MIP epic).
- UI for editing constraints.
- Seed data or example time windows in the repo.

---

## When to implement C1

**After F1** (minimal route plan) works with real stops and no constraints. Order: **F1 → demo with friend's data → C1 → C2**.
