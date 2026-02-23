---
name: alembic-migrations
description: Set up and use Alembic for SQLAlchemy migrations. Use when configuring Alembic, writing or changing ORM models, creating migrations, applying or rolling back migrations, or when the user asks how migrations or table creation work in this project.
---

# Alembic Migrations (where2now)

Tables are created and updated by **Alembic**, not by running the API. The API only uses the database.

## Process flow (order of operations)

1. **Change models** — Add or edit SQLAlchemy models under `app/models/`, using `app.db.base.Base`. Import every new model module in `app.models/__init__.py` so Alembic can see them.
2. **Generate a migration** — From project root: `alembic revision --autogenerate -m "Short description"`. Review the new file in `alembic/versions/`.
3. **Apply the migration** — `alembic upgrade head`. This creates or alters tables in the database.
4. **Then** run the API (or tests). The app uses the DB; it does not create the schema.

Never rely on “run the API to create tables” unless the project explicitly uses `Base.metadata.create_all()` at startup (this one does not).

## Running Alembic

- Always run from the **project root** (where `alembic.ini` lives), e.g. `c:\devs\where2now`.
- Commands: `alembic <command>` (no `python -m` needed if alembic is on PATH).

## Commands reference

| Command | Purpose |
|--------|--------|
| `alembic revision --autogenerate -m "message"` | Generate a new migration from current model changes. |
| `alembic upgrade head` | Apply all pending migrations (creates/updates tables). |
| `alembic downgrade -1` | Undo the last applied migration. |
| `alembic downgrade base` | Undo all migrations (DB has no schema). |
| `alembic current` | Show the revision currently applied in the DB. |
| `alembic history` | List all revisions (does not connect to DB). |
| `alembic check` | Verify env and config load; warns if model changes have no migration. |

## Model registration (required for autogenerate)

Alembic discovers tables via `Base.metadata`. For that to include your models:

1. All models must use the same `Base` as the app (`app.db.base.Base`).
2. `alembic/env.py` must set `target_metadata = Base.metadata` and must import all model modules (e.g. `import app.models`) so they attach to `Base`.
3. Every new model file (e.g. `app/models/client.py`) must be imported in `app/models/__init__.py`. Otherwise `alembic revision --autogenerate` will not see that table.

## Configuration (already wired in this project)

- **Database URL**: Taken from `app.db.session.DATABASE_URL` in `alembic/env.py`. Change the URL in one place (e.g. when moving from SQLite to PostgreSQL); Alembic will use it.
- **Base**: `alembic/env.py` imports `app.db.base.Base` and `import app.models` so `target_metadata = Base.metadata` includes all registered models.

## Autogenerate caveats

- **Review every generated migration** before running `alembic upgrade head`. Autogenerate can miss renames (shows as drop + create), data backfills, and sometimes indexes or constraints.
- To fix: edit the migration file in `alembic/versions/` and add or adjust `op.create_*`, `op.drop_*`, `op.alter_*`, or `op.execute()` as needed.

## First-time setup (if starting from scratch)

1. From project root: `alembic init alembic`.
2. In `alembic/env.py`: set `target_metadata = Base.metadata` (from `app.db.base`), import all model modules, and set `config.set_main_option("sqlalchemy.url", DATABASE_URL)` from `app.db.session` (or app config).
3. In `alembic.ini`: `sqlalchemy.url` can be a placeholder; env.py overrides it so the app remains the single source of truth for the URL.

## Troubleshooting

- **"No module named 'app'"** — Run Alembic from the project root so the app package is on the path (alembic.ini has `prepend_sys_path = .`).
- **Autogenerate sees no tables** — Ensure the model is imported in `app.models/__init__.py` and that it subclasses the same `Base` used in env.py.
- **SQLite "disk I/O" or lock errors** — Can be sandbox or antivirus; run Alembic in a normal terminal. For PostgreSQL, ensure the URL and permissions are correct.
