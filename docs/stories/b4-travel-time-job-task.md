# Story B4 — Travel time job task

**Goal:** A Celery task that takes a job ID, runs the travel-time engine, and writes the outcome back through `JobService` — so the full async flow works end-to-end.

**Depends on:** B2 (`JobService`, lifecycle transitions), B3 (Celery app, task infrastructure), A2–A4 (`TravelTimeEngine`, `build_travel_time_engine`).  
**Current state:** `JobService` controls state transitions; the Celery worker is running. Nothing yet connects a job row to actual travel-time computation.

---

## Product intent

When a client submits a travel-time request, the API will (in B5):

1. Create a `Job` row with `type="travel_time"` and the request as `input_payload`.
2. Enqueue `run_travel_time_job.delay(str(job.id))`.
3. Return the `job_id` immediately.

The worker then picks up the task, calls the engine, and writes either a result or an error back into the job row. The client polls `GET /jobs/{id}` (B5) until status is terminal.

B4 implements step 2 and everything the worker does. B5 wires in the API side.

---

## State flow

```
create_job() → PENDING
    ↓  [task starts]
mark_running() → RUNNING
    ↓  [engine called]
mark_success(result_payload)  ← engine returns legs, no errors
mark_failed(error)            ← engine returns errors OR unexpected exception
```

---

## Design decisions

### Task accepts `job_id` as a string

Celery serializes task arguments as JSON. `uuid.UUID` is not JSON-serializable, so the task signature takes `job_id_str: str` and converts it to `uuid.UUID` inside. Callers pass `str(job.id)`.

### Business logic lives in `_execute_travel_time_job`, not in the task decorator

The task wrapper (`run_travel_time_job`) owns only infrastructure: open DB session, build engine, call the logic function, close the session. The logic function (`_execute_travel_time_job`) accepts `job_id`, `db`, and `engine` — making it directly callable in tests without going through Celery machinery or touching a real broker.

This keeps tests simple: create a job with `db_session`, pass in a mock engine, call `_execute_travel_time_job` directly, assert on the job's final state.

### What counts as failure

Two failure modes:

1. **Provider-level errors** — `TravelTimeResult.errors` is non-empty. The engine already normalised these; we join their messages and call `mark_failed`.
2. **Unexpected exception** — anything Python raises during payload validation, engine construction, or unexpected DB errors. Caught by a broad `except Exception` and sent to `mark_failed`. Task itself does not re-raise, so Celery does not retry (retry logic is a design-backlog item).

### Result payload

On success, `result_payload` is `TravelTimeResult.model_dump(mode="json")`. This stores the full structured result (legs, provider, request_id) so B5 can return it without re-querying the engine.

### DB session lifecycle

The task opens a `SessionLocal()`, passes it to both `JobService` and `build_travel_time_engine`, and closes it in `finally`. One session per task execution — simple and correct.

---

## Target modules

| Path | Role |
|------|------|
| `app/jobs/tasks.py` | Add `run_travel_time_job` task and `_execute_travel_time_job` helper. |
| `tests/test_jobs/test_travel_time_task.py` | Tests for B4 logic; call `_execute_travel_time_job` directly with a mock engine. |

No changes to `app/celery_app.py`, `app/jobs/service.py`, or models.

---

## `app/jobs/tasks.py` — additions

```python
import uuid
import logging
from sqlalchemy.orm import Session
from app.celery_app import celery_app
from app.db.session import SessionLocal
from app.jobs.service import JobService
from app.travel_times_subsystem.engine import TravelTimeEngine
from app.travel_times_subsystem.provider_factory import build_travel_time_engine
from app.travel_times_subsystem.schemas import TravelTimeRequest

logger = logging.getLogger(__name__)


@celery_app.task(name="where2now.run_travel_time_job")
def run_travel_time_job(job_id_str: str) -> None:
    db = SessionLocal()
    try:
        engine = build_travel_time_engine(db)
        _execute_travel_time_job(uuid.UUID(job_id_str), db, engine)
    finally:
        db.close()


def _execute_travel_time_job(
    job_id: uuid.UUID,
    db: Session,
    engine: TravelTimeEngine,
) -> None:
    svc = JobService(db)
    job = svc.mark_running(job_id)
    try:
        request = TravelTimeRequest.model_validate(job.input_payload)
        result = engine.get_travel_times(request)
        if result.errors:
            error_msg = "; ".join(e.message for e in result.errors)
            svc.mark_failed(job_id, error=error_msg)
        else:
            svc.mark_success(job_id, result_payload=result.model_dump(mode="json"))
    except Exception as exc:
        logger.exception("Unexpected error in travel time job %s", job_id)
        try:
            svc.mark_failed(job_id, error=str(exc))
        except Exception:
            logger.exception("Failed to mark job %s as failed after error", job_id)
```

The inner `try/except` around `mark_failed` prevents a secondary failure (e.g. the job was cancelled between `mark_running` and `mark_failed`) from masking the original error log.

---

## Testing plan

All tests in `tests/test_jobs/test_travel_time_task.py`.  
Tests call `_execute_travel_time_job` directly — no broker, no eager mode needed.  
`TravelTimeEngine` is replaced with `unittest.mock.MagicMock` in every test.

### Fixtures

- `db_session` — from `conftest.py`.
- `travel_time_job(db_session)` — creates and returns a `PENDING` job with a valid `input_payload`.
- `mock_engine()` — returns a `MagicMock` with a controlled `get_travel_times` return value.

### Valid `input_payload` for fixtures

```python
{
    "origins": [{"type": "latlng", "lat": 52.37, "lng": 4.89}],
    "destinations": [{"type": "latlng", "lat": 52.38, "lng": 4.90}],
    "transport_mode": "driving",
}
```

### Happy path — `mark_success`
- After `_execute_travel_time_job`, job status is `"success"`.
- `result_payload` is a dict containing `"legs"` and `"provider"`.
- `error` is `None`.
- `started_at` and `finished_at` are both set.

### Provider errors — `mark_failed`
- Engine returns `TravelTimeResult(provider="mock", errors=[TravelTimeError(message="quota exceeded", code="quota")])`.
- After the call, job status is `"failed"`.
- `error` contains `"quota exceeded"`.
- `result_payload` is `None`.

### Unexpected exception — `mark_failed`
- Engine raises `RuntimeError("network timeout")`.
- After the call, job status is `"failed"`.
- `error` contains `"network timeout"`.

### Invalid `input_payload`
- Job created with `input_payload={"bad": "data"}` (not a valid `TravelTimeRequest`).
- After the call, job status is `"failed"`.
- `error` is non-empty.

### Task registration
- `"where2now.run_travel_time_job"` is in `celery_app.tasks`.

---

## Definition of done

- [ ] `run_travel_time_job` registered as `"where2now.run_travel_time_job"` in `celery_app.tasks`.
- [ ] `_execute_travel_time_job` drives the full PENDING → RUNNING → SUCCESS/FAILED flow.
- [ ] Both provider-level errors and unexpected exceptions reach `mark_failed`.
- [ ] All tests in `tests/test_jobs/test_travel_time_task.py` pass without a broker or live engine.

---

## Out of scope

- Job API endpoints (`POST /travel-times`, `GET /jobs/{id}`) — **B5**
- docker-compose wiring for Redis and the worker — **D2**
- Celery retry logic — design backlog
- Concurrency / row locking (`SELECT FOR UPDATE`) — design backlog
