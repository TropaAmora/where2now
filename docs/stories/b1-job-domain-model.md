# Story B1 — Job domain model & schema

**Goal:** Define a single, consistent representation of a background job so every future job type (travel time, routing, export) is stored and queried the same way.

**Depends on:** None — B1 is pure model and schema work; it does not depend on Epic A.  
**Current state:** No job concept exists. B1 introduces the `jobs` table, `JobStatus`, and the `JobRead` Pydantic schema. The lifecycle service (B2) and Celery wiring (B3) build directly on top.

---

## Product intent

When a client triggers a long-running computation (travel time, route planning, etc.), the API must be able to:

- hand back a job ID immediately, not block waiting for the result,
- let the client poll for completion,
- store the result (or error) so it can be retrieved later.

B1 defines *what a job looks like in the database and on the wire*. It does not yet implement creation, status updates, or Celery tasks — those are B2–B4.

---

## `JobStatus`

Status is a closed string enum. The full lifecycle is:

```
PENDING → RUNNING → SUCCESS
                 → FAILED
         → CANCELLED   (from PENDING or RUNNING)
```

| Value | Meaning |
|-------|---------|
| `pending` | Created, not yet picked up by a worker. |
| `running` | A worker has started processing it. |
| `success` | Completed successfully; `result_payload` is set. |
| `failed` | Processing failed; `error` (and optionally `result_payload`) is set. |
| `cancelled` | Cancelled before or during execution. |

Valid transitions are enforced by the service layer in **B2**, not at the DB level. The DB stores whatever string the service writes — keeping the schema stable and avoiding PostgreSQL `ENUM` type pain during migrations.

---

## ORM model — `app/models/job.py`

### Table: `jobs`

| Column | SQLAlchemy type | Nullable | Notes |
|--------|----------------|----------|-------|
| `id` | `Uuid(as_uuid=True)`, PK | No | Default `uuid.uuid4`. UUID prevents clients enumerating job IDs. |
| `tenant_id` | `String(64)`, indexed | No | Identifies the owning client/company. Default `"default"` for the single-tenant pilot. Indexed so all future queries can filter by tenant without a schema migration. |
| `type` | `String(64)`, indexed | No | Job type slug, e.g. `"travel_time"`. Unvalidated at DB level; validated by service. |
| `status` | `String(32)`, indexed | No | One of `JobStatus` values; default `"pending"`. |
| `input_payload` | `JSON` | Yes | The raw input that was passed to the task; stored for debugging and replay. |
| `result_payload` | `JSON` | Yes | The task's output; set on `SUCCESS`. |
| `error` | `Text` | Yes | Human-readable error message; set on `FAILED`. |
| `created_at` | `DateTime(timezone=True)` | No | Set at row creation. |
| `updated_at` | `DateTime(timezone=True)` | No | Set at creation; updated on every write. |
| `started_at` | `DateTime(timezone=True)` | Yes | Set when status moves to `RUNNING`. |
| `finished_at` | `DateTime(timezone=True)` | Yes | Set when status moves to `SUCCESS`, `FAILED`, or `CANCELLED`. |

### Why UUID primary key?

Every other model in this project uses integer PKs — that is fine for internal entities. Jobs are the first resource that will be handed to API clients as a reference they keep and poll. Integer PKs let clients enumerate all jobs by incrementing. UUID prevents that without any extra auth logic.

Use `sqlalchemy.types.Uuid` (stable in SQLAlchemy 2.0+), which stores as native UUID in PostgreSQL and as a string in SQLite — tests work without change.

### Why `tenant_id` now, even with one client?

The system is currently single-tenant, but adding `tenant_id` at this point costs almost nothing: one column, one index, one default value. Retrofitting it later — when a second client arrives — would require a migration across potentially large tables and changes to every query.

During the pilot, every row gets `tenant_id = "default"`. When a second client is onboarded, that value comes from the authenticated request context (to be defined in the auth layer, outside Epic B). All future queries that filter jobs by tenant will use the index without any schema change.

Do **not** add full row-level isolation logic in B1. That belongs to the auth/tenancy layer (design backlog). B1 only ensures the column exists and is indexed.

### `created_at` / `updated_at` pattern

Follow the same pattern as `DeliveryPoint`:

```python
created_at = Column(
    DateTime(timezone=True),
    default=lambda: datetime.now(timezone.utc),
    nullable=False,
)
updated_at = Column(
    DateTime(timezone=True),
    default=lambda: datetime.now(timezone.utc),
    onupdate=lambda: datetime.now(timezone.utc),
    nullable=False,
)
```

`started_at` and `finished_at` start as `None` and are set by the service layer (B2).

---

## Pydantic schemas — `app/jobs/schemas.py`

B1 introduces the `app/jobs/` package. This is where all Epic B business logic will live (service in B2, Celery tasks in B4).

### `JobStatus` (str enum)

```python
class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"
```

Lives in `schemas.py`, not in the ORM model, so it can be imported cleanly by both the service layer and HTTP handlers without touching `app/models/`.

### `JobRead`

The REST representation of a job. Used as the response model for all job endpoints (B5).

| Field | Type | Notes |
|-------|------|-------|
| `id` | `uuid.UUID` | The job's unique identifier. |
| `tenant_id` | `str` | Owning client identifier. `"default"` during single-tenant pilot. |
| `type` | `str` | Job type slug. |
| `status` | `JobStatus` | Current status. |
| `input_payload` | `dict \| None` | The input that was submitted. |
| `result_payload` | `dict \| None` | The result, if complete. |
| `error` | `str \| None` | Error message, if failed. |
| `created_at` | `datetime` | UTC-aware. |
| `updated_at` | `datetime` | UTC-aware. |
| `started_at` | `datetime \| None` | UTC-aware. |
| `finished_at` | `datetime \| None` | UTC-aware. |

Configure `model_config = ConfigDict(from_attributes=True)` so `JobRead.model_validate(job_orm_instance)` works without manual field mapping.

### Why no `JobCreate` schema in B1?

Jobs are not created by clients posting a JSON body directly to `/jobs`. They are created internally by the service (B2) when a handler decides to enqueue work. A `JobCreate`-like interface will emerge in B2 when we define `JobService.create_job(type, input_payload)`. Adding it in B1 would be premature — we do not know the exact call shape yet.

---

## Target modules

| Path | Role |
|------|------|
| `app/jobs/__init__.py` | New package — empty for B1; service and tasks land here in B2/B4. |
| `app/jobs/schemas.py` | `JobStatus` enum, `JobRead` schema. |
| `app/models/job.py` | `Job` SQLAlchemy ORM model. |
| `app/models/__init__.py` | Add `from app.models.job import Job` so Alembic sees the table. |
| `alembic/versions/<rev>_add_jobs_table.py` | Migration: `create_table("jobs", ...)`. Review before running. |
| `tests/test_models/test_job_model.py` | ORM round-trip tests (write and read back a row). |
| `tests/test_schemas/test_job_schemas.py` | Schema validation and `from_attributes` round-trip. |

---

## Migration

After the ORM model is written and `app/models/__init__.py` is updated, generate and apply the migration:

```bash
alembic revision --autogenerate -m "add jobs table"
alembic upgrade head
```

**Always review the generated file** in `alembic/versions/` before running `upgrade head`. Autogenerate does not know about UUIDs on SQLite — verify the column type looks correct for your target DB.

The test suite uses `Base.metadata.create_all()` via the `db_session` fixture in `conftest.py`, so tests do not depend on running Alembic manually.

---

## Testing plan

### `tests/test_models/test_job_model.py` — ORM round-trips

- Insert a `Job` row with `status="pending"` and `input_payload={"key": "value"}` — read it back and assert all fields match.
- `id` is a UUID, not an integer — assert `isinstance(job.id, uuid.UUID)`.
- `created_at` and `updated_at` are timezone-aware — assert `job.created_at.tzinfo is not None`.
- `started_at` and `finished_at` default to `None`.
- `result_payload` and `error` default to `None`.

### `tests/test_schemas/test_job_schemas.py` — Pydantic validation

- `JobRead.model_validate(orm_instance)` produces the correct field values (tests `from_attributes=True`).
- `JobStatus("pending")` → `JobStatus.PENDING`; `JobStatus("unknown")` → `ValueError`.
- `JobRead` with `status="running"` serializes `status` as the string `"running"` in JSON.

### No API tests in B1

API tests for job endpoints belong in B5. B1 only needs model and schema coverage.

---

## Definition of done

- [ ] `app/jobs/__init__.py` exists (empty).
- [ ] `app/jobs/schemas.py` defines `JobStatus` and `JobRead`.
- [ ] `app/models/job.py` defines `Job` with all columns in the table above.
- [ ] `Job` is imported in `app/models/__init__.py`.
- [ ] Alembic migration created and reviewed for the `jobs` table.
- [ ] `alembic upgrade head` applies cleanly against the development database.
- [ ] ORM round-trip tests pass.
- [ ] Schema validation tests pass.

---

## Out of scope

- Job lifecycle transitions and validation — **B2**
- Celery broker configuration — **B3**
- Travel time Celery task — **B4**
- Job API endpoints (`GET /jobs/{id}`, create job) — **B5**
- Job retention / cleanup policy — design backlog (aligns with Epic E)
