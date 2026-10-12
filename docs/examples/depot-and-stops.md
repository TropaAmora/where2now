# Example scenario — depot + 10–20 stops (real addresses)

**Status:** Template — fill in from a real B2B delivery run. Do not invent addresses or times.

**Purpose:** One real-world case (1 depot + roughly 10–20 delivery stops) to load into the DB and run through `POST /api/route-plans` once F1 is implemented.

---

## What this example contains

| Piece | Count | Notes |
|-------|-------|-------|
| **Depot** | 1 | Where the driver starts and finishes (round trip) |
| **Stops** | 10–20 | Real delivery addresses or lat/lng — your friend's typical day is ~20 |

---

## Operator (source)

| Field | Value |
|-------|-------|
| Contact | Friend — _name TBD_ |
| Operation | B2B deliveries (not food / not end-consumer real-time) |
| Typical day | ~20 delivery points (within the 10–20 POC range) |
| Frequency | Weekly — _confirm with them_ |
| Planning today | _spreadsheet / paper / other — ask_ |

---

## What we need to collect (checklist)

Ask for **facts only** — skip anything they don't know or don't use.

- [ ] **Depot** — one address or lat/lng (start/end of route)
- [ ] **Stop list** — 10–20 real delivery addresses (or lat/lng from GPS exports)
- [ ] **Rough leave time** — optional; only if they plan around traffic
- [ ] **Any hard rules?** — e.g. "always visit X first" — optional; leave blank if none
- [ ] **How they judge a good route today** — in their words (for manual comparison after POC)

**Do not collect for POC:** time windows unless they already enforce them; vehicle weight rules; customer phone numbers.

---

## Success criteria (manual)

After F1 returns a route, you (or your friend) should be able to say:

1. Order looks **plausible** on a map (no obvious backtracking across the city).
2. Total drive time is **in the same ballpark** as their intuition for the day.
3. Nothing required secret customer data in the repo — anonymize labels if needed.

---

## Data file

Structured depot + stops live in:

**[`fixtures/examples/depot-and-stops.json`](../../fixtures/examples/depot-and-stops.json)**

Fill that JSON as you gather real addresses. The demo script loads it into the API.

---

## Notes from conversations

_Use this section as you talk to your friend._

```
Date:
Notes:


```
