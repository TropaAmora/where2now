# where2now

REST API for solving constrained delivery routing problems using MIP/LP optimization and the Google Maps API — built for real-world logistics with support for capacity, time windows, and location restrictions.

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

## Open Items

- Detailed data models and database schema
- ML model for travel time prediction
- Frontend (React, optional)