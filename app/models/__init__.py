"""SQLAlchemy ORM models.

Import every model module here so they register with Base.metadata.
Alembic needs this for `alembic revision --autogenerate` to detect your tables.
"""

from app.models.clients import Client  # noqa: F401
from app.models.delivery_points import DeliveryPoint  # noqa: F401
from app.models.log_entry import LogEntry  # noqa: F401