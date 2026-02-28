# where2now

REST API for solving constrained delivery routing problems using MIP/LP optimization and the Google Maps API — built for real-world logistics with support for capacity, time windows, and location restrictions.

**What goes in this README:** High-level description of the project, how to run and test it, and a concise list of what the API offers (not every field—use `/docs` for that). Keep "Open Items" and "API Roadmap / Ideas" for things we might do next; move items out when they are done and document them in the right section (e.g. **API (configuration endpoints)**).

## Tech Stack

- **FastAPI** — REST API layer
- **PostgreSQL + SQLAlchemy** — Relational database with ORM, migrations via Alembic
- **Celery + Message Broker (Redis or RabbitMQ)** — Async task queue for long-running solve jobs
- **MIP/LP Solver** — Optimization engine (isolated component)
- **Google Maps API** — Travel time data source
- **Docker** — Containerized deployment

## Architecture Overview

### Core Components

1. **API Layer (FastAPI)** — Receives requests, validates input, submits jobs, returns results. Routes are kept thin; business logic lives in the services layer.

2. **Database (PostgreSQL + SQLAlchemy)** — Stores domain models (clients, delivery points, restrictions, travel times) and job tracking. Pydantic schemas handle API request/response validation separately from ORM models.

3. **Task Queue (Celery + Broker)** — Handles async job execution. The API submits solve requests to the broker, workers pick them up and run the solver. Results are stored in the database.

4. **Solver Engine** — MIP/LP optimization component. Called by Celery workers, not by the API directly. Takes problem data in, returns a solution. Isolated with a clean interface.

5. **Travel Time Subsystem** — Provides a single interface: "give me the travel time from A to B." Internally manages Google Maps API calls, caching/storing historical data, and (future) an ML prediction model. The solver does not need to know how travel times are computed.

### Request Flow

```
Client sends request
  → FastAPI validates and stores it
    → Submits a Celery task
      → Returns job ID immediately
        → Worker picks up the task
          → Fetches data from DB
            → Gets travel times from the travel time subsystem
              → Runs the solver
                → Stores results
                  → Client polls by job ID to retrieve results
```

## Project Structure

```
delivery-optimizer/
│
├── pyproject.toml
├── .env
├── .gitignore
├── docker-compose.yml
├── Dockerfile
├── alembic.ini
├── README.md
│
├── alembic/
│   └── versions/
│
├── app/
│   ├── __init__.py
│   ├── main.py                 # FastAPI app entry point
│   ├── config.py               # Settings (pydantic-settings, env loading)
│   ├── dependencies.py         # Shared FastAPI dependencies (DB session, etc.)
│   │
│   ├── api/
│   │   └── routes/
│   │       ├── clients.py
│   │       ├── delivery_points.py
│   │       ├── jobs.py         # Submit solve request, poll status, get results
│   │       └── health.py
│   │
│   ├── models/                 # SQLAlchemy ORM models
│   │   ├── client.py
│   │   ├── delivery_point.py
│   │   ├── restriction.py
│   │   ├── travel_time.py
│   │   └── job.py
│   │
│   ├── schemas/                # Pydantic schemas (request/response validation)
│   │   ├── client.py
│   │   ├── delivery_point.py
│   │   └── job.py
│   │
│   ├── db/
│   │   ├── session.py          # SQLAlchemy engine + session factory
│   │   └── base.py             # Declarative base for models
│   │
│   ├── services/               # Business logic layer
│   │   ├── routing_service.py
│   │   └── client_service.py
│   │
│   ├── solver/                 # Optimization engine (isolated)
│   │   ├── model.py            # MIP/LP model definition
│   │   ├── constraints.py
│   │   └── solver.py           # Entry point: takes problem data, returns solution
│   │
│   ├── travel_times/           # Travel time subsystem (isolated)
│   │   ├── client.py           # Google Maps API client
│   │   ├── cache.py            # Lookup/store cached times
│   │   ├── predictor.py        # ML model (future)
│   │   └── service.py          # Single interface: get_travel_time(A, B)
│   │
│   └── worker/                 # Celery configuration
│       ├── celery_app.py       # Celery instance + config
│       └── tasks.py            # Task definitions
│
└── tests/
    ├── conftest.py
    ├── test_api/
    ├── test_services/
    ├── test_solver/
    └── test_travel_times/
```

## Alembic (Migrations)

Migrations use the app’s `Base` and `DATABASE_URL`; tables are created by `alembic upgrade head`, not by running the API. For setup, workflow, and commands, see the **alembic-migrations** skill in `.cursor/skills/alembic-migrations/`.

## Testing

- **Run all tests** (from project root): `pytest`
- **Run with output**: `pytest -v`
- **Run one file**: `pytest tests/test_api/test_clients.py`
- **Run one test**: `pytest tests/test_api/test_clients.py::test_create_client`

Tests use an **in-memory SQLite** DB (no real DB touched). `conftest.py` creates tables per test and overrides `get_db_session` so the API uses that DB. Use the `client` fixture for HTTP calls and the `db_session` fixture when you need to insert data directly (e.g. for get/update/delete tests).

## CI/CD

- **CI** (`.github/workflows/ci.yml`): On every push/PR to `main`/`master`, runs `pytest`. Check the **Actions** tab on GitHub.
- **Automatic git tags** (`.github/workflows/tag-release.yml`): When you bump `version` in `pyproject.toml` and push to `main`, a tag `vX.Y.Z` is created and pushed. You can also run **Actions → Tag release → Run workflow** to tag the current version manually. Tags are only created if they don’t already exist.

## Git workflow (main + develop)

Branches: **main** (production-ready), **develop** (integration), and **feature branches** for new work.

### 1. Pull the latest changes

Always start from an up-to-date branch:

```bash
# If you're on main and want the latest from the remote:
git checkout main
git pull origin main

# If you use develop and want it up to date:
git checkout develop
git pull origin develop
```

If `develop` doesn’t exist on the remote yet, create it and push once:  
`git checkout -b develop && git push -u origin develop`

### 2. Create a new branch for a feature/fix

Create a branch from the branch you want to build on (usually **develop** for new features, **main** for hotfixes):

```bash
# Make sure you're up to date (see above), then:
git checkout develop
git pull origin develop
git checkout -b feature/my-new-thing
# or:  git checkout -b fix/something-broken
```

Now do your work on `feature/my-new-thing`. Commit as you go:

```bash
git add .
git commit -m "Add or fix something"
```

### 3. Push your branch and open a PR

```bash
git push -u origin feature/my-new-thing
```

Then on GitHub: **Pull requests → New pull request**, choose `feature/my-new-thing` → `develop` (or `main` if it’s a hotfix). CI will run on the PR.

### 4. After the PR is merged

Update your local branches and delete the feature branch so you don’t reuse it by mistake:

```bash
git checkout develop
git pull origin develop
git branch -d feature/my-new-thing
```

Summary: **pull** → **branch off develop** → **work & commit** → **push** → **open PR** → **merge** → **pull develop again**.

## API (configuration endpoints)

These endpoints are for **registering and maintaining data** (clients, delivery points, and their many-to-many links). The main product usage will be routing/solve jobs (future); these routes support that by keeping the database populated.

- **Clients** — `GET /clients`, `POST /clients`, `GET /clients/{id}`, `PATCH /clients/{id}`, `DELETE /clients/{id}`.
- **Client → delivery points** — `GET /clients/{id}/delivery-points`, `POST /clients/{id}/delivery-points` (body: `{ "delivery_point_ids": [1, 2, …] }`), `DELETE /clients/{id}/delivery-points/{delivery_point_id}`.
- **Delivery points** — `GET /delivery-points`, `POST /delivery-points`, `GET /delivery-points/{id}`, `PATCH /delivery-points/{id}`, `DELETE /delivery-points/{id}`.
- **Delivery point → clients** — `GET /delivery-points/{id}/clients`, `POST /delivery-points/{id}/clients` (body: `{ "client_ids": [1, 2, …] }`), `DELETE /delivery-points/{id}/clients/{client_id}`.

Full request/response shapes: run the app and open **/docs** (OpenAPI/Swagger).

## Open Items

- Detailed data models and database schema
- ML model for travel time prediction
- Frontend (React, optional)

## API Roadmap / Ideas

- **Richer client representations** — Optional expanded view: `ClientReadWithDeliveryPoints` and e.g. `GET /clients/{id}?include=delivery_points` when we want client + delivery points in one call.
- **Pagination and filtering** — Add pagination (e.g. `limit`/`offset`) to list endpoints once data volume grows.
- **Create a git flow to update develop when main has pushes**