"""add log_entries table

Revision ID: 1a2b3c4d5e6f
Revises: e079c37a071a
Create Date: 2026-02-27 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "1a2b3c4d5e6f"
down_revision = "e079c37a071a"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "log_entries",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("level", sa.String(length=50), nullable=False),
        sa.Column("logger_name", sa.String(length=255), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("context", sa.Text(), nullable=True),
    )
    op.create_index("ix_log_entries_level", "log_entries", ["level"], unique=False)
    op.create_index("ix_log_entries_logger_name", "log_entries", ["logger_name"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_log_entries_logger_name", table_name="log_entries")
    op.drop_index("ix_log_entries_level", table_name="log_entries")
    op.drop_table("log_entries")

