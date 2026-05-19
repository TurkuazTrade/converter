"""add optional second client name

Revision ID: 0004_client_second_name
Revises: 0003_conversion_multiplier
Create Date: 2026-05-15
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0004_client_second_name"
down_revision = "0003_conversion_multiplier"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("clients", sa.Column("name_2", sa.String(length=512), nullable=True))
    op.create_index(op.f("ix_clients_name_2"), "clients", ["name_2"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_clients_name_2"), table_name="clients")
    op.drop_column("clients", "name_2")
