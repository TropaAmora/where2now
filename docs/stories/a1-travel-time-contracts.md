# Story A1 — Travel time contracts

**Goal:** One shared "language" for asking and answering travel-time questions across the API, engine, and every provider.

**Implemented in:** `app/travel_times_subsystem/schemas.py`  
**Tests:** `tests/test_schemas/test_travel_time_contracts.py`

---

## Why Pydantic here

We use **Pydantic models** so that:

- HTTP JSON maps cleanly to Python types.
- Invalid payloads fail fast with structured validation errors.
- The same objects can be logged, serialized, and passed into providers.

---

## Core models (names and roles)

| Model | Purpose |
|-------|---------|
| `LatLng` | Concrete point: `lat`, `lng`; discriminator `type == "latlng"`. |
| `DeliveryPointRef` | DB reference: `delivery_point_id`; discriminator `type == "delivery_point"`. |
| `LocationRef` | Type alias: discriminated union `LatLng | DeliveryPointRef` (via Pydantic `Field(discriminator="type")`). |
| `TransportMode` | `str, Enum`: `driving`, `walking`, `bicycling`, `transit`. |
| `RequestMetadata` | Optional `request_id`, `scenario_id`, `user_id` for logging. |
| `TravelTimeRequest` | `origins`, `destinations`, optional `departure_time`, `transport_mode`, `restrictions`, `metadata`. |
| `TravelTimeLeg` | One matrix cell: `origin_index`, `destination_index`, `duration_seconds`, `distance_meters`, `confidence`, `error`. |
| `TravelTimeError` | Global or scoped error: optional indices, `message`, optional `code`. |
| `TravelTimeResult` | `request_id`, `provider` (string id), `legs`, `errors`. |
| `Confidence` | `str, Enum` for leg-level confidence when needed. |

---

## Matrix ordering

For `N` origins and `M` destinations, legs follow **row-major** order:

- Index pairs: `(0,0), (0,1), …, (0,M-1), (1,0), …, (N-1,M-1)`.

Providers and the engine must use the **same order** so indices stay meaningful.

---

## Restrictions (v1)

`TravelTimeRequest.restrictions` is intentionally a loose `dict | None` until Epic C defines a schema. Providers document what they honor.

---

## Checklist (done when A1 is complete)

- [x] Models exist and validate as in roadmap tables.
- [x] Discriminated union works for JSON dicts (`type` field).
- [x] Tests cover validation edges and round-trip serialization.
