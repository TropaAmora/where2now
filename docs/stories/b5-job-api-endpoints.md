# Story B5 — Job API endpoints

**Goal:** Clients can submit a travel-time request asynchronously, get a job ID back immediately, and poll for the result — without blocking an HTTP worker for the duration of the computation.

**Depends on:** B2 (`JobService`), B3 (Celery app), B4 (`run_travel_time_job` task), A1–A4 (`TravelTimeRequest` schema).  
**Current state:** `run_travel_time_job` exists and works; there is no HTTP surface for clients to trigger it or observe the outcome.

---

## Product intent

The current `POST /api/travel-times/` is synchronous — it blocks until Google responds. Under load, or with large matrices, this degrades throughput. B5 adds an async path:

1. Client posts a `TravelTimeRequest` to `POST /api/jobs/travel-time`.
2. The API creates a job row and enqueues the task immediately — returns `202 Accepted` with the `JobRead` payload.
3. Client polls `GET /api/jobs/{job_id}` until `status` is `success` or `failed`.
4. On `success`, `result_payload` contains the full `TravelTimeResult`. On `failed`, `error` contains a human-readable message.

The existing synchronous endpoint is **not changed** — it remains useful for small, latency-sensitive requests.

---

## Endpoints

| Method | Path | Description | Success code |
|--------|------|-------------|--------------|
| `POST` | `/api/jobs/travel-time` | Create an async travel-time job | `202 Accepted` |
| `GET` | `/api/jobs/{job_id}` | Poll job status and result | `200 OK` |
| `POST` | `/api/jobs/{job_id}/cancel` | Cancel a pending or running job | `200 OK` |

---

## Design decisions

### Why a dedicated `/api/jobs/` prefix?

A new `/api/jobs/` router keeps job concerns together and leaves `/api/travel-times/` untouched. Future job types (routing, export) will add their own `POST /api/jobs/<type>` create endpoints alongside this one.

### `tenant_id` is hardcoded to `"default"` in B5

No auth layer exists yet. Every job created in B5 gets `tenant_id="default"`. When auth is introduced, the handler will read `tenant_id` from the request context instead. This is a one-line change.

### `GET /api/jobs/{job_id}/result` is not added

It would just return `job.result_payload` — a subset of `GET /api/jobs/{job_id}`. Polling the full job is simpler for clients and avoids a redundant endpoint.

### Cancel returns 409 on invalid transition

If the job is already in a terminal state (`success`, `failed`, `cancelled`), `JobService.cancel_job` raises `InvalidJobTransitionError`. The handler catches this and returns `409 Conflict` with the error message.

### Schema fix: add `tenant_id` to `JobRead`

`JobRead` was specified in B1 with `tenant_id` but it was omitted from the implementation. B5 adds it so the full job is exposed on the wire.

---

## Target modules

| Path | Role |
|------|------|
| `app/jobs/schemas.py` | Add `tenant_id: str` to `JobRead`. |
| `app/dependencies.py` | Add `get_job_service` dependency. |
| `app/api/routes/jobs.py` | New router with the three endpoints. |
| `main.py` | Register `jobs.router` at `/api/jobs`. |
| `tests/test_api/test_jobs_api.py` | HTTP-layer tests; `run_travel_time_job.delay` is mocked. |

---

## `app/dependencies.py` addition

```python
from app.jobs.service import JobService

def get_job_service(db: Session = Depends(get_db_session)) -> JobService:
    return JobService(db)
```

---

## `app/api/routes/jobs.py`

```python
import uuid
from unittest.mock import patch

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.dependencies import get_job_service
from app.jobs.schemas import JobRead
from app.jobs.service import InvalidJobTransitionError, JobNotFoundError, JobService
from app.jobs.tasks import run_travel_time_job
from app.travel_times_subsystem.schemas import TravelTimeRequest

router = APIRouter()


@router.post("/travel-time", response_model=JobRead, status_code=202)
def create_travel_time_job(
    payload: TravelTimeRequest,
    svc: JobService = Depends(get_job_service),
) -> JobRead:
    job = svc.create_job(
        type="travel_time",
        input_payload=payload.model_dump(mode="json"),
        tenant_id="default",
    )
    run_travel_time_job.delay(str(job.id))
    return job


@router.get("/{job_id}", response_model=JobRead)
def get_job(job_id: uuid.UUID, svc: JobService = Depends(get_job_service)) -> JobRead:
    job = svc.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found.")
    return job


@router.post("/{job_id}/cancel", response_model=JobRead)
def cancel_job(job_id: uuid.UUID, svc: JobService = Depends(get_job_service)) -> JobRead:
    try:
        return svc.cancel_job(job_id)
    except JobNotFoundError:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found.")
    except InvalidJobTransitionError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
```

---

## Testing plan

All tests in `tests/test_api/test_jobs_api.py`. Uses the `client` fixture from `conftest.py`.  
`run_travel_time_job.delay` is patched to prevent any real Celery/Redis call.

### `POST /api/jobs/travel-time`
- Returns `202` with `status="pending"`.
- Response body contains a valid UUID `id`.
- `run_travel_time_job.delay` called once with a string job ID.
- Invalid `TravelTimeRequest` body → `422`.

### `GET /api/jobs/{job_id}`
- Returns `200` with the correct job after creation.
- Returns `404` for an unknown UUID.

### `POST /api/jobs/{job_id}/cancel`
- A `pending` job transitions to `cancelled`; returns `200`.
- Unknown UUID → `404`.
- A `success` job → `409` (terminal state, transition rejected).

---

## Definition of done

- [ ] `tenant_id` present in `JobRead`.
- [ ] `get_job_service` in `app/dependencies.py`.
- [ ] `app/api/routes/jobs.py` with all three endpoints.
- [ ] Router registered in `main.py` at `/api/jobs`.
- [ ] All tests in `tests/test_api/test_jobs_api.py` pass.
- [ ] Existing test suite (`pytest`) still passes in full.

---

## Out of scope

- Auth / real `tenant_id` from request context — auth layer (design backlog)
- `GET /api/jobs/` list endpoint — design backlog (needs pagination + tenant filtering)
- Job retry via API — design backlog
- `GET /api/jobs/{job_id}/result` — redundant with full `JobRead`; not added
- docker-compose for Redis + worker — **D2**
