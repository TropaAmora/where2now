# Story B2 — Job lifecycle management

**Goal:** A single service layer that creates jobs, drives status transitions, and rejects invalid moves — so no caller can accidentally put a job into an inconsistent state.

**Depends on:** B1 (Job ORM model, `JobStatus`, `JobRead`)  
**Current state:** The `Job` model exists and rows can be inserted. There is no business logic controlling how status changes — any code could write any status directly. B2 closes that gap.

---

## Product intent

When a Celery worker picks up a job (B4) or a client cancels one (B5), the status must change in a controlled, auditable way. The rules are simple:

- A job starts `PENDING`.
- A worker moves it to `RUNNING` when it starts.
- It ends in exactly one of `SUCCESS`, `FAILED`, or `CANCELLED`.
- Nothing moves backwards. Terminal states are final.

Any attempt to break these rules should fail loudly with a clear error — not silently write bad data.

---

## State machine

```
             ┌──────────┐
   create ──▶│  PENDING │─────────────────────────┐
             └──────────┘                         │
                  │ mark_running                  │ cancel_job
                  ▼                               │
             ┌──────────┐                         │
             │  RUNNING │─────────────────────────┤
             └──────────┘                         │
            │           │                         ▼
  mark_success     mark_failed              ┌───────────┐
            │           │                   │ CANCELLED │
            ▼           ▼                   └───────────┘
       ┌─────────┐  ┌────────┐
       │ SUCCESS │  │ FAILED │
       └─────────┘  └────────┘
```

`SUCCESS`, `FAILED`, and `CANCELLED` are **terminal** — no transitions are allowed out of them.

### Valid transition table

| From \ To | `running` | `success` | `failed` | `cancelled` |
|-----------|-----------|-----------|----------|-------------|
| `pending` | ✅ | ❌ | ❌ | ✅ |
| `running` | ❌ | ✅ | ✅ | ✅ |
| `success` | ❌ | ❌ | ❌ | ❌ |
| `failed` | ❌ | ❌ | ❌ | ❌ |
| `cancelled` | ❌ | ❌ | ❌ | ❌ |

---

## Exceptions

### `InvalidJobTransitionError` (subclass of `RuntimeError`)

Raised when a caller attempts a transition that is not in the table above.

The message must include:
- the job `id`
- the current status
- the attempted target status
- the set of allowed transitions (or a note that the state is terminal)

This makes it unambiguous for callers — no guessing why the transition failed.

### `JobNotFoundError` (subclass of `RuntimeError`)

Raised by transition methods (`mark_running`, `mark_success`, `mark_failed`, `cancel_job`) when the given `job_id` does not exist in the database.

`get_job` returns `None` for unknown IDs instead of raising — HTTP handlers decide what status code to return.

---

## Target modules

| Path | Role |
|------|------|
| `app/jobs/service.py` | `JobService` class, `InvalidJobTransitionError`, `JobNotFoundError`, `VALID_TRANSITIONS`. |
| `tests/test_jobs/test_job_service.py` | Service tests using the `db_session` fixture from `conftest.py`. |
| `tests/test_jobs/__init__.py` | Empty — makes the folder a package. |

No changes needed to `app/jobs/schemas.py` or `app/models/job.py` in B2.

---

## `app/jobs/service.py`

### `VALID_TRANSITIONS`

A module-level `dict[str, set[str]]` mapping each status to the set of statuses it may transition to:

```python
VALID_TRANSITIONS: dict[str, set[str]] = {
    "pending":   {"running", "cancelled"},
    "running":   {"success", "failed", "cancelled"},
    "success":   set(),
    "failed":    set(),
    "cancelled": set(),
}
```

This is the single source of truth. The `_transition` helper reads from it — adding or changing a rule means editing one line here.

### `JobService`

Takes a `db: Session` in `__init__`. One instance per request (wired through FastAPI's dependency system in B5) or per Celery task execution (B4).

#### `create_job(type, input_payload, tenant_id) -> Job`

1. Instantiate `Job(type=type, input_payload=input_payload, tenant_id=tenant_id)`.
2. `db.add(job)` → `db.commit()` → `db.refresh(job)`.
3. Return the persisted job.

`status` defaults to `"pending"` via the ORM model default (set in B1). Do not set it explicitly here.

#### `get_job(job_id: uuid.UUID) -> Job | None`

Return `db.get(Job, job_id)`. Returns `None` if not found — callers handle the missing case.

#### `mark_running(job_id) -> Job`

1. Load the job via `_get_or_raise(job_id)`.
2. Call `_transition(job, "running")`.
3. Set `job.started_at = datetime.now(timezone.utc)`.
4. Commit, refresh, return.

#### `mark_success(job_id, result_payload) -> Job`

1. Load via `_get_or_raise`.
2. `_transition(job, "success")`.
3. Set `job.result_payload = result_payload`, `job.finished_at = datetime.now(timezone.utc)`.
4. Commit, refresh, return.

#### `mark_failed(job_id, error) -> Job`

1. Load via `_get_or_raise`.
2. `_transition(job, "failed")`.
3. Set `job.error = error`, `job.finished_at = datetime.now(timezone.utc)`.
4. Commit, refresh, return.

#### `cancel_job(job_id) -> Job`

1. Load via `_get_or_raise`.
2. `_transition(job, "cancelled")`.
3. Set `job.finished_at = datetime.now(timezone.utc)`.
4. Commit, refresh, return.

### Private helpers

#### `_transition(job, new_status) -> None`

1. Look up `VALID_TRANSITIONS[job.status]`.
2. If `new_status` not in that set → raise `InvalidJobTransitionError` with a descriptive message.
3. Otherwise set `job.status = new_status`.

#### `_get_or_raise(job_id) -> Job`

1. `job = db.get(Job, job_id)`.
2. If `None` → raise `JobNotFoundError(f"Job {job_id} not found")`.
3. Return the job.

---

## FastAPI dependency (for B5)

Add to `app/dependencies.py`:

```python
from app.jobs.service import JobService

def get_job_service(db: Session = Depends(get_db_session)) -> JobService:
    return JobService(db)
```

Do not add this in B2 — wire it when B5 introduces the API endpoints. Documenting it here so the implementer knows where it will live.

---

## Testing plan

All tests use the `db_session` fixture from `conftest.py`. No mocking needed — the service is pure DB logic.

### `tests/test_jobs/test_job_service.py`

#### `create_job`
- Creates a job with `status="pending"`.
- `started_at` and `finished_at` are `None` after creation.
- `result_payload` and `error` are `None` after creation.
- Two calls produce jobs with different `id` values.

#### `get_job`
- Returns the job by UUID after creation.
- Returns `None` for an unknown UUID.

#### `mark_running`
- Transitions a `PENDING` job to `RUNNING`.
- Sets `started_at` to a non-`None` datetime.
- `finished_at` remains `None`.

#### `mark_success`
- Transitions a `RUNNING` job to `SUCCESS`.
- Sets `result_payload` and `finished_at`.
- `error` remains `None`.

#### `mark_failed`
- Transitions a `RUNNING` job to `FAILED`.
- Sets `error` and `finished_at`.
- `result_payload` remains `None`.

#### `cancel_job`
- Transitions a `PENDING` job to `CANCELLED`, sets `finished_at`.
- Transitions a `RUNNING` job to `CANCELLED`, sets `finished_at`.

#### Invalid transitions — `InvalidJobTransitionError`
- `PENDING → SUCCESS` raises; message contains `"pending"` and `"success"`.
- `PENDING → FAILED` raises.
- `SUCCESS → RUNNING` raises; message contains `"terminal"` or the empty allowed set.
- `FAILED → RUNNING` raises.
- `CANCELLED → RUNNING` raises.

#### `JobNotFoundError`
- `mark_running` with an unknown UUID raises `JobNotFoundError`.
- `mark_success`, `mark_failed`, `cancel_job` also raise for unknown IDs.

---

## Definition of done

- [ ] `app/jobs/service.py` defines `InvalidJobTransitionError`, `JobNotFoundError`, `VALID_TRANSITIONS`, and `JobService`.
- [ ] All five public methods (`create_job`, `get_job`, `mark_running`, `mark_success`, `mark_failed`, `cancel_job`) are implemented.
- [ ] `_transition` reads from `VALID_TRANSITIONS` — transition rules are not scattered across methods.
- [ ] `InvalidJobTransitionError` messages include the job ID, current status, and attempted status.
- [ ] All tests in the testing plan pass.

---

## Out of scope

- FastAPI dependency wiring (`get_job_service`) — **B5**
- Celery task calling the service — **B4**
- Job API endpoints — **B5**
- Concurrency / row locking (e.g. `SELECT FOR UPDATE`) — valid follow-up, not B2
- Job retry logic — design backlog
