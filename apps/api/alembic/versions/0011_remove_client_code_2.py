"""remove client code 2

Revision ID: 0011_remove_client_code_2
Revises: 0010_order_export_download_marker
Create Date: 2026-05-19
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0011_remove_client_code_2"
down_revision = "0010_order_export_download_marker"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("clients") as batch_op:
        batch_op.drop_column("client_code_2")


def downgrade() -> None:
    with op.batch_alter_table("clients") as batch_op:
        batch_op.add_column(sa.Column("client_code_2", sa.String(length=128), nullable=True))
        batch_op.create_index("ix_clients_client_code_2", ["client_code_2"], unique=False)
