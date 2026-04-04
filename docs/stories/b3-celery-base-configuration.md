# Story B3 — Celery base configuration

**Goal:** A working Celery application that can enqueue and execute tasks, configured entirely from environment variables, with a probe task that proves the pipeline end-to-end.

**Depends on:** B1 (Job model), B2 (JobService) — B3 does not call either yet, but the probe task and the module layout are designed so B4 slots in cleanly.  
**Current state:** No task queue exists. Every travel-time call is synchronous and blocks the HTTP worker. B3 installs and configures Celery so B4 can offload work to background processes.

---

## Product intent

Travel-time computations can take several seconds per batch. Blocking an HTTP worker for that long degrades throughput and user experience under load. Celery solves this by decoupling the "accept the request" step from the "do the work" step:

1. The API handler creates a `Job` row, enqueues a task, and returns the `job_id` immediately.
2. A Celery worker picks up the task, calls `TravelTimeEngine`, and writes the result back through `JobService`.

B3 is the foundation: a correctly configured Celery app instance, a broker, a working worker process, and a probe task. No business logic — that is B4.

---

## Design decisions

### Broker: Redis

Redis is the standard Celery broker for small-to-medium deployments. It requires zero schema management, has excellent Python support via `redis-py`, and fits naturally into a `docker-compose` stack (D2). RabbitMQ is more correct for durable production messaging but adds operational complexity that is not justified at this stage.

Configuration: `redis://localhost:6379/0` (default, overridable via `CELERY_BROKER_URL`).

### Result backend: not used — we own result storage

Celery's result backend stores task return values so callers can retrieve them via `AsyncResult`. We are **not using this mechanism** — our results live in the `jobs` table and are retrieved via `JobService.get_job`. Using a separate Celery result store would create a second source of truth for the same data.

Consequence: set `task_ignore_result = True` globally on the Celery app. Tasks return `None`. Workers write outcomes to the `jobs` table directly (B4). This also eliminates the need to run a result backend service.

`CELERY_RESULT_BACKEND` is still accepted as a config setting (defaulting to `None`) so operators can optionally enable it for debugging without code changes.

### Task module autodiscovery

The Celery app is given `include=["app.jobs.tasks"]` explicitly. This is simpler than `autodiscover_tasks` for a project of this size and makes the task list obvious to anyone reading `celery_app.py`.

### Testing without a broker

Celery's `task_always_eager` setting makes `.delay()` and `.apply_async()` execute synchronously in the calling process — no broker required. Tests set this via a fixture that patches `celery_app.conf`. Unit tests never touch Redis.

The `ping` task is also tested by calling it as a plain Python function, which is the most direct correctness check.

---

## Target modules

| Path | Role |
|------|------|
| `app/celery_app.py` | Celery app instance; reads broker URL and other settings from `app.config.settings`. |
| `app/jobs/tasks.py` | Task definitions. B3 adds only the `ping` probe task. B4 adds the travel-time task here. |
| `tests/test_jobs/test_tasks.py` | Tests for the probe task; uses an always-eager fixture. |

No changes to `app/jobs/service.py`, `app/models/`, or existing schemas.

---

## `app/config.py` additions

Add two new fields to the `Settings` class:

```python
# Celery / task queue
CELERY_BROKER_URL: str = "redis://localhost:6379/0"
CELERY_RESULT_BACKEND: str | None = None
```

`CELERY_BROKER_URL` defaults to local Redis on the standard port.  
`CELERY_RESULT_BACKEND` defaults to `None` — result storage is disabled by default (see design decision above).

---

## `app/celery_app.py`

```python
from celery import Celery
from app.config import settings

celery_app = Celery(
    "where2now",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.jobs.tasks"],
)

celery_app.conf.update(
    task_ignore_result=True,
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
)
```

Key choices:
- `task_ignore_result=True` — enforces the "jobs table is the result store" rule (see design decisions).
- `task_serializer="json"` / `accept_content=["json"]` — explicit; avoids pickle security issues.
- `enable_utc=True` — all Celery-internal timestamps are UTC; consistent with our `DateTime(timezone=True)` columns.

---

## `app/jobs/tasks.py`

B3 defines one task: `ping`. It exists purely to verify the broker connection, task routing, and worker startup.

```python
from app.celery_app import celery_app

@celery_app.task(name="where2now.ping")
def ping() -> str:
    return "pong"
```

The explicit `name` prevents the task name from changing if the module is ever moved. B4 will add the `run_travel_time_job` task in this file.

---

## Worker entrypoint

Start the worker from the project root:

```bash
celery -A app.celery_app worker --loglevel=info
```

The `-A app.celery_app` flag tells Celery where to find the `celery_app` instance. `include=["app.jobs.tasks"]` in the app config is what causes the tasks module to be imported (and tasks registered) when the worker starts.

For development, add `--pool=solo` to avoid multiprocessing issues on Windows:

```bash
celery -A app.celery_app worker --loglevel=info --pool=solo
```

Document both forms in a comment at the top of `celery_app.py`.

---

## `requirements.txt` additions

```
celery[redis]==5.4.0
```

`celery[redis]` installs both `celery` and `redis` (the Python client). Pin to a specific version to keep builds reproducible.

---

## Testing plan

All tests in `tests/test_jobs/test_tasks.py`. No broker is required — tests use the always-eager fixture.

### Fixture: `eager_celery`

```python
@pytest.fixture
def eager_celery():
    from app.celery_app import celery_app
    celery_app.conf.update(task_always_eager=True, task_eager_propagates=True)
    yield celery_app
    celery_app.conf.update(task_always_eager=False, task_eager_propagates=False)
```

`task_eager_propagates=True` ensures that exceptions raised inside a task propagate to the test, rather than being swallowed into an `FAILURE` result object.

### Tests

#### `ping` — direct call
- Calling `ping()` as a plain Python function returns `"pong"`.

#### `ping` — via `.delay()` with eager mode
- With `eager_celery` fixture active, `ping.delay()` returns a result object whose `.get()` is `"pong"` (requires `task_ignore_result=False` override in this specific test, since eager mode still runs the task but `.get()` needs the result).
- Alternatively, assert `ping.apply().result == "pong"`.

#### Celery app config sanity checks
- `celery_app.conf.task_serializer == "json"`.
- `celery_app.conf.enable_utc is True`.
- `celery_app.conf.task_ignore_result is True`.
- `"where2now.ping"` is in the registered task names (`celery_app.tasks`).

---

## Definition of done

- [ ] `celery[redis]` added to `requirements.txt`.
- [ ] `CELERY_BROKER_URL` and `CELERY_RESULT_BACKEND` added to `app/config.py` `Settings`.
- [ ] `app/celery_app.py` creates and configures the `celery_app` instance.
- [ ] `app/jobs/tasks.py` exists with the `ping` probe task registered under `"where2now.ping"`.
- [ ] All tests in `tests/test_jobs/test_tasks.py` pass without a running broker.
- [ ] `celery -A app.celery_app worker --loglevel=info` starts successfully when Redis is available (manual smoke test).

---

## Out of scope

- Travel-time Celery task — **B4**
- Job API endpoints — **B5**
- docker-compose wiring for Redis and the worker — **D2**
- Celery Beat / periodic tasks — design backlog
- Celery monitoring (Flower, etc.) — design backlog
- Retry logic and dead-letter queues — design backlog
